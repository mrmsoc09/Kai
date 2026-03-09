/**
 * Kaison K1 - Color System
 * Hunter green + black lettering with orange/purple highlights
 */

export const K1_COLORS = {
  // Base (IDE dark mode)
  charcoal: {
    base: '#0B0C0D',      // Primary background
    light: '#111316',     // Cards/panels
    lighter: '#1A1D21',   // Hover states
    border: '#4E7A57',    // Borders (green boxes)
  },

  // Accent (Hunter green)
  neon: {
    green: '#355E3B',       // Primary accent
    greenDim: '#3F6A44',    // Secondary accent
    greenGlow: '#355E3B40', // Glow effect (with alpha)
    greenDark: '#2A4A31',   // Pressed state
  },

  // Status colors
  status: {
    critical: '#A12B2B',   // Deep red
    error: '#A12B2B',      // Error red (alias)
    warning: '#D97706',    // Warning orange (alias)
    high: '#D97706',       // Orange
    medium: '#E0A43A',     // Amber
    low: '#355E3B',        // Hunter green
    info: '#5A2E8A',       // Purple
    success: '#355E3B',    // Hunter green
  },

  // Neutral
  neutral: {
    white: '#8FAF9B',      // Primary text (muted green)
    gray: '#6F8E7A',       // Secondary text
    darkGray: '#3A4F43',   // Disabled
  },

  // Semantic
  text: {
    primary: '#8FAF9B',
    secondary: '#6F8E7A',
    disabled: '#3A4F43',
    inverse: '#0B0C0D',
  },

  background: {
    default: '#0B0C0D',
    paper: '#111316',
    elevated: '#1A1D21',
  }
};

// Export individual color groups for convenience
export const { charcoal, neon, status, neutral, text, background } = K1_COLORS;
