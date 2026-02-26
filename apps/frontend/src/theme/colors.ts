/**
 * Kaison K1 - Color System
 * Dark IDE aesthetic with Matrix neon green accents
 */

export const K1_COLORS = {
  // Base (IDE dark mode)
  charcoal: {
    base: '#121212',      // Primary background
    light: '#1E1E1E',     // Cards/panels
    lighter: '#2D2D2D',   // Hover states
    border: '#3D3D3D',    // Borders
  },

  // Accent (Matrix neon green)
  neon: {
    green: '#00FF41',       // Primary accent
    greenDim: '#00CC34',    // Secondary accent
    greenGlow: '#00FF4155', // Glow effect (with alpha)
    greenDark: '#009929',   // Pressed state
  },

  // Status colors
  status: {
    critical: '#FF1744',   // Red
    high: '#FF9800',       // Orange
    medium: '#FFC107',     // Yellow
    low: '#4CAF50',        // Green
    info: '#2196F3',       // Blue
    success: '#00FF41',    // Neon green
  },

  // Neutral
  neutral: {
    white: '#E0E0E0',      // Text
    gray: '#9E9E9E',       // Secondary text
    darkGray: '#424242',   // Disabled
  },

  // Semantic
  text: {
    primary: '#E0E0E0',
    secondary: '#9E9E9E',
    disabled: '#424242',
    inverse: '#121212',
  },

  background: {
    default: '#121212',
    paper: '#1E1E1E',
    elevated: '#2D2D2D',
  }
};

// Export individual color groups for convenience
export const { charcoal, neon, status, neutral, text, background } = K1_COLORS;
