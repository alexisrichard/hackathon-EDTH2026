import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The map dashboard (deck.gl + MapLibre) is built day-of in src/components/.
// This config hosts the data layer (src/types, src/api) and the future app.
// `VITE_API_BASE_URL` points the typed client at the backend (default
// http://localhost:8000, mock mode).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
