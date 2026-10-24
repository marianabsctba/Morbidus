import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Em desenvolvimento, as chamadas /v1 vão para o gateway (dev_stack.py ou Traefik).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/v1": process.env.MORBIDUS_API ?? "http://127.0.0.1:8080" },
  },
});
