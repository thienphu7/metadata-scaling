import React from "react";
import {AbsoluteFill, interpolate, random, spring, useCurrentFrame, useVideoConfig, Easing} from "remotion";
import {loadFont as loadSans} from "@remotion/google-fonts/BeVietnamPro";
import {loadFont as loadMono} from "@remotion/google-fonts/JetBrainsMono";

export const SANS = loadSans("normal", {weights: ["400", "600", "800"], subsets: ["vietnamese", "latin"]}).fontFamily;
export const MONO = loadMono("normal", {weights: ["400", "700"], subsets: ["vietnamese", "latin"]}).fontFamily;

export const C = {
  bg: "#070B14", ink: "#F2EFE8", dim: "#9AA6BF", faint: "#3A4560",
  amber: "#FFB547", blue: "#5B9BFF", rose: "#FF6F91",
  // chart series, validated for the dark surface (#0B1020)
  sBase: "#D9668A", sA: "#3D82E0", sB: "#BE7F28",
};

export const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;

/** Background: deep gradient + drifting light leaks + dust. */
export const Backdrop: React.FC<{tint?: string}> = ({tint = C.blue}) => {
  const f = useCurrentFrame();
  const x = 50 + 18 * Math.sin(f / 140), y = 45 + 12 * Math.cos(f / 170);
  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse at ${x}% ${y}%, #13203A 0%, ${C.bg} 55%, #020306 100%)`}}>
      <AbsoluteFill style={{background: `radial-gradient(circle at ${100 - x}% ${100 - y}%, ${tint}22 0%, transparent 40%)`, mixBlendMode: "screen"}} />
      {Array.from({length: 46}).map((_, i) => {
        const px = random(`dx${i}`) * 1920, py = random(`dy${i}`) * 1080;
        const sp = 0.15 + random(`ds${i}`) * 0.5, sz = 2 + random(`dz${i}`) * 5;
        const yy = (py - f * sp * 1.6 + 1200) % 1200 - 60;
        return <div key={i} style={{position: "absolute", left: px + 20 * Math.sin((f + i * 30) / 60), top: yy,
          width: sz, height: sz, borderRadius: sz, background: i % 5 === 0 ? C.amber : "#B8C7E6",
          opacity: 0.08 + 0.18 * random(`do${i}`), filter: `blur(${sz > 5 ? 2 : 0.5}px)`}} />;
      })}
    </AbsoluteFill>
  );
};

/** Film grain + vignette + letterbox bars, on top of everything. */
export const Finish: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{pointerEvents: "none"}}>
      <AbsoluteFill style={{background: "radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.78) 100%)"}} />
      <svg width="1920" height="1080" style={{position: "absolute", opacity: 0.11, mixBlendMode: "overlay"}}>
        <filter id="g"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={f % 24} /></filter>
        <rect width="1920" height="1080" filter="url(#g)" />
      </svg>
      <div style={{position: "absolute", left: 0, right: 0, top: 0, height: 64, background: "#000"}} />
      <div style={{position: "absolute", left: 0, right: 0, bottom: 0, height: 64, background: "#000"}} />
    </AbsoluteFill>
  );
};

/** Scene envelope: blur/scale in, slow camera push, blur/scale out. */
export const Shot: React.FC<{dur: number; children: React.ReactNode; push?: number; cut?: boolean}> =
  ({dur, children, push = 0.04, cut = false}) => {
  const f = useCurrentFrame();
  const inn = cut ? 1 : interpolate(f, [0, 14], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const out = interpolate(f, [dur - 12, dur], [1, 0], {...clamp, easing: Easing.in(Easing.cubic)});
  const s = (1.07 - 0.07 * inn) * (1 + push * f / dur) * (0.97 + 0.03 * out);
  return (
    <AbsoluteFill style={{opacity: Math.min(inn, out), transform: `scale(${s})`,
      filter: `blur(${(1 - inn) * 14 + (1 - out) * 12}px)`}}>{children}</AbsoluteFill>
  );
};

/** White flash peaking at frame `at`. */
export const Flash: React.FC<{at: number; strength?: number}> = ({at, strength = 0.55}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [at - 2, at, at + 10], [0, strength, 0], clamp);
  return <AbsoluteFill style={{background: "#FFF6E5", opacity: o, mixBlendMode: "screen"}} />;
};

/** Words rise in with a stagger. */
export const Words: React.FC<{text: string; start?: number; size: number; color?: string; weight?: number;
  font?: string; stagger?: number; align?: "center" | "left"; style?: React.CSSProperties}> =
  ({text, start = 0, size, color = C.ink, weight = 600, font = SANS, stagger = 3, align = "center", style}) => {
  const f = useCurrentFrame(); const {fps} = useVideoConfig();
  return (
    <div style={{fontFamily: font, fontSize: size, fontWeight: weight, color, lineHeight: 1.15,
      textAlign: align, display: "flex", flexWrap: "wrap", justifyContent: align === "center" ? "center" : "flex-start",
      gap: `0 ${size * 0.28}px`, ...style}}>
      {text.split(" ").map((w, i) => {
        const p = spring({frame: f - start - i * stagger, fps, config: {damping: 18, stiffness: 120}});
        return <span key={i} style={{display: "inline-block", opacity: p, transform: `translateY(${(1 - p) * size * 0.6}px)`,
          filter: `blur(${(1 - p) * 10}px)`}}>{w}</span>;
      })}
    </div>
  );
};

/** Text with a light sweep passing through it. */
export const Sweep: React.FC<{children: React.ReactNode; at: number; style?: React.CSSProperties}> = ({children, at, style}) => {
  const f = useCurrentFrame();
  const p = interpolate(f, [at, at + 40], [-30, 130], clamp);
  return <div style={{...style, backgroundImage: `linear-gradient(100deg, ${C.ink} ${p - 12}%, #FFFFFF ${p}%, ${C.ink} ${p + 12}%)`,
    WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent"}}>{children}</div>;
};

/** RGB-split glitch around frame `at`. */
export const Glitch: React.FC<{children: React.ReactNode; at: number; len?: number; style?: React.CSSProperties}> =
  ({children, at, len = 12, style}) => {
  const f = useCurrentFrame();
  const on = f >= at && f < at + len;
  const j = on ? (random(`g${f}`) - 0.5) * 22 : 0;
  const k = on ? (random(`h${f}`) - 0.5) * 8 : 0;
  return (
    <div style={{position: "relative", ...style}}>
      {on && <div style={{position: "absolute", inset: 0, color: "#FF2E63", transform: `translate(${j}px, ${k}px)`, mixBlendMode: "screen", opacity: 0.8}}>{children}</div>}
      {on && <div style={{position: "absolute", inset: 0, color: "#08F7FE", transform: `translate(${-j}px, ${-k}px)`, mixBlendMode: "screen", opacity: 0.8}}>{children}</div>}
      <div style={{transform: `translateX(${j * 0.3}px)`}}>{children}</div>
    </div>
  );
};

export const vn = (x: number, nd: number) =>
  x.toLocaleString("de-DE", {minimumFractionDigits: nd, maximumFractionDigits: nd});

export const Counter: React.FC<{from?: number; to: number; start: number; len: number; nd?: number; suffix?: string;
  style?: React.CSSProperties}> = ({from = 0, to, start, len, nd = 0, suffix = "", style}) => {
  const f = useCurrentFrame();
  const v = interpolate(f, [start, start + len], [from, to], {...clamp, easing: Easing.out(Easing.exp)});
  return <span style={{fontVariantNumeric: "tabular-nums", ...style}}>{vn(v, nd)}{suffix}</span>;
};

export const Kicker: React.FC<{text: string; start?: number; color?: string}> = ({text, start = 0, color = C.amber}) => {
  const f = useCurrentFrame();
  const w = interpolate(f, [start, start + 20], [0, 120], {...clamp, easing: Easing.out(Easing.cubic)});
  return (
    <div style={{display: "flex", alignItems: "center", gap: 20, fontFamily: MONO, fontSize: 26, letterSpacing: 6,
      color, opacity: interpolate(f, [start, start + 12], [0, 1], clamp)}}>
      <div style={{width: w, height: 2, background: color}} />{text}
    </div>
  );
};

export const FakeBadge: React.FC<{on: boolean}> = ({on}) => on ? (
  <div style={{position: "absolute", top: 92, right: 80, fontFamily: SANS, fontWeight: 800, fontSize: 24, letterSpacing: 2,
    color: "#FFF", background: "#C0392B", padding: "10px 22px", borderRadius: 999, boxShadow: "0 0 30px #C0392B88"}}>
    SỐ LIỆU GIẢ · CHỈ ĐỂ DỰNG THỬ</div>
) : null;
