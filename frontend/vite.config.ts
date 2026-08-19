import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const envDir = path.resolve(__dirname, "..");
  // Read FRONTEND_PORT / BACKEND_PORT from ../.env (single source of truth,
  // shared with docker-compose). The "" prefix loads non-VITE_ vars too.
  const env = loadEnv(mode, envDir, "");
  const frontendPort = Number(env.FRONTEND_PORT) || 8080;
  const backendPort = Number(env.BACKEND_PORT) || 3000;

  return {
    envDir,
    server: {
      host: "::",
      port: frontendPort,
      hmr: {
        overlay: false,
      },
      proxy: {
        "/api": {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
  };
});
