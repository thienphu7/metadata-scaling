"""Shared helpers - DO NOT change signatures without telling the whole team."""
import json, os, time, uuid, platform
import numpy as np, pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc, yaml
from deltalake import DeltaTable, write_deltalake, PostCommitHookProperties
from deltalake.transaction import AddAction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = pa.schema([("id", pa.int64()), ("customer_id", pa.int64()), ("amount", pa.float64())])
NO_HOOK = PostCommitHookProperties(create_checkpoint=False, cleanup_expired_logs=False)

def load_config():
    with open(os.path.join(ROOT, "config.yaml")) as f:
        return yaml.safe_load(f)

def table_path(cfg, state, variant):
    return os.path.join(ROOT, cfg["paths"]["tables"], state, variant)

def make_logical_data(cfg):
    """Same 1M rows for EVERY state, random order (so baseline min/max stats overlap)."""
    rng = np.random.default_rng(cfg["seed"])
    n = cfg["n_rows"]
    t = pa.table({"id": np.arange(n, dtype="int64"),
                  "customer_id": rng.integers(0, cfg["n_customers"], n, dtype="int64"),
                  "amount": np.round(rng.random(n) * 1000, 4)}, schema=SCHEMA)
    return t.take(pa.array(rng.permutation(n)))

def _stats(tb):
    cols = tb.schema.names
    return json.dumps({"numRecords": tb.num_rows,
                       "minValues": {c: pc.min(tb[c]).as_py() for c in cols},
                       "maxValues": {c: pc.max(tb[c]).as_py() for c in cols},
                       "nullCount": {c: 0 for c in cols}})

def write_chunks(dt, data, n_files, files_per_commit, mode="append", prefix="part"):
    """Split `data` into n_files parquet files and commit them through the official
    deltalake transaction API, files_per_commit files per commit. Returns bytes written."""
    path = dt.table_uri.replace("file://", "").rstrip("/")
    per = data.num_rows // n_files
    acts, written, first = [], 0, True
    for i in range(n_files):
        tb = data.slice(i * per, per if i < n_files - 1 else data.num_rows - i * per)
        name = f"{prefix}-{i:06d}-{uuid.uuid4().hex[:8]}.parquet"
        fp = os.path.join(path, name)
        pq.write_table(tb, fp)
        size = os.path.getsize(fp); written += size
        acts.append(AddAction(name, size, {}, int(time.time() * 1000), True, _stats(tb)))
        if len(acts) == files_per_commit or i == n_files - 1:
            m = mode if first else "append"   # overwrite only in the first commit
            dt.create_write_transaction(acts, mode=m, schema=SCHEMA, post_commithook_properties=NO_HOOK)
            acts, first = [], False
    return written

def create_empty_table(path):
    os.makedirs(path, exist_ok=True)
    write_deltalake(path, SCHEMA.empty_table(),
                    configuration={"delta.checkpointInterval": "100000000"})
    return DeltaTable(path)

def has_checkpoint(path):
    return any("checkpoint" in f for f in os.listdir(os.path.join(path, "_delta_log")))

def plan(path, q):
    """PLANNING = load table (log replay) + min/max pruning on add-action stats.
    Returns (selected_file_paths, n_files_total, t_load, t_prune)."""
    t0 = time.perf_counter()
    dt = DeltaTable(path)
    aa = pa.table(dt.get_add_actions(flatten=True))
    t1 = time.perf_counter()
    c = q["column"]
    mask = pc.and_(pc.less_equal(aa[f"min.{c}"], q["high"]), pc.greater_equal(aa[f"max.{c}"], q["low"]))
    sel = [os.path.join(path, p) for p in pc.filter(aa["path"], mask).to_pylist()]
    t2 = time.perf_counter()
    return sel, aa.num_rows, t1 - t0, t2 - t1

def scan(files, q):
    """SCAN = read only selected files and apply the filter. Returns (rows, t_scan)."""
    t0 = time.perf_counter()
    c = q["column"]
    rows = sum(pq.read_table(f, filters=[(c, ">=", q["low"]), (c, "<=", q["high"])]).num_rows for f in files)
    return rows, time.perf_counter() - t0

def expected_rows(data, q):
    c = q["column"]
    return pc.sum(pc.and_(pc.greater_equal(data[c], q["low"]), pc.less_equal(data[c], q["high"]))).as_py()

def hardware():
    return f"{platform.node()}|{platform.platform()}|cpu={os.cpu_count()}"
