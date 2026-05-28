"use client";

import { useEffect, useState } from "react";

function LiveClock() {
  const [time, setTime] = useState("");
  useEffect(() => {
    const tick = () =>
      setTime(new Date().toISOString().replace("T", " ").substring(0, 19) + " UTC");
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return <span style={{ color: "#007A1E", fontFamily: "IBM Plex Mono, monospace", fontSize: "0.7rem" }}>{time}</span>;
}

const GLITCH_CHARS = "!#$%&01<>[]{}|*";
function glitchText(text: string) {
  return text
    .split("")
    .map((c) =>
      Math.random() < 0.15
        ? GLITCH_CHARS[Math.floor(Math.random() * GLITCH_CHARS.length)]
        : c
    )
    .join("");
}

export function Topbar() {
  const [label, setLabel] = useState("OPERATOR CONSOLE");

  useEffect(() => {
    const glitch = () => {
      setLabel(glitchText("OPERATOR CONSOLE"));
      const t = setTimeout(() => setLabel("OPERATOR CONSOLE"), 120);
      return t;
    };
    const id = setInterval(glitch, 4500 + Math.random() * 2000);
    return () => clearInterval(id);
  }, []);

  return (
    <header
      className="border-b border-border px-4 py-3"
      style={{ background: "rgba(0,0,0,0.92)" }}
    >
      <div className="flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-3">
          {/* Animated status dot */}
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "#00FF41",
              boxShadow: "0 0 6px #00FF41, 0 0 14px #00FF41",
              animation: "blink 1.4s step-end infinite",
            }}
          />
          <div>
            <p
              style={{
                fontSize: "0.6rem",
                textTransform: "uppercase",
                letterSpacing: "0.22em",
                color: "#007A1E",
                fontFamily: "IBM Plex Mono, monospace",
              }}
            >
              KAI / K1 ▸ AUTONOMOUS HUNT PLATFORM
            </p>
            <h1
              style={{
                fontSize: "1rem",
                fontWeight: 700,
                color: "#00FF41",
                textShadow: "0 0 8px #00FF41, 0 0 18px rgba(0,255,65,0.5)",
                fontFamily: "IBM Plex Mono, monospace",
                letterSpacing: "0.14em",
              }}
            >
              {label}
              <span style={{ animation: "blink 1s step-end infinite", marginLeft: 2 }}>_</span>
            </h1>
          </div>
        </div>

        {/* Right status chips */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <LiveClock />

          <div
            style={{
              borderRadius: 4,
              border: "1px solid #003300",
              background: "rgba(0,51,0,0.25)",
              padding: "2px 8px",
              fontSize: "0.65rem",
              fontFamily: "IBM Plex Mono, monospace",
              color: "#007A1E",
            }}
          >
            API:{" "}
            <span style={{ color: "#00FF41" }}>
              {process.env.NEXT_PUBLIC_API_BASE_URL ?? "localhost:8080"}
            </span>
          </div>

          <div
            style={{
              borderRadius: 4,
              border: "1px solid #003300",
              background: "rgba(0,51,0,0.25)",
              padding: "2px 8px",
              fontSize: "0.65rem",
              fontFamily: "IBM Plex Mono, monospace",
              color: "#007A1E",
            }}
          >
            SYS:{" "}
            <span style={{ color: "#00FF41", textShadow: "0 0 4px #00FF41" }}>ONLINE</span>
          </div>
        </div>
      </div>
    </header>
  );
}
