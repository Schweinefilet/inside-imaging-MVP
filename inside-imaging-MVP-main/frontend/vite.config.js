import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react' // if you use React; remove if not

export default defineConfig({
  plugins: [react()],
  base: '/Inside-Imaging-Public/',   // <-- required for GitHub Pages subpath
})
