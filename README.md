# 🛡️ WScaner — Link Discovery Scanner

> Discover, scan, and monitor all URLs on any website.  
> **Designed with brain. Built with heart. — Gainazarov • ZIYO**

---

## 🎯 What is WScaner?

WScaner is a powerful link discovery system that:

- 🔍 **Scans** websites to find ALL possible URLs
- 🆕 **Detects** new and hidden pages
- 📊 **Tracks** changes between scans
- ⚡ **Built** for speed with async architecture

## 🏗️ Architecture

```
User → Next.js UI → Django API → Celery → Scanner Service → DB → Diff Engine → UI
```

| Service | Tech | Port |
|---------|------|------|
| Frontend | Next.js + Tailwind + Framer Motion | :3000 |
| Backend API | Django + DRF + Celery | :8000 |
| Scanner | Python + aiohttp + BeautifulSoup | :8001 |
| Broker | Redis | :6379 |

## 📦 Scanner Modules

| Module | What it does |
|--------|-------------|
| **HTML Module** | Extracts links from `<a>`, `<link>`, `<img>`, `<script>`, `<form>`, etc. |
| **JS Module** | Parses `fetch()`, `axios`, API endpoints from JavaScript |
| **Robots Module** | Parses `/robots.txt` for Allow/Disallow paths |
| **Sitemap Module** | Parses `/sitemap.xml` including sitemap indexes |
| **Bruteforce Module** | Tries 100+ common paths (`/admin`, `/api`, `/dev`, etc.) |

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone and start everything
cd scaner
docker compose up --build
```

Then open:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/api/
- **Scanner Health**: http://localhost:8001/health

### Option 2: Manual Setup

#### Backend (Django)

```bash
cd backend
python -m venv venv
source venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

#### Scanner Service

```bash
cd scanner
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

#### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

#### Celery Worker (requires Redis)

```bash
cd backend
celery -A config worker -l info
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/scans/` | Create a new scan |
| `GET` | `/api/scans/` | List all scans |
| `GET` | `/api/scans/{id}/` | Get scan details |
| `GET` | `/api/scans/{id}/urls/` | Get discovered URLs (with filters) |
| `GET` | `/api/scans/{id}/diff/` | Get diff with previous scan |
| `POST` | `/api/scans/{id}/rescan/` | Re-scan same domain |
| `GET` | `/api/domains/` | Domain statistics |
| `GET` | `/api/dashboard/` | Dashboard stats |
| `GET` | `/api/monitoring/` | External monitoring + reputation summary |
| `GET` | `/api/monitoring/reputation/` | Cached domain reputation results |
| `POST` | `/api/monitoring/reputation/check/` | Queue/force one domain reputation check |
| `POST` | `/api/monitoring/reputation/check-all/` | Queue checks for all tracked domains |

### Create a scan

```bash
curl -X POST http://localhost:8000/api/scans/ \
  -H "Content-Type: application/json" \
  -d '{"domain": "example.com", "max_depth": 3, "max_pages": 500}'
```

### Filter URLs

```bash
# Get only new URLs
GET /api/scans/1/urls/?is_new=true

# Filter by source
GET /api/scans/1/urls/?source=bruteforce

# Search
GET /api/scans/1/urls/?search=admin
```

## 🎨 Frontend Features

- ⚡ **Dashboard** — Stats overview, recent scans, create new scan
- 🔍 **Scan Results** — URL list with filters by source, status, new/old
- 🗺️ **URL Explorer** — Browse all domains and scan history
- 📱 **Mobile-first** — Bottom navigation, card layout, touch-friendly
- ✨ **Animations** — Framer Motion transitions, skeleton loading, hover effects

## 🛡️ Domain Reputation

WScaner includes async domain reputation checks via:

- **Google Safe Browsing** (`MALWARE`, `SOCIAL_ENGINEERING`, `UNWANTED_SOFTWARE`)
- **VirusTotal** domain analysis
- **Risk aggregation** (`low` / `medium` / `high`)
- **Redis queue** (`reputation_queue`) + **Celery worker**
- **Cache TTL** (default 24h) to reduce API usage

### Required backend env vars

```bash
GOOGLE_SAFE_BROWSING_API_KEY=your_key
VIRUSTOTAL_API_KEY=your_key
DOMAIN_REPUTATION_CACHE_HOURS=24
```

## 🗄️ Database Schema

### Scans
- `id`, `domain`, `status`, `total_urls`, `new_urls`, `max_depth`, `max_pages`, `started_at`, `completed_at`

### Discovered URLs
- `id`, `scan_id`, `url`, `source`, `status_code`, `content_type`, `depth`, `is_internal`, `is_new`, `first_seen`, `last_seen`

### Scan Diffs
- `id`, `current_scan`, `previous_scan`, `new_urls_count`, `removed_urls_count`

## 📈 Roadmap

### v1 (MVP) ✅
- [x] HTML crawler
- [x] JS parser
- [x] Robots.txt parser
- [x] Sitemap parser
- [x] Bruteforce module
- [x] Diff engine
- [x] REST API
- [x] Next.js UI

### v2
- [ ] Telegram/Email alerts
- [ ] Scheduled scans (cron)
- [ ] Authentication & user accounts
- [ ] Export (CSV, JSON)

### v3
- [ ] Multiple workers (horizontal scaling)
- [ ] Subdomain discovery
- [ ] Technology detection
- [ ] SaaS multi-tenancy

## 📁 Project Structure

```
/scaner
  /backend                  ← Django API
    /config                 ← Settings, URLs, Celery
    /scans                  ← Models, Views, Serializers, Tasks
  /frontend                 ← Next.js UI
    /src
      /app                  ← Pages (Dashboard, Scan, Explorer)
      /components           ← React components
      /lib                  ← API client
  /scanner                  ← Standalone scanner service
    /core                   ← Scanner engine
    /modules                ← HTML, JS, Robots, Sitemap, Bruteforce
    /utils                  ← URL normalization, validation
  docker-compose.yml        ← Full stack orchestration
```

## License

MIT

---

**WScaner** — Find every link. Miss nothing.
