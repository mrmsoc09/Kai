
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  
server: { 
  port: 5173, host: true,
  proxy: {
    '/recordings': { target: 'http://localhost:8080', changeOrigin: true },
    '/submissions': { target: 'http://localhost:8080', changeOrigin: true },
    '/reports': { target: 'http://localhost:8080', changeOrigin: true },
    '/healthz': { target: 'http://localhost:8080', changeOrigin: true },
    '/findings': { target: 'http://localhost:8080', changeOrigin: true },
    '/hil': { target: 'http://localhost:8080', changeOrigin: true },
    '/scopes': { target: 'http://localhost:8080', changeOrigin: true },
    '/providers': { target: 'http://localhost:8080', changeOrigin: true },
    '/auth': { target: 'http://localhost:8080', changeOrigin: true },
    '/state': { target: 'http://localhost:8080', changeOrigin: true },
    '/evidence': { target: 'http://localhost:8080', changeOrigin: true },
    '/logs': { target: 'http://localhost:8080', changeOrigin: true },
    '/ws': { target: 'ws://localhost:8080', ws: true }
  }
},

})
