import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5192,
    proxy: { "^/agent/": "http://localhost:8200" },
  },
});
