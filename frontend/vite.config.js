import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy: redireciona /api para o backend FastAPI
    proxy: {
      "/api": {
        target: process.env.API_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
    // usePolling: necessário no Windows quando arquivos são modificados
    // por processos externos (o watcher padrão depende de eventos do SO
    // que nem sempre disparam fora do editor)
    watch: {
      usePolling: true,
      interval: 500,
    },
  },
});
