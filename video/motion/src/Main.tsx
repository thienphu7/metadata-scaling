import React from "react";
import {AbsoluteFill, Audio, Sequence, staticFile, interpolate} from "remotion";
import data from "./data.json";
import {Backdrop, Finish, Shot, C} from "./fx";
import * as S from "./scenes";

export const FPS = 30;
type Def = {comp: React.FC<S.P>; min: number; lead: number; tail?: number; cut?: boolean; tint?: string};
const DEFS: Record<string, Def> = {
  hook_1: {comp: S.Hook1, min: 70, lead: 8, cut: true},
  hook_2: {comp: S.Hook2, min: 70, lead: 4, cut: true},
  hook_3: {comp: S.Hook3, min: 140, lead: 6, cut: true, tint: C.amber},
  title: {comp: S.Title, min: 170, lead: 16, cut: true},
  prob_1: {comp: S.Prob1, min: 200, lead: 16},
  prob_2: {comp: S.Prob2, min: 190, lead: 16, tint: C.rose},
  hypo: {comp: S.Hypo, min: 200, lead: 16, tint: C.amber},
  meth_1: {comp: S.Meth1, min: 170, lead: 16},
  meth_2: {comp: S.Meth2, min: 200, lead: 16},
  exp: {comp: S.Exp, min: 230, lead: 16},
  res: {comp: S.Res, min: 230, lead: 20, tint: C.amber},
  fail: {comp: S.Fail, min: 200, lead: 16, tint: C.rose},
  outro: {comp: S.Outro, min: 200, lead: 16, tail: 75},
};
const OVERLAP = 12;

export const timeline = () => {
  let t = 0;
  return data.scenes.map((s, i) => {
    const d = DEFS[s.id];
    const vd = Math.ceil(s.dur * FPS);
    const dur = Math.max(d.min, d.lead + vd + (d.tail ?? 24));
    const start = i === 0 ? 0 : t - (d.cut ? 0 : OVERLAP);
    t = start + dur;
    return {...s, ...d, vd, dur, start, v0: d.lead};
  });
};
export const totalFrames = () => {const tl = timeline(); const l = tl[tl.length - 1]; return l.start + l.dur;};

const Sfx: React.FC<{name: string; at: number; vol?: number}> = ({name, at, vol = 1}) =>
  <Sequence from={Math.max(0, Math.round(at))} durationInFrames={150} layout="none"><Audio src={staticFile(`sfx/${name}.wav`)} volume={vol} /></Sequence>;

export const Main: React.FC = () => {
  const tl = timeline();
  const total = totalFrames();
  const g = Object.fromEntries(tl.map((s) => [s.id, s]));
  const A = (id: string, x: number) => g[id].start + g[id].v0 + x * g[id].vd;   // same timing as scenes' at()
  const speaking = (f: number) => tl.some((s) => f >= s.start + s.v0 - 6 && f <= s.start + s.v0 + s.vd + 6);
  const m = data.metrics as unknown as S.M;

  const cues: [string, number, number?][] = [
    ["boom", A("hook_1", 0) + 24, 0.9],
    ["shimmer", g.hook_2.start, 0.6], ["whoosh", g.hook_2.start - 4, 0.6],
    ...Array.from({length: Math.max(0, Math.floor((A("hook_3", 0.35) - A("hook_3", 0)) / 5))},
      (_, i) => ["tick", A("hook_3", 0) + i * 5, 0.5] as [string, number, number]),
    ["glitch", A("hook_3", 0.68), 0.7],
    ["riser", A("title", 0.3) - 90, 0.8], ["impact", A("title", 0.3), 1], ["boom", A("title", 0.3), 0.8], ["shimmer", A("title", 0.3) + 24, 0.5],
    ...Array.from({length: 9}, (_, i) => ["click", A("prob_1", 0) + i * 6, 0.35] as [string, number, number]),
    ["whoosh", A("prob_1", 0.25), 0.4], ["glitch", A("prob_2", 0.75), 0.7],
    ["impact", A("hypo", 0.78), 0.9],
    ["merge", A("meth_1", 0.45) - 18, 0.8], ["impact", A("meth_1", 0.45), 0.9],
    ["whoosh", A("meth_2", 0.2), 0.6], ["shimmer", A("meth_2", 0.55), 0.6],
    ["impact", A("exp", 0.62), 0.8],
    ["riser", A("res", 0.42) - 90, 0.7], ["impact", A("res", 0.42), 0.9], ["impact", A("res", 0.78), 1], ["boom", A("res", 0.78), 0.6],
    ["glitch", A("fail", 0.72), 0.7],
    ["boom", A("outro", 0.6), 0.8], ["shimmer", A("outro", 0.6) + 6, 0.5],
    ...tl.filter((s) => !s.cut).map((s) => ["whoosh", s.start - 6, 0.55] as [string, number, number]),
  ];

  return (
    <AbsoluteFill style={{background: "#000"}}>
      {tl.map((s) => (
        <Sequence key={s.id} from={s.start} durationInFrames={s.dur}>
          <Backdrop tint={s.tint} />
          <Shot dur={s.dur} cut={s.cut}>
            <s.comp dur={s.dur} v0={s.v0} vd={s.vd} m={m} />
          </Shot>
        </Sequence>
      ))}
      <Finish />

      {/* voice */}
      {tl.map((s) => (
        <Sequence key={`v-${s.id}`} from={s.start + s.v0} durationInFrames={s.vd + 10} layout="none">
          <Audio src={staticFile(s.voice)} volume={1} />
        </Sequence>
      ))}
      {/* music: drone under everything (ducked under the voice), heartbeat pulse in hook and results */}
      <Audio src={staticFile("sfx/drone.wav")} volume={(f) =>
        interpolate(f, [0, 60, total - 70, total], [0, 1, 1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"}) * (speaking(f) ? 0.35 : 0.7)} />
      <Sequence from={0} durationInFrames={g.title.start + 20} layout="none">
        <Audio src={staticFile("sfx/pulse.wav")} volume={(f) => interpolate(f, [0, 20, g.title.start - 10, g.title.start + 20], [0, 0.55, 0.55, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})} />
      </Sequence>
      <Sequence from={g.res.start} durationInFrames={g.res.dur} layout="none">
        <Audio src={staticFile("sfx/pulse.wav")} volume={(f) => interpolate(f, [0, 20, g.res.dur - 30, g.res.dur], [0, 0.45, 0.45, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})} />
      </Sequence>
      {cues.map(([n, at, v], i) => <Sfx key={i} name={n} at={at} vol={v} />)}
    </AbsoluteFill>
  );
};
