# Vulnerability Research & Analytics Dashboard (V-RAD)

## Overview

The **Vulnerability Research & Analytics Dashboard** is a high-fidelity React/Tailwind interface optimized for the LG 29WP60G-B UltraWide display (2560x1080 | 21:9 aspect ratio). Designed as a "Precision Engineering / High-Performance Lab" environment, V-RAD provides comprehensive threat intelligence visualization, global vulnerability tracking, and real-time research node management.

---

## Architecture

### Component Structure

```
ResearchDashboard (Main Container)
├── Header (Branding & Status)
├── Left Section: Global Threat Intelligence (40%)
│   ├── GlobeVisualization (Holographic globe + world map)
│   └── EventLogsSidebar (Global vulnerability events)
├── Center Section: Research Data (35%)
│   ├── Top Vulnerabilities List
│   └── Research Nodes Status
└── Right Section: Hardware Telemetry (25%)
    ├── LED Bars (Analysis Intensity / Rate Limiter)
    ├── Circular Gauges (CPU / Temp / VRAM / Bandwidth)
    └── System Controls
```

### Display Distribution

| Section | Width | Purpose |
|---------|-------|---------|
| **Left** | 40% | Global threat heatmap, holographic globe, event logs |
| **Center** | 35% | Vulnerability rankings, research node status |
| **Right** | 25% | Hardware telemetry, system controls, status LEDs |

**Total optimal viewport: 2560x1080 (21:9 aspect ratio)**

---

## Component Breakdown

### 1. ResearchDashboard (Main)

**File:** `ResearchDashboard.tsx`

The root component managing state and layout for the entire dashboard.

**State Management:**
```typescript
interface TelemetryMetrics {
  cpuLoad: number;           // 0-100%
  coreTemp: number;          // 0-100%
  vramUtilization: number;   // 0-100%
  bandwidthThroughput: number; // MB/s
  analysisThreads: number;   // Count
  rateLimitLevel: number;    // 0-100%
}

interface VulnerabilityEvent {
  id: string;
  timestamp: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  affectedNodes: number;
}

interface ResearchNode {
  id: string;
  name: string;
  region: string;
  vulnerabilityCount: number;
  lastUpdate: string;
  status: 'active' | 'idle' | 'warning';
}
```

**Key Features:**
- Auto-updating telemetry (2-second intervals)
- Mock data initialization for development
- Flexbox layout optimized for 21:9
- Real-time event stream simulation

---

### 2. GlobeVisualization

**Canvas-based 3D holographic globe visualization**

**Features:**
- Animated rotation using canvas drawing
- Research node positioning around globe
- Connection lines from center to regional hubs
- Pulsing center point
- Zoom controls (GLOBAL / REGION / LOCAL)

**Rendering:**
- Uses HTML5 Canvas API
- 60fps animation loop via `requestAnimationFrame`
- Dynamically sized to container
- Node status indicators (active/idle/warning)

**Regional Nodes:**
- NY (North America)
- London (Europe)
- Beijing (Asia Pacific)
- Moscow (Russia)
- Sydney (Australia)

---

### 3. LEDBar

**Segmented LED indicator for discrete metrics**

**Props:**
```typescript
interface LEDBarProps {
  value: number;      // Current value
  max: number;        // Maximum value
  color: 'green' | 'amber' | 'red'; // Color scheme
}
```

**Features:**
- 7-segment display
- Proportional fill based on value/max ratio
- Animated glow on active segments
- Color-coded status (green = normal, amber = warning, red = critical)

**Usage Examples:**
- Analysis Intensity (green, 0-200 threads)
- Rate Limiter (amber, 0-100%)

---

### 4. CircularGauge

**Circular progress indicator with needle effect**

**Props:**
```typescript
interface CircularGaugeProps {
  label: string;
  value: number;
  max: number;
  unit: string;
  color: string;
}
```

**Features:**
- SVG-based rendering
- Circular arc progress
- Center digital readout
- Color-coded indicators

**Used For:**
- CPU Load (0-100%)
- Core Temperature (0-100%)
- VRAM Utilization (0-100%)
- Bandwidth Throughput (0-5000 MB/s)

---

### 5. WaveformVisualizer

**Real-time waveform animation for bandwidth visualization**

**Features:**
- Sine wave generation
- Animated scroll effect
- Blue color with transparency
- Updates at 60fps

**Data Binding:**
Connect to `telemetry.bandwidthThroughput` for live bandwidth representation.

---

### 6. SystemButton

**Tactile toggle button for system controls**

**Props:**
```typescript
interface SystemButtonProps {
  label: string;
  active: boolean;
}
```

**Features:**
- Active state styling (green border + glow)
- Hover effects
- Icons optional
- Uppercase labels

**System Controls:**
- OLLAMA FALLBACK
- GEMINI INTEGRATION
- VAULT ACCESS
- RESEARCH VALIDATOR

---

## Styling & Theme

### Color Palette

```css
/* Primary Colors */
--color-void-black: #050505      /* Background */
--color-gold: #D4AF37            /* Accents & borders */
--color-cyber-purple: #6A0DAD    /* Secondary accent */

/* LED Colors */
Green:   #10b981                 /* Active status */
Amber:   #f59e0b                 /* Warning status */
Red:     #ef4444                 /* Critical status */
Blue:    #3b82f6                 /* Waveform / data */
```

### Typography

```css
/* Technical Monospace */
font-family: 'IBM Plex Mono', 'Courier New', monospace

/* Sans Serif */
font-family: 'Inter', system-ui, sans-serif

/* Letter Spacing */
tracking-wider: 0.15em           /* Headers */
tracking-normal: 0.025em         /* Body */
```

### Animations

| Animation | Duration | Use Case |
|-----------|----------|----------|
| `pulse-glow` | 2s | LED segments, status indicators |
| `breathing` | 3s | Globe center, card hover |
| `waveform` | 2s | Bandwidth visualization |
| `scan-line` | Variable | Loading states |

---

## Data Integration

### Mock Data Source

The dashboard initializes with mock data for development:

```typescript
// Vulnerability Events (4 items)
- Remote Code Execution in Struts2 (critical, 47 nodes)
- SQL Injection in Django ORM (high, 23 nodes)
- XXE in Apache Commons (high, 15 nodes)
- CSRF Token Bypass (medium, 8 nodes)

// Research Nodes (5 global hubs)
- New York Hub: 147 findings
- London Ops: 89 findings
- Beijing Analysis: 156 findings
- Moscow Lab: 62 findings
- Sydney Research: 34 findings
```

### Backend Integration

To connect to real data, replace mock state with API calls:

```typescript
// Example: Fetch telemetry from backend
useEffect(() => {
  const fetchTelemetry = async () => {
    const response = await fetch('/api/telemetry/current');
    const data = await response.json();
    setTelemetry(data);
  };

  const interval = setInterval(fetchTelemetry, 2000);
  return () => clearInterval(interval);
}, []);
```

---

## Performance Optimizations

### Canvas Rendering
- **GlobeVisualization**: Only redraws when nodes prop changes
- **WaveformVisualizer**: Uses `requestAnimationFrame` for 60fps
- Canvas size dynamically matches container (no scaling artifacts)

### CSS Animations
- GPU-accelerated transforms (`will-change`)
- Hardware-accelerated drop shadows
- Efficient SVG rendering for gauges

### React Optimization
- Memoized subcomponents (`React.memo`)
- useRef for canvas elements (avoids re-renders)
- Controlled telemetry updates (2-second intervals, not per-render)

---

## Responsiveness

### 21:9 UltraWide (Recommended)
```css
/* Optimal layout */
Width: 2560px
Height: 1080px
Left: 40% (1024px)
Center: 35% (896px)
Right: 25% (640px)
```

### 16:9 Fallback
```css
/* Stacked layout */
Layout switches to single column
Components stack vertically
Typography scales down to 14px
```

### Mobile (Unsupported)
- Not optimized for mobile displays
- Recommend desktop/laptop use only
- Minimum recommended: 1920x1080 (16:9)

---

## Customization Guide

### Changing Color Scheme

Edit `src/styles/ultrawide.css`:

```css
:root {
  --color-void-black: #050505;    /* Change background */
  --color-gold: #D4AF37;           /* Change accent */
  --color-cyber-purple: #6A0DAD;   /* Change secondary */
}
```

### Adjusting Telemetry Update Rate

In `ResearchDashboard.tsx`:

```typescript
useEffect(() => {
  const interval = setInterval(() => {
    // Update telemetry
  }, 2000); // Change this interval (milliseconds)

  return () => clearInterval(interval);
}, []);
```

### Customizing Segments in LEDBar

Modify the segments constant:

```typescript
const segments = 7; // Change to 5, 8, 10, etc.
```

### Adding New Circular Gauges

Add new gauge in the Right Section:

```typescript
<CircularGauge 
  label="YOUR_METRIC" 
  value={telemetry.yourMetric} 
  max={100} 
  unit="%" 
  color="blue" 
/>
```

---

## Known Limitations

1. **Canvas Rendering**: GlobeVisualization may have performance issues on very old browsers (pre-2020)
2. **Animation Performance**: Waveform animation disabled on low-performance devices
3. **Mobile**: Not responsive to mobile/tablet viewports
4. **Data Limits**: Mock data hardcoded (no pagination for large datasets)

---

## Future Enhancements

### Phase 2
- [ ] Real WebSocket data binding for live metrics
- [ ] Interactive node selection on globe
- [ ] Drill-down capability to regional vulnerability details
- [ ] Historical trend graphs (24h, 7d, 30d)

### Phase 3
- [ ] 3D WebGL globe rendering (instead of 2D canvas)
- [ ] Custom theme selector
- [ ] Dark/Light mode toggle
- [ ] Accessibility improvements (WCAG 2.1 AA compliance)

### Phase 4
- [ ] Multi-user collaboration features
- [ ] Real-time alert notifications
- [ ] Export reports to PDF/CSV
- [ ] Role-based dashboard customization

---

## File Structure

```
apps/frontend/
├── src/
│   ├── pages/
│   │   └── ResearchDashboard.tsx    (Main component)
│   ├── styles/
│   │   └── ultrawide.css             (Tailwind + custom styles)
│   ├── components/
│   │   ├── GlobeVisualization.tsx
│   │   ├── LEDBar.tsx
│   │   ├── CircularGauge.tsx
│   │   ├── WaveformVisualizer.tsx
│   │   └── SystemButton.tsx
│   └── types/
│       └── dashboard.ts              (TypeScript interfaces)
└── DASHBOARD_README.md               (This file)
```

---

## Testing

### Unit Tests

```bash
npm test -- ResearchDashboard.test.tsx
```

### Visual Regression

```bash
npm run test:visual
```

### Performance Profiling

```bash
npm run analyze
```

---

## Deployment

### Build for Production

```bash
npm run build
```

### Environment Variables

```bash
REACT_APP_API_BASE_URL=https://api.k1.local
REACT_APP_WEBSOCKET_URL=wss://ws.k1.local
```

### Docker Deployment

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY . .
RUN npm install && npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

---

## Support & Troubleshooting

### Canvas Not Rendering

**Solution:** Check browser console for errors. Ensure canvas context is available:

```typescript
const ctx = canvas.getContext('2d');
if (!ctx) console.error('Canvas 2D context unavailable');
```

### LED Bars Not Animating

**Solution:** Verify CSS animations are enabled. Check for `prefers-reduced-motion`:

```typescript
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
```

### Telemetry Values Not Updating

**Solution:** Check network tab for API calls. Verify interval is active:

```typescript
useEffect(() => {
  const interval = setInterval(() => {
    console.log('Telemetry update firing'); // Debug
  }, 2000);
  return () => clearInterval(interval);
}, []);
```

---

## License

© 2024 KaisonOne Security Research Platform. All rights reserved.

---

## Contact

For questions or feature requests, contact the K1 frontend team.
