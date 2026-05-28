import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        /* ── Hacker / Matrix palette ─────────────────────── */
        border:         "#003300",
        input:          "#001a00",
        background:     "#000000",
        foreground:     "#00FF41",   /* Matrix green — primary text   */
        panel:          "#050505",
        elevated:       "#0a0a0a",
        muted:          "#007A1E",   /* dim green                     */
        active:         "#00FF41",   /* bright green                  */
        finding:        "#FF00FF",   /* magenta — findings            */
        intelligence:   "#00FFFF",   /* cyan — intel                  */
        review:         "#FFD700",   /* gold — warnings / review      */
        blocked:        "#FF6600",   /* orange — blocked              */
        danger:         "#FF3333",   /* red — errors / kill           */
        success:        "#00FF41",   /* green                         */
        primary:        "#00FF41",
        secondary:      "#0a0a0a",
        card:           "#050505",
        destructive:    "#FF3333",
      },
      fontFamily: {
        mono: ["IBM Plex Mono", "JetBrains Mono", "Fira Code", "Courier New", "monospace"],
        sans: ["IBM Plex Mono", "JetBrains Mono", "Fira Code", "Courier New", "monospace"],
      },
      animation: {
        "blink":      "blink 1s step-end infinite",
        "glitch":     "glitch 4s infinite",
        "text-glow":  "text-glow 2s ease-in-out infinite alternate",
        "flicker":    "flicker 0.12s infinite",
      },
      keyframes: {
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%":       { opacity: "0" },
        },
        glitch: {
          "0%, 88%, 100%": { transform: "translate(0)" },
          "90%":            { transform: "translate(-2px, 1px)", filter: "hue-rotate(90deg)" },
          "92%":            { transform: "translate(2px, -1px)" },
          "94%":            { transform: "translate(-1px, 0px)", filter: "hue-rotate(-90deg)" },
          "96%":            { transform: "translate(1px, 1px)" },
        },
        flicker: {
          "0%, 100%": { opacity: "1" },
          "50%":       { opacity: "0.93" },
        },
        "text-glow": {
          "0%":   { textShadow: "0 0 4px #00FF41, 0 0 8px #00FF41" },
          "100%": { textShadow: "0 0 8px #00FF41, 0 0 20px #00FF41, 0 0 40px #007A1E" },
        },
      },
      boxShadow: {
        "green-glow": "0 0 8px #00FF41, 0 0 20px rgba(0,255,65,0.3)",
        "red-glow":   "0 0 8px #FF3333, 0 0 20px rgba(255,51,51,0.3)",
        "panel-glow": "inset 0 0 30px rgba(0,255,65,0.04), 0 0 1px #003300",
      },
    }
  },
  plugins: []
};

export default config;
