# JARVIS Web

Vite + React + TypeScript chat UI for the gateway.

## Dev

1. Copy env at repo root: `cp .env.example .env` and set `GATEWAY_PORT` / `VITE_GATEWAY_URL` to the same host port.
2. Start backend: `make dev` (gateway on `GATEWAY_PORT`, default `:8080`)
3. Install and run UI:

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). API calls are proxied to `VITE_GATEWAY_URL` from the root `.env` (falls back to `http://localhost:${GATEWAY_PORT}`).

## Build

```bash
npm run build
npm run preview   # static preview on :4173
```

Production deploy: serve `dist/` behind nginx or your CDN; point the app at the gateway API (same-origin or configure CORS).
