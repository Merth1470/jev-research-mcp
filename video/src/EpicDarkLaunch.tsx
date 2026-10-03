import "@fontsource/anton";
import "@fontsource/work-sans/400.css";
import "@fontsource/work-sans/600.css";
import "@fontsource/work-sans/700.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/700.css";
import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// ---------------------------------------------------------------------------
// DARK SIGNAL — epic night-shift launch cut for JEV Evidence MCP (60s, 1800f)
// Deliberately NOT the retired neon-terminal cliché: no Inter, no acid-green,
// no violet, no pill badges, no uniform card kit. Same brand faces as Proof
// Bench (Anton / Work Sans / JetBrains Mono) on a deep-navy void, with ember
// reserved for JEV decisions and ice for data flow. All figures SYNTHETIC.
// ---------------------------------------------------------------------------

const VOID = "#060913";
const ABYSS = "#0B1220";
const PANEL = "#111A2E";
const HAIRLINE = "rgba(143,216,255,0.16)";
const PAPER = "#F2EFE6";
const MUTED = "#8B93A7";
const EMBER = "#FF4A2B";
const ICE = "#8FD8FF";
const GOLD = "#FFC24B";

const DISPLAY = "'Anton', 'Arial Narrow', sans-serif";
const BODY = "'Work Sans', 'Segoe UI', sans-serif";
const MONO = "'JetBrains Mono', 'Consolas', monospace";

const DURATION = 1800;

function hash(i: number, seed: number): number {
  const x = Math.sin(i * 127.1 + seed * 311.7) * 43758.5453;
  return x - Math.floor(x);
}

function useLocal(start: number): number {
  const frame = useCurrentFrame();
  return Math.max(0, frame - start);
}

// ---------------- atmosphere ----------------

function Starfield({ frame, count = 110 }: { frame: number; count?: number }) {
  const stars = React.useMemo(() => {
    return Array.from({ length: count }, (_, i) => ({
      x: hash(i, 1) * 1920,
      y: hash(i, 2) * 1080,
      r: 0.6 + hash(i, 3) * 1.9,
      tw: hash(i, 4) * Math.PI * 2,
      ice: hash(i, 5) > 0.82,
    }));
  }, [count]);
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      {stars.map((s, i) => {
        const tw = 0.25 + 0.75 * Math.abs(Math.sin(frame * 0.03 + s.tw));
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: s.x,
              top: s.y,
              width: s.r * 2,
              height: s.r * 2,
              borderRadius: 999,
              background: s.ice ? ICE : PAPER,
              opacity: tw * 0.55,
              boxShadow: s.ice ? `0 0 ${8 + tw * 10}px rgba(143,216,255,0.5)` : "none",
            }}
          />
        );
      })}
    </div>
  );
}

function Grain() {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        opacity: 0.09,
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)' opacity='0.6'/%3E%3C/svg%3E")`,
      }}
    />
  );
}

function Vignette() {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        background:
          "radial-gradient(ellipse at 50% 42%, transparent 52%, rgba(0,0,0,0.62) 100%)",
      }}
    />
  );
}

function Scanlines() {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        opacity: 0.5,
        background:
          "repeating-linear-gradient(0deg, rgba(255,255,255,0.022) 0px, rgba(255,255,255,0.022) 1px, transparent 1px, transparent 4px)",
      }}
    />
  );
}

// ---------------- chrome ----------------

function TopRule({ frame }: { frame: number }) {
  const progress = Math.min(1, frame / DURATION);
  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        padding: "26px 72px 0 72px",
        zIndex: 30,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div
          style={{
            fontFamily: MONO,
            fontWeight: 700,
            fontSize: 23,
            letterSpacing: 3,
            color: PAPER,
          }}
        >
          JEV EVIDENCE <span style={{ color: EMBER }}>●</span>{" "}
          <span style={{ color: MUTED, fontWeight: 400 }}>SIGNAL / NOISE — 60s</span>
        </div>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 23,
            color: PAPER,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {String(Math.floor(frame / 30)).padStart(2, "0")}s / 60s
        </div>
      </div>
      <div style={{ height: 2, background: "rgba(242,239,230,0.14)", marginTop: 12 }}>
        <div style={{ width: `${progress * 100}%`, height: "100%", background: EMBER }} />
      </div>
    </div>
  );
}

function BottomSlug() {
  return (
    <div
      style={{
        position: "absolute",
        bottom: 24,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "space-between",
        padding: "0 72px",
        fontFamily: MONO,
        fontSize: 18,
        color: MUTED,
        zIndex: 30,
      }}
    >
      <span>Silent cut — captions burned in</span>
      <span>Figures illustrative — SYNTHETIC until bench run</span>
    </div>
  );
}

function CaptionBar({ text, local }: { text: string; local: number }) {
  const on = interpolate(local, [8, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  return (
    <div
      style={{
        position: "absolute",
        bottom: 92,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        zIndex: 25,
        opacity: on,
        transform: `translateY(${interpolate(on, [0, 1], [18, 0])}px)`,
      }}
    >
      <div
        style={{
          fontFamily: MONO,
          fontSize: 27,
          fontWeight: 700,
          letterSpacing: 0.5,
          color: PAPER,
          background: "rgba(3,5,10,0.72)",
          border: `1px solid ${HAIRLINE}`,
          padding: "12px 30px",
        }}
      >
        <span style={{ color: EMBER }}>▸ </span>
        {text}
      </div>
    </div>
  );
}

function KineticTitle({
  lines,
  local,
  size = 148,
  color = PAPER,
  accentLast = false,
}: {
  lines: string[];
  local: number;
  size?: number;
  color?: string;
  accentLast?: boolean;
}) {
  const { fps } = useVideoConfig();
  return (
    <div>
      {lines.map((ln, i) => {
        const s = spring({
          frame: Math.max(0, local - i * 9),
          fps,
          config: { stiffness: 92, damping: 15 },
        });
        const blur = interpolate(s, [0, 1], [14, 0]);
        return (
          <div
            key={ln}
            style={{
              fontFamily: DISPLAY,
              fontSize: size,
              lineHeight: 0.94,
              letterSpacing: -1,
              color: accentLast && i === lines.length - 1 ? EMBER : color,
              opacity: s,
              transform: `translateY(${interpolate(s, [0, 1], [70, 0])}px)`,
              filter: `blur(${Math.max(0, blur)}px)`,
              textShadow:
                accentLast && i === lines.length - 1
                  ? "0 0 60px rgba(255,74,43,0.35)"
                  : "0 18px 60px rgba(0,0,0,0.6)",
            }}
          >
            {ln}
          </div>
        );
      })}
    </div>
  );
}

// Glitch cuts on scene boundaries — 2-frame RGB split, frame-driven
const CUTS = [170, 430, 710, 1090, 1390];
function Glitch({ frame }: { frame: number }) {
  const near = CUTS.some((c) => frame >= c - 2 && frame <= c + 2);
  if (!near) {
    return null;
  }
  const shift = frame % 2 === 0 ? 14 : -12;
  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 40, pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "rgba(255,74,43,0.08)",
          transform: `translateX(${shift}px)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "rgba(143,216,255,0.07)",
          transform: `translateX(${-shift}px)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 200 + ((frame * 167) % 600),
          height: 26,
          background: "rgba(242,239,230,0.06)",
        }}
      />
    </div>
  );
}

// ---------------- ACT 1: void ----------------

function ActVoid() {
  const local = useLocal(0);
  const query = "how do I bound concurrent fetches with retries?";
  const chars = Math.floor(interpolate(local, [30, 110], [0, query.length], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  }));
  const caret = local > 20 && Math.floor(local / 12) % 2 === 0;
  const wake = spring({ frame: Math.max(0, local - 118), fps: 30, config: { stiffness: 60, damping: 14 } });
  return (
    <AbsoluteFill style={{ background: VOID, justifyContent: "center", alignItems: "center" }}>
      <Starfield frame={local} />
      {/* distant ember horizon */}
      <div
        style={{
          position: "absolute",
          left: -200,
          right: -200,
          bottom: -320,
          height: 560,
          background: "radial-gradient(ellipse at 50% 100%, rgba(255,74,43,0.20) 0%, transparent 65%)",
        }}
      />
      <div style={{ textAlign: "center", zIndex: 2, opacity: interpolate(local, [0, 22], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
        <div style={{ fontFamily: MONO, fontSize: 24, letterSpacing: 6, color: MUTED }}>
          EVERY CODING AGENT KNOWS THIS FEELING
        </div>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 44,
            color: PAPER,
            marginTop: 30,
            minHeight: 70,
          }}
        >
          <span style={{ color: ICE }}>&gt; </span>
          {query.slice(0, chars)}
          {caret ? <span style={{ color: EMBER }}>▍</span> : <span> </span>}
        </div>
        <div
          style={{
            opacity: wake,
            transform: `translateY(${interpolate(wake, [0, 1], [50, 0])}px)`,
            marginTop: 26,
          }}
        >
          <KineticTitle lines={["THE WEB", "ANSWERS."]} local={Math.max(0, local - 118)} size={150} accentLast />
        </div>
        <div
          style={{
            fontFamily: BODY,
            fontSize: 30,
            color: MUTED,
            marginTop: 22,
            opacity: interpolate(local, [135, 165], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          }}
        >
          …but it answers with <span style={{ color: PAPER, fontWeight: 700 }}>everything at once.</span>
        </div>
      </div>
      <CaptionBar text="your agent is drowning in tabs" local={local} />
    </AbsoluteFill>
  );
}

// ---------------- ACT 2: flood ----------------

const FLOOD_WORDS = [
  "install guide", "rate-limit recipe", "forum guess", "ads + banner", "stale mirror",
  "seo farm", "changelog", "official docs", "source thread", "cookbook",
  "hot take", "dead link", "pop-up", "mirror #4", "listicle",
  "outdated wiki", "promo post", "comment row", "pdf scan", "mayhem",
];

function ActFlood() {
  const local = useLocal(170);
  const blocks = Math.round(interpolate(local, [10, 190], [20, 400], { extrapolateRight: "clamp" }));
  const tokens = Math.round(interpolate(local, [10, 190], [1400, 48000], { extrapolateRight: "clamp" }));
  const push = 1 + local * 0.00028;
  return (
    <AbsoluteFill style={{ background: VOID, overflow: "hidden" }}>
      <Starfield frame={local + 500} count={70} />
      <div
        style={{
          position: "absolute",
          inset: -120,
          transform: `scale(${push})`,
        }}
      >
        {FLOOD_WORDS.map((w, i) => {
          const x = hash(i, 11) * 1650 + 60;
          const delay = hash(i, 12) * 90;
          const y = interpolate(local, [delay, delay + 150], [-260, 1150], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const rot = (hash(i, 13) - 0.5) * 14;
          const fade =
            interpolate(local, [delay, delay + 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) *
            (1 - interpolate(y, [800, 1120], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
          return (
            <div
              key={w}
              style={{
                position: "absolute",
                left: x,
                top: y,
                transform: `rotate(${rot}deg)`,
                opacity: Math.max(0, 0.16 + fade * 0.75),
                fontFamily: MONO,
                fontSize: 21 + hash(i, 14) * 14,
                fontWeight: 700,
                color: i % 7 === 0 ? ICE : "rgba(242,239,230,0.75)",
                background: "rgba(17,26,46,0.85)",
                border: `1px solid ${HAIRLINE}`,
                padding: "10px 18px",
                whiteSpace: "nowrap",
              }}
            >
              {w}
            </div>
          );
        })}
      </div>
      {/* red wash rising */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `linear-gradient(0deg, rgba(255,74,43,${0.05 + (local / 260) * 0.1}) 0%, transparent 55%)`,
        }}
      />
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", zIndex: 3 }}>
        <KineticTitle lines={["20 RESULTS.", "400 BLOCKS.", "ONE QUESTION."]} local={local} size={118} accentLast />
        <div style={{ display: "flex", gap: 60, marginTop: 40, fontFamily: MONO }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 64, fontWeight: 700, color: PAPER, fontVariantNumeric: "tabular-nums" }}>
              {blocks}
            </div>
            <div style={{ fontSize: 21, letterSpacing: 3, color: MUTED }}>BLOCKS SEEN</div>
          </div>
          <div style={{ width: 1, background: HAIRLINE }} />
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 64, fontWeight: 700, color: EMBER, fontVariantNumeric: "tabular-nums" }}>
              ~{tokens.toLocaleString()}
            </div>
            <div style={{ fontSize: 21, letterSpacing: 3, color: MUTED }}>RAW TOKENS · SYNTHETIC</div>
          </div>
        </div>
      </div>
      <CaptionBar text="20 results. 400 blocks. one question." local={local} />
    </AbsoluteFill>
  );
}

// ---------------- ACT 3: first cut ----------------

function ActCut() {
  const local = useLocal(430);
  const { fps } = useVideoConfig();
  const kept = new Set([0, 1, 6, 7, 8, 9]);
  const gate = spring({ frame: Math.max(0, local - 150), fps, config: { stiffness: 200, damping: 13 } });
  const ring = interpolate(local, [150, 210], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: ABYSS, justifyContent: "center", alignItems: "center" }}>
      <Starfield frame={local + 900} count={60} />
      {/* ember shockwave */}
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "46%",
          width: 200 + ring * 1500,
          height: 200 + ring * 1500,
          borderRadius: 999,
          border: `2px solid rgba(255,74,43,${Math.max(0, 0.5 - ring * 0.5)})`,
          transform: "translate(-50%,-50%)",
        }}
      />
      <div style={{ zIndex: 2, textAlign: "center", width: 1720 }}>
        <div style={{ fontFamily: MONO, fontSize: 24, letterSpacing: 6, color: ICE }}>
          JEV READS BEFORE YOU PAY TO FETCH
        </div>
        <div style={{ marginTop: 18 }}>
          <KineticTitle lines={["CUT IT BEFORE", "YOU FETCH IT."]} local={local} size={128} accentLast />
        </div>
        {/* shard wall */}
        <div style={{ display: "flex", gap: 14, marginTop: 44, justifyContent: "center" }}>
          {FLOOD_WORDS.slice(0, 10).map((w, i) => {
            const isKept = kept.has(i);
            const strikeAt = 60 + i * 10;
            const sp = interpolate(local, [strikeAt, strikeAt + 14], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const fall = isKept
              ? 0
              : interpolate(local, [strikeAt + 10, strikeAt + 60], [0, 130], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                });
            const fade = isKept
              ? 1
              : interpolate(local, [strikeAt + 10, strikeAt + 60], [1, 0.18], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                });
            return (
              <div
                key={w}
                style={{
                  width: 158,
                  background: isKept ? "rgba(255,74,43,0.10)" : PANEL,
                  border: isKept ? `2px solid ${EMBER}` : `1px solid ${HAIRLINE}`,
                  padding: "16px 10px 12px 10px",
                  opacity: fade,
                  transform: `translateY(${fall}px) rotate(${(i % 3) - 1}deg)`,
                  boxShadow: isKept ? "0 0 34px rgba(255,74,43,0.30)" : "none",
                  position: "relative",
                  overflow: "hidden",
                }}
              >
                <div style={{ fontFamily: MONO, fontSize: 17, fontWeight: 700, color: isKept ? PAPER : MUTED, minHeight: 52 }}>
                  {w}
                </div>
                {!isKept && sp > 0 ? (
                  <div
                    style={{
                      position: "absolute",
                      left: 8,
                      right: 8,
                      top: "52%",
                      height: 5,
                      background: EMBER,
                      transform: `scaleX(${sp}) rotate(-4deg)`,
                      transformOrigin: "left center",
                    }}
                  />
                ) : null}
                {isKept ? (
                  <div style={{ fontFamily: MONO, fontSize: 15, fontWeight: 700, color: EMBER, marginTop: 8 }}>
                    ● KEEP
                  </div>
                ) : (
                  <div style={{ fontFamily: MONO, fontSize: 15, color: MUTED, marginTop: 8 }}>× CUT</div>
                )}
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 30, opacity: gate, transform: `scale(${interpolate(gate, [0, 1], [1.6, 1])}) rotate(-3deg)` }}>
          <span
            style={{
              fontFamily: DISPLAY,
              fontSize: 52,
              letterSpacing: 4,
              color: EMBER,
              border: `4px solid ${EMBER}`,
              padding: "10px 34px",
              background: "rgba(255,74,43,0.08)",
            }}
          >
            14 CUT — NEVER FETCHED
          </span>
        </div>
      </div>
      <CaptionBar text="what is cut is never fetched" local={local} />
    </AbsoluteFill>
  );
}

// ---------------- ACT 4: the line ----------------

const STAGES = [
  { n: "SEARCH", v: "20", d: "live results in", jev: false },
  { n: "MARK", v: "6 kept", d: "relevant + useful", jev: true },
  { n: "PULL", v: "6 down", d: "bounded + gated", jev: false },
  { n: "SET", v: "50 kept", d: "400 blocks proofed", jev: true },
  { n: "BIND", v: "8k", d: "whole blocks bound", jev: false },
];

function ActLine() {
  const local = useLocal(710);
  const frame = useCurrentFrame();
  const active = Math.min(4, Math.floor(local / 62));
  const dolly = interpolate(local, [0, 380], [24, -24], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: VOID, padding: "150px 72px 120px 72px" }}>
      <Starfield frame={local + 1300} count={80} />
      <div style={{ fontFamily: MONO, fontSize: 24, letterSpacing: 6, color: ICE }}>
        THE PIPELINE — FIVE SIGNATURES
      </div>
      <div style={{ marginTop: 12 }}>
        <KineticTitle lines={["JEV DECIDES.", "CODE DISPOSES."]} local={local} size={94} />
      </div>
      <div style={{ position: "relative", marginTop: 44, transform: `translateX(${dolly}px)` }}>
        {/* flowing backbone */}
        <svg width={1776} height={26} style={{ position: "absolute", top: 118, left: 0, overflow: "visible" }}>
          <line
            x1={0}
            y1={13}
            x2={1776}
            y2={13}
            stroke={ICE}
            strokeWidth={3}
            strokeDasharray="26 18"
            strokeDashoffset={-frame * 3.2}
            opacity={0.55}
          />
          <line
            x1={0}
            y1={13}
            x2={interpolate(local, [0, 340], [0, 1776], { extrapolateRight: "clamp" })}
            y2={13}
            stroke={EMBER}
            strokeWidth={4}
            opacity={0.9}
          />
        </svg>
        <div style={{ display: "flex", gap: 26 }}>
          {STAGES.map((p, i) => {
            const on = i <= active;
            const pop = spring({ frame: Math.max(0, local - i * 62), fps: 30, config: { stiffness: 120, damping: 14 } });
            return (
              <div
                key={p.n}
                style={{
                  flex: 1,
                  background: on ? PANEL : "rgba(17,26,46,0.4)",
                  border: p.jev ? `2px solid ${on ? EMBER : "rgba(255,74,43,0.35)"}` : `1px solid ${HAIRLINE}`,
                  padding: "28px 22px",
                  textAlign: "center",
                  opacity: interpolate(pop, [0, 1], [0.25, 1]),
                  transform: `translateY(${interpolate(pop, [0, 1], [60, p.jev && on ? -10 : 0])}px)`,
                  boxShadow: p.jev && on ? "0 0 44px rgba(255,74,43,0.28)" : "0 24px 60px rgba(0,0,0,0.5)",
                }}
              >
                <div
                  style={{
                    fontFamily: DISPLAY,
                    fontSize: 30,
                    letterSpacing: 3,
                    color: p.jev ? EMBER : PAPER,
                  }}
                >
                  {p.n}
                  {p.jev ? <span style={{ fontFamily: MONO, fontSize: 15 }}> · JEV</span> : null}
                </div>
                <div style={{ fontFamily: DISPLAY, fontSize: 66, color: PAPER, marginTop: 6 }}>{p.v}</div>
                <div style={{ fontFamily: BODY, fontSize: 22, color: MUTED }}>{p.d}</div>
              </div>
            );
          })}
        </div>
      </div>
      <div style={{ display: "flex", gap: 28, marginTop: 34, alignItems: "center" }}>
        <div style={{ flex: 1.4, background: PANEL, border: `1px solid ${HAIRLINE}`, padding: "20px 28px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <span style={{ fontFamily: DISPLAY, fontSize: 26, letterSpacing: 2, color: PAPER }}>BUDGET</span>
            <div style={{ flex: 1, height: 14, background: "rgba(242,239,230,0.12)" }}>
              <div
                style={{
                  width: `${interpolate(local, [240, 330], [8, 86], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}%`,
                  height: "100%",
                  background: `linear-gradient(90deg, ${ICE}, ${EMBER})`,
                }}
              />
            </div>
            <span style={{ fontFamily: MONO, fontSize: 26, fontWeight: 700, color: PAPER }}>8k</span>
          </div>
          <div style={{ fontFamily: BODY, fontSize: 21, color: MUTED, marginTop: 8 }}>
            Whole blocks only — deduped, headings restored, provenance tied on.
          </div>
        </div>
        <div style={{ flex: 1, fontFamily: MONO, fontSize: 22, color: MUTED }}>
          one failure <span style={{ color: PAPER, fontWeight: 700 }}>≠</span> total failure
          <br />
          <span style={{ color: ICE }}>SSRF-checked · size-gated · bounded</span>
        </div>
      </div>
      <CaptionBar text="five signatures. two are judgments." local={local} />
    </AbsoluteFill>
  );
}

// ---------------- ACT 5: one state ----------------

function ActState() {
  const local = useLocal(1090);
  const frame = useCurrentFrame();
  const qs = [
    { q: "relevant?", s: "0.93", x: -560, y: -190 },
    { q: "useful?", s: "0.88", x: 560, y: -190 },
    { q: "authoritative?", s: "0.81", x: -560, y: 190 },
    { q: "actionable?", s: "0.90", x: 560, y: 190 },
  ];
  const pulse = 1 + 0.06 * Math.sin(frame * 0.12);
  return (
    <AbsoluteFill style={{ background: ABYSS, justifyContent: "center", alignItems: "center" }}>
      <Starfield frame={local + 1700} count={90} />
      <div style={{ fontFamily: MONO, fontSize: 24, letterSpacing: 6, color: ICE, position: "absolute", top: 150 }}>
        ONE SHARED STATE — MANY QUESTIONS — ONE CALL
      </div>
      <div style={{ position: "relative", width: 1500, height: 560, marginTop: 60 }}>
        <svg width={1500} height={560} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
          {qs.map((it, i) => {
            const vis = interpolate(local, [40 + i * 30, 80 + i * 30], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const dx = it.x * 0.72;
            const dy = it.y * 0.72;
            const len = Math.sqrt(dx * dx + dy * dy) || 1;
            const sx = 750 + (dx / len) * 178;
            const sy = 280 + (dy / len) * 178;
            return (
              <line
                key={it.q}
                x1={sx}
                y1={sy}
                x2={750 + dx}
                y2={280 + dy}
                stroke={vis > 0.5 ? EMBER : HAIRLINE}
                strokeWidth={3}
                strokeDasharray="14 12"
                strokeDashoffset={-frame * 2.4}
                opacity={0.35 + vis * 0.6}
              />
            );
          })}
        </svg>
        {/* core */}
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: "50%",
            width: 340,
            height: 340,
            transform: `translate(-50%,-50%) scale(${pulse})`,
            borderRadius: 999,
            background: "radial-gradient(circle, rgba(255,74,43,0.28) 0%, rgba(255,74,43,0.06) 55%, transparent 70%)",
            border: `2px solid rgba(255,74,43,0.6)`,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            boxShadow: "0 0 90px rgba(255,74,43,0.35)",
          }}
        >
          <div style={{ fontFamily: MONO, fontSize: 20, letterSpacing: 4, color: PAPER }}>TASK STATE</div>
          <div style={{ fontFamily: MONO, fontSize: 19, color: ICE, marginTop: 10, textAlign: "center", padding: "0 40px" }}>
            bound concurrent
            <br />
            fetches + retries
          </div>
          <div style={{ fontFamily: MONO, fontSize: 18, color: MUTED, marginTop: 8 }}>20 slips · ×30 blocks</div>
        </div>
        {qs.map((it, i) => {
          const vis = interpolate(local, [40 + i * 30, 80 + i * 30], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          });
          return (
            <div
              key={it.q}
              style={{
                position: "absolute",
                left: 750 + it.x - 190,
                top: 280 + it.y - 60,
                width: 380,
                opacity: vis,
                transform: `translateY(${interpolate(vis, [0, 1], [24, 0])}px)`,
                background: PANEL,
                border: `1px solid ${HAIRLINE}`,
                padding: "22px 26px",
                boxShadow: "0 24px 60px rgba(0,0,0,0.55)",
              }}
            >
              <div style={{ fontFamily: MONO, fontSize: 36, fontWeight: 700, color: PAPER }}>{it.q}</div>
              <div style={{ fontFamily: MONO, fontSize: 24, fontWeight: 700, color: EMBER, marginTop: 4 }}>
                {it.s} <span style={{ color: MUTED, fontWeight: 400, fontSize: 18 }}>· mapped by ID</span>
              </div>
            </div>
          );
        })}
      </div>
      <div
        style={{
          fontFamily: DISPLAY,
          fontSize: 44,
          color: PAPER,
          marginTop: 10,
          opacity: interpolate(local, [190, 230], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        }}
      >
        KEEP = <span style={{ color: EMBER }}>RELEVANT + USEFUL</span>
      </div>
      <div style={{ fontFamily: BODY, fontStyle: "italic", fontSize: 24, color: MUTED, marginTop: 6 }}>
        Uncertain means keep — a lost proof costs more than a kept maybe.
      </div>
      <CaptionBar text="one state. many questions. one call." local={local} />
    </AbsoluteFill>
  );
}

// ---------------- ACT 6: proof + CTA ----------------

const CODE_LINES = [
  "research(",
  '  query,',
  "  max_sources 6,",
  "  max_tokens 8000,",
  '  mode \"jev\"',
  ")",
];

function ActProof() {
  const local = useLocal(1390);
  const { fps } = useVideoConfig();
  const full = CODE_LINES.join("\n");
  const chars = Math.floor(interpolate(local, [40, 170], [0, full.length], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  }));
  const install = "$ pip install -e \".[dev]\"";
  const ichars = Math.floor(interpolate(local, [180, 250], [0, install.length], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  }));
  const slipStamp = spring({ frame: Math.max(0, local - 180), fps, config: { stiffness: 240, damping: 13 } });
  const stampP = interpolate(local, [235, 265], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const stamp = spring({ frame: Math.max(0, local - 235), fps, config: { stiffness: 240, damping: 13 } });
  const caret = Math.floor(local / 12) % 2 === 0;
  return (
    <AbsoluteFill style={{ background: VOID, justifyContent: "center", alignItems: "center" }}>
      <Starfield frame={local + 2100} count={100} />
      <div
        style={{
          position: "absolute",
          left: -200,
          right: -200,
          top: -320,
          height: 560,
          background: "radial-gradient(ellipse at 50% 0%, rgba(143,216,255,0.12) 0%, transparent 60%)",
        }}
      />
      <div
        style={{
          zIndex: 2,
          width: 1680,
          display: "flex",
          gap: 48,
          alignItems: "center",
          transform: "translateY(-46px)",
        }}
      >
        <div style={{ flex: 1 }}>
          <KineticTitle lines={["PROOF,", "NOT PROMISE."]} local={local} size={124} />
          <div style={{ fontFamily: BODY, fontSize: 29, color: MUTED, marginTop: 18, maxWidth: 700 }}>
            Local. Self-hosted. BYOK. Nothing phones home — queries stay on{" "}
            <span style={{ color: PAPER, fontWeight: 700 }}>your machine.</span>
          </div>
          <div
            style={{
              marginTop: 30,
              background: "#04060C",
              border: `1px solid ${HAIRLINE}`,
              padding: "26px 30px",
              boxShadow: "0 30px 80px rgba(0,0,0,0.6)",
            }}
          >
            <div style={{ fontFamily: MONO, fontSize: 21, letterSpacing: 3, color: MUTED }}>
              INSTALL — VERBATIM FROM README
            </div>
            <div style={{ fontFamily: MONO, fontSize: 34, color: PAPER, marginTop: 12 }}>
              {install.slice(0, ichars)}
              {local >= 180 && local < 300 && caret ? <span style={{ color: EMBER }}>▍</span> : null}
            </div>
            <div style={{ fontFamily: MONO, fontSize: 24, color: ICE, marginTop: 12 }}>
              python -m jev_research_mcp <span style={{ color: MUTED }}>· dashboard localhost:8765</span>
            </div>
          </div>
        </div>
        <div style={{ flex: 0.92 }}>
          <div
            style={{
              background: PAPER,
              color: "#14120F",
              padding: "34px 36px",
              transform: "rotate(1deg)",
              boxShadow: "0 30px 90px rgba(0,0,0,0.65)",
              position: "relative",
            }}
          >
            <div style={{ fontFamily: MONO, fontSize: 20, fontWeight: 700, letterSpacing: 3, color: "#4A463C" }}>
              QUERY SLIP — EVIDENCE, VERBATIM
            </div>
            <pre
              style={{
                fontFamily: MONO,
                fontSize: 33,
                lineHeight: 1.5,
                margin: "14px 0 0 0",
                whiteSpace: "pre-wrap",
                minHeight: 300,
              }}
            >
              {full.slice(0, chars)}
              {chars < full.length && caret ? <span style={{ color: EMBER }}>▍</span> : null}
            </pre>
            <div style={{ display: "flex", gap: 12, marginTop: 18 }}>
              <span style={{ fontFamily: MONO, fontSize: 19, fontWeight: 700, background: "#14120F", color: PAPER, padding: "8px 16px" }}>
                code stays verbatim
              </span>
              <span style={{ fontFamily: MONO, fontSize: 19, color: "#4A463C", padding: "8px 4px" }}>
                fences · language · headings kept
              </span>
            </div>
            <div
              style={{
                position: "absolute",
                right: 26,
                bottom: 120,
                opacity: slipStamp,
                transform: `rotate(-9deg) scale(${interpolate(slipStamp, [0, 1], [1.7, 1])})`,
                border: `4px solid ${EMBER}`,
                color: EMBER,
                fontFamily: DISPLAY,
                fontSize: 46,
                letterSpacing: 3,
                padding: "8px 24px",
                background: "rgba(242,239,230,0.85)",
              }}
            >
              KEEP
            </div>
          </div>
        </div>
      </div>
      {/* closing stamp */}
      <div
        style={{
          position: "absolute",
          bottom: 170,
          left: 0,
          right: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          opacity: stampP,
          zIndex: 5,
        }}
      >
        <div
          style={{
            fontFamily: DISPLAY,
            fontSize: 58,
            letterSpacing: 5,
            color: PAPER,
            border: `4px solid ${PAPER}`,
            padding: "12px 44px",
            transform: `rotate(-2deg) scale(${interpolate(stamp, [0, 1], [1.5, 1])})`,
            background: "rgba(255,74,43,0.14)",
            boxShadow: "0 0 70px rgba(255,74,43,0.35)",
          }}
        >
          START PROOFING
        </div>
        <div style={{ fontFamily: MONO, fontSize: 24, color: GOLD, marginTop: 14 }}>
          What will you stop fetching?
        </div>
      </div>
      <CaptionBar text="pip install. proof it yourself." local={local} />
    </AbsoluteFill>
  );
}

// ---------------- root ----------------

export function EpicDarkLaunch() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: VOID }}>
      {frame < 170 ? <ActVoid /> : null}
      {frame >= 170 && frame < 430 ? <ActFlood /> : null}
      {frame >= 430 && frame < 710 ? <ActCut /> : null}
      {frame >= 710 && frame < 1090 ? <ActLine /> : null}
      {frame >= 1090 && frame < 1390 ? <ActState /> : null}
      {frame >= 1390 ? <ActProof /> : null}
      <Scanlines />
      <Grain />
      <Vignette />
      <Glitch frame={frame} />
      {/* letterbox */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 8, background: "#000", zIndex: 29 }} />
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 8, background: "#000", zIndex: 29 }} />
      <TopRule frame={frame} />
      <BottomSlug />
    </AbsoluteFill>
  );
}
