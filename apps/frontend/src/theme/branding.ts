/**
 * Kaison K1 Unified Platform Branding
 * Centralized theme and branding constants for entire frontend
 */

export const BRANDING = {
  name: "Kaison K1",
  tagline: "Unified Automated Bug Bounty Intelligence Platform",
  version: "7.0",
  phase: "Phase 7 - AI-Active Multi-Agent System",
} as const;

export const COLORS = {
  // Primary brand colors
  primary: {
    main: "#1a472a",      // Deep forest green
    light: "#2d7a47",     // Medium green
    lighter: "#45a369",   // Light green
    contrast: "#ffffff",  // White text on primary
  },

  // Secondary colors
  secondary: {
    main: "#d4571e",      // Deep orange (accent)
    light: "#ff7a3d",     // Light orange
    contrast: "#ffffff",
  },

  // Status colors (consistent across all systems)
  status: {
    success: "#22c55e",   // Bright green
    warning: "#f59e0b",   // Amber
    error: "#ef4444",     // Red
    info: "#3b82f6",      // Blue
    pending: "#8b5cf6",   // Purple
  },

  // Neutral palette
  neutral: {
    black: "#000000",
    white: "#ffffff",
    gray_50: "#f9fafb",
    gray_100: "#f3f4f6",
    gray_200: "#e5e7eb",
    gray_300: "#d1d5db",
    gray_400: "#9ca3af",
    gray_500: "#6b7280",
    gray_600: "#4b5563",
    gray_700: "#374151",
    gray_800: "#1f2937",
    gray_900: "#111827",
  },

  // Semantic colors for threat levels
  severity: {
    critical: "#dc2626",      // Dark red
    high: "#ea580c",          // Orange-red
    medium: "#eab308",        // Yellow
    low: "#84cc16",           // Light green
    info: "#0ea5e9",          // Cyan
  },

  // DeepAgent/Reasoning colors
  reasoning: {
    thinking: "#8b5cf6",      // Purple - deep thinking
    analyzing: "#06b6d4",     // Cyan - analysis step
    verifying: "#10b981",     // Green - verification
    concluding: "#f59e0b",    // Amber - conclusion
  },
} as const;

export const UI = {
  // Border radius for modern design
  borderRadius: {
    none: "0",
    small: "4px",
    medium: "8px",
    large: "12px",
    xl: "16px",
    full: "9999px",
  },

  // Spacing scale (8px base)
  spacing: {
    xs: "4px",
    sm: "8px",
    md: "16px",
    lg: "24px",
    xl: "32px",
    xxl: "48px",
  },

  // Typography
  fonts: {
    family_sans: '"Segoe UI", Roboto, "Helvetica Neue", sans-serif',
    family_mono: '"Fira Code", "Monaco", "Courier New", monospace',
    size_xs: "12px",
    size_sm: "14px",
    size_base: "16px",
    size_lg: "18px",
    size_xl: "20px",
    size_2xl: "24px",
    size_3xl: "30px",
  },

  // Shadows
  shadow: {
    none: "none",
    sm: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
    md: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
    lg: "0 10px 15px -3px rgba(0, 0, 0, 0.1)",
    xl: "0 20px 25px -5px rgba(0, 0, 0, 0.1)",
  },

  // Transitions
  transition: {
    fast: "150ms",
    base: "250ms",
    slow: "350ms",
    function: "cubic-bezier(0.4, 0, 0.2, 1)",
  },
} as const;

export const COMPONENT_STYLES = {
  button: {
    primary: {
      backgroundColor: COLORS.primary.main,
      color: COLORS.neutral.white,
      borderRadius: UI.borderRadius.medium,
      padding: `${UI.spacing.sm} ${UI.spacing.md}`,
      cursor: "pointer",
      border: "none",
      fontSize: UI.fonts.size_base,
      fontWeight: 600,
      transition: `all ${UI.transition.base} ${UI.transition.function}`,
      "&:hover": {
        backgroundColor: COLORS.primary.light,
        boxShadow: UI.shadow.md,
      },
      "&:active": {
        backgroundColor: COLORS.primary.main,
      },
    },
    secondary: {
      backgroundColor: COLORS.secondary.main,
      color: COLORS.neutral.white,
      borderRadius: UI.borderRadius.medium,
      padding: `${UI.spacing.sm} ${UI.spacing.md}`,
      cursor: "pointer",
      border: "none",
      fontSize: UI.fonts.size_base,
      fontWeight: 600,
      transition: `all ${UI.transition.base} ${UI.transition.function}`,
      "&:hover": {
        backgroundColor: COLORS.secondary.light,
      },
    },
    outline: {
      backgroundColor: COLORS.neutral.white,
      color: COLORS.primary.main,
      borderRadius: UI.borderRadius.medium,
      padding: `${UI.spacing.sm} ${UI.spacing.md}`,
      cursor: "pointer",
      border: `2px solid ${COLORS.primary.main}`,
      fontSize: UI.fonts.size_base,
      fontWeight: 600,
      transition: `all ${UI.transition.base} ${UI.transition.function}`,
      "&:hover": {
        backgroundColor: COLORS.primary.lighter + "20",
      },
    },
    danger: {
      backgroundColor: COLORS.status.error,
      color: COLORS.neutral.white,
      borderRadius: UI.borderRadius.medium,
      padding: `${UI.spacing.sm} ${UI.spacing.md}`,
      cursor: "pointer",
      border: "none",
      fontSize: UI.fonts.size_base,
      fontWeight: 600,
      "&:hover": {
        opacity: 0.9,
      },
    },
  },

  card: {
    backgroundColor: COLORS.neutral.white,
    borderRadius: UI.borderRadius.large,
    border: `1px solid ${COLORS.neutral.gray_200}`,
    boxShadow: UI.shadow.md,
    padding: UI.spacing.lg,
  },

  alert: {
    success: {
      backgroundColor: COLORS.status.success + "10",
      borderLeft: `4px solid ${COLORS.status.success}`,
      padding: UI.spacing.md,
      borderRadius: UI.borderRadius.small,
    },
    warning: {
      backgroundColor: COLORS.status.warning + "10",
      borderLeft: `4px solid ${COLORS.status.warning}`,
      padding: UI.spacing.md,
      borderRadius: UI.borderRadius.small,
    },
    error: {
      backgroundColor: COLORS.status.error + "10",
      borderLeft: `4px solid ${COLORS.status.error}`,
      padding: UI.spacing.md,
      borderRadius: UI.borderRadius.small,
    },
    info: {
      backgroundColor: COLORS.status.info + "10",
      borderLeft: `4px solid ${COLORS.status.info}`,
      padding: UI.spacing.md,
      borderRadius: UI.borderRadius.small,
    },
  },
} as const;

// Icon mappings using Unicode symbols
export const ICONS = {
  success: "✓",
  error: "✕",
  warning: "⚠",
  info: "ℹ",
  thinking: "🧠",
  tool: "🔧",
  database: "💾",
  network: "🌐",
  shield: "🛡",
  lightning: "⚡",
  gear: "⚙",
  loading: "⌛",
} as const;

// Severity color mapping
export const SEVERITY_COLORS = {
  critical: COLORS.severity.critical,
  high: COLORS.severity.high,
  medium: COLORS.severity.medium,
  low: COLORS.severity.low,
  info: COLORS.severity.info,
} as const;

// Tool category colors
export const CATEGORY_COLORS: Record<string, string> = {
  osint: COLORS.primary.light,
  scanner: COLORS.secondary.main,
  cti: COLORS.reasoning.analyzing,
  analysis: COLORS.reasoning.thinking,
  validation: COLORS.status.success,
  reporting: COLORS.primary.main,
  orchestration: COLORS.reasoning.verifying,
  reasoning: COLORS.reasoning.thinking,
} as const;

// Create CSS custom properties (for use in CSS files)
export const generateCSSVariables = () => {
  const vars: Record<string, string> = {};

  // Colors
  Object.entries(COLORS).forEach(([key, value]) => {
    if (typeof value === "object") {
      Object.entries(value).forEach(([subkey, subvalue]) => {
        vars[`--color-${key}-${subkey}`] = subvalue as string;
      });
    }
  });

  // UI
  Object.entries(UI).forEach(([key, value]) => {
    if (typeof value === "object") {
      Object.entries(value).forEach(([subkey, subvalue]) => {
        if (typeof subvalue === "string") {
          vars[`--ui-${key}-${subkey}`] = subvalue;
        }
      });
    }
  });

  return vars;
};

// Default theme configuration
export const DEFAULT_THEME = {
  colors: COLORS,
  ui: UI,
  components: COMPONENT_STYLES,
  icons: ICONS,
} as const;

export type Theme = typeof DEFAULT_THEME;
export type ThemeColors = typeof COLORS;
export type ThemeUI = typeof UI;
