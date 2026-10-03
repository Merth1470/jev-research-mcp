import "@fontsource/anton";
import "@fontsource/work-sans/400.css";
import "@fontsource/work-sans/600.css";
import "@fontsource/work-sans/700.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/700.css";
import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// ---------- Proof-bench world tokens ----------
const PAPER = "#F6F1E7";
const BENCH = "#E9E0C8";
const SHEET = "#FBF7EC";
const INK = "#14120F";
const INK_SOFT = "#4A463C";
const ASH = "#8A867E";
const RED = "#C8341F";
const BLUE = "#2440A0";
const TAG = "#EFE0BC";
const STRING = "#6B5B3E";

const DISPLAY = "'Anton', 'Arial Narrow', sans-serif";
const BODY = "'Work Sans', 'Segoe UI', sans-serif";
const MONO = "'JetBrains Mono', 'Consolas', monospace";

const SHEET_SHADOW = "0 18px 42px rgba(20,18,15,0.22)";
const SLIP_SHADOW = "0 10px 24px rgba(20,18,15,0.18)";

function useLocal(start: number) {
  const frame = useCurrentFrame();
  return Math.max(0, frame - start);
}

// ---------- Chrome: registration, rules, slugs ----------
function CropMarks() {
  const c: React.CSSProperties = {
    position: "absolute",
    width: 46,
    height: 46,
    borderColor: BLUE,
    borderStyle: "solid",
    opacity: 0.85,
  };
  return (
    <>
      <div style={{ ...c, top: 26, left: 30, borderWidth: "2px 0 0 2px" }} />
      <div style={{ ...c, top: 26, right: 30, borderWidth: "2px 2px 0 0" }} />
      <div style={{ ...c, bottom: 26, left: 30, borderWidth: "0 0 2px 2px" }} />
      <div style={{ ...c, bottom: 26, right: 30, borderWidth: "0 2px 2px 0" }} />
    </>
  );
}

function TopRule({ frame }: { frame: number }) {
  const progress = Math.min(1, frame / 1800);
  return (
    <div style={{ position: "absolute", top: 0, left: 0, right: 0, padding: "30px 72px 0 72px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 24, letterSpacing: 2.5, color: INK }}>
          JEV RESEARCH <span style={{ color: INK_SOFT, fontWeight: 400 }}>— PROOF · 60s</span>
        </div>
        <div style={{ fontFamily: MONO, fontSize: 24, color: INK, fontVariantNumeric: "tabular-nums" }}>
          {String(Math.floor(frame / 30)).padStart(2, "0")}s / 60s
        </div>
      </div>
      <div style={{ height: 3, background: "rgba(20,18,15,0.16)", marginTop: 12 }}>
        <div style={{ width: `${progress * 100}%`, height: "100%", background: RED }} />
      </div>
    </div>
  );
}

function BottomSlug() {
  return (
    <div
      style={{
        position: "absolute",
        bottom: 30,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "space-between",
        padding: "0 72px",
        fontFamily: MONO,
        fontSize: 19,
        color: INK_SOFT,
      }}
    >
      <span>Set in Anton · Work Sans · JetBrains Mono — paper daylight</span>
      <span>Figures illustrative — SYNTHETIC until bench run</span>
    </div>
  );
}

// ---------- Press furniture ----------
function Tag({
  children,
  rotate = -4,
  style,
}: {
  children: React.ReactNode;
  rotate?: number;
  style?: React.CSSProperties;
}) {
  return (
    <div style={{ position: "relative", display: "inline-block", transform: `rotate(${rotate}deg)`, ...style }}>
      <div
        style={{
          width: 2,
          height: 44,
          background: STRING,
          margin: "0 auto",
          transform: "rotate(12deg)",
          transformOrigin: "bottom center",
        }}
      />
      <div
        style={{
          background: TAG,
          border: `1.5px solid ${INK}`,
          borderRadius: 3,
          padding: "10px 18px 10px 30px",
          fontFamily: MONO,
          fontSize: 22,
          fontWeight: 700,
          color: INK,
          boxShadow: SLIP_SHADOW,
          position: "relative",
          whiteSpace: "nowrap",
        }}
      >
        <span
          style={{
            position: "absolute",
            left: 10,
            top: "50%",
            width: 10,
            height: 10,
            borderRadius: 999,
            background: PAPER,
            border: `1.5px solid ${INK}`,
            transform: "translateY(-50%)",
          }}
        />
        {children}
      </div>
    </div>
  );
}

function Stamp({
  label,
  progress,
  rotate = -7,
  color = RED,
}: {
  label: string;
  progress: number;
  rotate?: number;
  color?: string;
}) {
  const p = spring({
    frame: Math.max(0, progress * 30),
    fps: 30,
    config: { stiffness: 260, damping: 14 },
  });
  const s = interpolate(p, [0, 1], [1.7, 1]);
  return (
    <div
      style={{
        display: "inline-block",
        opacity: p,
        transform: `rotate(${rotate}deg) scale(${s})`,
        border: `4px solid ${color}`,
        borderRadius: 4,
        color,
        fontFamily: DISPLAY,
        fontSize: 54,
        letterSpacing: 3,
        padding: "8px 26px",
        background: "rgba(251,247,236,0.72)",
      }}
    >
      {label}
    </div>
  );
}

function GreaseEllipse({
  progress,
  width,
  height,
  stroke = 8,
}: {
  progress: number;
  width: number;
  height: number;
  stroke?: number;
}) {
  const rx = width / 2;
  const ry = height / 2;
  const circ = 2 * Math.PI * Math.sqrt((rx * rx + ry * ry) / 2);
  const draw = interpolate(progress, [0, 1], [circ, 0]);
  return (
    <svg width={width + stroke * 3} height={height + stroke * 3} style={{ overflow: "visible" }}>
      <ellipse
        cx={(width + stroke * 3) / 2}
        cy={(height + stroke * 3) / 2}
        rx={rx}
        ry={ry}
        fill="none"
        stroke={RED}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={draw}
        transform={`rotate(-4 ${(width + stroke * 3) / 2} ${(height + stroke * 3) / 2})`}
      />
      <ellipse
        cx={(width + stroke * 3) / 2}
        cy={(height + stroke * 3) / 2}
        rx={rx - 14}
        ry={ry + 10}
        fill="none"
        stroke={RED}
        strokeWidth={stroke - 3}
        strokeLinecap="round"
        opacity={0.55}
        strokeDasharray={circ}
        strokeDashoffset={interpolate(progress, [0.25, 1], [circ, 0])}
      />
    </svg>
  );
}

function StrikeThrough({ progress, width }: { progress: number; width: number }) {
  const w = interpolate(progress, [0, 1], [0, width]);
  return (
    <svg width={width} height={14} style={{ display: "block", overflow: "visible" }}>
      <line x1={0} y1={8} x2={w} y2={5} stroke={RED} strokeWidth={7} strokeLinecap="round" />
    </svg>
  );
}

function SceneTitle({ title, sub }: { title: string; sub: string }) {
  return (
    <div style={{ textAlign: "left" }}>
      <div
        style={{
          fontFamily: DISPLAY,
          fontSize: 84,
          lineHeight: 0.98,
          letterSpacing: -0.5,
          color: INK,
        }}
      >
        {title}
      </div>
      <div style={{ fontFamily: BODY, fontSize: 30, color: INK_SOFT, marginTop: 14, maxWidth: 1180 }}>{sub}</div>
    </div>
  );
}

// ---------- Scene 1: Hook ----------
function SceneHook() {
  const local = useLocal(0);
  const { fps } = useVideoConfig();
  const rise = spring({ frame: local, fps, config: { stiffness: 70, damping: 17 } });
  const circle = interpolate(local, [28, 95], [0, 1], { extrapolateRight: "clamp" });
  const clip = interpolate(local, [4, 40], [100, 0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: BENCH, justifyContent: "center", alignItems: "center" }}>
      <div
        style={{
          width: 1560,
          background: SHEET,
          boxShadow: SHEET_SHADOW,
          border: `1px solid rgba(20,18,15,0.25)`,
          padding: "72px 84px 64px 84px",
          opacity: rise,
          transform: `translateY(${interpolate(rise, [0, 1], [60, 0])}px)`,
          position: "relative",
        }}
      >
        <div style={{ position: "absolute", top: -58, right: 40 }}>
          <Tag>EXHIBIT A — 20 IN / 6 KEPT</Tag>
        </div>
        <div
          style={{
            fontFamily: DISPLAY,
            fontSize: 148,
            lineHeight: 0.94,
            letterSpacing: -1,
            color: INK,
            clipPath: `inset(0 0 ${clip}% 0)`,
          }}
        >
          STOP FETCHING.
          <br />
          START PROOFING.
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 48, marginTop: 44 }}>
          <div style={{ position: "relative", padding: 18 }}>
            <div style={{ position: "absolute", inset: -34, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <GreaseEllipse progress={circle} width={460} height={150} />
            </div>
            <div
              style={{
                fontFamily: MONO,
                fontSize: 54,
                fontWeight: 700,
                color: INK,
                background: PAPER,
                border: `2px solid ${INK}`,
                padding: "18px 34px",
              }}
            >
              research(query)
            </div>
          </div>
          <div style={{ fontFamily: BODY, fontSize: 31, color: INK_SOFT, lineHeight: 1.4, maxWidth: 640 }}>
            One tool proofs the web twice —<br />
            <span style={{ color: INK, fontWeight: 700 }}>before anything is fetched.</span>
            <br />
            <span style={{ fontFamily: MONO, fontSize: 26 }}>What is cut is never downloaded.</span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------- Scene 2: The cut ----------
const SLIPS = [
  "install guide",
  "rate-limit recipe",
  "forum guess",
  "ads + banner",
  "stale mirror",
  "seo farm",
  "changelog",
  "official docs",
  "source thread",
  "cookbook",
];

function SceneCut() {
  const local = useLocal(150);
  const kept = new Set([1, 6, 7, 8, 3, 0]);
  return (
    <AbsoluteFill style={{ background: BENCH, padding: "132px 72px 90px 72px" }}>
      <SceneTitle
        title="Fourteen never leave the bench."
        sub="Twenty slips pinned. The reader circles six and cuts the rest — cut slips are never fetched, never parsed, never billed."
      />
      <div style={{ display: "flex", gap: 18, marginTop: 40 }}>
        {SLIPS.map((t, i) => {
          const isKept = kept.has(i);
          const strikeStart = 30 + i * 11;
          const sp = interpolate(local, [strikeStart, strikeStart + 12], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const fade = isKept ? 1 : interpolate(local, [strikeStart + 6, strikeStart + 26], [1, 0.42], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const drop = isKept ? 0 : interpolate(local, [strikeStart + 6, strikeStart + 30], [0, 20], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <div
              key={t}
              style={{
                flex: 1,
                background: isKept ? SHEET : PAPER,
                border: isKept ? `2.5px solid ${RED}` : `1.5px solid rgba(20,18,15,0.4)`,
                borderRadius: 3,
                padding: "18px 10px 14px 10px",
                boxShadow: SLIP_SHADOW,
                opacity: fade,
                transform: `translateY(${drop}px) rotate(${(i % 3) - 1}deg)`,
              }}
            >
              <div style={{ fontFamily: MONO, fontSize: 19, fontWeight: 700, color: INK, minHeight: 56 }}>{t}</div>
              <div style={{ marginTop: 8, minHeight: 16 }}>
                {!isKept && sp > 0 ? <StrikeThrough progress={sp} width={110} /> : null}
                {isKept ? (
                  <div
                    style={{
                      border: `3px solid ${RED}`,
                      borderRadius: 999,
                      width: 64,
                      height: 30,
                      transform: "rotate(-8deg)",
                    }}
                  />
                ) : null}
              </div>
              <div style={{ fontFamily: MONO, fontSize: 17, color: ASH, marginTop: 8 }}>×2 slips</div>
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", gap: 40, marginTop: 36, alignItems: "center" }}>
        <div style={{ fontFamily: MONO, fontSize: 25, color: INK }}>
          relevant <span style={{ fontWeight: 700 }}>0.93</span>
          <span style={{ color: ASH }}> · </span>useful <span style={{ fontWeight: 700 }}>0.88</span>
          <span style={{ color: ASH, fontSize: 21 }}> — every keep carries its figures on the pin</span>
        </div>
        <div style={{ marginLeft: "auto", opacity: interpolate(local, [150, 180], [0, 1], { extrapolateLeft: "clamp" }) }}>
          <Stamp label="14 CUT — NEVER FETCHED" progress={interpolate(local, [150, 180], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} rotate={-3} />
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------- Scene 3: One tool ----------
function SceneTool() {
  const local = useLocal(360);
  const { fps } = useVideoConfig();
  const s = spring({ frame: local, fps, config: { stiffness: 80, damping: 17 } });
  const stampP = interpolate(local, [110, 140], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const tickets = [
    { t: "LOCAL — runs on your machine", d: "compute, network and keys are yours", r: -1.4, w: 460 },
    { t: "PRIVATE — BYOK, no telemetry", d: "nothing returns to the author", r: 1, w: 500 },
    { t: "COMPLETE — code stays verbatim", d: "fences, language and headings kept", r: -0.6, w: 480 },
  ];
  return (
    <AbsoluteFill style={{ background: BENCH, padding: "132px 72px 90px 72px" }}>
      <SceneTitle title="One tool on the bench." sub="research(query) — search, proof, evidence. It selects. It never rewrites." />
      <div
        style={{
          display: "flex",
          gap: 48,
          marginTop: 40,
          opacity: s,
          transform: `translateY(${interpolate(s, [0, 1], [46, 0])}px)`,
        }}
      >
        <div style={{ flex: 1.05, background: INK, color: PAPER, padding: "40px 44px", boxShadow: SHEET_SHADOW, position: "relative" }}>
          <div style={{ fontFamily: MONO, fontSize: 22, color: "#B9B2A0", letterSpacing: 2 }}>QUERY SLIP — SET VERBATIM</div>
          <div style={{ fontFamily: MONO, fontSize: 37, lineHeight: 1.55, marginTop: 16 }}>
            research(
            <br />
            &nbsp;&nbsp;query,
            <br />
            &nbsp;&nbsp;max_sources <span style={{ color: "#E8B4A6" }}>6</span>,
            <br />
            &nbsp;&nbsp;max_tokens <span style={{ color: "#E8B4A6" }}>8000</span>,
            <br />
            &nbsp;&nbsp;mode <span style={{ color: "#E8B4A6" }}>"jev"</span>
            <br />)
          </div>
          <div style={{ position: "absolute", bottom: 26, right: 30 }}>
            <Stamp label="KEEP" progress={stampP} rotate={-9} />
          </div>
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20, justifyContent: "center" }}>
          {tickets.map((k, i) => {
            const vis = interpolate(local, [40 + i * 26, 70 + i * 26], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div
                key={k.t}
                style={{
                  width: k.w,
                  maxWidth: "100%",
                  background: SHEET,
                  border: `2px solid ${INK}`,
                  borderRadius: 3,
                  padding: "20px 26px",
                  boxShadow: SLIP_SHADOW,
                  transform: `rotate(${k.r}deg)`,
                  opacity: vis,
                }}
              >
                <div style={{ fontFamily: DISPLAY, fontSize: 33, letterSpacing: 0.5, color: INK }}>{k.t}</div>
                <div style={{ fontFamily: BODY, fontSize: 25, color: INK_SOFT, marginTop: 4 }}>{k.d}</div>
              </div>
            );
          })}
          <div style={{ fontFamily: MONO, fontSize: 24, color: INK, marginTop: 6 }}>
            MCP stdio · <span style={{ fontWeight: 700 }}>jev-research / research</span> · dashboard :8765
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------- Scene 4: The line ----------
function StepChevron({ lit }: { lit: boolean }) {
  return (
    <svg width={26} height={44} viewBox="0 0 26 44" style={{ alignSelf: "center", flexShrink: 0 }}>
      <polyline
        points="6,8 20,22 6,36"
        fill="none"
        stroke={lit ? RED : ASH}
        strokeWidth={5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const PLATES = [
  { n: "SEARCH", v: "20", d: "live results in", jev: false },
  { n: "MARK", v: "6 kept", d: "relevant + useful", jev: true },
  { n: "PULL", v: "6 down", d: "bounded, gated", jev: false },
  { n: "SET", v: "50 kept", d: "400 blocks proofed", jev: true },
  { n: "BIND", v: "8k", d: "whole blocks bound", jev: false },
];

function SceneLine() {
  const local = useLocal(600);
  const active = Math.min(4, Math.floor(local / 80));
  const budget = interpolate(local, [330, 420], [0, 1], { extrapolateRight: "clamp" });
  const stampP = interpolate(local, [400, 430], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: BENCH, padding: "132px 72px 90px 72px" }}>
      <SceneTitle title="The line runs five signatures." sub="JEV marks in red. The shop does every fetch, parse and bind in ink." />
      <div style={{ display: "flex", gap: 14, marginTop: 38, alignItems: "stretch" }}>
        {PLATES.map((p, i) => {
          const on = i <= active;
          const isJev = p.jev;
          return (
            <React.Fragment key={p.n}>
              <div
                style={{
                  flex: 1,
                  background: on ? SHEET : "rgba(251,247,236,0.55)",
                  border: isJev ? `3px solid ${RED}` : `2px solid ${INK}`,
                  borderRadius: 3,
                  padding: "22px 18px",
                  textAlign: "center",
                  boxShadow: SLIP_SHADOW,
                  opacity: on ? 1 : 0.5,
                  transform: isJev && on ? "translateY(-8px)" : "none",
                }}
              >
                <div style={{ fontFamily: DISPLAY, fontSize: 30, letterSpacing: 2, color: isJev ? RED : INK }}>
                  {p.n}
                  {isJev ? <span style={{ fontFamily: MONO, fontSize: 16 }}> · JEV</span> : null}
                </div>
                <div style={{ fontFamily: DISPLAY, fontSize: 62, color: INK, marginTop: 4 }}>{p.v}</div>
                <div style={{ fontFamily: BODY, fontSize: 22, color: INK_SOFT }}>{p.d}</div>
              </div>
              {i < PLATES.length - 1 ? <StepChevron lit={i < active} /> : null}
            </React.Fragment>
          );
        })}
      </div>
      <div style={{ display: "flex", gap: 28, marginTop: 30, alignItems: "center" }}>
        <div style={{ flex: 1.3, background: SHEET, border: `2px solid ${INK}`, borderRadius: 3, padding: "20px 28px", boxShadow: SLIP_SHADOW }}>
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <span style={{ fontFamily: DISPLAY, fontSize: 28, letterSpacing: 1.5, color: INK }}>BUDGET</span>
            <div style={{ flex: 1, height: 18, background: "rgba(20,18,15,0.14)" }}>
              <div style={{ width: `${14 + budget * 86}%`, height: "100%", background: RED }} />
            </div>
            <span style={{ fontFamily: MONO, fontSize: 28, fontWeight: 700, color: INK, fontVariantNumeric: "tabular-nums" }}>8k</span>
          </div>
          <div style={{ fontFamily: BODY, fontSize: 22, color: INK_SOFT, marginTop: 8 }}>
            Whole blocks only — deduped, headings restored, provenance tied on.
          </div>
        </div>
        <div style={{ flex: 1, opacity: interpolate(local, [400, 430], [0, 1], { extrapolateLeft: "clamp" }) }}>
          <Stamp label="CUT NEVER FETCHED" progress={stampP} rotate={-2} />
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------- Scene 5: One state ----------
function SceneState() {
  const local = useLocal(1080);
  const qs = ["relevant?", "useful?", "authoritative?", "actionable?"];
  return (
    <AbsoluteFill style={{ background: BENCH, padding: "132px 72px 90px 72px" }}>
      <div style={{ display: "flex", gap: 44, height: "100%" }}>
        <div style={{ flex: 1, background: SHEET, border: `2px solid ${INK}`, boxShadow: SHEET_SHADOW, padding: "44px 46px", borderRadius: 3 }}>
          <div style={{ fontFamily: DISPLAY, fontSize: 64, lineHeight: 1, color: INK }}>
            ONE SHEET,
            <br />
            MANY QUESTIONS.
          </div>
          <div style={{ fontFamily: BODY, fontSize: 28, color: INK_SOFT, marginTop: 16 }}>
            One shared state plus every question in a single call — batched, mapped by ID, never by order.
          </div>
          <div style={{ fontFamily: MONO, fontSize: 24, color: INK, background: PAPER, border: `1.5px solid ${INK}`, padding: "18px 22px", marginTop: 24 }}>
            task: bound concurrent fetches + retries
            <br />
            candidates: 20 slips · blocks: batched ×30
          </div>
          <div style={{ fontFamily: BODY, fontStyle: "italic", fontSize: 26, color: INK_SOFT, marginTop: 20 }}>
            Margin note — uncertain means keep. A lost proof costs more than a kept maybe.
          </div>
        </div>
        <div style={{ flex: 0.95, display: "flex", flexDirection: "column", justifyContent: "center", gap: 18 }}>
          {qs.map((q, i) => {
            const vis = interpolate(local, [30 + i * 30, 60 + i * 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={q} style={{ display: "flex", alignItems: "center", gap: 18, opacity: vis, transform: `rotate(${i % 2 === 0 ? -1 : 1}deg)` }}>
                <div style={{ width: 120, height: 2, background: RED }} />
                <div
                  style={{
                    background: SHEET,
                    border: `2px solid ${INK}`,
                    borderRadius: 3,
                    padding: "16px 26px",
                    fontFamily: MONO,
                    fontSize: 32,
                    fontWeight: 700,
                    color: INK,
                    boxShadow: SLIP_SHADOW,
                  }}
                >
                  {q}
                </div>
                <div style={{ fontFamily: MONO, fontSize: 24, color: RED, fontWeight: 700 }}>0.9{i}</div>
              </div>
            );
          })}
          <div style={{ fontFamily: DISPLAY, fontSize: 36, color: INK, marginTop: 10 }}>
            KEEP = <span style={{ color: RED }}>RELEVANT + USEFUL</span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------- Scene 6: Bind ----------
function SceneBind() {
  const local = useLocal(1410);
  const { fps } = useVideoConfig();
  const s = spring({ frame: local, fps, config: { stiffness: 75, damping: 17 } });
  const stampP = interpolate(local, [190, 220], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: BENCH, justifyContent: "center", alignItems: "center" }}>
      <div
        style={{
          textAlign: "center",
          opacity: s,
          transform: `translateY(${interpolate(s, [0, 1], [46, 0])}px)`,
          width: 1500,
        }}
      >
        <div style={{ fontFamily: DISPLAY, fontSize: 118, lineHeight: 0.95, color: INK }}>
          TAKE THE BOUND COPY.
        </div>
        <div style={{ fontFamily: BODY, fontSize: 31, color: INK_SOFT, marginTop: 14 }}>
          Proofed on your machine — silent cut, add music on publish
        </div>
        <div style={{ display: "flex", gap: 26, justifyContent: "center", marginTop: 36 }}>
          <div style={{ background: INK, color: PAPER, fontFamily: MONO, fontSize: 33, padding: "24px 36px", boxShadow: SHEET_SHADOW, whiteSpace: "nowrap" }}>
            <span style={{ color: "#B9B2A0" }}>$</span> pip install -e ".[<span style={{ color: "#E8B4A6" }}>dev</span>]"
          </div>
          <div
            style={{
              background: SHEET,
              border: `2.5px solid ${INK}`,
              fontFamily: MONO,
              fontSize: 30,
              color: INK,
              padding: "24px 30px",
              boxShadow: SLIP_SHADOW,
              whiteSpace: "nowrap",
            }}
          >
            dashboard <span style={{ fontWeight: 700 }}>localhost:8765</span>
          </div>
        </div>
        <div style={{ marginTop: 30 }}>
          <Stamp label="START PROOFING" progress={stampP} rotate={-3} />
        </div>
        <div style={{ fontFamily: MONO, fontSize: 26, color: INK, marginTop: 26 }}>
          python -m jev_research_mcp · jev-research / research
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------- Root ----------
export function ProofBenchVideo() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: BENCH }}>
      {frame < 150 ? <SceneHook /> : null}
      {frame >= 150 && frame < 360 ? <SceneCut /> : null}
      {frame >= 360 && frame < 600 ? <SceneTool /> : null}
      {frame >= 600 && frame < 1080 ? <SceneLine /> : null}
      {frame >= 1080 && frame < 1410 ? <SceneState /> : null}
      {frame >= 1410 ? <SceneBind /> : null}
      <CropMarks />
      <TopRule frame={frame} />
      <BottomSlug />
    </AbsoluteFill>
  );
}
