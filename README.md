<p align="center">
  <img src="https://img.shields.io/badge/WScaner-Link_Discovery_Tool-0a0a0a?style=for-the-badge&labelColor=0a0a0a&color=22c55e" alt="WScaner" />
</p>

<h1 align="center">🛡️ WScaner</h1>

<p align="center">
  <strong>Local-First Link Discovery & Security Scanner</strong><br/>
  <em>Discover, scan, and monitor all URLs on any website — from your machine.</em>
</p>

<p align="center">
  <a href="#-quick-start--installation"><img src="https://img.shields.io/badge/🚀_Quick_Start-Install_Now-22c55e?style=for-the-badge" alt="Quick Start" /></a>
  <a href="#-features"><img src="https://img.shields.io/badge/✨_Features-Overview-3b82f6?style=for-the-badge" alt="Features" /></a>
  <a href="#-api-reference"><img src="https://img.shields.io/badge/📡_API-Reference-f59e0b?style=for-the-badge" alt="API" /></a>
  <a href="#-contact"><img src="https://img.shields.io/badge/📬_Contact-Author-ef4444?style=for-the-badge" alt="Contact" /></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/next.js-14-000000?style=flat-square&logo=next.js&logoColor=white" />
  <img src="https://img.shields.io/badge/django-4.2-092E20?style=flat-square&logo=django&logoColor=white" />
  <img src="https://img.shields.io/badge/playwright-browser-2EAD33?style=flat-square&logo=playwright&logoColor=white" />
  <img src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square" />
</p>

<p align="center"><em>Designed with brain. Built with heart. — <a href="https://gainazarov.com">Gainazarov</a></em></p>

---

## 📑 Table of Contents

- [🎯 What is WScaner?](#-what-is-wscaner)
- [💡 Why Local-First?](#-why-local-first)
- [✨ Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [🚀 Quick Start & Installation](#-quick-start--installation)
  - [📋 Prerequisites](#-prerequisites)
  - [🍎 macOS / Linux Installation](#-macos--linux-installation)
  - [🪟 Windows Installation](#-windows-installation)
  - [🔧 Manual Installation (Any OS)](#-manual-installation-any-os)
- [🔑 API Keys Setup](#-api-keys-setup)
  - [Google Safe Browsing API Key](#-google-safe-browsing-api-key)
  - [VirusTotal API Key](#-virustotal-api-key)
  - [Configuring Keys in .env](#️-configuring-keys-in-env)
- [📦 Scanner Modules](#-scanner-modules)
- [📡 API Reference](#-api-reference)
- [🎨 Frontend Features](#-frontend-features)
- [🛡️ Domain Reputation](#️-domain-reputation)
- [📁 Project Structure](#-project-structure)
- [⚙️ Command Files Reference](#️-command-files-reference)
- [🛑 Stopping & Managing Services](#-stopping--managing-services)
- [🔧 Troubleshooting](#-troubleshooting)
- [📬 Contact](#-contact)
- [📄 License](#-license)

---

## 🎯 What is WScaner?

WScaner is a **local-first** security & link discovery tool that runs entirely on your machine. It uses **your browser, your IP, your network** — making it indistinguishable from a real user.

| Capability | Description |
|:---|:---|
| 🔍 **Deep Scanning** | Finds ALL possible URLs — HTML, JavaScript, sitemaps, robots.txt, bruteforce |
| 🧠 **Behavior-driven** | Clicks buttons, detects SPA navigation, captures API calls via Playwright |
| 🔐 **Authenticated** | Login via recorded flows, discover private pages behind auth |
| 🌐 **Local Network** | Uses your IP & network — bypasses geo-blocks and anti-bot protections |
| 🆕 **Diff Engine** | Detects new and hidden pages between scans |
| 📊 **Monitoring** | Monitors external domains for reputation threats in real-time |

---

## 💡 Why Local-First?

```
❌ Server-based scanner  →  blocked by anti-bot, geo-restrictions, IP bans, CAPTCHAs
✅ Local-first scanner   →  your browser, your IP, your network = real user behavior
```

| | Server-based | WScaner (Local) |
|---|:---:|:---:|
| **Anti-bot bypass** | ❌ Blocked | ✅ Real browser |
| **Geo-restrictions** | ❌ Server IP | ✅ Your location |
| **CAPTCHA** | ❌ Triggered | ✅ Rare/none |
| **Auth support** | ⚠️ Limited | ✅ Full recorded flows |
| **Privacy** | ❌ Data on server | ✅ 100% local |
| **Cost** | 💰 Subscription | 🆓 Free forever |

> **No server needed. No deployment. No VPS. Just Docker and one click.**

---

## ✨ Features

<table>
<tr><td>

### 🔍 Scanner Engine
- HTML link extraction (`<a>`, `<link>`, `<img>`, `<script>`, `<form>`)
- JavaScript API endpoint discovery (`fetch()`, `axios`, hardcoded URLs)
- `/robots.txt` and `/sitemap.xml` parsing
- Bruteforce with 100+ common paths
- Playwright-based browser crawling
- SPA route detection with DOM change tracking

</td><td>

### 🛡️ Security & Monitoring
- Google Safe Browsing integration
- VirusTotal domain analysis
- Risk aggregation (low / medium / high)
- Periodic monitoring with Celery Beat
- External domain reputation tracking
- Alert system for domain changes

</td></tr>
<tr><td>

### 🔐 Authentication
- Record login flows interactively
- Replay auth for private page scanning
- Cookie/session management
- Multi-strategy auth support
- Sensitive page detection

</td><td>

### 🎨 UI / UX
- Dashboard with stats overview
- URL explorer with filters
- Scan results with diff view
- Mobile-first design
- Bottom navigation
- Dark mode ready

</td></tr>
</table>

---

## 🏗️ Architecture

```
Your Machine (localhost)
 ┌──────────────────────────────────────────────────────────┐
 │                                                          │
 │  ┌─────────────────┐    ┌─────────────────────────────┐  │
 │  │  Frontend        │    │  Backend (Django + DRF)     │  │
 │  │  Next.js :3000   │◄──►│  API Server :8000          │  │
 │  └─────────────────┘    └──────┬──────────────────────┘  │
 │                                │                         │
 │                    ┌───────────┴───────────┐             │
 │                    │                       │             │
 │              ┌─────▼─────┐          ┌──────▼──────┐     │
 │              │  Celery    │          │  Scanner    │     │
 │              │  Worker    │          │  Playwright │     │
 │              │  + Beat    │          │  :8001      │     │
 │              └─────┬─────┘          └─────────────┘     │
 │                    │                                     │
 │              ┌─────▼─────┐    ┌───────────────┐         │
 │              │  Redis     │    │  SQLite DB    │         │
 │              │  :6379     │    │  (local)      │         │
 │              └───────────┘    └───────────────┘         │
 │                                                          │
 └──────────────────────────────────────────────────────────┘
 
 All traffic comes from YOUR machine — same IP, same browser fingerprint
```

---

## 🚀 Quick Start & Installation

### 📋 Prerequisites

Before installing WScaner, make sure you have:

| Requirement | Minimum | Recommended | Download |
|:---|:---:|:---:|:---|
| **Docker Desktop** | v20+ | Latest | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Git** | v2.30+ | Latest | [git-scm.com](https://git-scm.com/downloads) |
| **RAM** | 4 GB | 8 GB+ | — |
| **Disk Space** | 3 GB | 5 GB+ | — |

> 💡 **Docker Desktop** already includes Docker Compose. No separate installation needed.

---

Choose your platform:

<p align="center">
  <a href="#-macos--linux-installation"><img src="https://img.shields.io/badge/🍎_macOS-Install-000000?style=for-the-badge" alt="macOS" /></a>&nbsp;&nbsp;
  <a href="#-windows-installation"><img src="https://img.shields.io/badge/🪟_Windows-Install-0078D4?style=for-the-badge" alt="Windows" /></a>&nbsp;&nbsp;
  <a href="#-manual-installation-any-os"><img src="https://img.shields.io/badge/🔧_Manual-Any_OS-6b7280?style=for-the-badge" alt="Manual" /></a>
</p>

---

### 🍎 macOS / Linux Installation

<details open>
<summary><strong>▶️ Click to expand/collapse macOS / Linux instructions</strong></summary>

#### One-Command Install

Open **Terminal** and run:

```bash
curl -sL https://raw.githubusercontent.com/gainazarov/wscaner/main/start.command -o start.command && chmod +x start.command && ./start.command
```

#### What `start.command` does (step by step):

| Step | Action | Details |
|:---:|:---|:---|
| 1️⃣ | **Check Git** | Detects Git. If missing — installs via `brew` (macOS) or `apt` (Linux) |
| 2️⃣ | **Check Docker** | Detects Docker. If missing — opens download page |
| 3️⃣ | **Start Docker** | If Docker Desktop isn't running — launches it automatically and waits up to 2 min |
| 4️⃣ | **Clone project** | Clones the repo to `~/wscaner` (or pulls updates if already exists) |
| 5️⃣ | **Setup `.env`** | Prompts for API keys (optional) and generates `backend/.env` with secure secret key |
| 6️⃣ | **Build containers** | Runs `docker compose build` with visible progress output |
| 7️⃣ | **Start services** | Runs `docker compose up -d` and waits for health checks |
| 8️⃣ | **Open browser** | Opens `http://localhost:3000` in your default browser |

#### During installation — API Keys prompt:

```
  Для работы репутации доменов нужны API ключи.
  Можно оставить пустыми — сканер будет работать без них.

  Введите GOOGLE_SAFE_BROWSING_API_KEY (Enter = пропустить): <your_key_or_enter>
  Введите VIRUSTOTAL_API_KEY (Enter = пропустить): <your_key_or_enter>
```

> 💡 You can skip both keys and add them later. See [API Keys Setup](#-api-keys-setup).

#### After installation:

```
  ╔══════════════════════════════════════════════╗
  ║          ✅  WScaner запущен!  ✅            ║
  ║                                              ║
  ║    🌐  http://localhost:3000                 ║
  ║    📡  http://localhost:8000/api             ║
  ╚══════════════════════════════════════════════╝
```

Press **Enter** in the terminal to stop services and exit.

</details>

---

### 🪟 Windows Installation

<details>
<summary><strong>▶️ Click to expand Windows instructions</strong></summary>

#### Step 0 — Install Prerequisites

Before running the installer, make sure you have:

**1. Git for Windows**

- Download: [https://git-scm.com/downloads](https://git-scm.com/downloads)
- During installation: leave all defaults, click **"Next"** → **"Install"**
- ✅ After install, **restart your terminal**

**2. Docker Desktop for Windows**

- Download: [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
- Requirements: **Windows 10/11** (64-bit), **WSL 2** enabled
- During installation: check ✅ **"Use WSL 2 instead of Hyper-V"**
- ✅ After install, **restart your PC**
- Launch Docker Desktop and wait for it to fully start (whale icon 🐳 in system tray)

> ⚠️ **WSL 2 Note**: Docker Desktop requires WSL 2. If you don't have it, Docker installer will prompt you. Or install manually:
> ```powershell
> wsl --install
> ```
> Then **restart your PC**.

#### Step 1 — Download and run the installer

Open **PowerShell** or **Command Prompt** and run:

```powershell
curl -sL https://raw.githubusercontent.com/gainazarov/wscaner/main/start.bat -o start.bat && .\start.bat
```

**Or manually:**
1. Download [`start.bat`](https://raw.githubusercontent.com/gainazarov/wscaner/main/start.bat) from the repository
2. Double-click `start.bat`

#### What `start.bat` does (step by step):

| Step | Action | Details |
|:---:|:---|:---|
| 1️⃣ | **Check Git** | Detects Git. If missing — tries `winget install Git.Git`. If winget unavailable — opens download page |
| 2️⃣ | **Check Docker** | Detects Docker. If missing — opens Docker Desktop download page |
| 3️⃣ | **Start Docker** | If Docker isn't running — launches `Docker Desktop.exe` and waits up to 2 min |
| 4️⃣ | **Clone project** | Clones the repo to `%USERPROFILE%\wscaner` (or pulls updates if exists) |
| 5️⃣ | **Setup `.env`** | Prompts for API keys (optional) and creates `backend\.env` |
| 6️⃣ | **Build containers** | Runs `docker compose build` — may take 3-10 min on first build |
| 7️⃣ | **Start services** | Runs `docker compose up -d` and checks for running containers |
| 8️⃣ | **Open browser** | Opens `http://localhost:3000` in your default browser |

#### During installation — API Keys prompt:

```
  API keys are needed for domain reputation features.
  You can leave them empty - scanner will work without them.

  GOOGLE_SAFE_BROWSING_API_KEY (Enter to skip): <your_key_or_enter>
  VIRUSTOTAL_API_KEY (Enter to skip): <your_key_or_enter>
```

> 💡 You can skip both keys by pressing **Enter**. See [API Keys Setup](#-api-keys-setup) for how to get and add them later.

#### After installation:

```
  =========================================================
  =                                                       =
  =           [OK] WScaner is running!                    =
  =                                                       =
  =    WEB:  http://localhost:3000                         =
  =    API:  http://localhost:8000/api                     =
  =                                                       =
  =========================================================
```

Press **any key** in the terminal window to stop services and exit.

#### ⚠️ Common Windows Issues:

| Problem | Solution |
|:---|:---|
| `winget` not found | Install **App Installer** from Microsoft Store, or install Git manually |
| Git installed but "not found" | Close terminal and run `start.bat` again (PATH update needs new terminal) |
| Docker not starting | Make sure WSL 2 is installed: `wsl --install`, then restart PC |
| Build fails with permission error | Right-click `start.bat` → **"Run as Administrator"** |
| Port 3000 or 8000 in use | Stop other services using those ports (see [Troubleshooting](#-troubleshooting)) |
| "Hyper-V is not enabled" | Enable in: Settings → Apps → Optional Features → More Windows Features → ✅ Hyper-V |

</details>

---

### 🔧 Manual Installation (Any OS)

<details>
<summary><strong>▶️ Click to expand manual installation instructions</strong></summary>

If you prefer full control, follow these steps:

#### Step 1 — Clone the repository

```bash
git clone https://github.com/gainazarov/wscaner.git
cd wscaner
```

#### Step 2 — Create the environment file

Create the file `backend/.env`:

```bash
cat > backend/.env << 'EOF'
# WScaner Backend Environment
APP_MODE=local
DJANGO_SECRET_KEY=your-random-secret-key-change-this
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
SCANNER_SERVICE_URL=http://scanner:8001
GOOGLE_SAFE_BROWSING_API_KEY=
VIRUSTOTAL_API_KEY=
DOMAIN_REPUTATION_CACHE_HOURS=24
EOF
```

> 💡 Generate a secure secret key:
> ```bash
> openssl rand -hex 32
> ```

#### Step 3 — (Optional) Add API keys

Edit `backend/.env` and set your keys:

```dotenv
GOOGLE_SAFE_BROWSING_API_KEY=your_google_key_here
VIRUSTOTAL_API_KEY=your_virustotal_key_here
```

See [API Keys Setup](#-api-keys-setup) for how to get these keys.

#### Step 4 — Build all containers

```bash
docker compose build --progress=plain
```

> ⏱️ First build takes **3-10 minutes** depending on your internet speed.

#### Step 5 — Start all services

```bash
docker compose up -d
```

#### Step 6 — Verify everything is running

```bash
# Check all containers
docker compose ps

# Expected output — all services should be "running":
# NAME                    STATUS
# wscaner-backend-1       running
# wscaner-celery-1        running
# wscaner-celery-beat-1   running
# wscaner-frontend-1      running
# wscaner-redis-1         running (healthy)
# wscaner-scanner-1       running
```

#### Step 7 — Open the UI

Open your browser and navigate to:

| Service | URL |
|:---|:---|
| 🌐 **Frontend** | [http://localhost:3000](http://localhost:3000) |
| 📡 **API** | [http://localhost:8000/api](http://localhost:8000/api) |

</details>

---

## 🔑 API Keys Setup

API keys enable **domain reputation checking** — detecting malware, phishing, and other threats. The scanner works fully without them, but reputation features will be disabled.

---

### 🔎 Google Safe Browsing API Key

<details>
<summary><strong>▶️ How to get a Google Safe Browsing API Key (free)</strong></summary>

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services** → **Library**
4. Search for **"Safe Browsing API"**
5. Click **Enable**
6. Go to **APIs & Services** → **Credentials**
7. Click **"+ CREATE CREDENTIALS"** → **"API key"**
8. Copy the generated key
9. *(Recommended)* Restrict the key to "Safe Browsing API" only for security

> 🆓 **Free tier**: 10,000 requests/day — more than enough for local scanning.

</details>

---

### 🦠 VirusTotal API Key

<details>
<summary><strong>▶️ How to get a VirusTotal API Key (free)</strong></summary>

1. Go to [virustotal.com](https://www.virustotal.com/)
2. Sign up for a free account
3. Go to your **Profile** (top-right avatar) → **API Key**
4. Copy your API key

> 🆓 **Free tier**: 4 requests/minute, 500 requests/day.

</details>

---

### ⚙️ Configuring Keys in `.env`

#### Option A: During installation (recommended)

Both `start.command` (macOS/Linux) and `start.bat` (Windows) will **prompt you for API keys** during the first install. Simply paste them when asked:

```
  GOOGLE_SAFE_BROWSING_API_KEY (Enter to skip): AIzaSy...paste_your_key_here
  VIRUSTOTAL_API_KEY (Enter to skip): 6ec42a...paste_your_key_here
```

#### Option B: Edit `.env` file manually after install

```bash
# Navigate to the project
cd ~/wscaner           # macOS/Linux
cd %USERPROFILE%\wscaner  # Windows
```

Open `backend/.env` in any text editor and set your keys:

```dotenv
GOOGLE_SAFE_BROWSING_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
VIRUSTOTAL_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Then **restart** the backend and celery to apply changes:

```bash
docker compose restart backend celery
```

#### Option C: Skip keys entirely

Leave the values empty. The scanner will work perfectly for URL discovery and scanning — only domain reputation checks will be unavailable:

```dotenv
GOOGLE_SAFE_BROWSING_API_KEY=
VIRUSTOTAL_API_KEY=
```

---

## 📦 Scanner Modules

| Module | File | What it does |
|:---|:---|:---|
| **HTML Module** | `scanner/modules/html_module.py` | Extracts links from `<a>`, `<link>`, `<img>`, `<script>`, `<form>`, `<iframe>`, `<meta>`, etc. |
| **JS Module** | `scanner/modules/js_module.py` | Parses `fetch()`, `axios()`, API endpoints, hardcoded URLs from JavaScript files |
| **Robots Module** | `scanner/modules/robots_module.py` | Parses `/robots.txt` for Allow/Disallow paths and sitemap references |
| **Sitemap Module** | `scanner/modules/sitemap_module.py` | Parses `/sitemap.xml` including nested sitemap indexes |
| **Bruteforce Module** | `scanner/modules/bruteforce_module.py` | Tries 100+ common paths (`/admin`, `/api`, `/dev`, `/login`, `/dashboard`, etc.) |
| **Browser Crawler** | `scanner/core/engine.py` | Playwright-based: clicks buttons, detects SPA routes, captures XHR/fetch requests |
| **SPA Crawler** | `scanner/core/spa_crawler.py` | Advanced SPA detection with DOM change tracking & click deduplication |
| **Auth Helpers** | `scanner/core/auth_helpers.py` | Authenticated scanning — replays recorded login flows |
| **Diff Engine** | `scanner/core/diff_engine.py` | Compares scans to detect new, removed, or changed URLs |

---

## 📡 API Reference

### Scans

| Method | Endpoint | Description |
|:---:|:---|:---|
| `POST` | `/api/scans/` | Create a new scan |
| `GET` | `/api/scans/` | List all scans |
| `GET` | `/api/scans/{id}/` | Get scan details with full stats |
| `GET` | `/api/scans/{id}/urls/` | Get discovered URLs (with source/status filters) |
| `GET` | `/api/scans/{id}/diff/` | Get diff with previous scan (new/removed URLs) |
| `POST` | `/api/scans/{id}/rescan/` | Re-scan the same domain |

### Domains & Dashboard

| Method | Endpoint | Description |
|:---:|:---|:---|
| `GET` | `/api/domains/` | Domain statistics |
| `GET` | `/api/dashboard/` | Dashboard stats (total scans, URLs, domains) |

### Monitoring & Reputation

| Method | Endpoint | Description |
|:---:|:---|:---|
| `GET` | `/api/monitoring/` | External monitoring + reputation data |
| `POST` | `/api/monitoring/reputation/check/` | Queue async domain reputation check |

### System

| Method | Endpoint | Description |
|:---:|:---|:---|
| `GET` | `/api/health/` | Service health check |

---

## 🎨 Frontend Features

| Feature | Description |
|:---|:---|
| ⚡ **Dashboard** | Stats overview, recent scans, one-click new scan creation |
| 🔍 **Scan Results** | URL list with filters by source, HTTP status, new/old detection |
| 🗺️ **URL Explorer** | Browse all discovered domains and scan history |
| 🔐 **Auth Settings** | Record login flows for authenticated scanning |
| 📊 **Monitoring** | Track external domains, check reputation, view alerts |
| 📱 **Mobile-first** | Bottom navigation, card layout, touch-friendly design |

---

## 🛡️ Domain Reputation

Built-in async reputation checks powered by:

| Provider | Detects |
|:---|:---|
| **Google Safe Browsing** | Malware, social engineering, unwanted software, potentially harmful apps |
| **VirusTotal** | Comprehensive domain analysis with 70+ security vendors |
| **Risk Aggregation** | Combines all results into **low** / **medium** / **high** risk score |

Results are cached for **24 hours** (configurable via `DOMAIN_REPUTATION_CACHE_HOURS` in `.env`).

---

## 📁 Project Structure

```
wscaner/
├── start.command             ← 🍎 macOS/Linux one-click launcher
├── start.bat                 ← 🪟 Windows one-click launcher
├── stop.command              ← 🍎 macOS/Linux service stopper
├── stop.bat                  ← 🪟 Windows service stopper
├── docker-compose.yml        ← 🐳 Local stack (6 services)
│
├── backend/                  ← 🐍 Django REST API
│   ├── .env                  ← 🔐 Environment variables (API keys, secrets)
│   ├── manage.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── config/               ← ⚙️  Django settings, URLs, Celery config
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── celery.py
│   │   └── wsgi.py
│   └── scans/                ← 📊 Models, Views, Serializers, Tasks
│       ├── models.py         ← Data models (Scan, URL, Domain, Alert)
│       ├── views.py          ← API endpoints
│       ├── serializers.py    ← DRF serializers
│       ├── tasks.py          ← Celery async tasks
│       ├── reputation.py     ← Domain reputation checking
│       ├── light_scanner.py  ← Lightweight scan mode
│       └── migrations/       ← Database migrations
│
├── frontend/                 ← ⚛️  Next.js UI
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── app/              ← 📄 Pages (Dashboard, Scan, Explorer, Settings, Monitoring)
│       ├── components/       ← 🧩 React components (organized by feature)
│       └── lib/              ← 🔗 API client (axios-based)
│
└── scanner/                  ← 🔍 Scanner microservice (FastAPI + Playwright)
    ├── main.py               ← Uvicorn entrypoint
    ├── Dockerfile
    ├── requirements.txt
    ├── core/                 ← 🧠 Engine, SPA crawler, Auth, Diff, Recorder
    ├── modules/              ← 📦 HTML, JS, Robots, Sitemap, Bruteforce parsers
    ├── utils/                ← 🔧 URL normalization & validation
    └── workers/              ← 👷 Worker processes
```

---

## ⚙️ Command Files Reference

### `start.command` — macOS / Linux Launcher

| Feature | Description |
|:---|:---|
| **Auto-install Git** | Detects missing Git and installs via `brew` (macOS) or `apt-get` (Linux) |
| **Auto-detect Docker** | Opens Docker Desktop download page if Docker is not found |
| **Auto-start Docker** | Launches Docker Desktop if not running, waits up to 2 minutes for readiness |
| **Smart mode detection** | **First install** = clone + setup `.env`; **Repeat run** = `git pull` + preserve existing `.env` |
| **API key prompt** | Interactive prompt for Google Safe Browsing & VirusTotal keys |
| **Secure secret key** | Generates random `DJANGO_SECRET_KEY` via `openssl rand -hex 32` |
| **Animated progress** | Shows build progress with animated spinners and progress bars |
| **Health check** | Waits for both backend (`/api/health/`) and frontend (`:3000`) before opening browser |
| **Graceful shutdown** | Press Enter in terminal → stops all containers via `docker compose down` |

### `start.bat` — Windows Launcher

| Feature | Description |
|:---|:---|
| **Auto-install Git** | Tries `winget install Git.Git` automatically if Git is missing |
| **Docker check** | Detects Docker, opens download page if not installed |
| **Auto-start Docker** | Launches `Docker Desktop.exe` if not running, waits up to 2 minutes |
| **Smart mode detection** | **First install** = clone + setup `.env`; **Repeat run** = `git pull` + preserve `.env` |
| **API key prompt** | Interactive prompt for API keys during first install |
| **Full build output** | Runs `docker compose build` with complete progress visible |
| **Service readiness check** | Polls containers until they reach "running" state |
| **Auto-open browser** | Opens `http://localhost:3000` automatically after services are ready |
| **Graceful shutdown** | Press any key → stops all containers and exits |

### `stop.command` / `stop.bat` — Service Stoppers

| Feature | Description |
|:---|:---|
| **Safe stop** | Gracefully stops all Docker containers with `docker compose down` |
| **Status display** | Shows currently running services and their ports before stopping |
| **Force fallback** | If graceful stop fails → `docker compose down --remove-orphans --timeout 10` |
| **Helpful tips** | Displays useful Docker commands after stopping |

---

## 🛑 Stopping & Managing Services

### Stop all services

```bash
# Using stop script
./stop.command          # macOS/Linux
stop.bat                # Windows

# Or manually from the project directory
cd ~/wscaner && docker compose down
```

### Useful Docker commands

```bash
# View running containers
docker compose ps

# View real-time logs (all services)
docker compose logs -f

# View logs for a specific service
docker compose logs -f backend
docker compose logs -f scanner
docker compose logs -f frontend

# Restart a specific service
docker compose restart backend

# Rebuild and restart everything
docker compose down && docker compose build && docker compose up -d

# Rebuild without cache (fixes stale build issues)
docker compose build --no-cache

# Clean Docker cache (free disk space)
docker system prune -f
docker volume prune -f
```

---

## 🔧 Troubleshooting

<details>
<summary><strong>🐳 Docker Issues</strong></summary>

| Problem | Solution |
|:---|:---|
| Docker not found | Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) |
| Docker not starting | Restart Docker Desktop, check system resources (RAM, disk) |
| WSL 2 error (Windows) | Run `wsl --install` in PowerShell as admin, then restart PC |
| Permission denied (Linux) | Add user to docker group: `sudo usermod -aG docker $USER`, then re-login |
| Out of disk space | Run `docker system prune -af && docker volume prune -f` |
| "Cannot connect to Docker daemon" | Start Docker Desktop app first, then retry |

</details>

<details>
<summary><strong>🌐 Port Conflicts</strong></summary>

If a port is already in use:

**macOS / Linux:**
```bash
# Find what's using port 3000
lsof -i :3000

# Kill the process
kill -9 <PID>
```

**Windows:**
```powershell
# Find what's using port 3000
netstat -ano | findstr :3000

# Kill the process
taskkill /PID <PID> /F
```

| Port | Service | Default user |
|:---:|:---|:---|
| 3000 | Frontend (Next.js) | Node.js apps, React dev servers |
| 8000 | Backend (Django) | Other Django/Python apps |
| 8001 | Scanner (Playwright) | — |
| 6379 | Redis | Local Redis instance |

</details>

<details>
<summary><strong>🔑 API Keys Not Working</strong></summary>

1. Verify `backend/.env` file exists:
   ```bash
   cat backend/.env  # macOS/Linux
   type backend\.env  # Windows
   ```
2. Check there are **no extra spaces** around `=`:
   ```dotenv
   # ✅ Correct
   GOOGLE_SAFE_BROWSING_API_KEY=AIzaSy...
   
   # ❌ Wrong
   GOOGLE_SAFE_BROWSING_API_KEY = AIzaSy...
   ```
3. Restart services after changing `.env`:
   ```bash
   docker compose restart backend celery
   ```
4. Check logs for API errors:
   ```bash
   docker compose logs backend | grep -i "api\|key\|error\|reputation"
   ```

</details>

<details>
<summary><strong>🏗️ Build Failures</strong></summary>

| Problem | Solution |
|:---|:---|
| Network timeout during build | Check internet connection, retry: `docker compose build` |
| Out of memory | Close other apps, increase Docker memory in Settings → Resources |
| Stale cache issues | Rebuild without cache: `docker compose build --no-cache` |
| Platform mismatch (Apple M1/M2/M3) | Docker Desktop handles ARM natively — just rebuild |
| `npm install` fails | Delete `frontend/node_modules` and rebuild: `docker compose build --no-cache frontend` |

</details>

<details>
<summary><strong>🗄️ Database Issues</strong></summary>

| Problem | Solution |
|:---|:---|
| Migration errors | Run: `docker compose exec backend python manage.py migrate` |
| Corrupted database | Delete `backend/db.sqlite3` and restart — migrations will recreate it |
| Reset everything | `docker compose down -v` (⚠️ deletes all data including Redis) |

</details>

---

## 📬 Contact

<p align="center">
  <a href="https://gainazarov.com"><img src="https://img.shields.io/badge/🌐_Website-gainazarov.com-22c55e?style=for-the-badge" alt="Website" /></a>&nbsp;&nbsp;
  <a href="mailto:ardashergainazarov@gmail.com"><img src="https://img.shields.io/badge/📧_Email-ardashergainazarov@gmail.com-ea4335?style=for-the-badge" alt="Email" /></a>&nbsp;&nbsp;
  <a href="https://t.me/gainazarov_a"><img src="https://img.shields.io/badge/💬_Telegram-@gainazarov__a-2AABEE?style=for-the-badge" alt="Telegram" /></a>
</p>

| Channel | Contact |
|:---|:---|
| 🌐 **Website** | [gainazarov.com](https://gainazarov.com) |
| 📧 **Email** | [ardashergainazarov@gmail.com](mailto:ardashergainazarov@gmail.com) |
| 💬 **Telegram** | [@gainazarov_a](https://t.me/gainazarov_a) |

---

## 📄 License

MIT License — free for personal and commercial use.

---

<p align="center">
  <strong>🛡️ WScaner</strong> — Find every link. Miss nothing. From your machine.<br/><br/>
  <em>Made with ❤️ by <a href="https://gainazarov.com">Gainazarov</a></em>
</p>