"""Build the project video: slides (HTML -> PNG via headless Chrome) + narration + transitions + SFX.
Numbers come ONLY from the results CSVs.

  python video/make_video.py --fake          # results/results_fake.csv, every number badged FAKE
  python video/make_video.py --state S4      # results/results_S4.csv + costs_S4.csv (after freeze)

Narration = each slide's <aside>. Default voice: macOS `say -v Linh` (placeholder).
To use Gemini TTS instead, put video/audio/<slide>.wav files (hook_1..hook_3, cover, pain,
design, results, decision) and pass --audio-dir video/audio.
Output: video/build/nhom7_<fake|S4>.mp4"""
import argparse, os, re, subprocess, json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FONTS = ("https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700"
         "&family=JetBrains+Mono:wght@400;600&display=swap")
COLORS = {"baseline": "#8E5BB5", "opt_a_checkpoint": "#2F5FB8", "opt_b_sorted": "#C2701F"}  # validated
FPS = 30

# (slide id, transition INTO this slide, transition seconds)
SEQ = [("hook_1", None, 0), ("hook_2", "fade", 0.12), ("hook_3", "fade", 0.12),
       ("cover", "fadeblack", 0.8), ("pain", "smoothleft", 0.6), ("design", "smoothleft", 0.6),
       ("results", "smoothleft", 0.6), ("decision", "smoothleft", 0.6)]

def sh(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def dur(fp):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", fp],
                         check=True, capture_output=True, text=True).stdout
    return float(json.loads(out)["format"]["duration"])

def vn(x, nd):
    """Vietnamese number format: 20.000 / 0,51"""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")

def metrics(args):
    rdir = os.path.join(ROOT, "results")
    if args.fake:
        df = pd.read_csv(os.path.join(rdir, "results_fake.csv"))
        state, costs, source = "S4", None, "results/results_fake.csv — SỐ LIỆU GIẢ, chỉ để dựng thử"
    else:
        state = args.state
        df = pd.read_csv(os.path.join(rdir, f"results_{state}.csv"))
        cp = os.path.join(rdir, f"costs_{state}.csv")
        costs = pd.read_csv(cp) if os.path.exists(cp) else None
        source = f"results/results_{state}.csv, results/costs_{state}.csv"
    s = df[(df.state == state) & (df["mode"] == "cold")]
    p95 = lambda v, q="q_main": s[(s.variant == v) & (s["query"] == q)].t_plan.quantile(0.95)
    base, a, b = p95("baseline"), p95("opt_a_checkpoint"), p95("opt_b_sorted")
    n_files = int(s.n_files_total.iloc[0])
    alt_sel = int(s[(s.variant == "opt_b_sorted") & (s["query"] == "q_alt")].files_selected.median())
    m = {"n_files": vn(n_files, 0), "n_files_spoken": vn(n_files, 0),
         "base": vn(base, 2), "a": vn(a, 2), "b": vn(b, 2),
         "sa": vn(base / a, 1), "sb": vn(base / b, 1),
         "alt_sel": vn(alt_sel, 0), "alt_sel_spoken": vn(alt_sel, 0),
         "hyp": "đạt" if base / b >= 3 else "không đạt",
         "hyp_spoken": "được xác nhận" if base / b >= 3 else "không được xác nhận",
         "source": source, "cost_a": "—", "cost_b": "—", "cost_clause": ""}
    if costs is not None:
        c = costs.groupby("variant").wall_time_s.sum()
        if "opt_a_checkpoint" in c: m["cost_a"] = f"{vn(c['opt_a_checkpoint'], 1)} s"
        if "opt_b_sorted" in c:
            m["cost_b"] = f"{vn(c['opt_b_sorted'], 1)} s"
            m["cost_clause"] = f", với chi phí {vn(c['opt_b_sorted'], 1)} giây"
    # chart: p95 t_plan vs n_files, q_main cold, all states in the file
    if not args.fake:   # chart needs every state, not only the held-out one
        import glob
        df = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(rdir, "results_S*.csv")))])
    allc = df[(df["mode"] == "cold") & (df["query"] == "q_main")]
    g = allc.groupby(["variant", "n_files_total"]).t_plan.quantile(0.95).reset_index()
    return m, g

def chart(g, fp, fake):
    from matplotlib.ticker import FuncFormatter
    plt.rcParams.update({"font.family": "Arial", "font.size": 22})
    fig, ax = plt.subplots(figsize=(8.4, 6.2), dpi=100)
    fig.patch.set_facecolor("#FCFCFB"); ax.set_facecolor("#FCFCFB")
    for v, col in COLORS.items():
        d = g[g.variant == v].sort_values("n_files_total")
        ax.plot(d.n_files_total, d.t_plan, color=col, lw=2.5, marker="o", ms=9,
                markeredgecolor="#FCFCFB", markeredgewidth=2, label=v)
        ax.annotate(v, (d.n_files_total.iloc[-1], d.t_plan.iloc[-1]), xytext=(10, 0),
                    textcoords="offset points", va="center", color="#14213D", fontsize=20)
    ax.set_xscale("log"); ax.set_yscale("log")
    names = {100: "S1", 1000: "S2", 10000: "S3", 20000: "S4"}
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: names.get(int(round(x)), vn(x, 0))))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: vn(y, 3).rstrip("0").rstrip(",")))
    ax.set_xticks(sorted(g.n_files_total.unique())); ax.minorticks_off()
    ax.set_xlabel("Số file: 100 → 20.000 (log)", color="#45506A"); ax.set_ylabel("p95 t_plan (s)", color="#45506A")
    ax.set_title("p95 t_plan · q_main · cold" + (" · SỐ LIỆU GIẢ" if fake else ""),
                 loc="left", color="#14213D", fontsize=22, pad=14)
    ax.grid(True, which="major", color="#E4E2DC", lw=1); ax.tick_params(colors="#45506A")
    for sp in ["top", "right"]: ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]: ax.spines[sp].set_color("#BFC3CC")
    ax.legend(frameon=False, loc="lower right", fontsize=18)
    ax.set_xlim(right=ax.get_xlim()[1] * 6)
    fig.tight_layout(); fig.savefig(fp); plt.close(fig)

def fill(tpl, m):
    return re.sub(r"\{\{(\w+)\}\}", lambda x: str(m[x.group(1)]), tpl)

def page(section, fake):
    badge = ('<div style="position:absolute;top:40px;right:48px;background:#C0392B;color:#FFF;'
             'font:700 26px \'Be Vietnam Pro\',Arial;padding:10px 22px;border-radius:999px;'
             'letter-spacing:1px">SỐ LIỆU GIẢ — CHỈ ĐỂ DỰNG THỬ</div>') if fake else ""
    section = section.replace("</section>", badge + "</section>")
    return f"""<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}">
<style>html,body{{margin:0;width:1920px;height:1080px;overflow:hidden}}
section{{position:relative;width:1920px;height:1080px;box-sizing:border-box}}
section *{{box-sizing:border-box}} h1,h2,h3,p{{margin:0}} aside,x-icon{{display:none}}
table{{border-collapse:collapse;width:100%}} th,td{{padding:.35em .6em;border-bottom:1px solid #DDD9CF}}
th{{text-align:left}}</style></head><body>{section}</body></html>"""

def render(html, png, build):
    hp = os.path.join(build, os.path.basename(png).replace(".png", ".html"))
    open(hp, "w").write(html)
    sh([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
        "--window-size=1920,1080", "--virtual-time-budget=4000", f"--screenshot={png}", "file://" + hp])

def tts(text, wav, build):
    aiff = wav.replace(".wav", ".aiff")
    sh(["say", "-v", "Linh", "-r", "185", "-o", aiff, text])
    sh(["ffmpeg", "-y", "-i", aiff, "-ar", "48000", "-ac", "2", wav])

def sfx(build):
    """Synthesised SFX (no external assets)."""
    S = {"whoosh": "anoisesrc=d=0.8:c=pink:a=0.6,highpass=f=300,lowpass=f=4000,"
                   "afade=t=in:d=0.45:curve=exp,afade=t=out:st=0.45:d=0.35,volume=0.5",
         "boom":   "aevalsrc='0.9*sin(2*PI*(45+90*exp(-9*t))*t)*exp(-3.5*t)':d=1.4:s=48000,volume=1.2",
         "pop":    "aevalsrc='0.5*sin(2*PI*1320*t)*exp(-14*t)+0.35*sin(2*PI*660*t)*exp(-9*t)':d=0.5:s=48000",
         "riser":  "anoisesrc=d=1.6:c=white:a=0.3,highpass=f=1200,afade=t=in:d=1.5:curve=qsin,"
                   "afade=t=out:st=1.5:d=0.1,volume=0.35"}
    out = {}
    for k, f in S.items():
        out[k] = os.path.join(build, f"sfx_{k}.wav")
        sh(["ffmpeg", "-y", "-f", "lavfi", "-i", f, "-ar", "48000", "-ac", "2", out[k]])
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--state", default="S4")
    ap.add_argument("--audio-dir", default=None, help="pre-made narration wavs (e.g. Gemini TTS)")
    args = ap.parse_args()
    tag = "fake" if args.fake else args.state
    build = os.path.join(HERE, "build", tag); os.makedirs(build, exist_ok=True)

    m, g = metrics(args)
    chart(g, os.path.join(build, "chart.png"), args.fake)
    tpl = {k: open(os.path.join(HERE, "slides", f"{k}.html")).read()
           for k in ["hook", "cover", "pain", "design", "results", "decision"]}

    # slides + narration text
    slides, texts = {}, {}
    hook_lines = re.search(r"<aside>(.*?)</aside>", fill(tpl["hook"], {**m, "o2": 0, "o3": 0}), re.S).group(1).split("|")
    for i in (1, 2, 3):
        mm = {**m, "o2": 1 if i >= 2 else 0, "o3": 1 if i >= 3 else 0}
        slides[f"hook_{i}"] = page(fill(tpl["hook"], mm), args.fake)
        texts[f"hook_{i}"] = hook_lines[i - 1]
    for k in ["cover", "pain", "design", "results", "decision"]:
        sec = fill(tpl[k], m)
        texts[k] = re.search(r"<aside>(.*?)</aside>", sec, re.S).group(1).strip()
        slides[k] = page(sec, args.fake and k in ("results", "decision"))
    with open(os.path.join(build, "narration.txt"), "w") as f:
        f.writelines(f"[{k}] {texts[k]}\n" for k, *_ in SEQ)

    # render + audio
    seg = []
    for k, tr, td in SEQ:
        png, wav = os.path.join(build, f"{k}.png"), os.path.join(build, f"{k}.wav")
        render(slides[k], png, build)
        if args.audio_dir and os.path.exists(os.path.join(args.audio_dir, f"{k}.wav")):
            sh(["ffmpeg", "-y", "-i", os.path.join(args.audio_dir, f"{k}.wav"), "-ar", "48000", "-ac", "2", wav])
        else:
            tts(texts[k], wav, build)
        hook = k.startswith("hook")
        pre, post = (0.15, 0.35) if hook else (0.6, 0.9)
        seg.append(dict(k=k, png=png, wav=wav, tr=tr, td=td, pre=pre, d=pre + dur(wav) + post))
        print(f"{k:9s} {seg[-1]['d']:5.1f}s")

    # timeline: start of segment i = start(i-1) + d(i-1) - td(i)
    t = 0.0
    for i, s in enumerate(seg):
        if i: t = seg[i - 1]["start"] + seg[i - 1]["d"] - s["td"]
        s["start"] = t
    total = seg[-1]["start"] + seg[-1]["d"] + 1.5
    seg[-1]["d"] += 1.5                         # hold the last slide for the fade-out

    fx = sfx(build)
    cues = [("boom", 0.0), ("riser", max(0, seg[3]["start"] - 1.5)), ("boom", seg[3]["start"])]
    cues += [("pop", s["start"]) for s in seg[1:3]]
    cues += [("whoosh", s["start"] - 0.25) for s in seg[4:]]

    inp, fc = [], []
    for s in seg:
        inp += ["-loop", "1", "-framerate", str(FPS), "-t", f"{s['d']:.3f}", "-i", s["png"]]
    for i in range(len(seg)):
        zoom = "" if not seg[i]["k"].startswith("hook") else \
            f",scale=w='trunc(1920*(1+0.04*t/{seg[i]['d']:.3f})/2)*2':h=-2:eval=frame,crop=1920:1080"
        fc.append(f"[{i}:v]fps={FPS},format=yuv420p{zoom},settb=AVTB[v{i}]")
    last = "v0"
    for i in range(1, len(seg)):
        fc.append(f"[{last}][v{i}]xfade=transition={seg[i]['tr']}:duration={seg[i]['td']}:"
                  f"offset={seg[i]['start']:.3f}[x{i}]")
        last = f"x{i}"
    fc.append(f"[{last}]fade=t=in:d=0.4,fade=t=out:st={total - 1.2:.3f}:d=1.2[vout]")

    n = len(seg); a_idx = n
    for s in seg: inp += ["-i", s["wav"]]
    voice = []
    for i, s in enumerate(seg):
        ms = int((s["start"] + s["pre"]) * 1000)
        fc.append(f"[{a_idx + i}:a]adelay={ms}|{ms}[n{i}]"); voice.append(f"[n{i}]")
    fc.append(f"{''.join(voice)}amix=inputs={n}:normalize=0,apad=whole_dur={total:.3f}[voice]")
    fc.append("[voice]asplit=2[vmix][vside]")

    b_idx = a_idx + n
    inp += ["-f", "lavfi", "-t", f"{total:.3f}", "-i",
            "aevalsrc='0.05*(sin(2*PI*110*t)+0.7*sin(2*PI*164.81*t)+0.6*sin(2*PI*220*t)+0.4*sin(2*PI*261.63*t))"
            "*(0.75+0.25*sin(2*PI*0.08*t))':s=48000:c=stereo"]
    fc.append(f"[{b_idx}:a]lowpass=f=900,afade=t=in:d=2,afade=t=out:st={total - 2.5:.3f}:d=2.5,volume=0.9[bgm]")
    fc.append("[bgm][vside]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=400[bgmd]")

    s_idx = b_idx + 1; fxl = []
    for j, (name, at) in enumerate(cues):
        inp += ["-i", fx[name]]; ms = int(at * 1000)
        fc.append(f"[{s_idx + j}:a]adelay={ms}|{ms}[f{j}]"); fxl.append(f"[f{j}]")
    fc.append(f"{''.join(fxl)}amix=inputs={len(fxl)}:normalize=0,volume=0.6[sfx]")
    fc.append(f"[vmix][bgmd][sfx]amix=inputs=3:normalize=0,afade=t=out:st={total - 1.2:.3f}:d=1.2,"
              f"loudnorm=I=-16:TP=-1.5,aresample=48000[aout]")

    out = os.path.join(HERE, "build", f"nhom7_{tag}.mp4")
    sh(["ffmpeg", "-y", *inp, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", out])
    print(f"\n-> {out}  ({total:.1f}s)")

if __name__ == "__main__":
    main()
