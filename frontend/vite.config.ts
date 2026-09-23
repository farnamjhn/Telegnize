import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Port 3000 matches TELEGNIZE_CORS_ORIGINS' default, so direct cross-origin
// calls work too; the proxy below means the common case needs no CORS at all.
export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.PORT) || 3000,
    strictPort: false,
    proxy: {
      "/api": {
        target: process.env.TELEGNIZE_API ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
