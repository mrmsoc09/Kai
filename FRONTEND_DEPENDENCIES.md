# Frontend Dependencies to Install

The following npm packages need to be installed in the `apps/frontend` directory:

```bash
cd apps/frontend
npm install d3@^7.8.5
npm install recharts@^2.10.0
npm install react-force-graph-2d@^1.25.4
npm install @types/d3@^7.4.3 --save-dev
```

## Package Purposes

- **d3** - Data visualization library for creating custom charts and graphs
- **recharts** - React charting library for heatmaps and statistical visualizations
- **react-force-graph-2d** - Force-directed graph visualization for attack surface mapping
- **@types/d3** - TypeScript type definitions for D3.js

## Alternative: Manual Installation

If npm install fails due to version conflicts, update `package.json` manually:

```json
{
  "dependencies": {
    "d3": "^7.8.5",
    "recharts": "^2.10.0",
    "react-force-graph-2d": "^1.25.4"
  },
  "devDependencies": {
    "@types/d3": "^7.4.3"
  }
}
```

Then run:
```bash
npm install
```

## Notes

The visualization components created in this update:
- `RSSIntelligenceDashboard` - Uses standard React (no extra deps)
- `AttackSurfaceGraph` - Uses Canvas API (no extra deps needed, but react-force-graph-2d recommended for production)
- `CVSSTemporalHeatmap` - Requires recharts
- `EPSSRiskMatrix` - Requires recharts
- `VulnerabilityDensityMap` - Requires d3
