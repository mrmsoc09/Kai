"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type OperatorThemeMode = "dark" | "light";

export type OperatorThemeColors = {
  mode: OperatorThemeMode;
  shellBg: string;
  pageBg: string;
  panel: string;
  panelElevated: string;
  panelSoft: string;
  border: string;
  borderStrong: string;
  text: string;
  textStrong: string;
  textMuted: string;
  accent: string;
  accentSoft: string;
  accentGlow: string;
  highlight: string;
  highlightSoft: string;
  warning: string;
  danger: string;
  success: string;
  inputBg: string;
  inputBorder: string;
  overlay: string;
  matrixOpacity: number;
};

const STORAGE_KEY = "k1-operator-theme";

const THEME_PRESETS: Record<OperatorThemeMode, OperatorThemeColors> = {
  dark: {
    mode: "dark",
    shellBg: "#050607",
    pageBg: "#0a0f0a",
    panel: "#0d140d",
    panelElevated: "#101910",
    panelSoft: "rgba(0, 0, 0, 0.45)",
    border: "#003300",
    borderStrong: "#006600",
    text: "#d9f7dc",
    textStrong: "#00FF41",
    textMuted: "#6a8b70",
    accent: "#00FF41",
    accentSoft: "rgba(0, 255, 65, 0.08)",
    accentGlow: "rgba(0, 255, 65, 0.32)",
    highlight: "#ff9f1a",
    highlightSoft: "rgba(255, 159, 26, 0.1)",
    warning: "#ff9f1a",
    danger: "#ff5a52",
    success: "#00FF41",
    inputBg: "#060c06",
    inputBorder: "#003300",
    overlay: "rgba(0, 0, 0, 0.72)",
    matrixOpacity: 0.45,
  },
  light: {
    mode: "light",
    shellBg: "#f4f6f8",
    pageBg: "#f7fafc",
    panel: "#ffffff",
    panelElevated: "#f9fbfd",
    panelSoft: "rgba(255, 255, 255, 0.9)",
    border: "#d7e0ea",
    borderStrong: "#b4c2d0",
    text: "#1f2937",
    textStrong: "#0f172a",
    textMuted: "#5e6b7a",
    accent: "#0f766e",
    accentSoft: "rgba(15, 118, 110, 0.08)",
    accentGlow: "rgba(15, 118, 110, 0.18)",
    highlight: "#ea580c",
    highlightSoft: "rgba(234, 88, 12, 0.12)",
    warning: "#d97706",
    danger: "#dc2626",
    success: "#0f766e",
    inputBg: "#ffffff",
    inputBorder: "#c6d2de",
    overlay: "rgba(15, 23, 42, 0.28)",
    matrixOpacity: 0,
  },
};

type ThemeContextValue = {
  mode: OperatorThemeMode;
  setMode: (mode: OperatorThemeMode) => void;
  toggleMode: () => void;
  colors: OperatorThemeColors;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readInitialMode(): OperatorThemeMode {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "dark" || stored === "light") return stored;
  if (window.matchMedia?.("(prefers-color-scheme: light)").matches) return "light";
  return "dark";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<OperatorThemeMode>(() => readInitialMode());

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = mode;
    root.style.colorScheme = mode;
    window.localStorage.setItem(STORAGE_KEY, mode);
  }, [mode]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      mode,
      setMode,
      toggleMode: () => setMode((current) => (current === "dark" ? "light" : "dark")),
      colors: THEME_PRESETS[mode],
    }),
    [mode]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useOperatorTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    return {
      mode: "dark" as OperatorThemeMode,
      setMode: () => undefined,
      toggleMode: () => undefined,
      colors: THEME_PRESETS.dark,
    };
  }
  return ctx;
}

export function getOperatorThemeColors(mode: OperatorThemeMode) {
  return THEME_PRESETS[mode];
}
