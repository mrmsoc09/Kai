# V-RAD Frontend Integration Guide

## Quick Start

### Installation

```bash
cd apps/frontend
npm install
```

### Running Development Server

```bash
npm run dev
```

Navigate to `http://localhost:5173/dashboard` (or configured port).

### Building for Production

```bash
npm run build
```

---

## Component Integration Checklist

- [x] **ResearchDashboard.tsx** — Main container component
- [x] **GlobeVisualization** — Canvas-based holographic globe
- [x] **LEDBar** — Segmented LED indicators
- [x] **CircularGauge** — SVG circular progress gauges
- [x] **WaveformVisualizer** — Real-time bandwidth animation
- [x] **SystemButton** — Tactile control buttons
- [x] **ultrawide.css** — Tailwind + custom styles
- [x] **dashboard.ts** — Complete TypeScript definitions
- [x] **DASHBOARD_README.md** — Component documentation
- [x] **INTEGRATION_GUIDE.md** — This guide

---

## Wiring to K1 Backend

### 1. Telemetry API Integration

Replace mock data in `ResearchDashboard.tsx`:

```typescript
// OLD: Static mock update
useEffect(() => {
  const interval = setInterval(() => {
    setTelemetry(prev => ({ /* mock updates */ }));
  }, 2000);
  return () => clearInterval(interval);
}, []);

// NEW: Backend API call
useEffect(() => {
  const fetchTelemetry = async () => {
    try {
      const response = await fetch('/api/k1/telemetry/current', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setTelemetry(data.metrics);
    } catch (error) {
      console.error('Failed to fetch telemetry:', error);
    }
  };

  const interval = setInterval(fetchTelemetry, 2000);
  return () => clearInterval(interval);
}, [token]);
```

### 2. Global Vulnerability Events

```typescript
// Fetch live vulnerability events
useEffect(() => {
  const fetchEvents = async () => {
    const response = await fetch('/api/k1/vulnerabilities/events?limit=10');
    const data = await response.json();
    setGlobalEvents(data.events);
  };

  fetchEvents();
  const interval = setInterval(fetchEvents, 5000);
  return () => clearInterval(interval);
}, []);
```

### 3. Research Nodes

```typescript
// Get live node status
useEffect(() => {
  const fetchNodes = async () => {
    const response = await fetch('/api/k1/nodes/topology');
    const data = await response.json();
    setResearchNodes(data.nodes);
  };

  fetchNodes();
  const interval = setInterval(fetchNodes, 10000);
  return () => clearInterval(interval);
}, []);
```

### 4. System Status

```typescript
// Wire system controls to backend
const handleSystemControl = async (control: string, state: boolean) => {
  const response = await fetch(`/api/k1/system/control/${control}`, {
    method: 'POST',
    body: JSON.stringify({ enabled: state })
  });

  const result = await response.json();
  setSystemStatus(prev => ({
    ...prev,
    controls: { ...prev.controls, [control]: result.enabled }
  }));
};
```

---

## Environment Configuration

### .env.local

```env
# API Configuration
REACT_APP_API_BASE_URL=http://localhost:8080
REACT_APP_API_TIMEOUT=30000

# WebSocket Configuration (for real-time updates)
REACT_APP_WS_URL=ws://localhost:8080/ws
REACT_APP_WS_RECONNECT_INTERVAL=5000

# Authentication
REACT_APP_AUTH_TOKEN_KEY=k1_auth_token

# Feature Flags
REACT_APP_ENABLE_ANIMATIONS=true
REACT_APP_ENABLE_SOUND=false
REACT_APP_DEBUG_MODE=false
```

---

## Backend API Endpoints

### Telemetry

**GET** `/api/k1/telemetry/current`

```json
{
  "cpuLoad": 68,
  "coreTemp": 85,
  "vramUtilization": 72,
  "bandwidthThroughput": 3500,
  "analysisThreads": 147,
  "rateLimitLevel": 35,
  "timestamp": "2024-04-11T14:30:00Z"
}
```

### Vulnerabilities

**GET** `/api/k1/vulnerabilities/events?limit=10&severity=critical`

```json
{
  "events": [
    {
      "id": "vuln-001",
      "timestamp": "2024-04-11T14:32:00Z",
      "severity": "critical",
      "title": "Remote Code Execution",
      "affectedNodes": 47
    }
  ]
}
```

### Research Nodes

**GET** `/api/k1/nodes/topology`

```json
{
  "nodes": [
    {
      "id": "ny-01",
      "name": "New York Hub",
      "region": "NA",
      "vulnerabilityCount": 147,
      "status": "active",
      "lastUpdate": "2024-04-11T14:30:00Z"
    }
  ]
}
```

### System Status

**GET** `/api/k1/system/status`

```json
{
  "operational": true,
  "controls": {
    "ollamaFallback": true,
    "geminiIntegration": true,
    "vaultAccess": true,
    "researchValidator": true
  },
  "lastHealthCheck": "2024-04-11T14:30:00Z"
}
```

**POST** `/api/k1/system/control/{controlName}`

```json
{
  "enabled": true,
  "timestamp": "2024-04-11T14:30:00Z"
}
```

---

## WebSocket Real-Time Updates (Optional)

### Connection Setup

```typescript
import { useEffect, useRef } from 'react';

const useWebSocket = (url: string) => {
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    wsRef.current = new WebSocket(url);

    wsRef.current.onopen = () => console.log('Connected');
    wsRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      // Handle message type
      switch (message.type) {
        case 'telemetry_update':
          setTelemetry(message.data);
          break;
        case 'vulnerability_event':
          setGlobalEvents(prev => [message.data, ...prev.slice(0, 9)]);
          break;
        case 'node_status_change':
          // Update node status
          break;
      }
    };

    return () => wsRef.current?.close();
  }, [url]);

  return wsRef;
};

// Usage in ResearchDashboard
useWebSocket(process.env.REACT_APP_WS_URL || 'ws://localhost:8080/ws');
```

---

## Performance Monitoring

### Enable React DevTools Profiler

```typescript
import { Profiler } from 'react';

export default function App() {
  const onRenderCallback = (id, phase, actualDuration) => {
    console.log(`${id} (${phase}) took ${actualDuration}ms`);
  };

  return (
    <Profiler id="ResearchDashboard" onRender={onRenderCallback}>
      <ResearchDashboard />
    </Profiler>
  );
}
```

### Monitor Canvas Performance

```typescript
// In GlobeVisualization
useEffect(() => {
  const startTime = performance.now();
  // ... rendering code ...
  const endTime = performance.now();
  console.log(`Globe render: ${(endTime - startTime).toFixed(2)}ms`);
}, [nodes]);
```

---

## Error Handling

### Global Error Boundary

```typescript
import React, { ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Dashboard Error:', error, errorInfo);
    // Send to error tracking service
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center w-full h-full bg-red-900 text-white">
          <div className="text-center">
            <h1 className="text-2xl font-bold mb-2">Dashboard Error</h1>
            <p>{this.state.error?.message}</p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
```

### API Error Handling

```typescript
const fetchWithErrorHandling = async (url: string) => {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Fetch failed:', error);
    // Fall back to mock data
    return getMockData();
  }
};
```

---

## Authentication Integration

### JWT Token Management

```typescript
const useAuth = () => {
  const getToken = () => localStorage.getItem('k1_auth_token');
  
  const apiCall = async (url: string, options: RequestInit = {}) => {
    return fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        'Authorization': `Bearer ${getToken()}`
      }
    });
  };

  return { getToken, apiCall };
};
```

### Protected Route

```typescript
import { Navigate } from 'react-router-dom';

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('k1_auth_token');
  
  if (!token) {
    return <Navigate to="/login" />;
  }

  return children;
};

// Usage
<Route path="/dashboard" element={<ProtectedRoute><ResearchDashboard /></ProtectedRoute>} />
```

---

## Testing

### Unit Tests

```bash
npm test -- ResearchDashboard.test.tsx
```

### Example Test

```typescript
import { render, screen } from '@testing-library/react';
import ResearchDashboard from './ResearchDashboard';

describe('ResearchDashboard', () => {
  it('renders header with correct title', () => {
    render(<ResearchDashboard />);
    expect(screen.getByText('KAISONONE SECURITY RESEARCH & ANALYTICS')).toBeInTheDocument();
  });

  it('displays telemetry metrics', () => {
    render(<ResearchDashboard />);
    expect(screen.getByText(/ANALYSIS INTENSITY/i)).toBeInTheDocument();
  });
});
```

---

## Deployment

### Docker Deployment

```dockerfile
# Build stage
FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Runtime stage
FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package*.json ./
RUN npm ci --production
EXPOSE 3000
CMD ["npm", "start"]
```

### Nginx Proxy Configuration

```nginx
server {
  listen 80;
  server_name k1-dashboard.local;

  location / {
    proxy_pass http://localhost:3000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_cache_bypass $http_upgrade;
  }

  location /api {
    proxy_pass http://backend:8080;
    proxy_set_header Authorization $http_authorization;
  }
}
```

---

## Troubleshooting

### Canvas Not Rendering

Check browser console for errors. Verify:

```typescript
const canvas = document.querySelector('canvas');
const ctx = canvas?.getContext('2d');
console.log('Canvas available:', !!canvas);
console.log('2D context available:', !!ctx);
```

### High CPU Usage

Profile with Chrome DevTools:
1. Open DevTools Performance tab
2. Record for 10 seconds
3. Look for long-running tasks (>50ms)
4. Common culprits: unoptimized canvas redraws, excessive re-renders

### Data Not Updating

Check network tab for API failures:

```typescript
// Enable debug logging
const DEBUG = true;

const fetchTelemetry = async () => {
  if (DEBUG) console.log('Fetching telemetry...');
  try {
    const response = await fetch('/api/k1/telemetry/current');
    if (DEBUG) console.log('Response:', response);
    const data = await response.json();
    if (DEBUG) console.log('Data:', data);
    setTelemetry(data);
  } catch (error) {
    console.error('Fetch error:', error);
  }
};
```

---

## Next Steps

1. **Backend API Implementation**: Implement the required endpoints in K1 backend
2. **Authentication**: Integrate with K1 authentication system
3. **WebSocket**: Optional real-time data streaming
4. **Analytics**: Add historical trends and reports
5. **Customization**: Theme selector and user preferences
6. **Mobile Responsive**: Adapt for smaller screens (future release)

---

## Support

For questions or issues, refer to:
- `DASHBOARD_README.md` — Component documentation
- `apps/frontend/src/types/dashboard.ts` — Type definitions
- `/api/k1/docs` — Backend API documentation

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-04-11 | Initial release for 21:9 UltraWide |

---

## License

© 2024 KaisonOne Security Research Platform
