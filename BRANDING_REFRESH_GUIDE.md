# Branding Refresh Guide - v7.6

This document outlines the branding updates for Kaison K1 Platform v7.6.

## New Branding Elements

### Colors (from `theme/branding.ts`)

```typescript
import { COLORS, UI, BRANDING, ICONS } from '@/theme/branding';
```

**Primary Colors:**
- `COLORS.primary.main` - Matrix neon green (#00ff41)
- `COLORS.primary.light` - Lighter neon green
- `COLORS.primary.dark` - Darker neon green

**Background:**
- `COLORS.background` - Dark IDE background
- `COLORS.surface` - Elevated surfaces
- `COLORS.elevated` - Higher elevation surfaces

**Status Colors:**
- `COLORS.status.success` - Green
- `COLORS.status.error` - Red
- `COLORS.status.warning` - Yellow/Amber
- `COLORS.status.info` - Blue
- `COLORS.status.critical` - Dark red
- `COLORS.status.high` - Orange
- `COLORS.status.medium` - Yellow
- `COLORS.status.low` - Light blue

## Components Already Updated

✅ **New Components (v7.6):**
- `CommunicationsSettings`
- `RSSIntelligenceDashboard`
- `OllamaSetup`
- `AttackSurfaceGraph`
- `AgentZeroChat` (RAG enhancement)
- `Dashboard` (new tabs)

## Components Needing Branding Refresh

The following existing components should be updated to use the new branding:

### High Priority
1. `FlowBoard.tsx`
2. `RunHUD.tsx`
3. `TopHUD.tsx`
4. `Sidebar.tsx`
5. `Layout.tsx`

### Medium Priority
6. `AgentGrid.tsx`
7. `ArsenalView.tsx`
8. `IntelTable.tsx`
9. `PersonaGrid.tsx`
10. `LogsView.tsx`

### Low Priority
11. `WizardPanel.tsx`
12. `Heatmap.tsx`
13. `KpiMini.tsx`

## Update Pattern

### Before (Old Pattern):
```tsx
<div style={{ backgroundColor: '#f5f5f5', color: '#333' }}>
  <h1 style={{ color: '#0066cc' }}>Title</h1>
</div>
```

### After (New Pattern):
```tsx
import { COLORS, UI } from '@/theme/branding';

<div style={{ backgroundColor: COLORS.background, color: COLORS.text }}>
  <h1 style={{ color: COLORS.primary.main }}>Title</h1>
</div>
```

## CSS Variables

If using CSS files, import and use CSS variables:

```css
.component {
  background-color: var(--color-background-default);
  color: var(--color-text-primary);
}

.component-header {
  color: var(--color-primary-main);
}
```

## Icons

Replace hardcoded emoji/symbols with ICONS constants:

```tsx
import { ICONS } from '@/theme/branding';

// Before
<span>✓</span>

// After
<span>{ICONS.success}</span>
```

## Typography

Use UI.fonts for consistent typography:

```tsx
<h1 style={{ fontSize: UI.fonts.size_2xl, fontFamily: UI.fonts.family_mono }}>
  Kaison K1
</h1>
```

## Spacing

Use UI.spacing for consistent spacing:

```tsx
<div style={{ padding: UI.spacing.lg, gap: UI.spacing.md }}>
  Content
</div>
```

## Shadows and Effects

Use predefined shadows:

```tsx
<div style={{ boxShadow: UI.shadow.glow }}>
  Glowing element
</div>
```

## Version Info

Update version references:

```tsx
import { BRANDING } from '@/theme/branding';

<p>Version: {BRANDING.version}</p>
<p>Phase: {BRANDING.phase}</p>
```

## Checklist for Each Component

- [ ] Import COLORS, UI, BRANDING from theme/branding
- [ ] Replace hardcoded colors with COLORS.*
- [ ] Replace hardcoded sizes with UI.fonts.* and UI.spacing.*
- [ ] Replace hardcoded shadows with UI.shadow.*
- [ ] Update version strings to use BRANDING.*
- [ ] Replace emoji/symbols with ICONS.*
- [ ] Test component in light and dark themes
- [ ] Verify accessibility (contrast ratios)

## Testing

After updating each component:

1. Visual inspection in browser
2. Test all interactive elements
3. Verify responsive behavior
4. Check console for errors
5. Test theme consistency across pages

## Notes

- The new branding emphasizes a dark IDE aesthetic with Matrix-inspired neon green accents
- All new components use this branding by default
- Gradual migration of existing components is recommended
- Maintain backward compatibility where possible
