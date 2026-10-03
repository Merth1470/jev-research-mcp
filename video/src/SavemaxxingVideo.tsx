import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const BG = "#08090C";
const PANEL = "#11141B";
const BORDER = "#232A35";
const TEXT = "#F5F7FA";
const MUTED = "#9AA3B2";
const GREEN = "#00E599";
const RED = "#FF5C5C";
const VIOLET = "#7C6CFF";
const YELLOW = "#FFC247";

const FONT: React.CSSProperties = {
  fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
};

function useLocal(start: number) {
  const frame = useCurrentFrame();
  return Math.max(0, frame - start);
}

const Pill: React.FC<{ children: React.ReactNode; color?: string; bg?: string }> = ({
  children,
  color = GREEN,
  bg = "rgba(0,229,153,0.10)",
}) => (
  <div
    style={{
      ...FONT,
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      padding: "10px 22px",
      borderRadius: 999,
      border: `1px solid ${color}`,
      background: bg,
      color,
      fontSize: 26,
      fontWeight: 700,
      letterSpacing: 3,
    }}
  >
    {children}
  </div>
);

const Caption: React.FC<{ kicker: string; title: string; sub?: string }> = ({
  kicker,
  title,
  sub,
}) => (
  <div style={{ ...FONT, textAlign: "center" }}>
    <div style={{ color: GREEN, fontSize: 28, fontWeight: 800, letterSpacing: 4, marginBottom: 14 }}>
      {kicker}
    </div>
    <div style={{ color: TEXT, fontSize: 76, fontWeight: 850, lineHeight: 1.02, letterSpacing: -2 }}>
      {title}
    </div>
    {sub ? (
      <div style={{ color: MUTED, fontSize: 32, marginTop: 16, fontWeight: 500 }}>{sub}</div>
    ) : null}
  </div>
);

function TopBar({ frame }: { frame: number }) {
  const progress = frame / 1800;
  return (
    <div style={{ position: "absolute", top: 0, left: 0, right: 0, padding: "36px 64px 0 64px" }}>
      <div style={{ ...FONT, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ color: TEXT, fontSize: 30, fontWeight: 850, letterSpacing: 1 }}>
          save<span style={{ color: GREEN }}>maxxing</span>
          <span style={{ color: MUTED, fontWeight: 500, fontSize: 22 }}> &nbsp;•&nbsp; JEV Research MCP</span>
        </div>
        <div style={{ color: MUTED, fontSize: 24, fontWeight: 600 }}>
          {String(Math.floor(frame / 30)).padStart(2, "0")}s / 60s
        </div>
      </div>
      <div style={{ height: 6, background: "#1B2030", borderRadius: 999, marginTop: 16, overflow: "hidden" }}>
        <div style={{ width: `${progress * 100}%`, height: "100%", background: GREEN }} />
      </div>
    </div>
  );
}

// ---------- SCENE 1: HOOK ----------
function SceneHook() {
  const local = useLocal(0);
  const { fps } = useVideoConfig();
  const pop = spring({ frame: local, fps, config: { stiffness: 90, damping: 16 } });
  const burn = interpolate(local, [10, 130], [0, 1], { extrapolateRight: "clamp" });
  const tokens = Math.round(interpolate(local, [10, 130], [0, 48000], { extrapolateRight: "clamp" }));
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", background: BG }}>
      <div style={{ transform: `scale(${interpolate(pop, [0, 1], [0.92, 1])})`, opacity: pop, textAlign: "center", ...FONT }}>
        <Pill color={RED} bg="rgba(255,92,92,0.10)">
          VIBE CODERS — THIS IS FOR YOU
        </Pill>
        <div style={{ height: 26 }} />
        <div style={{ color: TEXT, fontSize: 118, fontWeight: 900, letterSpacing: -4, lineHeight: 1 }}>
          STOP TOKEN-MAXXING.
        </div>
        <div style={{ color: GREEN, fontSize: 118, fontWeight: 900, letterSpacing: -4, lineHeight: 1.05 }}>
          START SAVEMAXXING.
        </div>
        <div style={{ height: 34 }} />
        <div style={{ width: 1100, margin: "0 auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", color: MUTED, fontSize: 26, fontWeight: 700 }}>
            <span>CONTEXT WINDOW</span>
            <span style={{ color: RED }}>{tokens.toLocaleString()} tokens wasted</span>
          </div>
          <div style={{ height: 28, background: "#1B2030", borderRadius: 999, marginTop: 12, overflow: "hidden", border: `1px solid ${BORDER}` }}>
            <div style={{ width: `${burn * 100}%`, height: "100%", background: `linear-gradient(90deg,#FF5C5C,#FF9A3D)`, transition: "none" }} />
          </div>
          <div style={{ color: MUTED, fontSize: 28, marginTop: 16 }}>
            Your agent fetches the whole internet to answer one question.
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------- SCENE 2: PROBLEM ----------
function SceneProblem() {
  const local = useLocal(150);
  const { fps } = useVideoConfig();
  const a = spring({ frame: local, fps });
  const b = spring({ frame: Math.max(0, local - 40), fps });
  const c = spring({ frame: Math.max(0, local - 80), fps });
  const wasteH = interpolate(Math.min(1, local / 160), [0, 1], [60, 300]);
  const saveH = 52;
  return (
    <AbsoluteFill style={{ background: BG, padding: "140px 90px 60px 90px", ...FONT }}>
      <Caption kicker="THE PROBLEM" title="Web search burns your context" sub="20 hits fetched in full — boilerplate, ads, nav, junk included" />
      <div style={{ height: 36 }} />
      <div style={{ display: "flex", gap: 32 }}>
        <div style={{ flex: 1.15, background: PANEL, border: `1px solid ${BORDER}`, borderRadius: 24, padding: 36, opacity: a, transform: `translateY(${interpolate(a, [0, 1], [40, 0])}px)` }}>
          <div style={{ color: RED, fontWeight: 800, fontSize: 26, letterSpacing: 2 }}>OLD WORKFLOW</div>
          <div style={{ color: TEXT, fontSize: 38, fontWeight: 800, marginTop: 8 }}>Fetch everything. Pray.</div>
          <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {["result 01 … full page", "result 02 … full page", "result 03 … full page", "result 04 … full page", "… × 20 pages", "cookie banners + ads"].map((t) => (
              <div key={t} style={{ background: "#1A0F12", border: "1px solid rgba(255,92,92,0.35)", color: "#FFB4B4", borderRadius: 12, padding: "14px 16px", fontSize: 24, fontWeight: 600 }}>
                {t}
              </div>
            ))}
          </div>
        </div>
        <div style={{ flex: 1, background: PANEL, border: `1px solid ${BORDER}`, borderRadius: 24, padding: 36, opacity: b, transform: `translateY(${interpolate(b, [0, 1], [40, 0])}px)` }}>
          <div style={{ color: MUTED, fontWeight: 800, fontSize: 26, letterSpacing: 2 }}>CONTEXT COST</div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 28, marginTop: 20, height: 330 }}>
            <div style={{ flex: 1, textAlign: "center" }}>
              <div style={{ color: RED, fontWeight: 850, fontSize: 34 }}>~48k</div>
              <div style={{ height: wasteH, background: RED, borderRadius: 14, marginTop: 10 }} />
              <div style={{ color: MUTED, fontSize: 24, marginTop: 10, fontWeight: 700 }}>baseline</div>
            </div>
            <div style={{ flex: 1, textAlign: "center", opacity: c }}>
              <div style={{ color: GREEN, fontWeight: 850, fontSize: 34 }}>~8k</div>
              <div style={{ height: saveH, background: GREEN, borderRadius: 14, marginTop: 10 }} />
              <div style={{ color: MUTED, fontSize: 24, marginTop: 10, fontWeight: 700 }}>savemaxxed</div>
            </div>
            <div style={{ flex: 1.1, color: TEXT, fontSize: 27, fontWeight: 600, paddingBottom: 40, lineHeight: 1.35 }}>
              Same question.
              <br />
              <span style={{ color: GREEN }}>Fraction of the tokens.</span>
              <br />
              <span style={{ color: MUTED }}>No summaries. Just evidence.</span>
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------- SCENE 3: INTRO ----------
function SceneIntro() {
  const local = useLocal(360);
  const { fps } = useVideoConfig();
  const s = spring({ frame: local, fps });
  const typing = Math.min(24, Math.floor(local / 3));
  const cmd = "research(query)".slice(0, typing);
  return (
    <AbsoluteFill style={{ background: BG, justifyContent: "center", alignItems: "center", ...FONT }}>
      <div style={{ textAlign: "center", opacity: s, transform: `translateY(${interpolate(s, [0, 1], [50, 0])}px)` }}>
        <Pill>SAVEMAXXING • LAUNCH</Pill>
        <div style={{ height: 20 }} />
        <div style={{ color: TEXT, fontSize: 96, fontWeight: 900, letterSpacing: -3 }}>JEV Research MCP</div>
        <div style={{ color: MUTED, fontSize: 34, marginTop: 10 }}>
          One MCP tool that filters web research <span style={{ color: GREEN, fontWeight: 800 }}>before it hits your model</span>
        </div>
        <div style={{ height: 30 }} />
        <div style={{ display: "flex", gap: 24, justifyContent: "center" }}>
          <div style={{ background: PANEL, border: `1px solid ${BORDER}`, borderRadius: 20, padding: "26px 34px", width: 560, textAlign: "left" }}>
            <div style={{ color: MUTED, fontSize: 22, fontWeight: 800, letterSpacing: 2 }}>ONE TOOL • MCP STDIO</div>
            <div style={{ background: "#0B0E14", border: `1px solid ${BORDER}`, borderRadius: 14, marginTop: 14, padding: "18px 20px", fontFamily: "ui-monospace, Menlo, Consolas, monospace", fontSize: 30, color: GREEN }}>
              {"> "}{cmd}<span style={{ opacity: local % 20 < 10 ? 1 : 0 }}>▍</span>
            </div>
            <div style={{ color: MUTED, fontSize: 24, marginTop: 12 }}>query + max_sources + max_evidence_tokens + mode</div>
          </div>
          <div style={{ background: PANEL, border: `1px solid ${BORDER}`, borderRadius: 20, padding: "26px 34px", width: 560, textAlign: "left" }}>
            <div style={{ color: MUTED, fontSize: 22, fontWeight: 800, letterSpacing: 2 }}>SELF-HOSTED</div>
            <div style={{ color: TEXT, fontSize: 32, fontWeight: 800, marginTop: 14, lineHeight: 1.3 }}>
              Local. Private. BYOK.
              <br />
              <span style={{ color: MUTED, fontWeight: 500 }}>No telemetry. No hosted service.</span>
            </div>
            <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
              {["Brave search", "TypeSafe JEV", "Python"].map((t) => (
                <span key={t} style={{ border: `1px solid ${BORDER}`, background: "#0B0E14", color: TEXT, borderRadius: 999, padding: "8px 18px", fontSize: 22, fontWeight: 700 }}>{t}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------- SCENE 4: PIPELINE ----------
const STEPS = [
  { n: "SEARCH", v: "20", d: "Brave live results", c: TEXT },
  { n: "JEFF FILTERS", v: "6 kept", d: "relevant + useful", c: VIOLET },
  { n: "FETCH ONLY 6", v: "−70%", d: "bounded, SSRF-safe", c: GREEN },
  { n: "PARSE", v: "400 blocks", d: "code kept verbatim", c: TEXT },
  { n: "JEFF FILTERS", v: "50 kept", d: "relevant + actionable", c: VIOLET },
];

function ScenePipeline() {
  const local = useLocal(600);
  const active = Math.min(4, Math.floor(local / 85));
  const tailProgress = interpolate(local, [430, 475], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: BG, padding: "140px 80px 50px 80px", ...FONT }}>
      <Caption kicker="HOW IT SAVES CONTEXT" title="Filter twice. Fetch less. Keep proof." sub="JEV decides — deterministic code disposes" />
      <div style={{ height: 34 }} />
      <div style={{ display: "flex", gap: 16, alignItems: "stretch" }}>
        {STEPS.map((s, i) => {
          const on = i <= active;
          return (
            <React.Fragment key={s.n + i}>
              <div
                style={{
                  flex: 1,
                  background: on ? "#141926" : PANEL,
                  border: `2px solid ${on ? s.c : BORDER}`,
                  borderRadius: 20,
                  padding: "24px 20px",
                  textAlign: "center",
                  opacity: on ? 1 : 0.45,
                  transform: on ? "scale(1)" : "scale(0.97)",
                }}
              >
                <div style={{ color: s.c, fontSize: 22, fontWeight: 850, letterSpacing: 2 }}>{s.n}</div>
                <div style={{ color: TEXT, fontSize: 52, fontWeight: 900, marginTop: 6 }}>{s.v}</div>
                <div style={{ color: MUTED, fontSize: 23, marginTop: 6 }}>{s.d}</div>
              </div>
              {i < STEPS.length - 1 && (
                <div style={{ alignSelf: "center", color: i < active ? GREEN : BORDER, fontSize: 44, fontWeight: 900 }}>›</div>
              )}
            </React.Fragment>
          );
        })}
      </div>
      <div style={{ height: 26 }} />
      <div style={{ display: "flex", gap: 20 }}>
        <div style={{ flex: 1.4, background: PANEL, border: `1px solid ${BORDER}`, borderRadius: 20, padding: "22px 28px", display: "flex", alignItems: "center", gap: 24 }}>
          <div style={{ color: MUTED, fontSize: 24, fontWeight: 800, whiteSpace: "nowrap" }}>EVIDENCE<br />BUDGET</div>
          <div style={{ flex: 1, height: 26, background: "#1B2030", borderRadius: 999, overflow: "hidden" }}>
            <div style={{ width: `${20 + tailProgress * 80}%`, height: "100%", background: GREEN }} />
          </div>
          <div style={{ color: GREEN, fontSize: 30, fontWeight: 900 }}>8k tokens</div>
          <div style={{ color: MUTED, fontSize: 22 }}>whole blocks only • deduped • with headings</div>
        </div>
        <div style={{ flex: 1, background: "rgba(124,108,255,0.08)", border: `1px solid ${VIOLET}`, borderRadius: 20, padding: "22px 28px" }}>
          <div style={{ color: VIOLET, fontSize: 24, fontWeight: 850 }}>DISCARDED RESULTS ARE NEVER FETCHED</div>
          <div style={{ color: TEXT, fontSize: 26, marginTop: 6 }}>No network work for junk. That is the whole trick.</div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------- SCENE 5: JEFF + FEATURES ----------
function SceneJeff() {
  const local = useLocal(1080);
  const { fps } = useVideoConfig();
  const s = spring({ frame: local, fps });
  const q = ["relevant?", "useful?", "authoritative?", "actionable?"];
  return (
    <AbsoluteFill style={{ background: BG, padding: "140px 80px 50px 80px", ...FONT }}>
      <div style={{ display: "flex", gap: 32, height: "100%" }}>
        <div style={{ flex: 1, background: `linear-gradient(180deg,#171A32,#101323)`, border: `2px solid ${VIOLET}`, borderRadius: 28, padding: 44, opacity: s }}>
          <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
            <div style={{ width: 110, height: 110, borderRadius: 999, background: VIOLET, color: "white", fontSize: 62, fontWeight: 900, display: "flex", alignItems: "center", justifyContent: "center" }}>
              J
            </div>
            <div>
              <div style={{ color: TEXT, fontSize: 52, fontWeight: 900, lineHeight: 1 }}>JEFF DOES</div>
              <div style={{ color: VIOLET, fontSize: 52, fontWeight: 900, lineHeight: 1 }}>THE HEAVY LIFTING</div>
            </div>
          </div>
          <div style={{ color: MUTED, fontSize: 28, marginTop: 18 }}>
            TypeSafe JEV — one shared state + many questions in <b style={{ color: TEXT }}>a single call</b>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 22 }}>
            {q.map((t, i) => {
              const vis = local > 30 + i * 22 ? 1 : 0.25;
              return (
                <span key={t} style={{ opacity: vis, background: "#0B0E14", border: `1px solid ${VIOLET}`, color: TEXT, borderRadius: 999, padding: "12px 22px", fontSize: 26, fontWeight: 700 }}>
                  {t}
                </span>
              );
            })}
          </div>
          <div style={{ marginTop: 24, background: "#0B0E14", border: `1px solid ${BORDER}`, borderRadius: 16, padding: "18px 22px", color: TEXT, fontSize: 27, fontWeight: 600 }}>
            keep = <span style={{ color: GREEN }}>relevant AND useful / actionable</span>
            <span style={{ color: MUTED }}> • uncertain → retain • authority reorders</span>
          </div>
        </div>
        <div style={{ flex: 1.1 }}>
          <div style={{ color: GREEN, fontSize: 26, fontWeight: 850, letterSpacing: 3 }}>EVERYTHING INCLUDED</div>
          <div style={{ color: TEXT, fontSize: 54, fontWeight: 900, marginTop: 4 }}>Clean. Minimal. Complete.</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 22 }}>
            {[
              ["</> Code preserved", "verbatim + language kept"],
              ["Provenance always", "URL + heading + also_seen_at"],
              ["SSRF-safe fetch", "redirects revalidated"],
              ["Private by design", "keys stay on your machine"],
              ["Live dashboard", "kept-vs-cut funnel :8765"],
              ["Baseline vs JEV", "benchmark proves the cut"],
            ].map(([t, d]) => (
              <div key={t} style={{ background: PANEL, border: `1px solid ${BORDER}`, borderRadius: 18, padding: "20px 22px" }}>
                <div style={{ color: TEXT, fontSize: 27, fontWeight: 800 }}>{t}</div>
                <div style={{ color: MUTED, fontSize: 23, marginTop: 4 }}>{d}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------- SCENE 6: CTA ----------
function SceneCTA() {
  const local = useLocal(1410);
  const { fps } = useVideoConfig();
  const s = spring({ frame: local, fps });
  const glow = local % 40 < 20 ? 1 : 0.75;
  return (
    <AbsoluteFill style={{ background: BG, justifyContent: "center", alignItems: "center", ...FONT }}>
      <div style={{ textAlign: "center", opacity: s, transform: `translateY(${interpolate(s, [0, 1], [50, 0])}px)` }}>
        <Pill>LAUNCH</Pill>
        <div style={{ height: 18 }} />
        <div style={{ color: TEXT, fontSize: 100, fontWeight: 900, letterSpacing: -3 }}>
          Stop wasting context.
        </div>
        <div style={{ color: GREEN, fontSize: 100, fontWeight: 900, letterSpacing: -3, opacity: glow }}>
          Start savemaxxing.
        </div>
        <div style={{ height: 28 }} />
        <div style={{ display: "flex", gap: 22, justifyContent: "center" }}>
          <div style={{ background: "#0B0E14", border: `1px solid ${BORDER}`, borderRadius: 16, padding: "20px 30px", fontFamily: "ui-monospace, Menlo, monospace", fontSize: 30, color: TEXT }}>
            <span style={{ color: MUTED }}>$</span> pip install -e ".[dev]"
          </div>
          <div style={{ background: GREEN, color: "#06110C", borderRadius: 16, padding: "20px 44px", fontSize: 32, fontWeight: 900 }}>
            Share #savemaxxing
          </div>
        </div>
        <div style={{ color: MUTED, fontSize: 30, marginTop: 24 }}>
          python -m jev_research_mcp &nbsp;•&nbsp; MCP: <span style={{ color: TEXT }}>jev-research / research</span> &nbsp;•&nbsp; dashboard :8765
        </div>
      </div>
    </AbsoluteFill>
  );
}

export function SavemaxxingVideo() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: BG }}>
      {frame < 150 ? <SceneHook /> : null}
      {frame >= 150 && frame < 360 ? <SceneProblem /> : null}
      {frame >= 360 && frame < 600 ? <SceneIntro /> : null}
      {frame >= 600 && frame < 1080 ? <ScenePipeline /> : null}
      {frame >= 1080 && frame < 1410 ? <SceneJeff /> : null}
      {frame >= 1410 ? <SceneCTA /> : null}
      <TopBar frame={frame} />
      <div style={{ position: "absolute", bottom: 28, left: 0, right: 0, textAlign: "center", ...FONT, color: "rgba(154,163,178,0.9)", fontSize: 22, fontWeight: 600, letterSpacing: 1 }}>
        savemaxxing • JEV Research MCP • self-hosted • silent cut — add music / voiceover on publish
      </div>
    </AbsoluteFill>
  );
}
