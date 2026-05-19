import { useEffect, useState, useRef } from "react";

const STATES = ["idle", "listening", "thinking", "speaking"] as const;
type FaceState = typeof STATES[number];

function useAnimLoop(fps = 60) {
  const [t, setT] = useState(0);
  const raf = useRef<number>(0);
  const last = useRef(0);
  useEffect(() => {
    const tick = (now: number) => {
      if (now - last.current > 1000 / fps) { setT(now); last.current = now; }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [fps]);
  return t;
}

// Smooth blob path from control points
function blobPath(cx: number, cy: number, r: number, points: number, t: number, distortion: number): string {
  const pts = Array.from({ length: points }, (_, i) => {
    const angle = (i / points) * Math.PI * 2;
    const noise = distortion * (
      0.4 * Math.sin(t * 1.3 + i * 2.1) +
      0.3 * Math.sin(t * 2.1 + i * 1.5) +
      0.3 * Math.cos(t * 0.9 + i * 3.2)
    );
    const rr = r * (1 + noise);
    return { x: cx + rr * Math.cos(angle), y: cy + rr * Math.sin(angle) };
  });

  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 0; i < pts.length; i++) {
    const curr = pts[i];
    const next = pts[(i + 1) % pts.length];
    const mx = (curr.x + next.x) / 2;
    const my = (curr.y + next.y) / 2;
    d += ` Q ${curr.x} ${curr.y} ${mx} ${my}`;
  }
  d += " Z";
  return d;
}

export function Fluid() {
  const t = useAnimLoop(60);
  const [state, setState] = useState<FaceState>("idle");

  useEffect(() => {
    const id = setInterval(() => {
      setState((s) => {
        const idx = STATES.indexOf(s);
        return STATES[(idx + 1) % STATES.length];
      });
    }, 2500);
    return () => clearInterval(id);
  }, []);

  const sec = t / 1000;

  const themes: Record<FaceState, { from: string; to: string; accent: string; label: string }> = {
    idle:      { from: "#1a0533", to: "#0d1a44", accent: "#a78bfa", label: "Resting" },
    listening: { from: "#001a2e", to: "#002244", accent: "#38bdf8", label: "Hearing you" },
    thinking:  { from: "#1a1200", to: "#2a1a00", accent: "#f59e0b", label: "Processing" },
    speaking:  { from: "#1a0018", to: "#0a001a", accent: "#f472b6", label: "Speaking" },
  };

  const { from, to, accent, label } = themes[state];

  // Blob distortion
  const dist = state === "idle" ? 0.08 : state === "listening" ? 0.14 : state === "thinking" ? 0.18 : 0.22;
  const blobD = blobPath(140, 140, 95, 12, sec, dist);
  const innerD = blobPath(140, 140, 60, 10, sec * 1.4 + 1, dist * 0.6);

  // Eyes: organic teardrop shapes
  const eyeBlink = Math.floor(sec / 4) % 1 === 0 && (sec % 4) < 0.2;
  const eyeH = eyeBlink ? 2 : 14;
  const eyeW = 12;

  // Speaking ripple waves
  const ripples = Array.from({ length: 5 }, (_, i) => ({
    r: 115 + i * 22,
    op: state === "speaking" ? Math.max(0, (0.6 - i * 0.12) * (0.5 + 0.5 * Math.sin(sec * 8 - i * 0.8))) : 0,
  }));

  // Voice waveform
  const wavePoints = Array.from({ length: 32 }, (_, i) => {
    const x = (i / 31) * 180 + 50;
    const amp = state === "speaking"
      ? 22 * Math.abs(Math.sin(sec * 6 + i * 0.6)) * Math.sin(i * 0.4)
      : state === "listening"
      ? 8 * Math.sin(sec * 4 + i * 0.4)
      : 2 * Math.sin(sec * 1.5 + i * 0.3);
    return `${x},${280 + amp}`;
  });
  const wavePath = `M ${wavePoints.join(" L ")}`;

  // Thinking: orbiting particles
  const particles = Array.from({ length: 6 }, (_, i) => {
    const angle = sec * 2 + (i / 6) * Math.PI * 2;
    const r = 115 + 8 * Math.sin(sec * 3 + i);
    return { x: 140 + r * Math.cos(angle), y: 140 + r * Math.sin(angle) };
  });

  // Iris detail
  const irisAngle = state === "thinking" ? sec * 0.8 : sec * 0.2;

  return (
    <div style={{
      width: "100%", height: "100vh",
      background: `radial-gradient(ellipse at 50% 40%, ${from}, ${to}, #050508)`,
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      fontFamily: "'Inter', 'Segoe UI', sans-serif",
      overflow: "hidden", position: "relative",
      transition: "background 1.2s ease",
    }}>
      {/* Background particles */}
      {Array.from({ length: 12 }, (_, i) => {
        const px = 20 + (i * 73 % 280);
        const py = 30 + (i * 61 % 620);
        const op = 0.08 + 0.06 * Math.sin(sec * 0.8 + i * 1.3);
        return (
          <div key={i} style={{
            position: "absolute", left: px, top: py,
            width: 2, height: 2, borderRadius: "50%",
            background: accent, opacity: op,
          }} />
        );
      })}

      {/* SVG canvas */}
      <svg width={280} height={280} style={{ overflow: "visible" }}>
        <defs>
          <radialGradient id="blobGrad" cx="40%" cy="35%" r="65%">
            <stop offset="0%" stopColor={accent} stopOpacity={0.9} />
            <stop offset="50%" stopColor={accent} stopOpacity={0.4} />
            <stop offset="100%" stopColor={accent} stopOpacity={0.05} />
          </radialGradient>
          <radialGradient id="innerGrad" cx="40%" cy="35%" r="65%">
            <stop offset="0%" stopColor="white" stopOpacity={0.15} />
            <stop offset="100%" stopColor={accent} stopOpacity={0.05} />
          </radialGradient>
          <filter id="blur">
            <feGaussianBlur stdDeviation="6" />
          </filter>
        </defs>

        {/* Glow behind blob */}
        <path d={blobD} fill={accent} filter="url(#blur)" opacity={0.18} />

        {/* Ripple rings (speaking) */}
        {ripples.map((rp, i) => (
          <circle key={i} cx={140} cy={140} r={rp.r}
            fill="none" stroke={accent} strokeWidth={1.5}
            opacity={rp.op} />
        ))}

        {/* Main blob */}
        <path d={blobD} fill="url(#blobGrad)"
          style={{ filter: `drop-shadow(0 0 18px ${accent}60)` }} />

        {/* Inner blob */}
        <path d={innerD} fill="url(#innerGrad)" />

        {/* Thinking particles */}
        {state === "thinking" && particles.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={3 + 1.5 * Math.sin(sec * 4 + i)}
            fill={accent} opacity={0.7} />
        ))}

        {/* Eyes */}
        {!eyeBlink && (
          <>
            <ellipse cx={118} cy={132} rx={eyeW / 2} ry={eyeH / 2}
              fill="white" opacity={0.9} />
            <ellipse cx={162} cy={132} rx={eyeW / 2} ry={eyeH / 2}
              fill="white" opacity={0.9} />
            {/* Iris */}
            <ellipse cx={118} cy={132} rx={5} ry={5}
              fill={accent}
              style={{ filter: `drop-shadow(0 0 4px ${accent})` }} />
            <ellipse cx={162} cy={132} rx={5} ry={5}
              fill={accent}
              style={{ filter: `drop-shadow(0 0 4px ${accent})` }} />
            {/* Pupil */}
            <circle cx={119} cy={131} r={2.5} fill="#000" opacity={0.8} />
            <circle cx={163} cy={131} r={2.5} fill="#000" opacity={0.8} />
            {/* Specular */}
            <circle cx={117} cy={130} r={1.2} fill="white" opacity={0.9} />
            <circle cx={161} cy={130} r={1.2} fill="white" opacity={0.9} />
          </>
        )}
        {eyeBlink && (
          <>
            <line x1={112} y1={132} x2={124} y2={132} stroke="white" strokeWidth={2.5} strokeLinecap="round" />
            <line x1={156} y1={132} x2={168} y2={132} stroke="white" strokeWidth={2.5} strokeLinecap="round" />
          </>
        )}

        {/* Mouth — changes per state */}
        {state === "idle" && (
          <path d="M 125 155 Q 140 162 155 155" fill="none" stroke="white" strokeWidth={2}
            strokeLinecap="round" opacity={0.7} />
        )}
        {state === "listening" && (
          <ellipse cx={140} cy={158} rx={10} ry={6} fill="none" stroke="white"
            strokeWidth={2} opacity={0.7} />
        )}
        {state === "thinking" && (
          <path d="M 125 158 Q 140 153 155 158" fill="none" stroke="white" strokeWidth={2}
            strokeLinecap="round" opacity={0.7} />
        )}
        {state === "speaking" && (
          <ellipse cx={140} cy={158}
            rx={10 + 5 * Math.abs(Math.sin(sec * 10))}
            ry={6 + 5 * Math.abs(Math.sin(sec * 12))}
            fill="none" stroke="white" strokeWidth={2} opacity={0.8} />
        )}
      </svg>

      {/* Voice waveform */}
      <svg width={280} height={60} style={{ marginTop: -10 }}>
        <path d={wavePath} fill="none" stroke={accent} strokeWidth={1.5}
          strokeOpacity={0.6} strokeLinecap="round" />
        <path d={wavePath} fill="none" stroke="white" strokeWidth={0.5}
          strokeOpacity={0.2} strokeLinecap="round" />
      </svg>

      {/* Status */}
      <div style={{
        fontSize: 16, fontWeight: 300,
        color: "white", letterSpacing: "0.12em",
        textTransform: "uppercase",
        textShadow: `0 0 20px ${accent}`,
        opacity: 0.9, marginTop: 4,
        transition: "text-shadow 0.8s",
      }}>
        {label}
      </div>

      {/* Toggle buttons */}
      <div style={{ display: "flex", gap: 8, marginTop: 24, flexWrap: "wrap", justifyContent: "center" }}>
        {STATES.map((s) => (
          <button key={s} onClick={() => setState(s)} style={{
            background: state === s ? `${accent}18` : "transparent",
            border: `1px solid ${accent}35`,
            borderRadius: 20, color: state === s ? accent : "#444",
            fontSize: 11, padding: "5px 14px", cursor: "pointer",
            fontFamily: "inherit", letterSpacing: "0.05em",
            transition: "all 0.4s",
          }}>
            {s}
          </button>
        ))}
      </div>

      {/* Bottom label */}
      <div style={{
        position: "absolute", bottom: 24,
        fontSize: 10, color: "#222", letterSpacing: "0.2em", textTransform: "uppercase",
      }}>
        Snowball · Fluid Face
      </div>
    </div>
  );
}
