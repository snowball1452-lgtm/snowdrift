import { useEffect, useState, useRef } from "react";

const STATES = ["idle", "listening", "thinking", "speaking"] as const;
type FaceState = typeof STATES[number];

function useAnimLoop(fps = 60) {
  const [t, setT] = useState(0);
  const raf = useRef<number>(0);
  const last = useRef(0);
  useEffect(() => {
    const tick = (now: number) => {
      if (now - last.current > 1000 / fps) {
        setT(now);
        last.current = now;
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [fps]);
  return t;
}

export function Orb() {
  const t = useAnimLoop(30);
  const [state, setState] = useState<FaceState>("idle");
  const [stateIdx, setStateIdx] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setStateIdx((i) => {
        const next = (i + 1) % STATES.length;
        setState(STATES[next]);
        return next;
      });
    }, 2500);
    return () => clearInterval(id);
  }, []);

  const sec = t / 1000;

  const stateColors: Record<FaceState, string> = {
    idle:      "#4fc3f7",
    listening: "#81c784",
    thinking:  "#ffb74d",
    speaking:  "#ce93d8",
  };
  const stateLabels: Record<FaceState, string> = {
    idle:      "Snowball is ready",
    listening: "Listening...",
    thinking:  "Thinking...",
    speaking:  "Speaking...",
  };

  const color = stateColors[state];

  // Pulse scale
  const pulseScale = state === "idle"
    ? 1 + 0.025 * Math.sin(sec * 1.8)
    : state === "speaking"
    ? 1 + 0.06 * Math.sin(sec * 8)
    : state === "thinking"
    ? 1 + 0.03 * Math.sin(sec * 4)
    : 1 + 0.04 * Math.sin(sec * 6);

  // Eye blink
  const blinkCycle = Math.floor(sec / 3.2) % 2;
  const blinkPhase = sec % 3.2;
  const eyeScaleY = blinkPhase > 3.0 ? Math.max(0.05, 1 - (blinkPhase - 3.0) * 10) : 1;

  // Eye glow intensity
  const eyeGlow = state === "listening" ? 1.4 : state === "speaking" ? 1 + 0.4 * Math.sin(sec * 12) : 1;

  // Thinking rotation
  const thinkAngle = state === "thinking" ? sec * 180 : 0;

  // Speaking bars
  const bars = Array.from({ length: 9 }, (_, i) => {
    const freq = 3 + i * 1.7;
    const amp = state === "speaking" ? 0.3 + 0.7 * Math.abs(Math.sin(sec * freq + i)) : 0.08;
    return amp;
  });

  // Ring radius pulsing
  const r1 = 88 + (state === "listening" ? 8 * Math.sin(sec * 5) : 3 * Math.sin(sec * 2));
  const r2 = 115 + (state === "listening" ? 12 * Math.sin(sec * 5 + 1) : 4 * Math.sin(sec * 2 + 0.5));

  return (
    <div style={{
      width: "100%", height: "100vh",
      background: "linear-gradient(180deg, #080c12 0%, #0a1020 60%, #060810 100%)",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      fontFamily: "'Inter', sans-serif", overflow: "hidden", position: "relative",
    }}>
      {/* Ambient glow behind orb */}
      <div style={{
        position: "absolute",
        width: 260, height: 260,
        borderRadius: "50%",
        background: `radial-gradient(circle, ${color}18 0%, transparent 70%)`,
        filter: "blur(40px)",
        transform: `scale(${pulseScale * 1.4})`,
        transition: "background 0.8s ease",
      }} />

      {/* Outer rings */}
      <svg width={280} height={280} style={{ position: "absolute" }}>
        <circle
          cx={140} cy={140} r={r1}
          fill="none"
          stroke={color}
          strokeWidth={state === "listening" ? 1.5 : 0.8}
          strokeOpacity={0.25 + 0.1 * Math.sin(sec * 2)}
          strokeDasharray={state === "thinking" ? "8 12" : "none"}
          transform={state === "thinking" ? `rotate(${thinkAngle}, 140, 140)` : undefined}
        />
        <circle
          cx={140} cy={140} r={r2}
          fill="none"
          stroke={color}
          strokeWidth={0.6}
          strokeOpacity={0.12 + 0.05 * Math.sin(sec * 1.5 + 1)}
          strokeDasharray="4 18"
          transform={state === "thinking" ? `rotate(${-thinkAngle * 0.7}, 140, 140)` : undefined}
        />
      </svg>

      {/* Main orb sphere */}
      <div style={{
        width: 156, height: 156,
        borderRadius: "50%",
        background: `
          radial-gradient(circle at 38% 32%,
            ${color}cc 0%,
            ${color}55 30%,
            #0d1a2e 65%,
            #050a14 100%)
        `,
        boxShadow: `
          0 0 0 1px ${color}30,
          0 0 24px ${color}50,
          0 0 60px ${color}20,
          inset 0 2px 8px rgba(255,255,255,0.18)
        `,
        transform: `scale(${pulseScale})`,
        transition: "background 0.8s ease, box-shadow 0.8s ease",
        display: "flex", alignItems: "center", justifyContent: "center",
        position: "relative",
        zIndex: 2,
      }}>
        {/* Specular highlight */}
        <div style={{
          position: "absolute", top: 18, left: 28,
          width: 34, height: 20,
          borderRadius: "50%",
          background: "radial-gradient(ellipse, rgba(255,255,255,0.55), transparent)",
          filter: "blur(3px)",
        }} />

        {/* Eyes */}
        <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
          {[0, 1].map((i) => (
            <div key={i} style={{
              width: 18, height: 18 * eyeScaleY,
              borderRadius: "50%",
              background: `radial-gradient(circle at 40% 40%, white, ${color})`,
              boxShadow: `0 0 ${8 * eyeGlow}px ${color}, 0 0 ${20 * eyeGlow}px ${color}80`,
              transition: "box-shadow 0.1s",
            }} />
          ))}
        </div>
      </div>

      {/* Speaking voice wave */}
      {state === "speaking" && (
        <div style={{
          display: "flex", alignItems: "center", gap: 4,
          marginTop: 28, height: 36,
        }}>
          {bars.map((amp, i) => (
            <div key={i} style={{
              width: 4, borderRadius: 3,
              height: `${Math.max(4, amp * 36)}px`,
              background: color,
              opacity: 0.7 + amp * 0.3,
              transition: "height 0.05s ease",
            }} />
          ))}
        </div>
      )}

      {/* Idle/Listening dots */}
      {(state === "idle" || state === "listening") && (
        <div style={{ display: "flex", gap: 6, marginTop: 32 }}>
          {[0, 1, 2].map((i) => {
            const phase = sec * 4 + i * 1.2;
            const op = 0.3 + 0.5 * (0.5 + 0.5 * Math.sin(phase));
            const scale = 0.7 + 0.5 * (0.5 + 0.5 * Math.sin(phase));
            return (
              <div key={i} style={{
                width: 6, height: 6, borderRadius: "50%",
                background: color,
                opacity: op,
                transform: `scale(${scale})`,
              }} />
            );
          })}
        </div>
      )}

      {/* Thinking spinner */}
      {state === "thinking" && (
        <div style={{ marginTop: 28 }}>
          <svg width={32} height={32}>
            <circle cx={16} cy={16} r={11} fill="none" stroke={color} strokeWidth={2.5}
              strokeOpacity={0.3} />
            <path
              d={`M 16 5 A 11 11 0 0 1 ${16 + 11 * Math.sin(sec * 4)} ${16 - 11 * Math.cos(sec * 4)}`}
              fill="none" stroke={color} strokeWidth={2.5} strokeLinecap="round"
            />
          </svg>
        </div>
      )}

      {/* Status label */}
      <div style={{
        marginTop: 24, fontSize: 15, fontWeight: 500,
        color: color, letterSpacing: "0.03em",
        textShadow: `0 0 12px ${color}80`,
        transition: "color 0.8s ease",
        opacity: 0.9,
      }}>
        {stateLabels[state]}
      </div>

      {/* State toggle buttons */}
      <div style={{ display: "flex", gap: 8, marginTop: 28, flexWrap: "wrap", justifyContent: "center" }}>
        {STATES.map((s) => (
          <button key={s} onClick={() => setState(s)} style={{
            background: state === s ? color + "22" : "transparent",
            border: `1px solid ${color}40`,
            borderRadius: 8, color: state === s ? color : "#555",
            fontSize: 11, padding: "5px 10px", cursor: "pointer",
            fontFamily: "inherit", transition: "all 0.3s",
          }}>
            {s}
          </button>
        ))}
      </div>

      {/* Bottom label */}
      <div style={{
        position: "absolute", bottom: 28,
        fontSize: 11, color: "#333", letterSpacing: "0.15em", textTransform: "uppercase",
      }}>
        Snowball · Orb Face
      </div>
    </div>
  );
}
