# Curio Web

Curio on the web: **Pages** (the Notion-style workspace) and **Finance**, from any device. The other parts of Curio say
“Coming soon” here and keep working in the desktop app. The desktop app and the web are separate — the web has its own data.

## How it is built
- `public/` — the site. `public/pages/` is the same Pages build as the desktop (`channel.js` replaces Qt's web channel),
  `public/finance/` is Finance for the web, `public/app.js` the Curio sidebar, Home and Settings (with the one-time import).
- `api/index.py` — every `/api/*` call (Python standard library only, no packages).
- `server/finance/` — the desktop app's own money rules, unchanged. `server/pages.py` — the desktop's Pages logic.
- `server/tdb.py` — the database: Turso (SQLite in the cloud). Finance and Pages are kept in memory on the server and every
  change is written to Turso in one transaction, guarded so two tabs never overwrite each other.
- Sign-in: Google, only the address in `ALLOWED_EMAIL`. No passwords are stored anywhere.

## Put it online (Vercel)
1. Vercel → Add New → Project → import this repository (no build settings needed).
2. Project → Storage → Create Database → **Turso** → connect it to this project (region: Mumbai / `ap-south-1` is closest
   to Pakistan). This adds `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`.
3. Project → Settings → Environment Variables:
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — Google Cloud → Credentials → OAuth client ID → Web application,
     redirect URI `https://<your-domain>/api/auth/callback`
   - `ALLOWED_EMAIL` — your Gmail
4. Deployments → Redeploy. Open the site, sign in, Settings → *Bring your desktop data in*.

## Run it on your PC
`python dev.py` → http://localhost:8787 (uses `.data/curio-web.db`, signs you in automatically).
