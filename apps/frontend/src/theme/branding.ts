/**
 * Kaison K1 Unified Platform Branding
 * Centralized theme and branding constants for entire frontend
 * Updated with hunter green + black lettering + orange/purple highlights
 */

import { K1_COLORS } from './colors';

export const BRANDING = {
  name: "Kaison K1",
  tagline: "Unified Automated Bug Bounty Intelligence Platform",
  version: "7.6",
  phase: "Phase 7.6 - Platform Expansion & Intelligence Integration",
} as const;

export const COLORS = {
  // Primary brand colors — structured as objects so .main/.light/.dark work
  primary: {
    main: K1_COLORS.neon.green,
    light: K1_COLORS.neon.greenDim,
    lighter: K1_COLORS.neon.greenGlow,
    dark: K1_COLORS.neon.greenDark,
  },
  // Keep flat aliases for components that use COLORS.primaryLight etc directly
  primaryLight: K1_COLORS.neon.greenDim,
  primaryDark: K1_COLORS.neon.greenDark,
  primaryGlow: K1_COLORS.neon.greenGlow,
  // Secondary — purple highlight
  secondary: {
    main: "#5a2e8a",
    light: "#6d3aa6",
    dark: "#48226f",
  },

  // Background colors (dark IDE aesthetic)
  background: K1_COLORS.background.default,
  surface: K1_COLORS.background.paper,
  elevated: K1_COLORS.background.elevated,

  // Text colors
  text: K1_COLORS.text.primary,
  textSecondary: K1_COLORS.text.secondary,
  textDisabled: K1_COLORS.text.disabled,
  textInverse: K1_COLORS.text.inverse,

  // Status colors — spread flat AND keep nested .status object for COLORS.status.error etc
  ...K1_COLORS.status,
  status: K1_COLORS.status,

  // Border colors
  border: K1_COLORS.charcoal.border,
  borderHover: "#5a2e8a",

  // Legacy compatibility (for components not yet updated)
  neutral: {
    black: "#000000",
    white: K1_COLORS.text.primary,
    gray_50: K1_COLORS.charcoal.border,
    gray_100: K1_COLORS.charcoal.lighter,
    gray_200: K1_COLORS.charcoal.light,
    gray_300: K1_COLORS.charcoal.border,
    gray_400: K1_COLORS.neutral.gray,
    gray_500: K1_COLORS.neutral.gray,
    gray_600: K1_COLORS.neutral.darkGray,
    gray_700: K1_COLORS.charcoal.lighter,
    gray_800: K1_COLORS.charcoal.light,
    gray_900: K1_COLORS.charcoal.base,
  },

  // Semantic colors for threat levels
  severity: K1_COLORS.status,

  // DeepAgent/Reasoning colors (keep existing for compatibility)
  reasoning: {
    thinking: "#5a2e8a",      // Purple - deep thinking
    analyzing: "#6d3aa6",     // Purple - analysis step
    verifying: "#355e3b",     // Hunter green - verification
    concluding: "#d97706",    // Orange - conclusion
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

  // Typography (updated to JetBrains Mono)
  fonts: {
    family_sans: '"Space Grotesk", "JetBrains Mono", "Segoe UI", sans-serif',
    family_mono: "'JetBrains Mono', 'Fira Code', 'Consolas', 'Courier New', monospace",
    size_xs: "0.75rem",    // 12px
    size_sm: "0.875rem",   // 14px
    size_base: "1rem",     // 16px
    size_lg: "1.125rem",   // 18px
    size_xl: "1.5rem",     // 24px
    size_2xl: "2rem",      // 32px
    size_3xl: "2.5rem",    // 40px
  },

  // Shadows (updated with neon glow)
  shadow: {
    none: "none",
    sm: "0 1px 2px 0 rgba(0, 0, 0, 0.3)",
    md: "0 4px 12px rgba(0, 0, 0, 0.5)",
    lg: "0 8px 24px rgba(0, 0, 0, 0.7)",
    xl: "0 12px 32px rgba(0, 0, 0, 0.8)",
    glow: `0 0 20px ${K1_COLORS.neon.greenGlow}`,
    glowStrong: `0 0 30px ${K1_COLORS.neon.greenGlow}, 0 0 60px ${K1_COLORS.neon.greenGlow}`,
  },

  // Transitions
  transition: {
    fast: "150ms ease-in-out",
    base: "250ms ease-in-out",
    slow: "400ms ease-in-out",
    function: "cubic-bezier(0.4, 0, 0.2, 1)",
  },
} as const;

export const COMPONENT_STYLES = {
  button: {
    primary: {
      backgroundColor: COLORS.primary.main,
      color: COLORS.textInverse,
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
      color: COLORS.textInverse,
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
      backgroundColor: COLORS.surface,
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
      color: COLORS.textInverse,
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
    backgroundColor: COLORS.surface,
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
