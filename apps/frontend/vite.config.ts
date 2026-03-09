
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
    '/api/v1': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/recordings': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/submissions': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/reports': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/metrics': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/healthz': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/findings': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/hil': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/scopes': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/providers': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/auth': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/settings': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/keys': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/state': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/evidence': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/logs': { target: 'http://k1_backend:8080', changeOrigin: true },
    '/ws': { target: 'ws://k1_backend:8080', ws: true },
    '/api/v1/agent-zero/ws': { target: 'ws://k1_backend:8080', ws: true }
  }
},

})
