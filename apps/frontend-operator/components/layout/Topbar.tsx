"use client";

import Image from "next/image";
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
  return (
    <span style={{ color: "#007A1E", fontFamily: "IBM Plex Mono, monospace", fontSize: "0.7rem" }}>
      {time}
    </span>
  );
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
      className="border-b border-border px-4 py-2"
      style={{ background: "rgba(0,0,0,0.95)" }}
    >
      <div className="flex items-center justify-between gap-4">

        {/* ── Brand section ─────────────────────────────────────── */}
        <div className="flex items-center gap-3">

          {/* Logo — circular badge with gold glow */}
          <div
            style={{
              position: "relative",
              width: 52,
              height: 52,
              flexShrink: 0,
              borderRadius: "50%",
              border: "1px solid rgba(180,140,30,0.5)",
              boxShadow:
                "0 0 10px rgba(180,140,30,0.35), 0 0 24px rgba(180,140,30,0.15), inset 0 0 8px rgba(0,0,0,0.8)",
              overflow: "hidden",
              background: "#0a0a0a",
            }}
          >
            <Image
              src="/kai-logo.png"
              alt="KAISON AI Logo"
              width={52}
              height={52}
              priority
              style={{ objectFit: "cover", borderRadius: "50%" }}
            />
          </div>

          {/* Text block */}
          <div>
            {/* Super-label */}
            <p
              style={{
                fontSize: "0.55rem",
                textTransform: "uppercase",
                letterSpacing: "0.25em",
                color: "#7A6000",   /* muted gold */
                fontFamily: "IBM Plex Mono, monospace",
                lineHeight: 1,
                marginBottom: 2,
              }}
            >
              KAI / K1 ▸ AUTONOMOUS HUNT PLATFORM
            </p>

            {/* Platform name with glitch */}
            <h1
              style={{
                fontSize: "1rem",
                fontWeight: 700,
                color: "#00FF41",
                textShadow: "0 0 8px #00FF41, 0 0 18px rgba(0,255,65,0.5)",
                fontFamily: "IBM Plex Mono, monospace",
                letterSpacing: "0.14em",
                lineHeight: 1.1,
              }}
            >
              {label}
              <span style={{ animation: "blink 1s step-end infinite", marginLeft: 2 }}>_</span>
            </h1>

            {/* Tagline — gold, tight spacing */}
            <p
              style={{
                fontSize: "0.55rem",
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                fontFamily: "IBM Plex Mono, monospace",
                marginTop: 2,
                /* Gold gradient to echo the logo palette */
                background: "linear-gradient(90deg, #B8860B 0%, #FFD700 50%, #B8860B 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              ◆ To Plot · To Plan · To Plunder ◆
            </p>
          </div>
        </div>

        {/* ── Right status chips ─────────────────────────────────── */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexShrink: 0 }}>
          <LiveClock />

          {/* KAISON_01 unit badge — echoes logo */}
          <div
            style={{
              borderRadius: 3,
              border: "1px solid rgba(180,140,30,0.3)",
              background: "rgba(30,20,0,0.5)",
              padding: "2px 8px",
              fontSize: "0.6rem",
              fontFamily: "IBM Plex Mono, monospace",
              color: "#7A6000",
              letterSpacing: "0.1em",
            }}
          >
            UNIT:{" "}
            <span style={{ color: "#FFD700" }}>KAISON_01</span>
          </div>

          <div
            style={{
              borderRadius: 3,
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
              borderRadius: 3,
              border: "1px solid #003300",
              background: "rgba(0,51,0,0.25)",
              padding: "2px 8px",
              fontSize: "0.65rem",
              fontFamily: "IBM Plex Mono, monospace",
              color: "#007A1E",
            }}
          >
            {/* Status dot */}
            <span
              style={{
                display: "inline-block",
                width: 5,
                height: 5,
                borderRadius: "50%",
                background: "#00FF41",
                boxShadow: "0 0 4px #00FF41",
                animation: "blink 1.4s step-end infinite",
                marginRight: 4,
                verticalAlign: "middle",
              }}
            />
            SYS:{" "}
            <span style={{ color: "#00FF41", textShadow: "0 0 4px #00FF41" }}>ONLINE</span>
          </div>
        </div>

      </div>
    </header>
  );
}
