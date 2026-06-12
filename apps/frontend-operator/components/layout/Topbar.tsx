"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import { useOperatorTheme } from "@/lib/theme";

function LiveClock() {
  const [time, setTime] = useState("");
  useEffect(() => {
    const tick = () =>
      setTime(new Date().toISOString().replace("T", " ").substring(0, 19) + " UTC");
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  const { colors } = useOperatorTheme();
  return (
    <span style={{ color: colors.highlight, fontFamily: "IBM Plex Mono, monospace", fontSize: "0.7rem" }}>
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
  const { mode, toggleMode, colors } = useOperatorTheme();

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
      className="border-b px-4 py-2"
      style={{
        background: colors.panelSoft,
        borderBottomColor: colors.border,
        backdropFilter: "blur(10px)",
      }}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div
            style={{
              position: "relative",
              width: 52,
              height: 52,
              flexShrink: 0,
              borderRadius: "50%",
              border: `1px solid ${colors.highlight}66`,
              boxShadow:
                mode === "dark"
                  ? `0 0 10px ${colors.highlight}40, 0 0 24px ${colors.highlight}22, inset 0 0 8px rgba(0,0,0,0.8)`
                  : `0 0 10px ${colors.highlight}22, inset 0 0 8px rgba(0,0,0,0.15)`,
              overflow: "hidden",
              background: colors.shellBg,
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

          <div>
            <p
              style={{
                fontSize: "0.55rem",
                textTransform: "uppercase",
                letterSpacing: "0.25em",
                color: colors.highlight,
                fontFamily: "IBM Plex Mono, monospace",
                lineHeight: 1,
                marginBottom: 2,
              }}
            >
              KAI / K1 ▸ AUTONOMOUS HUNT PLATFORM
            </p>

            <h1
              style={{
                fontSize: "1rem",
                fontWeight: 700,
                color: colors.accent,
                textShadow: mode === "dark" ? `0 0 8px ${colors.accent}, 0 0 18px rgba(0,255,65,0.5)` : "none",
                fontFamily: "IBM Plex Mono, monospace",
                letterSpacing: "0.14em",
                lineHeight: 1.1,
              }}
            >
              {label}
              <span style={{ animation: "blink 1s step-end infinite", marginLeft: 2 }}>_</span>
            </h1>

            <p
              style={{
                fontSize: "0.55rem",
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                fontFamily: "IBM Plex Mono, monospace",
                marginTop: 2,
                background: `linear-gradient(90deg, ${colors.highlight} 0%, #ffd87a 50%, ${colors.highlight} 100%)`,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              ◆ To Plot · To Plan · To Plunder ◆
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexShrink: 0 }}>
          <LiveClock />

          <div
            style={{
              borderRadius: 3,
              border: `1px solid ${colors.highlight}4d`,
              background: mode === "dark" ? "rgba(30,20,0,0.5)" : colors.panelElevated,
              padding: "2px 8px",
              fontSize: "0.6rem",
              fontFamily: "IBM Plex Mono, monospace",
              color: colors.highlight,
              letterSpacing: "0.1em",
            }}
          >
            UNIT: <span style={{ color: colors.highlight }}>KAISON_01</span>
          </div>

          <div
            style={{
              borderRadius: 3,
              border: `1px solid ${colors.border}`,
              background: mode === "dark" ? "rgba(0,51,0,0.25)" : colors.panelElevated,
              padding: "2px 8px",
              fontSize: "0.65rem",
              fontFamily: "IBM Plex Mono, monospace",
              color: colors.textMuted,
            }}
          >
            API: <span style={{ color: colors.accent }}>{process.env.NEXT_PUBLIC_API_BASE_URL ?? "localhost:8080"}</span>
          </div>

          <div
            style={{
              borderRadius: 3,
              border: `1px solid ${colors.border}`,
              background: mode === "dark" ? "rgba(0,51,0,0.25)" : colors.panelElevated,
              padding: "2px 8px",
              fontSize: "0.65rem",
              fontFamily: "IBM Plex Mono, monospace",
              color: colors.textMuted,
            }}
          >
            <span
              style={{
                display: "inline-block",
                width: 5,
                height: 5,
                borderRadius: "50%",
                background: colors.success,
                boxShadow: `0 0 4px ${colors.success}`,
                animation: "blink 1.4s step-end infinite",
                marginRight: 4,
                verticalAlign: "middle",
              }}
            />
            SYS: <span style={{ color: colors.success, textShadow: mode === "dark" ? `0 0 4px ${colors.success}` : "none" }}>ONLINE</span>
          </div>

          <button
            type="button"
            onClick={toggleMode}
            title={`Switch to ${mode === "dark" ? "light" : "dark"} theme`}
            style={{
              borderRadius: 999,
              border: `1px solid ${colors.border}`,
              background: colors.panelElevated,
              padding: "3px 10px",
              fontSize: "0.62rem",
              fontFamily: "IBM Plex Mono, monospace",
              color: colors.text,
              letterSpacing: "0.1em",
              cursor: "pointer",
            }}
          >
            {mode === "dark" ? "☼ LIGHT" : "☾ DARK"}
          </button>
        </div>
      </div>
    </header>
  );
}
