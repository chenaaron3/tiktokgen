import path from "node:path"
import { fileURLToPath } from "node:url"

import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

import { createCacheApiMiddleware } from "./cache-api-middleware"

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")

const viewerDir = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: "cache-api-localhost",
      configureServer(server) {
        server.middlewares.use(createCacheApiMiddleware(repoRoot))
      },
    },
  ],
  resolve: {
    alias: {
      "@": path.resolve(viewerDir, "./src"),
      "@remotion-shared": path.resolve(viewerDir, "../remotion/src"),
    },
    dedupe: ["react", "react-dom", "remotion"],
  },
})
