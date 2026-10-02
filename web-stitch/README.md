# JARVIS Web (Stitch)

React + TypeScript UI wired to the Go gateway (`/api/v1/*`). Intended to match the [Stitch project](https://stitch.withgoogle.com/projects/13160455557984658905).

## Dev

1. Root env: `cp .env.example .env` — set `GATEWAY_PORT` and `VITE_GATEWAY_URL` to the same port.
2. Backend: `make dev` (gateway on `GATEWAY_PORT`, default `:8080`).
3. Frontend:

```bash
cd web-stitch
npm install
npm run dev
```

Open [http://localhost:5174](http://localhost:5174) (default; override with `VITE_STITCH_PORT`).

Brand assets live in `public/assets/` (arc-reactor logo: `jarvis-arc-core.png`). Add more files there and reference via `/assets/...` in components.

## Stitch sync (optional)

To download screen HTML from your Stitch project (requires [Stitch API key](https://www.npmjs.com/package/@google/stitch-sdk)):

```bash
# In repo root .env:
# STITCH_API_KEY=...
# STITCH_PROJECT_ID=13160455557984658905

cd web-stitch && npm run stitch:pull
```

Exports land in `web-stitch/stitch-export/` for reference while porting styles into React.

## Build

```bash
npm run build
```

Serve `dist/` behind your CDN; API must be reachable at the same origin or via CORS.
