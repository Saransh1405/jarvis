import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, repoRoot, "");
  const gatewayPort = env.GATEWAY_PORT || "8080";
  const gateway = env.VITE_GATEWAY_URL || `http://localhost:${gatewayPort}`;

  return {
    envDir: repoRoot,
    plugins: [react()],
    server: {
      port: Number(env.VITE_STITCH_PORT || env.VITE_PORT) || 5174,
      proxy: {
        "/api": {
          target: gateway,
          changeOrigin: true,
        },
      },
    },
  };
});
