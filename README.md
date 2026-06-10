# FinWatch India — Anti-Corruption Intelligence Platform

Public platform tracking declared vs estimated wealth of Indian elected officials
using only publicly available government data (ECI, MCA21, eCourts, RERA).

## Quick Deploy (5 minutes)

### Prerequisites
- Docker + Docker Compose installed
- Anthropic API key (get one at console.anthropic.com)

### Steps

```bash
# 1. Clone / download this folder
cd finwatch

# 2. Set your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Start everything
docker-compose up -d

# 4. Open browser
# http://localhost        → Frontend
# http://localhost:8000   → API docs
```

## Deploy to Cloud (Render.com — Free)

### Backend
1. Go to render.com → New → Web Service
2. Connect your GitHub repo
3. Set:
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variable: `ANTHROPIC_API_KEY=your_key`

### Frontend
1. render.com → New → Static Site
2. Set:
   - Root directory: `frontend`
   - Build command: `npm install && npm run build`
   - Publish directory: `dist`
3. Add environment variable: `VITE_API_URL=https://your-backend.onrender.com/api`

## Deploy to Railway (Recommended — $5/mo)

```bash
npm install -g railway
railway login
railway init
railway up
```

## Deploy to VPS (DigitalOcean / Hetzner)

```bash
# On your server:
git clone <your-repo>
cd finwatch
cp .env.example .env && nano .env   # add API key
docker-compose up -d

# Optional: point domain + SSL
apt install certbot nginx
certbot --nginx -d yourdomain.com
```

## Architecture

```
Frontend (React + Vite)
    ↓ /api/*
Backend (FastAPI + SQLite)
    ↓ scrapes
Myneta.info   MCA21   eCourts   RERA   GEM Portal
```

## Data Sources (All Public)

| Source | Data | URL |
|--------|------|-----|
| Myneta.info | EC affidavits, declared assets | myneta.info |
| MCA21 | Company directors, CIN, compliance | mca.gov.in |
| eCourts | FIRs, charge sheets | ecourts.gov.in |
| RERA | Property registrations | rera.gov.in |
| GEM Portal | Govt contracts | gem.gov.in |
| Sansad.in | Parliamentary debates | sansad.in |

## Trigger Real Data Scrape

Once deployed, call:
```
POST /api/scrape/run-full
```
This fetches real Myneta affidavit data for Lok Sabha 2024, UP 2022,
Bihar 2020, Maharashtra 2024, Jharkhand 2024.

Or scrape a specific official:
```
POST /api/scrape/myneta
{"myneta_url": "https://myneta.info/loksabha2024/candidate.php?candidate_id=123"}
```

## Legal & Ethical

- All data is sourced from public government portals
- No private data is collected or stored
- Platform is for transparency and public interest journalism
- Users should verify findings before publication
