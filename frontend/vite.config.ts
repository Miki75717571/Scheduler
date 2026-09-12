/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // Forwards same-origin /api requests to the backend. This is what
      // lets a phone on the LAN talk to the API at all: uvicorn stays bound
      // to 127.0.0.1 (see start.ps1), so the phone can only ever reach it
      // through this proxy, never directly. Because the browser's request
      // is same-origin (relative /api/v1/... - see api/client.ts), no CORS
      // is involved and the httpOnly refresh cookie round-trips untouched:
      // this is a plain server-to-server HTTP relay (changeOrigin fixes up
      // the Host header for the backend), not a browser fetch, so the
      // Set-Cookie response header passes through as-is with no rewriting.
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        // Without this, a dead backend makes the proxy answer with its own
        // plain-text 500 - a response the browser's fetch() sees as a normal
        // (if failed) reply, not a thrown error, so api/client.ts's network
        // failure detection (which only catches fetch() itself throwing)
        // never fires and the UI falls back to a generic message. Emitting
        // the same {detail:{message_key}} shape client.ts already parses
        // for every other error lets "backend unreachable" surface as the
        // same distinct network.unreachable message either way.
        configure: (proxyServer) => {
          proxyServer.on("error", (_err, _req, res) => {
            if ("writeHead" in res && !res.headersSent) {
              res.writeHead(502, { "Content-Type": "application/json" });
            }
            if ("end" in res) {
              res.end(JSON.stringify({ detail: { message_key: "network.unreachable" } }));
            }
          });
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
