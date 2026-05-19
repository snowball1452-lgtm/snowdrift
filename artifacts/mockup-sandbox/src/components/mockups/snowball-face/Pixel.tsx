import { useEffect, useState, useRef } from "react";

const STATES = ["idle", "listening", "thinking", "speaking"] as const;
type FaceState = typeof STATES[number];

function useAnimLoop(fps = 20) {
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

// 8x8 face pixel map: 1=filled, 0=empty
const FACE_BASE = [
  [0,0,1,1,1,1,0,0],
  [0,1,1,1,1,1,1,0],
  [1,1,0,1,1,0,1,1],
  [1,1,1,1,1,1,1,1],
  [1,1,0,0,0,0,1,1],
  [1,1,1,0,0,1,1,1],
  [0,1,1,1,1,1,1,0],
  [0,0,1,1,1,1,0,0],
];

const FACE_BLINK = [
  [0,0,1,1,1,1,0,0],
  [0,1,1,1,1,1,1,0],
  [1,1,1,1,1,1,1,1],
  [1,1,1,1,1,1,1,1],
  [1,1,0,0,0,0,1,1],
  [1,1,1,0,0,1,1,1],
  [0,1,1,1,1,1,1,0],
  [0,0,1,1,1,1,0,0],
];

const FACE_THINKING = [
  [0,0,1,1,1,1,0,0],
  [0,1,1,1,1,1,1,0],
  [1,1,0,1,1,0,1,1],
  [1,1,1,1,1,1,1,1],
  [1,1,1,1,1,1,1,1],
  [1,0,1,1,1,1,0,1],
  [0,1,1,1,1,1,1,0],
  [0,0,1,1,1,1,0,0],
];

const FACE_SPEAKING = [
  [0,0,1,1,1,1,0,0],
  [0,1,1,1,1,1,1,0],
  [1,1,0,1,1,0,1,1],
  [1,1,1,1,1,1,1,1],
  [1,0,1,1,1,1,0,1],
  [1,1,0,1,1,0,1,1],
  [0,1,1,1,1,1,1,0],
  [0,0,1,1,1,1,0,0],
];

const FACE_LISTENING = [
  [0,0,1,1,1,1,0,0],
  [0,1,1,1,1,1,1,0],
  [1,1,1,1,1,1,1,1],
  [1,0,1,1,1,1,0,1],
  [1,1,0,1,1,0,1,1],
  [1,1,1,0,0,1,1,1],
  [0,1,1,1,1,1,1,0],
  [0,0,1,1,1,1,0,0],
];

export function Pixel() {
  const t = useAnimLoop(20);
  const [state, setState] = useState<FaceState>("idle");
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setState((s) => {
        const idx = STATES.indexOf(s);
        return STATES[(idx + 1) % STATES.length];
      });
    }, 2500);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const id = setInterval(() => setFrame((f) => f + 1), 150);
    return () => clearInterval(id);
  }, []);

  const sec = t / 1000;

  const stateColors: Record<FaceState, string> = {
    idle:      "#00e676",
    listening: "#40c4ff",
    thinking:  "#ffd740",
    speaking:  "#ff6d00",
  };

  const color = stateColors[state];

  const isBlink = Math.floor(sec / 3) % 4 === 0 && (sec % 3) < 0.25;

  const faceMap = isBlink
    ? FACE_BLINK
    : state === "thinking"
    ? FACE_THINKING
    : state === "speaking"
    ? (frame % 2 === 0 ? FACE_SPEAKING : FACE_BASE)
    : state === "listening"
    ? (frame % 3 === 0 ? FACE_LISTENING : FACE_BASE)
    : FACE_BASE;

  const PIXEL = 14;
  const GAP = 2;

  // Scanline flicker
  const scanline = Math.floor(sec * 8) % 10;

  // Speaking bars (retro style)
  const bars = Array.from({ length: 16 }, (_, i) => {
    if (state !== "speaking") return 1;
    const v = Math.abs(Math.sin(sec * (4 + i * 1.3) + i * 0.5));
    return Math.floor(1 + v * 7);
  });

  // Idle: scrolling matrix chars
  const matrixChars = "01SnOwBaLl10";

  return (
    <div style={{
      width: "100%", height: "100vh",
      background: "#0a0a0a",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      fontFamily: "'Courier New', Courier, monospace",
      overflow: "hidden", position: "relative",
    }}>
      {/* Scanline overlay */}
      {Array.from({ length: 30 }, (_, i) => (
        <div key={i} style={{
          position: "absolute", left: 0, right: 0,
          top: i * 26, height: 1,
          background: "rgba(0,255,0,0.03)",
          pointerEvents: "none",
        }} />
      ))}

      {/* CRT glow border */}
      <div style={{
        position: "absolute", inset: 8,
        border: `1px solid ${color}30`,
        borderRadius: 4,
        boxShadow: `0 0 20px ${color}15, inset 0 0 20px ${color}08`,
        pointerEvents: "none",
      }} />

      {/* Header bar */}
      <div style={{
        position: "absolute", top: 20,
        display: "flex", alignItems: "center", gap: 8,
        fontSize: 10, color: color, letterSpacing: "0.2em",
        textTransform: "uppercase", opacity: 0.7,
      }}>
        <span style={{ opacity: 0.5 + 0.5 * Math.sin(sec * 3) }}>▮</span>
        SNOWBALL_OS v2.0
        <span style={{ opacity: 0.5 + 0.5 * Math.sin(sec * 3 + 1) }}>▮</span>
      </div>

      {/* State indicator row */}
      <div style={{
        display: "flex", gap: 16, marginBottom: 24,
        fontSize: 10, color: "#333", letterSpacing: "0.12em",
      }}>
        {STATES.map((s) => (
          <span key={s} style={{ color: state === s ? color : "#333", transition: "color 0.2s" }}>
            {state === s ? `[${s.toUpperCase()}]` : s}
          </span>
        ))}
      </div>

      {/* Pixel face grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: `repeat(8, ${PIXEL}px)`,
        gap: `${GAP}px`,
        filter: `drop-shadow(0 0 8px ${color}80)`,
        transition: "filter 0.3s",
      }}>
        {faceMap.map((row, ri) =>
          row.map((cell, ci) => (
            <div key={`${ri}-${ci}`} style={{
              width: PIXEL, height: PIXEL,
              background: cell
                ? (ri === scanline % 8 && state === "idle" ? `${color}cc` : color)
                : "transparent",
              border: cell ? "none" : `1px solid ${color}12`,
              opacity: cell ? (state === "thinking" && frame % 4 === ri % 4 ? 0.6 : 1) : 1,
              transition: "background 0.05s, opacity 0.1s",
            }} />
          ))
        )}
      </div>

      {/* Speaking bars (pixel style) */}
      {state === "speaking" && (
        <div style={{
          display: "flex", alignItems: "flex-end", gap: 2,
          height: 40, marginTop: 20,
        }}>
          {bars.map((h, i) => (
            <div key={i} style={{
              width: PIXEL - 2, height: `${h * 5}px`,
              background: i % 2 === 0 ? color : `${color}99`,
              transition: "height 0.08s",
            }} />
          ))}
        </div>
      )}

      {/* Thinking: scanning dots */}
      {state === "thinking" && (
        <div style={{ marginTop: 20, display: "flex", gap: 8 }}>
          {[0,1,2,3,4,5,6,7].map((i) => {
            const lit = Math.floor(sec * 8) % 8 === i;
            return (
              <div key={i} style={{
                width: 8, height: 8,
                background: lit ? color : `${color}20`,
                transition: "background 0.05s",
              }} />
            );
          })}
        </div>
      )}

      {/* Idle: scrolling text */}
      {state === "idle" && (
        <div style={{ marginTop: 20, overflow: "hidden", width: 130 }}>
          <div style={{
            fontSize: 10, color: `${color}60`, letterSpacing: "0.15em",
            whiteSpace: "nowrap",
            transform: `translateX(${-(sec * 24) % 80}px)`,
          }}>
            {matrixChars.repeat(4)}
          </div>
        </div>
      )}

      {/* Listening: input bar */}
      {state === "listening" && (
        <div style={{
          marginTop: 20,
          width: 120, height: 3,
          background: `${color}20`,
          borderRadius: 2, overflow: "hidden",
        }}>
          <div style={{
            width: `${50 + 50 * Math.abs(Math.sin(sec * 3))}%`,
            height: "100%", background: color,
            transition: "width 0.1s",
          }} />
        </div>
      )}

      {/* Status line */}
      <div style={{
        marginTop: 28, fontSize: 11, color: color,
        letterSpacing: "0.1em", opacity: 0.8,
      }}>
        {state === "idle"      && "> STANDBY_"}
        {state === "listening" && "> RECV_INPUT" + (frame % 2 === 0 ? "_" : "")}
        {state === "thinking"  && "> PROC" + ".".repeat((frame % 4) + 1)}
        {state === "speaking"  && "> TX_AUDIO_" + (frame % 2 === 0 ? "▶" : "▷")}
      </div>

      {/* Toggle buttons */}
      <div style={{ display: "flex", gap: 6, marginTop: 24, flexWrap: "wrap", justifyContent: "center" }}>
        {STATES.map((s) => (
          <button key={s} onClick={() => setState(s)} style={{
            background: state === s ? `${color}20` : "transparent",
            border: `1px solid ${color}40`,
            borderRadius: 2, color: state === s ? color : "#444",
            fontSize: 10, padding: "4px 10px", cursor: "pointer",
            fontFamily: "inherit", letterSpacing: "0.1em", textTransform: "uppercase",
          }}>
            {s}
          </button>
        ))}
      </div>

      {/* Bottom label */}
      <div style={{
        position: "absolute", bottom: 20,
        fontSize: 9, color: "#2a2a2a", letterSpacing: "0.2em", textTransform: "uppercase",
      }}>
        SNOWBALL · PIXEL_FACE · 8BIT_REV
      </div>
    </div>
  );
}
