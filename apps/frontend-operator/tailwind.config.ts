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
        border: "#263241",
        input: "#263241",
        background: "#0B0F14",
        foreground: "#E6EDF3",
        panel: "#121821",
        elevated: "#1A2330",
        muted: "#9BA7B4",
        active: "#3B82F6",
        finding: "#8B5CF6",
        intelligence: "#6366F1",
        review: "#F59E0B",
        blocked: "#F97316",
        danger: "#EF4444",
        success: "#22C55E",
        primary: "#3B82F6",
        secondary: "#1A2330",
        card: "#121821",
        destructive: "#EF4444"
      }
    }
  },
  plugins: []
};

export default config;
