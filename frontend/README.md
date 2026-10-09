# Campus Intelligence & Action Platform — frontend

## Development

Install dependencies with `npm install`, then start the app with `npm run dev`.
The Vite development server proxies `/api` to `http://localhost:8766`, where
the FastAPI backend should be started for local development.

To use another backend port, set `CAMPUS_API_PROXY` before starting Vite:

```powershell
$env:CAMPUS_API_PROXY = 'http://127.0.0.1:8766'
npm run dev
```

## Validation

- `npm run lint`
- `npm run build`
