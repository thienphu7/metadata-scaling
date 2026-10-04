import React from "react";
import {AbsoluteFill, interpolate, random, spring, useCurrentFrame, useVideoConfig, Easing} from "remotion";
import {C, SANS, MONO, clamp, Words, Sweep, Glitch, Counter, Kicker, Flash, FakeBadge, vn} from "./fx";

export type M = {
  fake: boolean; n_files: number; base: number; a: number; b: number; sa: number; sb: number;
  sel_b: number; alt_sel: number; chart: Record<string, [number, number][]>;
  fmt: Record<string, string>;
};
export type P = {dur: number; v0: number; vd: number; m: M};
const at = (p: P, x: number) => Math.round(p.v0 + x * p.vd);   // moment inside the voice line
const center: React.CSSProperties = {justifyContent: "center", alignItems: "center", flexDirection: "column", display: "flex"};

/* ---------- HOOK ---------- */
const DataRain: React.FC<{o?: number}> = ({o = 0.18}) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{opacity: o}}>
      {Array.from({length: 34}).map((_, i) => {
        const sp = 4 + random(`rs${i}`) * 9, off = random(`ro${i}`) * 1400;
        const digits = Array.from({length: 22}).map((_, j) => Math.floor(random(`d${i}-${j}-${Math.floor(f / 4)}`) * 10)).join("\n");
        return <pre key={i} style={{position: "absolute", left: i * 57 + 10, top: ((f * sp + off) % 1500) - 700, margin: 0,
          fontFamily: MONO, fontSize: 22, lineHeight: 1.3, color: i % 6 === 0 ? C.amber : "#7FA2E0"}}>{digits}</pre>;
      })}
    </AbsoluteFill>
  );
};

export const Hook1: React.FC<P> = (p) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const land = p.v0 + 26;
  const bump = spring({frame: f - land, fps, config: {damping: 9, stiffness: 200}});
  return (
    <AbsoluteFill style={center}>
      <DataRain o={interpolate(f, [0, 20], [0, 0.22], clamp)} />
      <div style={{transform: `scale(${1 + 0.06 * Math.sin(bump * Math.PI)})`, ...center}}>
        <Counter to={1000000} start={p.v0 - 4} len={30} style={{fontFamily: MONO, fontWeight: 700, fontSize: 210, color: C.ink,
          textShadow: "0 0 60px #5B9BFF55"}} />
        <div style={{fontFamily: SANS, fontSize: 54, letterSpacing: 18, color: C.dim, marginTop: 10,
          opacity: interpolate(f, [land - 6, land + 6], [0, 1], clamp)}}>DÒNG DỮ LIỆU</div>
      </div>
      <Flash at={land} strength={0.35} />
    </AbsoluteFill>
  );
};

export const Hook2: React.FC<P> = (p) => {
  const f = useCurrentFrame();
  const r = interpolate(f, [0, 26], [0, 1300], {...clamp, easing: Easing.out(Easing.cubic)});
  return (
    <AbsoluteFill style={center}>
      <svg width="1920" height="1080" style={{position: "absolute"}}>
        <defs>
          <pattern id="tiles" width="9.6" height="10.8" patternUnits="userSpaceOnUse">
            <rect x="1" y="1" width="7.6" height="8.8" rx="1.2" fill="#2B4C8C" />
          </pattern>
          <radialGradient id="fade"><stop offset="0.55" stopColor="#fff" /><stop offset="1" stopColor="#fff" stopOpacity="0" /></radialGradient>
          <mask id="m"><circle cx="960" cy="540" r={r} fill="url(#fade)" /></mask>
        </defs>
        <rect width="1920" height="1080" fill="url(#tiles)" mask="url(#m)" opacity={0.75} />
      </svg>
      <AbsoluteFill style={{background: "radial-gradient(ellipse at center, #070B14EE 0%, #070B1499 35%, transparent 70%)"}} />
      <div style={{fontFamily: MONO, fontWeight: 700, fontSize: 200, color: C.amber, textShadow: "0 0 80px #FFB54777",
        opacity: interpolate(f, [p.v0, p.v0 + 8], [0, 1], clamp),
        transform: `scale(${interpolate(f, [p.v0, p.v0 + 12], [1.25, 1], {...clamp, easing: Easing.out(Easing.back(2))})})`}}>
        {p.m.fmt.n_files} file</div>
      <div style={{fontFamily: SANS, fontSize: 34, color: C.dim, letterSpacing: 6, marginTop: 16,
        opacity: interpolate(f, [p.v0 + 14, p.v0 + 26], [0, 1], clamp)}}>mỗi ô là một file Parquet</div>
    </AbsoluteFill>
  );
};

export const Hook3: React.FC<P> = (p) => {
  const f = useCurrentFrame();
  const runEnd = at(p, 0.35);
  const prog = interpolate(f, [p.v0, runEnd], [0, 1], {...clamp, easing: Easing.out(Easing.quad)});
  const R = 200, L = 2 * Math.PI * R;
  const second = at(p, 0.68);
  return (
    <AbsoluteFill style={center}>
      <svg width="640" height="640" style={{position: "absolute", top: 150}}>
        <circle cx="320" cy="320" r={R} stroke="#1C2A48" strokeWidth="10" fill="none" />
        <circle cx="320" cy="320" r={R} stroke={C.amber} strokeWidth="10" fill="none" strokeLinecap="round"
          strokeDasharray={L} strokeDashoffset={L * (1 - prog)} transform="rotate(-90 320 320)"
          style={{filter: "drop-shadow(0 0 18px #FFB547)"}} />
        {Array.from({length: 60}).map((_, i) => {
          const a = (i / 60) * 2 * Math.PI, r1 = R + 26, r2 = R + (i % 5 === 0 ? 46 : 36);
          return <line key={i} x1={320 + r1 * Math.sin(a)} y1={320 - r1 * Math.cos(a)} x2={320 + r2 * Math.sin(a)} y2={320 - r2 * Math.cos(a)}
            stroke={i / 60 <= prog ? C.amber : "#2A3858"} strokeWidth={i % 5 === 0 ? 4 : 2} />;
        })}
      </svg>
      <div style={{position: "absolute", top: 410, fontFamily: MONO, fontWeight: 700, fontSize: 110, color: C.ink}}>
        <Counter to={p.m.base} start={p.v0} len={runEnd - p.v0} nd={2} />
        <span style={{fontSize: 50, color: C.dim}}> s</span>
      </div>
      <div style={{position: "absolute", top: 800}}>
        <Words text="chỉ để LÊN KẾ HOẠCH" start={at(p, 0.3)} size={50} color={C.amber} weight={600} />
      </div>
      <div style={{position: "absolute", bottom: 100}}>
        <Glitch at={second} len={14}>
          <Words text="Chưa đọc một dòng nào." start={second} size={52} weight={800} color={C.rose} stagger={2} />
        </Glitch>
      </div>
      <FakeBadge on={p.m.fake} />
    </AbsoluteFill>
  );
};

/* ---------- TITLE ---------- */
export const Title: React.FC<P> = (p) => {
  const f = useCurrentFrame();
  const t0 = at(p, 0.3);
  const rise = (d: number) => interpolate(f, [t0 + d, t0 + d + 18], [110, 0], {...clamp, easing: Easing.out(Easing.cubic)});
  const track = interpolate(f, [t0, t0 + 80], [40, 10], {...clamp, easing: Easing.out(Easing.cubic)});
  const line = interpolate(f, [t0 + 14, t0 + 40], [0, 900], {...clamp, easing: Easing.inOut(Easing.cubic)});
  return (
    <AbsoluteFill style={center}>
      <Words text="Đây là câu chuyện về metadata." start={p.v0} size={40} color={C.dim} weight={400}
        style={{position: "absolute", top: 230, opacity: interpolate(f, [t0 - 6, t0 + 4], [1, 0], clamp)}} />
      <div style={{overflow: "hidden", paddingBottom: 10}}>
        <div style={{transform: `translateY(${rise(0)}%)`}}>
          <Sweep at={t0 + 24} style={{fontFamily: SANS, fontWeight: 800, fontSize: 150, letterSpacing: track, lineHeight: 1}}>METADATA SCALING</Sweep>
        </div>
      </div>
      <div style={{width: line, height: 3, background: `linear-gradient(90deg, transparent, ${C.amber}, transparent)`, margin: "26px 0"}} />
      <div style={{overflow: "hidden"}}>
        <div style={{transform: `translateY(${rise(8)}%)`, fontFamily: MONO, fontSize: 60, color: C.amber, letterSpacing: track * 0.6}}>
          &amp; QUERY PLANNING</div>
      </div>
      <div style={{fontFamily: SANS, fontSize: 28, color: C.dim, letterSpacing: 10, marginTop: 40,
        opacity: interpolate(f, [t0 + 30, t0 + 45], [0, 1], clamp)}}>NHÓM 7 · AI20K TRACK 2 · DATA LAKEHOUSE CHALLENGE</div>
      <Flash at={t0} strength={0.5} />
    </AbsoluteFill>
  );
};

/* ---------- PROBLEM ---------- */
export const Prob1: React.FC<P> = (p) => {
  const f = useCurrentFrame();
  const cols = 8, rows = 7, beam = interpolate(f, [at(p, 0.25), at(p, 0.85)], [-10, 110], clamp);
  return (
    <AbsoluteFill>
      <div style={{position: "absolute", left: 140, top: 150}}><Kicker text="TRANSACTION LOG · REPLAY" start={p.v0} /></div>
      <div style={{position: "absolute", left: 140, top: 230, width: 1050, height: 700, overflow: "hidden"}}>
        {Array.from({length: cols * rows}).map((_, i) => {
          const c = i % cols, r = Math.floor(i / cols), s = p.v0 + i * 1.2;
          const o = interpolate(f, [s, s + 8], [0, 1], clamp);
          const lit = Math.abs(beam - ((r + 0.5) / rows) * 100) < 9;
          return <div key={i} style={{position: "absolute", left: c * 130, top: r * 98, width: 118, height: 84, borderRadius: 8,
            border: `1.5px solid ${lit ? C.amber : "#2E4270"}`, background: lit ? "#FFB54722" : "#0E1830CC", opacity: o,
            transform: `translateY(${(1 - o) * -40}px)`, fontFamily: MONO, fontSize: 15, color: lit ? C.amber : "#6F86B8",
            padding: "12px 10px", boxShadow: lit ? "0 0 24px #FFB54766" : "none"}}>
            {`${String(i + 1).padStart(6, "0")}`}<br />.json</div>;
        })}
        <div style={{position: "absolute", left: 0, right: 0, top: `${beam}%`, height: 4, background: C.amber,
          boxShadow: "0 0 40px 12px #FFB54788", opacity: beam > -5 && beam < 105 ? 1 : 0}} />
      </div>
      <div style={{position: "absolute", right: 150, top: 330, display: "flex", flexDirection: "column", gap: 70, alignItems: "flex-end"}}>
        {[["commit", 1000, at(p, 0.45)], ["bản ghi file", 20000, at(p, 0.7)]].map(([label, n, s]) => (
          <div key={label as string} style={{textAlign: "right", opacity: interpolate(f, [s as number, (s as number) + 8], [0, 1], clamp)}}>
            <Counter to={n as number} start={s as number} len={24} style={{fontFamily: MONO, fontWeight: 700, fontSize: 120, color: C.ink}} />
            <div style={{fontFamily: SANS, fontSize: 36, color: C.dim}}>{label}</div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const N = 14;
const overlap = Array.from({length: N}).map((_, i) => [random(`mn${i}`) * 0.07, 0.93 + random(`mx${i}`) * 0.07]);
const sorted = Array.from({length: N}).map((_, i) => [i / N, (i + 1) / N]);
const BAR_X = 260, BAR_W = 1400, GAP = 36;

const Bars: React.FC<{mix: number; band: [number, number]; bandOn: number; litUpTo: number; axis: string; hot?: string; dimOthers?: number}> =
  ({mix, band, bandOn, litUpTo, axis, hot = C.amber, dimOthers = 0}) => {
  const f = useCurrentFrame();
  return (
    <div style={{position: "absolute", left: BAR_X, top: 240, width: BAR_W, height: N * GAP}}>
      {overlap.map(([a0, a1], i) => {
        const lo = a0 + (sorted[i][0] - a0) * mix, hi = a1 + (sorted[i][1] - a1) * mix;
        const grow = interpolate(f, [i * 2, i * 2 + 16], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
        const hits = lo <= band[1] && hi >= band[0];
        const lit = hits && i < litUpTo;
        return <div key={i} style={{position: "absolute", top: i * GAP, left: `${lo * 100}%`, width: `${(hi - lo) * 100 * grow}%`, height: 22,
          borderRadius: 6, background: lit ? hot : "#2B4C8C", boxShadow: lit ? `0 0 22px ${hot}99` : "none",
          opacity: !hits && dimOthers ? 1 - 0.75 * dimOthers : 1}} />;
      })}
      <div style={{position: "absolute", top: -30, bottom: -30, left: `${band[0] * 100}%`, width: `max(10px, ${(band[1] - band[0]) * 100}%)`,
        background: "#5B9BFF", opacity: 0.55 * bandOn, boxShadow: `0 0 40px 10px #5B9BFF${bandOn > 0.5 ? "AA" : "00"}`}} />
      <div style={{position: "absolute", top: N * GAP + 14, left: 0, right: 0, height: 2, background: C.faint}} />
      <div style={{position: "absolute", top: N * GAP + 30, left: 0, fontFamily: MONO, fontSize: 26, color: C.dim}}>{axis}</div>
    </div>
  );
};

export const Prob2: React.FC<P> = (p) => {
  const f = useCurrentFrame();
  const bandAt = at(p, 0.35), zero = at(p, 0.75);
  const lit = interpolate(f, [bandAt + 8, bandAt + 8 + N * 2], [0, N], clamp);
  return (
    <AbsoluteFill>
      <div style={{position: "absolute", left: 140, top: 150}}><Kicker text="MIN / MAX CỦA TỪNG FILE · THỨ TỰ NGẪU NHIÊN" start={p.v0} /></div>
      <Bars mix={0} band={[0.0, 0.012]} bandOn={interpolate(f, [bandAt, bandAt + 8], [0, 1], clamp)} litUpTo={lit}
        axis="customer_id   0 ──────────────────────────────────────────────►  99.999" />
      <div style={{position: "absolute", right: 140, bottom: 100, textAlign: "right", opacity: interpolate(f, [zero, zero + 6], [0, 1], clamp)}}>
        <Glitch at={zero} len={16}>
          <div style={{fontFamily: MONO, fontWeight: 700, fontSize: 92, color: C.rose}}>0 file bị loại</div>
        </Glitch>
      </div>
    </AbsoluteFill>
  );
};

/* ---------- HYPOTHESIS ---------- */
export const Hypo: React.FC<P> = (p) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const strike = interpolate(f, [at(p, 0.5), at(p, 0.6)], [0, 100], clamp);
  const slam = at(p, 0.78);
  const s = spring({frame: f - slam, fps, config: {damping: 11, stiffness: 160}});
  return (
    <AbsoluteFill style={center}>
      <div style={{position: "absolute", left: 140, top: 150}}><Kicker text="GIẢ THUYẾT" start={p.v0} /></div>
      <Words text="Planning time tăng theo" start={at(p, 0.05)} size={64} color={C.dim} weight={400} />
      <Words text="số file × số commit" start={at(p, 0.2)} size={110} weight={800} style={{marginTop: 10}} />
      <div style={{position: "relative", marginTop: 26, opacity: interpolate(f, [at(p, 0.42), at(p, 0.48)], [0, 1], clamp)}}>
        <span style={{fontFamily: SANS, fontSize: 64, color: C.dim}}>không theo dung lượng</span>
        <div style={{position: "absolute", left: 0, top: "52%", height: 6, width: `${strike}%`, background: C.rose, boxShadow: `0 0 16px ${C.rose}`}} />
      </div>
      <div style={{position: "absolute", bottom: 110, right: 160, fontFamily: MONO, fontWeight: 700, fontSize: 200 * (0.6 + 0.4 * s),
        color: C.amber, opacity: s, textShadow: "0 0 70px #FFB54788"}}>≥ 3×</div>
      <Flash at={slam} strength={0.3} />
    </AbsoluteFill>
  );
};

/* ---------- METHOD ---------- */
export const Meth1: React.FC<P> = (p) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const merge = at(p, 0.45);
  const k = interpolate(f, [merge - 18, merge], [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
  const block = spring({frame: f - merge, fps, config: {damping: 12, stiffness: 140}});
  return (
    <AbsoluteFill style={center}>
      <div style={{position: "absolute", left: 140, top: 150}}><Kicker text="CÁCH 01 · CHECKPOINT" start={p.v0} /></div>
      {Array.from({length: 70}).map((_, i) => {
        const x0 = 160 + random(`cx${i}`) * 1600, y0 = 260 + random(`cy${i}`) * 600;
        const x = x0 + (960 - 60 - x0) * k, y = y0 + (560 - 40 - y0) * k;
        const o = interpolate(f, [p.v0 + i * 0.4, p.v0 + i * 0.4 + 6], [0, 1], clamp) * (1 - interpolate(f, [merge - 2, merge + 2], [0, 1], clamp));
        return <div key={i} style={{position: "absolute", left: x, top: y, width: 120, height: 80, borderRadius: 8,
          border: "1.5px solid #2E4270", background: "#0E1830", opacity: o, fontFamily: MONO, fontSize: 14, color: "#6F86B8",
          padding: 10, transform: `rotate(${(1 - k) * (random(`cr${i}`) - 0.5) * 30}deg)`}}>{String(i * 14 + 1).padStart(6, "0")}.json</div>;
      })}
      <div style={{opacity: block, transform: `scale(${0.4 + 0.6 * block})`, width: 520, height: 260, borderRadius: 20,
        background: "linear-gradient(135deg, #3D82E0, #1D3F86)", boxShadow: "0 0 120px 20px #3D82E077", ...center}}>
        <div style={{fontFamily: MONO, fontWeight: 700, fontSize: 40, color: "#fff"}}>checkpoint</div>
        <div style={{fontFamily: MONO, fontSize: 30, color: "#CFE0FF"}}>.parquet</div>
      </div>
      <div style={{position: "absolute", bottom: 120, display: "flex", gap: 40, alignItems: "center", fontFamily: SANS, fontSize: 44,
        opacity: interpolate(f, [merge + 10, merge + 22], [0, 1], clamp)}}>
        <span style={{color: C.dim}}>1.000 file JSON</span><span style={{color: C.amber}}>→</span><span style={{color: C.ink, fontWeight: 800}}>1 file</span>
      </div>
      <Flash at={merge} strength={0.6} />
    </AbsoluteFill>
  );
};

export const Meth2: React.FC<P> = (p) => {
  const f = useCurrentFrame();
  const sortAt = at(p, 0.2), bandAt = at(p, 0.55);
  const mix = interpolate(f, [sortAt, sortAt + 30], [0, 1], {...clamp, easing: Easing.inOut(Easing.cubic)});
  const bandOn = interpolate(f, [bandAt, bandAt + 8], [0, 1], clamp);
  return (
    <AbsoluteFill>
      <div style={{position: "absolute", left: 140, top: 150}}><Kicker text="CÁCH 02 · SẮP XẾP THEO CỘT LỌC" start={p.v0} /></div>
      <Bars mix={mix} band={[0.0, 0.012]} bandOn={bandOn} litUpTo={bandOn > 0.5 ? N : 0} dimOthers={bandOn}
        axis="customer_id   0 ──────────────────────────────────────────────►  99.999" />
      <div style={{position: "absolute", right: 140, bottom: 100, textAlign: "right", opacity: interpolate(f, [bandAt + 10, bandAt + 20], [0, 1], clamp)}}>
        <div style={{fontFamily: MONO, fontWeight: 700, fontSize: 92, color: C.amber}}>{p.m.fmt.sel_b} / {p.m.fmt.n_files}</div>
        <div style={{fontFamily: SANS, fontSize: 34, color: C.dim}}>file được chọn</div>
      </div>
      <FakeBadge on={p.m.fake} />
    </AbsoluteFill>
  );
};

/* ---------- EXPERIMENT ---------- */
export const Exp: React.FC<P> = (p) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const S = [["S1", 100, 5], ["S2", 1000, 50], ["S3", 10000, 500], ["S4", 20000, 1000]] as const;
  const lockAt = at(p, 0.62);
  const stamp = spring({frame: f - lockAt, fps, config: {damping: 10, stiffness: 180}});
  return (
    <AbsoluteFill>
      <div style={{position: "absolute", left: 140, top: 150}}><Kicker text="THÍ NGHIỆM · 1.000.000 DÒNG CỐ ĐỊNH" start={p.v0} /></div>
      <div style={{position: "absolute", left: 200, bottom: 240, display: "flex", gap: 60, alignItems: "flex-end"}}>
        {S.map(([s, n, c], i) => {
          const h = 90 + (Math.log10(n) - 2) / (Math.log10(20000) - 2) * 430;
          const g = spring({frame: f - at(p, 0.05) - i * 8, fps, config: {damping: 16}});
          const held = s === "S4";
          return (
            <div key={s} style={{display: "flex", flexDirection: "column", alignItems: "center", width: 240}}>
              <div style={{fontFamily: MONO, fontSize: 40, fontWeight: 700, color: held ? C.amber : C.ink, opacity: g}}>{vn(n, 0)}</div>
              <div style={{fontFamily: SANS, fontSize: 24, color: C.dim, opacity: g, marginBottom: 14}}>file · {vn(c, 0)} commit</div>
              <div style={{position: "relative", width: 170, height: h * g, borderRadius: "10px 10px 0 0",
                background: held ? "linear-gradient(#FFB547, #8A5A12)" : "linear-gradient(#3D82E0, #16305F)",
                boxShadow: held ? "0 0 60px #FFB54755" : "none"}}>
                {held && <svg width="90" height="110" viewBox="0 0 90 110" style={{position: "absolute", left: 40, top: 40, opacity: stamp}}>
                  <path d="M20 50 V32 a25 25 0 0 1 50 0 V50" stroke="#1A1206" strokeWidth="10" fill="none" />
                  <rect x="8" y="48" width="74" height="56" rx="10" fill="#1A1206" />
                </svg>}
              </div>
              <div style={{fontFamily: MONO, fontSize: 38, color: C.ink, marginTop: 16}}>{s}</div>
            </div>
          );
        })}
      </div>
      <div style={{position: "absolute", right: 90, top: 420, transform: `rotate(-8deg) scale(${2.2 - 1.2 * stamp})`, opacity: stamp,
        border: `6px solid ${C.amber}`, color: C.amber, fontFamily: MONO, fontWeight: 700, fontSize: 64, padding: "10px 30px", letterSpacing: 6}}>
        HELD-OUT</div>
      <div style={{position: "absolute", left: 200, bottom: 130, display: "flex", gap: 24}}>
        {["10 lần / tổ hợp", "cold & warm", "rows == expected_rows"].map((t, i) => (
          <div key={t} style={{fontFamily: MONO, fontSize: 28, color: C.ink, border: `1.5px solid ${C.faint}`, borderRadius: 999,
            padding: "10px 26px", opacity: interpolate(f, [at(p, 0.35) + i * 6, at(p, 0.35) + i * 6 + 10], [0, 1], clamp)}}>{t}</div>
        ))}
      </div>
      <Flash at={lockAt} strength={0.25} />
    </AbsoluteFill>
  );
};

/* ---------- RESULTS ---------- */
export const Res: React.FC<P> = (p) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  const W = 760, H = 540, X0 = 140, Y0 = 300, PADL = 120;
  const all = Object.values(p.m.chart).flat();
  const [xMin, xMax] = [Math.log10(Math.min(...all.map((d) => d[0]))), Math.log10(Math.max(...all.map((d) => d[0])))];
  const [yMin, yMax] = [Math.log10(Math.min(...all.map((d) => d[1]))) - 0.2, Math.log10(Math.max(...all.map((d) => d[1]))) + 0.2];
  const sx = (x: number) => ((Math.log10(x) - xMin) / (xMax - xMin)) * W;
  const sy = (y: number) => H - ((Math.log10(y) - yMin) / (yMax - yMin)) * H;
  const series = [["baseline", C.sBase], ["opt_a_checkpoint", C.sA], ["opt_b_sorted", C.sB]] as const;
  const draw = interpolate(f, [p.v0, at(p, 0.3)], [0, 1], {...clamp, easing: Easing.inOut(Easing.cubic)});
  const n1 = at(p, 0.42), n2 = at(p, 0.78);
  const s1 = spring({frame: f - n1, fps, config: {damping: 12, stiffness: 170}});
  const s2 = spring({frame: f - n2, fps, config: {damping: 12, stiffness: 170}});
  const names: Record<number, string> = {100: "S1", 1000: "S2", 10000: "S3", 20000: "S4"};
  return (
    <AbsoluteFill>
      <div style={{position: "absolute", left: 140, top: 150}}><Kicker text="KẾT QUẢ · p95 t_plan · q_main · cold" start={p.v0} /></div>
      <svg width={PADL + W + 250} height={H + 80} style={{position: "absolute", left: X0, top: Y0}}><g transform={`translate(${PADL},0)`}>
        {[1e-3, 1e-2, 1e-1, 1].filter((y) => Math.log10(y) >= yMin && Math.log10(y) <= yMax).map((y) => (
          <g key={y}><line x1={0} x2={W} y1={sy(y)} y2={sy(y)} stroke="#1C2A48" strokeWidth={1.5} />
            <text x={-16} y={sy(y) + 8} fill={C.dim} fontFamily={MONO} fontSize={22} textAnchor="end">{vn(y, y < 0.01 ? 3 : y < 0.1 ? 2 : 1)} s</text></g>
        ))}
        {series.map(([v, col]) => {
          const pts = p.m.chart[v] || [];
          const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${sx(x)},${sy(y)}`).join(" ");
          const len = 2000;
          return (
            <g key={v}>
              <path d={d} stroke={col} strokeWidth={4} fill="none" strokeDasharray={len} strokeDashoffset={len * (1 - draw)}
                style={{filter: `drop-shadow(0 0 10px ${col})`}} />
              {pts.map(([x, y], i) => <circle key={i} cx={sx(x)} cy={sy(y)} r={8} fill={col} stroke={C.bg} strokeWidth={3}
                opacity={draw > (i + 0.5) / pts.length ? 1 : 0} />)}
              {pts.length > 0 && <text x={sx(pts[pts.length - 1][0]) + 18} y={sy(pts[pts.length - 1][1]) + 8} fill={C.ink}
                fontFamily={MONO} fontSize={24} opacity={draw > 0.95 ? 1 : 0}>{v}</text>}
            </g>
          );
        })}
        {Object.entries(names).map(([x, s]) => <text key={x} x={sx(+x)} y={H + 50} fill={C.dim} fontFamily={MONO} fontSize={26} textAnchor="middle">{s}</text>)}
      </g></svg>
      <div style={{position: "absolute", left: X0 + PADL, top: Y0 + H + 80, fontFamily: SANS, fontSize: 24, color: C.dim}}>
        trục log · thấp hơn là nhanh hơn</div>
      <div style={{position: "absolute", right: 130, top: 300, display: "flex", flexDirection: "column", gap: 60, alignItems: "flex-end"}}>
        {[[s1, p.m.sa, "checkpoint", C.sA], [s2, p.m.sb, "checkpoint + sort", C.sB]].map(([s, v, l, col], i) => (
          <div key={i} style={{textAlign: "right", opacity: s as number, transform: `scale(${1.6 - 0.6 * (s as number)})`, transformOrigin: "right center"}}>
            <div style={{fontFamily: MONO, fontWeight: 700, fontSize: 170, color: C.ink, lineHeight: 1, textShadow: `0 0 60px ${col}`}}>
              {vn(v as number, 1)}×</div>
            <div style={{display: "flex", gap: 14, justifyContent: "flex-end", alignItems: "center", fontFamily: SANS, fontSize: 34, color: C.dim}}>
              <div style={{width: 28, height: 6, borderRadius: 3, background: col as string}} />{l as string}</div>
          </div>
        ))}
      </div>
      <Flash at={n1} strength={0.25} /><Flash at={n2} strength={0.4} />
      <FakeBadge on={p.m.fake} />
    </AbsoluteFill>
  );
};

/* ---------- FAILURE ---------- */
export const Fail: React.FC<P> = (p) => {
  const f = useCurrentFrame();
  const bandAt = at(p, 0.35), hit = at(p, 0.72);
  const lit = interpolate(f, [bandAt + 6, bandAt + 6 + N * 1.5], [0, N], clamp);
  return (
    <AbsoluteFill>
      <div style={{position: "absolute", left: 140, top: 150}}><Kicker text="FAILURE CASE · q_alt · CỘT amount KHÔNG ĐƯỢC SẮP XẾP" start={p.v0} color={C.rose} /></div>
      <Bars mix={0} band={[0.1, 0.103]} bandOn={interpolate(f, [bandAt, bandAt + 8], [0, 1], clamp)} litUpTo={lit} hot={C.rose}
        axis="amount   0 ────────────────────────────────────────────────►  1.000" />
      <div style={{position: "absolute", right: 140, bottom: 100, textAlign: "right", opacity: interpolate(f, [hit, hit + 6], [0, 1], clamp)}}>
        <Glitch at={hit} len={14}>
          <div style={{fontFamily: MONO, fontWeight: 700, fontSize: 92, color: C.rose}}>{p.m.fmt.alt_sel} / {p.m.fmt.n_files}</div>
        </Glitch>
        <div style={{fontFamily: SANS, fontSize: 34, color: C.dim}}>file vẫn phải mở</div>
      </div>
      <FakeBadge on={p.m.fake} />
    </AbsoluteFill>
  );
};

/* ---------- OUTRO ---------- */
export const Outro: React.FC<P> = (p) => {
  const f = useCurrentFrame();
  const t2 = at(p, 0.6);
  const out = interpolate(f, [p.dur - 30, p.dur], [1, 0], clamp);
  return (
    <AbsoluteFill style={{...center, opacity: out}}>
      <div style={{opacity: interpolate(f, [t2 - 8, t2], [1, 0.25], clamp)}}>
        <Words text="Metadata cũng là dữ liệu." start={p.v0} size={92} weight={800} />
        <Words text="và nó cần được chăm sóc." start={at(p, 0.25)} size={56} color={C.amber} weight={400} style={{marginTop: 16}} />
      </div>
      <div style={{position: "absolute", bottom: 170, ...center, opacity: interpolate(f, [t2, t2 + 14], [0, 1], clamp)}}>
        <Sweep at={t2 + 6} style={{fontFamily: SANS, fontWeight: 800, fontSize: 80, letterSpacing: 24}}>NHÓM 7</Sweep>
        <div style={{fontFamily: MONO, fontSize: 30, color: C.dim, letterSpacing: 6, marginTop: 14}}>Phong · Hùng · Phú · Đạt · Vinh</div>
      </div>
      <Flash at={t2} strength={0.3} />
    </AbsoluteFill>
  );
};
