import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The desk runs on http://localhost:5173 and calls the FastAPI backend on http://localhost:8000
// (see src/api.ts). `npm run dev` opens it in the browser.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, open: true },
})
