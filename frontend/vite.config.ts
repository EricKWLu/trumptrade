import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // Proxy all backend REST routes to FastAPI (port 8000)
      // Keeps BASE="" in api.ts — same-origin assumption works in prod too
      "^/(posts|trades|portfolio|alerts|watchlist|settings|trading|benchmarks|health)": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
})
