
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  
server: { 
  port: 5173, host: true,
  proxy: {
    '/api/v1': { target: 'http://localhost:8080', changeOrigin: true },
    '/recordings': { target: 'http://localhost:8080', changeOrigin: true },
    '/submissions': { target: 'http://localhost:8080', changeOrigin: true },
    '/reports': { target: 'http://localhost:8080', changeOrigin: true },
    '/metrics': { target: 'http://localhost:8080', changeOrigin: true },
    '/healthz': { target: 'http://localhost:8080', changeOrigin: true },
    '/findings': { target: 'http://localhost:8080', changeOrigin: true },
    '/hil': { target: 'http://localhost:8080', changeOrigin: true },
    '/scopes': { target: 'http://localhost:8080', changeOrigin: true },
    '/providers': { target: 'http://localhost:8080', changeOrigin: true },
    '/auth': { target: 'http://localhost:8080', changeOrigin: true },
    '/settings': { target: 'http://localhost:8080', changeOrigin: true },
    '/keys': { target: 'http://localhost:8080', changeOrigin: true },
    '/state': { target: 'http://localhost:8080', changeOrigin: true },
    '/evidence': { target: 'http://localhost:8080', changeOrigin: true },
    '/logs': { target: 'http://localhost:8080', changeOrigin: true },
    '/ws': { target: 'ws://localhost:8080', ws: true },
    '/api/v1/orchestration/ws': { target: 'ws://localhost:8080', ws: true }
  }
},

})
