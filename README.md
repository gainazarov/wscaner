# 🛡️ WScaner — Local-First Link Discovery Tool

> Discover, scan, and monitor all URLs on any website.  
> Runs entirely on your machine — your IP, your network, your browser.  
> **Designed with brain. Built with heart. — Gainazarov**

---

## 🎯 What is WScaner?

WScaner is a **local-first** security & link discovery tool that:

- 🔍 **Scans** websites to find ALL possible URLs (HTML, JS, sitemap, robots, bruteforce)
- 🧠 **Behavior-driven** — clicks buttons, detects SPA navigation, captures API calls
- 🔐 **Authenticated scanning** — login via recorded flows, discover private pages
- 🌐 **Uses your IP & network** — bypasses geo-blocks and anti-bot protections
- 🆕 **Detects** new and hidden pages with diff engine
- 📊 **Monitors** external domains for reputation threats

## 💡 Why Local-First?

```
❌ Server-based scanner → blocked by anti-bot, geo-restrictions, IP bans
✅ Local scanner → your browser, your IP, your network = real user behavior
```

No server needed. No deployment. No VPS. Just Docker and one click.

## 🏗️ Architecture

```
Your Machine (localhost)
 ├── Frontend (Next.js)      → :3000
 ├── Backend (Django + DRF)  → :8000
 ├── Scanner (Playwright)    → :8001
 ├── Celery Worker           → async tasks
 ├── Redis                   → :6379
 └── SQLite (local DB)
```

All traffic comes from **your machine** — same IP, same network, same browser fingerprint as a real user.

## 🚀 Quick Start

### Prerequisites

- **Git** — [git-scm.com/downloads](https://git-scm.com/downloads)
- **Docker Desktop** — [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
- **4GB+ RAM** recommended

### Install & Run (One Command)

#### macOS / Linux

```bash
# Download and run the launcher:
curl -sL https://raw.githubusercontent.com/gainazarov/wscaner/main/start.command -o start.command && chmod +x start.command && ./start.command
```

#### Windows

```powershell
# Download and run the launcher:
curl -sL https://raw.githubusercontent.com/gainazarov/wscaner/main/start.bat -o start.bat && start.bat
```

#### Manual

```bash
git clone https://github.com/gainazarov/wscaner.git
cd wscaner
docker compose build --progress=plain
docker compose up -d
# Open: http://localhost:3000
```

**The launcher will automatically:**
1. ✅ Check/install Git & Docker
2. ✅ Clone the project from GitHub
3. ✅ Build all containers (with visible progress)
4. ✅ Start services & health-check
5. ✅ Open the UI in your browser

## 📦 Scanner Modules

| Module | What it does |
|--------|-------------|
| **HTML Module** | Extracts links from `<a>`, `<link>`, `<img>`, `<script>`, `<form>`, etc. |
| **JS Module** | Parses `fetch()`, `axios`, API endpoints from JavaScript |
| **Robots Module** | Parses `/robots.txt` for Allow/Disallow paths |
| **Sitemap Module** | Parses `/sitemap.xml` including sitemap indexes |
| **Bruteforce Module** | Tries 100+ common paths (`/admin`, `/api`, `/dev`, etc.) |
| **Browser Crawler** | Playwright-based: clicks buttons, detects SPA routes, captures XHR/fetch |
| **SPA Crawler** | Authenticated browsing with DOM change detection & click deduplication |

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
| `GET` | `/api/monitoring/` | External monitoring + reputation |
| `POST` | `/api/monitoring/reputation/check/` | Queue domain reputation check |

## 🎨 Frontend Features

- ⚡ **Dashboard** — Stats overview, recent scans, create new scan
- 🔍 **Scan Results** — URL list with filters by source, status, new/old
- 🗺️ **URL Explorer** — Browse all domains and scan history
- 🔐 **Auth Settings** — Record login flows for authenticated scanning
- 📊 **Monitoring** — Track external domains, reputation checks
- 📱 **Mobile-first** — Bottom navigation, card layout, touch-friendly

## 🛡️ Domain Reputation

Built-in async reputation checks:

- **Google Safe Browsing** (malware, social engineering, unwanted software)
- **VirusTotal** domain analysis
- **Risk aggregation** (low / medium / high)

```bash
# Set API keys in backend/.env
GOOGLE_SAFE_BROWSING_API_KEY=your_key
VIRUSTOTAL_API_KEY=your_key
```

## 📁 Project Structure

```
/scaner
  start.command             ← macOS one-click launcher
  start.bat                 ← Windows one-click launcher
  docker-compose.yml        ← Local stack (all services)
  /backend                  ← Django API
    /config                 ← Settings, URLs, Celery
    /scans                  ← Models, Views, Serializers, Tasks
  /frontend                 ← Next.js UI
    /src
      /app                  ← Pages (Dashboard, Scan, Explorer, Settings)
      /components           ← React components
      /lib                  ← API client
  /scanner                  ← Scanner service
    /core                   ← Engine, SPA crawler, Recorder, Auth helpers
    /modules                ← HTML, JS, Robots, Sitemap, Bruteforce
    /utils                  ← URL normalization, validation
```

## ⚙️ Requirements

- **Docker Desktop** (macOS / Windows / Linux)
- **4GB+ RAM** recommended
- **Git** (for cloning)

## 🛑 Stopping

```bash
# From terminal
docker compose down

# Or press Enter in the launcher window
```

## License

MIT

---

**WScaner** — Find every link. Miss nothing. From your machine.
