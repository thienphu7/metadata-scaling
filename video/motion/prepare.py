"""Prepare the motion video: metrics from results CSVs -> narration -> voice (Gemini TTS) -> SFX/music -> src/data.json

  GEMINI_API_KEY=... python video/motion/prepare.py --fake        # numbers from results_fake.csv (badged FAKE)
  GEMINI_API_KEY=... python video/motion/prepare.py --state S4    # real numbers after the freeze
  then: cd video/motion && npm run render

Without GEMINI_API_KEY the voice falls back to macOS `say -v Linh` (placeholder only).
Voice clips are cached by text hash, so re-running only calls the API for changed lines.
Key: GEMINI_API_KEY env or `gemini_key=` in the repo's .env (gitignored).
Optional env: GEMINI_TTS_MODELS (fallback chain "model:rpm,..."), GEMINI_VOICE (default Charon).
--primary-only: regenerate clips that a fallback model produced, using only the primary model."""
import argparse, base64, glob, http.client, hashlib, json, os, subprocess, sys, time, urllib.request, urllib.error
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PUB = os.path.join(HERE, "public")
# No style prefix by default: transcripts showed the TTS models sometimes READ the direction
# aloud (Vietnamese and English prefixes both leaked). Every clip is verified by transcription.
STYLE = os.environ.get("GEMINI_STYLE", "")

def vn(x, nd):
    s = f"{x:,.{nd}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")

def metrics(fake, state):
    """Every number shown or spoken comes from here. S4 (held-out) from results/; the chart's other
    states come from results/ when the owner has pushed them, else from video/motion/assumed/
    (local runs on Phong's machine, labelled as such in the video)."""
    rdir = os.path.join(ROOT, "results"); adir = os.path.join(HERE, "assumed")
    if fake:
        df, costs, state = pd.read_csv(os.path.join(rdir, "results_fake.csv")), None, "S4"
        curve_df, local = df, []
    else:
        df = pd.read_csv(os.path.join(rdir, f"results_{state}.csv"))
        cp = os.path.join(rdir, f"costs_{state}.csv")
        costs = pd.read_csv(cp) if os.path.exists(cp) else None
        parts, local = [df], []
        for st in ["S1", "S2", "S3"]:
            off, loc = os.path.join(rdir, f"results_{st}.csv"), os.path.join(adir, f"results_{st}.csv")
            if os.path.exists(off): parts.append(pd.read_csv(off))
            elif os.path.exists(loc): parts.append(pd.read_csv(loc)); local.append(st)
        curve_df = pd.concat(parts)
    s = df[df.state == state]
    def p95(v, q="q_main", mode="cold", col="t_plan"):
        return float(s[(s.variant == v) & (s["query"] == q) & (s["mode"] == mode)][col].quantile(0.95))
    def med(v, q, col="files_selected"):
        return int(s[(s.variant == v) & (s["query"] == q) & (s["mode"] == "cold")][col].median())
    V = ["baseline", "opt_a_checkpoint", "opt_b_sorted"]
    m = dict(fake=fake, state=state, n_files=int(s.n_files_total.iloc[0]), local=local)
    for mode, k in [("cold", "c"), ("warm", "w")]:
        b, a, o = (p95(v, mode=mode) for v in V)
        m.update({f"base_{k}": b, f"a_{k}": a, f"b_{k}": o, f"sa_{k}": b / a, f"sb_{k}": b / o})
    m["load"] = {v: p95(v, col="t_load") for v in V}
    m["prune"] = {v: p95(v, col="t_prune") for v in V}
    m["scan_base"], m["scan_b"] = p95("baseline", col="t_scan"), p95("opt_b_sorted", col="t_scan")
    m["sel_base"], m["sel_b"], m["alt_sel"] = med("baseline", "q_main"), med("opt_b_sorted", "q_main"), med("opt_b_sorted", "q_alt")
    m["rows_main"] = int(s[(s["query"] == "q_main")].rows.iloc[0])
    m["rows_ok"] = bool((s.rows == s.expected_rows).all())
    m["cost_a"] = m["cost_b"] = m["mb_b"] = None
    if costs is not None:
        c = costs.set_index("variant")
        m["cost_a"], m["cost_b"] = float(c.loc["opt_a_checkpoint", "wall_time_s"]), float(c.loc["opt_b_sorted", "wall_time_s"])
        m["mb_b"] = float(c.loc["opt_b_sorted", "bytes_rewritten"]) / 1e6
    # scaling curve must compare states measured on ONE machine: if some states are local runs,
    # plot only those (S4 official ran on a different machine)
    if local:
        curve_df = curve_df[curve_df.state.isin(local)]
    m["curve_hw_note"] = f"{', '.join(local)} đo trên cùng một máy (máy Phong)" if local else ""
    g = curve_df[(curve_df["mode"] == "cold") & (curve_df["query"] == "q_main")]
    g = g.groupby(["variant", "n_files_total"]).t_plan.quantile(0.95).reset_index()
    m["chart"] = {v: [[int(r.n_files_total), float(r.t_plan)] for r in g[g.variant == v].sort_values("n_files_total").itertuples()] for v in V}
    cb = m["chart"]["baseline"]
    m["curve_lo"], m["curve_hi"], m["curve_n_lo"], m["curve_n_hi"] = cb[0][1], cb[-1][1], cb[0][0], cb[-1][0]
    f2 = lambda x: vn(x, 2)
    m["fmt"] = dict(n_files=vn(m["n_files"], 0), base_c=f2(m["base_c"]), a_c=f2(m["a_c"]), b_c=f2(m["b_c"]),
                    sa_c=vn(m["sa_c"], 1), sb_c=vn(m["sb_c"], 1), sa_w=vn(m["sa_w"], 1), sb_w=vn(m["sb_w"], 1),
                    base_w=f2(m["base_w"]), a_w=vn(m["a_w"], 3), load_base=f2(m["load"]["baseline"]),
                    load_a=f2(m["load"]["opt_a_checkpoint"]), prune_base=vn(m["prune"]["baseline"], 4),
                    scan_base=f2(m["scan_base"]), scan_b=f2(m["scan_b"]), sel_base=vn(m["sel_base"], 0),
                    sel_b=vn(m["sel_b"], 0), alt_sel=vn(m["alt_sel"], 0), rows_main=vn(m["rows_main"], 0),
                    curve_lo=f2(m["curve_lo"]), curve_hi=f2(m["curve_hi"]), curve_n_lo=vn(m["curve_n_lo"], 0), curve_n_hi=vn(m["curve_n_hi"], 0),
                    cost_a=vn(m["cost_a"], 2) if m["cost_a"] is not None else "—",
                    cost_b=vn(m["cost_b"], 2) if m["cost_b"] is not None else "—",
                    mb_b=vn(m["mb_b"], 1) if m["mb_b"] is not None else "—",
                    load_share=vn(100 * m["load"]["baseline"] / m["base_c"], 0))
    return m

def narration(m):
    f = m["fmt"]
    hyp_c = m["sb_c"] >= 3
    lines = [
        ("hook_1", "Một triệu dòng dữ liệu."),
        ("hook_2", f"{f['n_files']} file."),
        ("hook_3", f"Và engine mất {f['base_c']} giây... chỉ để lên kế hoạch. Chưa đọc một dòng nào."),
        ("title", "Đây là câu chuyện về metadata. Nhóm 7: Metadata Scaling và Query Planning."),
        ("prob_1", "Mỗi lần mở bảng, engine phải đọc lại toàn bộ transaction log. Một nghìn commit. Hai mươi nghìn bản ghi file."),
        ("prob_2", "Dữ liệu lại nằm ngẫu nhiên, nên khoảng min max của các file chồng lên nhau. Lọc bằng min max loại được rất ít file."),
        ("hypo", "Giả thuyết: thời gian planning tăng theo số file và số commit, không theo dung lượng. Và có thể giảm ít nhất ba lần."),
        ("meth_1", "Cách thứ nhất: checkpoint. Gộp toàn bộ log thành một file duy nhất, không đụng tới dữ liệu."),
        ("meth_2", "Cách thứ hai: sắp xếp lại dữ liệu theo cột lọc, giữ nguyên số file, rồi checkpoint. Mỗi file chỉ còn giữ một khoảng hẹp."),
        ("exp", "Cùng một triệu dòng, chia từ một trăm đến hai mươi nghìn file. Ba truy vấn, mười lần mỗi tổ hợp. Trạng thái lớn nhất bị khóa lại, chỉ chạy khi phương pháp đã chốt."),
        ("measure", "Thời gian planning gồm hai phần: đọc log để biết danh sách file, và lọc file bằng min max. Cold là mỗi lần một tiến trình mới. Warm là chạy lại trong cùng tiến trình."),
        ("curve", ("Trên cùng một máy, " if m["local"] else "") + f"từ {f['curve_n_lo']} đến {f['curve_n_hi']} file, p chín mươi lăm planning của baseline tăng từ {f['curve_lo']} lên {f['curve_hi']} giây. Cùng dữ liệu, chỉ khác số file. Checkpoint kéo đường cong xuống."),
        ("split", f"Và gần như toàn bộ thời gian đó là đọc log: {f['load_share']} phần trăm. Checkpoint cắt phần này từ {f['load_base']} xuống còn {f['load_a']} giây."),
        ("speed", (f"Trên tập held-out, ở chế độ cold: checkpoint nhanh hơn {f['sa_c']} lần, thêm sắp xếp được {f['sb_c']} lần. "
                   + ("Đạt ngưỡng ba lần." if hyp_c else "Chưa đạt ngưỡng ba lần.")
                   + f" Ở chế độ warm, con số là {f['sa_w']} và {f['sb_w']} lần.")),
        ("scan", f"Sắp xếp gần như không làm planning nhanh hơn checkpoint. Nhưng nó giúp phần đọc dữ liệu: chỉ còn {f['sel_b']} trên {f['n_files']} file, thời gian scan giảm từ {f['scan_base']} xuống {f['scan_b']} giây."),
        ("cost", f"Cái giá: checkpoint mất {f['cost_a']} giây và không ghi lại dữ liệu. Sắp xếp mất {f['cost_b']} giây và ghi lại {f['mb_b']} megabyte."),
        ("fail", f"Và sắp xếp không phải phép màu. Lọc theo cột amount chưa sắp xếp, engine vẫn phải mở {f['alt_sel']} trên {f['n_files']} file."),
        ("decide", "Kết luận: checkpoint rẻ và nên bật. Sắp xếp chỉ đáng khi truy vấn chủ yếu lọc theo đúng cột đó. Chưa kiểm thử: object storage, lọc nhiều cột, và ghi đồng thời."),
        ("outro", "Metadata cũng là dữ liệu, và nó cần được chăm sóc. Nhóm 7. Cảm ơn đã theo dõi."),
    ]
    if m["fake"]:
        lines = [(k, ("Số liệu minh họa. " + t) if k == "speed" else t) for k, t in lines]
    return lines

def sh(cmd, **kw):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **kw)

def dur(fp):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", fp],
                         check=True, capture_output=True, text=True).stdout
    return float(json.loads(out)["format"]["duration"])

# Model chain: primary first; on its RPM budget or a 429 -> next model. "name:rpm" (rpm 0 = unknown).
MODELS = os.environ.get("GEMINI_TTS_MODELS",
    "gemini-3.8-flash-tts:10,gemini-3.1-flash-tts-preview:0,gemini-2.5-flash-preview-tts:0,gemini-2.5-pro-preview-tts:0")
CHAIN = [(m.split(":")[0], int(m.split(":")[1]) if ":" in m else 0) for m in MODELS.split(",")]
_calls, _cool = {}, {}   # model -> recent call timestamps / cooldown-until

def _ready(model, rpm):
    now = time.time()
    if _cool.get(model, 0) > now:
        return False
    _calls[model] = [t for t in _calls.get(model, []) if now - t < 60]
    return rpm == 0 or len(_calls[model]) < rpm

def _request(model, text, key):
    voice = os.environ.get("GEMINI_VOICE", "Charon")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": STYLE + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    _calls.setdefault(model, []).append(time.time())
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    return base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])

def gemini_tts(text, wav, key):
    """Returns the model that produced the clip."""
    for _ in range(40):
        for model, rpm in CHAIN:
            if not _ready(model, rpm):
                continue
            try:
                pcm = _request(model, text, key)
            except urllib.error.HTTPError as e:
                msg = e.read().decode()[:200].replace("\n", " ")
                if e.code in (429, 500, 503):
                    _cool[model] = time.time() + (60 if e.code == 429 else 10)
                    print(f"    {model}: HTTP {e.code} -> fallback"); continue
                if e.code in (400, 404):
                    _cool[model] = float("inf"); print(f"    {model}: HTTP {e.code} {msg} -> skipped"); continue
                raise
            except (KeyError, IndexError, OSError, http.client.HTTPException) as e:
                _cool[model] = time.time() + 10; print(f"    {model}: {type(e).__name__} -> fallback"); continue
            raw = wav + ".pcm"
            open(raw, "wb").write(pcm)
            sh(["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", raw,
                "-af", "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                       "silenceremove=start_periods=1:start_threshold=-50dB,areverse",
                "-ar", "48000", "-ac", "2", wav])
            os.remove(raw)
            print(f"    tail: {clean_tail(wav)}")
            return model
        time.sleep(5)   # every model busy -> wait for a window to free up
    sys.exit("Gemini TTS: no model available after retries")

def _seg_stats(wav, start, length):
    """RMS (dB) and zero-crossing rate of a segment."""
    import re
    log = subprocess.run(["ffmpeg", "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", wav, "-af", "astats", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    rms = re.findall(r"RMS level dB: (-?[\d.]+|-inf)", log)
    zcr = re.findall(r"Zero crossings rate: ([\d.]+)", log)
    return (float(rms[-1]) if rms and rms[-1] != "-inf" else -99.0), (float(zcr[-1]) if zcr else 0.0)

def clean_tail(wav):
    """Gemini clips end with a short loud burst after the last pause (audible 'rẹt'):
    measured ~0.13 s at about -8 dB. Cut it only if the trailing segment is that short AND that
    loud; a real last word after a pause is longer/quieter and is kept. Run once, on fresh clips only."""
    import re
    total = dur(wav)
    log = subprocess.run(["ffmpeg", "-i", wav, "-af", "silencedetect=n=-45dB:d=0.08", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    if not starts or len(ends) < len(starts):
        return None
    s0, e0 = starts[-1], ends[-1]
    tail = total - e0
    rms, zcr = _seg_stats(wav, e0, tail)
    info = f"tail {tail:.2f}s rms {rms:.0f}dB zcr {zcr:.2f}"
    if tail > 0.2 or rms < -13:   # burst: ~0.13 s at about -8 dB, louder than speech
        return f"kept ({info})"
    cut = s0 + 0.05
    tmp = wav + ".tmp.wav"
    sh(["ffmpeg", "-y", "-i", wav, "-t", f"{cut:.3f}", "-af", f"afade=t=out:st={max(0, cut - 0.06):.3f}:d=0.06", tmp])
    os.replace(tmp, wav)
    return f"cut noise ({info})"

def _norm(t):
    import re, unicodedata
    return re.sub(r"[^\w ]", " ", unicodedata.normalize("NFC", t.lower())).split()

def transcribe(wav, key):
    model = os.environ.get("GEMINI_STT_MODEL", "gemini-3.8-flash")
    mp3 = wav + ".mp3"
    sh(["ffmpeg", "-y", "-i", wav, "-ac", "1", "-b:a", "64k", mp3])
    b = base64.b64encode(open(mp3, "rb").read()).decode(); os.remove(mp3)
    body = {"contents": [{"parts": [{"inlineData": {"mimeType": "audio/mp3", "data": b}},
                                    {"text": "Transcribe this Vietnamese audio verbatim. Write numbers as digits. Output only the transcript."}]}]}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503): time.sleep(10 * (attempt + 1)); continue
            raise
        except (KeyError, IndexError, OSError, http.client.HTTPException):   # empty answer / network -> retry
            time.sleep(5 * (attempt + 1)); continue
    return None   # could not verify

def matches(text, heard):
    """Word-level similarity; also rejects any leaked style direction."""
    import difflib
    a, b = _norm(text), _norm(heard)
    import re
    leak = STYLE and any(w in b for w in _norm(STYLE)[:3])
    # every number written with digits must be heard exactly (e.g. 0,51 must not become 5,51)
    nums_ok = all(n in heard.replace(" ", "") for n in re.findall(r"\d[\d.,]*\d|\d", text))
    r = difflib.SequenceMatcher(None, a, b).ratio()
    return (not leak) and nums_ok and r >= 0.6, r

def say_tts(text, wav):
    aiff = wav + ".aiff"
    sh(["say", "-v", "Linh", "-r", "170", "-o", aiff, text])
    sh(["ffmpeg", "-y", "-i", aiff, "-ar", "48000", "-ac", "2", wav]); os.remove(aiff)

def load_env():
    fp = os.path.join(ROOT, ".env")   # gitignored; accepts GEMINI_API_KEY or gemini_key
    if os.path.exists(fp):
        for line in open(fp):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def voices(lines, primary_only=False):
    load_env()
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("gemini_key") or os.environ.get("GOOGLE_API_KEY")
    engine = "gemini" if key else "say"
    if not key:
        print("!! GEMINI_API_KEY not set -> placeholder voice (macOS Linh)")
    vdir = os.path.join(PUB, "voice"); os.makedirs(vdir, exist_ok=True)
    if primary_only:
        del CHAIN[1:]
    out = []
    for sid, text in lines:
        h = hashlib.sha1(f"{engine}|{os.environ.get('GEMINI_VOICE','Charon')}|{STYLE}|{text}".encode()).hexdigest()[:10]
        wav = os.path.join(vdir, f"{sid}.wav"); stamp = wav + ".hash"
        old = open(stamp).read().split("|") if os.path.exists(stamp) and os.path.exists(wav) else ["", ""]
        stale = old[0] != h or (primary_only and old[1:] != [CHAIN[0][0]])
        if stale:
            if not key:
                say_tts(text, wav); model = "say"
            for attempt in range(3 if key else 0):
                model = gemini_tts(text, wav, key)
                heard = transcribe(wav, key)
                if heard is None:
                    print("    check SKIPPED (checker returned nothing) -> listen to this clip"); break
                ok, r = matches(text, heard)
                print(f"    check {r:.2f} {'OK ' if ok else 'BAD'} heard: {heard}")
                if ok: break
            else:
                if key: print(f"!! {sid}: transcript still differs after 3 tries -> listen to it")
            open(stamp, "w").write(f"{h}|{model}")
        else:
            model = old[1] if len(old) > 1 else "?"
        d = dur(wav); out.append(dict(id=sid, text=text, voice=f"voice/{sid}.wav", dur=round(d, 3), model=model))
        print(f"  {sid:7s} {d:5.2f}s  [{model}]  {text}")
    used = sorted({o["model"] for o in out})
    if key and used != [CHAIN[0][0]]:
        print(f"!! models used: {used} -> voices may differ slightly; rerun with --primary-only to unify")
    return out, engine

SFX = {  # synthesised with ffmpeg -> no licensing issues
    "boom":    "aevalsrc='1.0*sin(2*PI*(38+110*exp(-7*t))*t)*exp(-2.6*t)':d=2.2:s=48000",
    "impact":  "aevalsrc='0.9*sin(2*PI*(50+160*exp(-12*t))*t)*exp(-4*t)+0.25*(random(0)*2-1)*exp(-22*t)':d=1.5:s=48000",
    "whoosh":  "anoisesrc=d=0.9:c=pink:a=0.7,bandpass=f=1400:w=1800,afade=t=in:d=0.55:curve=exp,afade=t=out:st=0.55:d=0.35",
    "riser":   "aevalsrc='0.35*sin(2*PI*(120*t+260*t*t))*(t/3)+0.12*(random(0)*2-1)*(t/3)^2':d=3:s=48000,highpass=f=150",
    "tick":    "aevalsrc='0.6*sin(2*PI*2400*t)*exp(-90*t)':d=0.08:s=48000",
    "glitch":  "aevalsrc='0.35*sgn(sin(2*PI*(90+600*mod(floor(t*40),7))*t))*gt(random(0),0.3)':d=0.35:s=48000,lowpass=f=5000",
    "shimmer": "aevalsrc='0.18*(sin(2*PI*1760*t)*exp(-3*t)+sin(2*PI*2217*t)*exp(-3.5*t)+sin(2*PI*2637*t)*exp(-4*t))':d=2:s=48000",
    "click":   "aevalsrc='0.5*(random(0)*2-1)*exp(-120*t)':d=0.05:s=48000,highpass=f=1500",
    "merge":   "aevalsrc='0.5*sin(2*PI*(900*exp(-6*t)+60)*t)*exp(-3*t)':d=1.2:s=48000",
}

def music(total):
    """Dark cinematic drone (A minor) + slow heartbeat pulse."""
    vdir = os.path.join(PUB, "sfx")
    drone = ("aevalsrc='0.10*sin(2*PI*55*t)+0.07*sin(2*PI*82.41*t)+0.05*sin(2*PI*110*t)"
             "+0.025*sin(2*PI*130.81*t)*(0.5+0.5*sin(2*PI*0.05*t))+0.02*sin(2*PI*164.81*t)*(0.5+0.5*sin(2*PI*0.031*t))'"
             f":d={total}:s=48000,lowpass=f=700,aecho=0.8:0.7:180|360:0.3|0.2")
    pulse = (f"aevalsrc='0.55*sin(2*PI*(48+70*exp(-30*mod(t,0.857)))*mod(t,0.857))*exp(-9*mod(t,0.857))'"
             f":d={total}:s=48000,lowpass=f=200")
    for name, f in [("drone", drone), ("pulse", pulse)]:
        sh(["ffmpeg", "-y", "-f", "lavfi", "-i", f, "-ac", "2", "-ar", "48000", os.path.join(vdir, f"{name}.wav")])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--state", default="S4")
    ap.add_argument("--primary-only", action="store_true")
    args = ap.parse_args()
    m = metrics(args.fake, args.state)
    print(f"metrics ({'FAKE' if args.fake else args.state}; local states {m['local']}): " + json.dumps(m["fmt"], ensure_ascii=False))
    scenes, engine = voices(narration(m), args.primary_only)
    os.makedirs(os.path.join(PUB, "sfx"), exist_ok=True)
    for k, f in SFX.items():
        sh(["ffmpeg", "-y", "-f", "lavfi", "-i", f, "-ac", "2", "-ar", "48000", os.path.join(PUB, "sfx", f"{k}.wav")])
    music(int(sum(s["dur"] for s in scenes) + 60))
    json.dump(dict(metrics=m, scenes=scenes, voiceEngine=engine),
              open(os.path.join(HERE, "src", "data.json"), "w"), ensure_ascii=False, indent=1)
    print(f"-> src/data.json  (voice: {engine})")

if __name__ == "__main__":
    main()
