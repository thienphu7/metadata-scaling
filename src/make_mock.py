"""Phase 0: build the MOCK table (20 files) + results/results_fake.csv so everyone can work in parallel."""
import os, csv, random
from common import *
cfg = load_config()
data = make_logical_data(cfg).slice(0, 20000)
for v in cfg["variants"]:
    p = table_path(cfg, "MOCK", v)
    dt = create_empty_table(p)
    d = data.sort_by("customer_id") if v == "opt_b_sorted" else data
    write_chunks(dt, d, cfg["states"]["MOCK"], 2)
    if v != "baseline":
        DeltaTable(p).create_checkpoint()
os.makedirs(os.path.join(ROOT, cfg["paths"]["results"]), exist_ok=True)
cols = ["state","variant","query","mode","run","t_load","t_prune","t_plan","t_scan",
        "n_files_total","files_selected","rows","expected_rows","hardware"]
random.seed(0)
with open(os.path.join(ROOT, cfg["paths"]["results"], "results_fake.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(cols)
    for s, nf in [("S1",100),("S2",1000),("S3",10000),("S4",20000)]:
        for v, k in [("baseline",1.0),("opt_a_checkpoint",0.3),("opt_b_sorted",0.1)]:
            for q in ["q_main","q_alt","q_empty"]:
                for mode in ["cold","warm"]:
                    for r in range(10):
                        tl = nf*2e-5*k*random.uniform(.8,1.3); tp = nf*1e-6*random.uniform(.8,1.2)
                        sel = 0 if q == "q_empty" else (nf if (v != "opt_b_sorted" or q == "q_alt") else max(1, nf//200))
                        ts = sel*2e-4*random.uniform(.8,1.2)
                        er = 0 if q == "q_empty" else 500
                        w.writerow([s,v,q,mode,r,tl,tp,tl+tp,ts,nf,sel,er,er,"FAKE"])
print("MOCK tables + fake results ready")
