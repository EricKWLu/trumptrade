# TrumpTrade

Automated trading bot that monitors Donald Trump's Truth Social and X/Twitter posts, analyzes them with AI sentiment analysis and keyword rules, and executes trades on a user-defined stock watchlist via Alpaca. Includes a live web dashboard for monitoring and control.

**Goal:** React to Trump's posts faster than a human can — turning his words into trade signals before the market moves.

---

## How It Works

```
[Truth Social poller] ─┐
                       ├─► [SHA-256 dedup] ─► [LLM + keyword analysis]
[X/Twitter poller]  ───┘                               │
                                              [confidence gate ≥0.7]
                                                        │
                                              [risk guard queue]
                                         (position size, daily cap,
                                          market hours check)
                                                        │
                                    ┌───────────────────┴───────────────────┐
                                    ▼                                       ▼
                          [Alpaca executor]                      [shadow portfolios]
                         (paper or live)                      (SPY / QQQ / random NAV)
                                    │
                                    ▼
                          [SQLite audit log]
                                    │
                                    ▼
                      [FastAPI + WebSocket + React dashboard]
```

1. **Pollers** check Truth Social (every 60s) and X/Twitter (every 5m) for new posts
2. **Deduplication** — SHA-256 hash of stripped post text prevents duplicate analysis
3. **Analysis** — LLM classifies the post as BULLISH / BEARISH / NEUTRAL against your watchlist; keyword rules act as an override layer
4. **Risk guard** — checks position size, daily loss cap, and market hours before queuing a trade
5. **Executor** — places bracket orders on Alpaca (stop-loss always atomic with entry)
6. **Dashboard** — live feed, trade history, portfolio, benchmark comparison, settings

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, APScheduler (in-process) |
| Trading | `alpaca-py` — paper and live via `paper-api.alpaca.markets` / `api.alpaca.markets` |
| Truth Social | `truthbrush` — Chrome-impersonating scraper (no official API) |
| X/Twitter | `tweepy` — X API v2 (requires paid Basic tier) |
| LLM | OpenAI, Anthropic, or Groq (configurable via `.env`) |
| Database | SQLite + SQLAlchemy 2.x async + Alembic migrations |
| Frontend | React 18, Vite, shadcn/ui, TanStack Query v5, Recharts |
| Server | Nginx (reverse proxy + static files), systemd (process manager) |

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- An Alpaca account (paper trading is free)

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/trump_trade.git
cd trump_trade

# Backend
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .

# Frontend
cd frontend && npm install && cd ..
```

### 2. Configure `.env`

Copy `.env.example` to `.env` and fill in your credentials:

```env
# Alpaca — paper trading keys (PK... prefix) from alpaca.markets
ALPACA_API_KEY=PKxxxxxxxxxxxxxxxxxxxxxxxx
ALPACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# X/Twitter — requires paid Basic developer tier (~$100/mo)
X_API_KEY=
X_API_SECRET=
X_BEARER_TOKEN=

# LLM — at least one required (Groq is cheapest for testing)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=

# Truth Social — your account credentials (used by truthbrush scraper)
TRUTH_SOCIAL_USERNAME=your@email.com
TRUTH_SOCIAL_PASSWORD=yourpassword
TRUTH_SOCIAL_TOKEN=          # optional: manual token override

# Database — absolute path recommended for production; relative fine for dev
DB_URL=sqlite+aiosqlite:///./trumptrade.db
DEBUG=false
```

### 3. Run database migrations

```bash
alembic upgrade head
```

### 4. Start the backend

```bash
python -m trumptrade
# FastAPI starts on http://localhost:8000
```

### 5. Start the frontend (separate terminal)

```bash
cd frontend
npm run dev
# Vite dev server starts on http://localhost:5173
# Proxies /posts, /trades, /portfolio, etc. to localhost:8000 automatically
```

Open `http://localhost:5173` in your browser.

---

## Configuration

All runtime settings (risk controls, trading mode) are stored in the database and editable from the dashboard Settings page. No restart required.

| Setting | Default | Description |
|---------|---------|-------------|
| Max position size | 2% | Maximum % of portfolio per trade |
| Stop-loss | 5% | Stop-loss distance from fill price |
| Max daily loss | $500 | Daily loss cap — halts trading when hit |
| Signal staleness | 5 min | Posts older than this are ignored |
| Trading mode | paper | `paper` or `live` — switch from Settings page |
| Bot enabled | true | Kill switch — disables trade execution instantly |

### LLM Provider

Set in `.env` via which key you populate. The analysis engine tries providers in this order: OpenAI → Anthropic → Groq. Leave unused keys empty.

### Watchlist

Managed from the dashboard Settings page. The bot only trades symbols on your watchlist — the LLM is never allowed to suggest new tickers.

---

## Trading Modes

### Paper Mode (default)

- Trades go to `paper-api.alpaca.markets` — simulated money, real market prices
- Safe for testing — no real money at risk
- Switch from the Settings page

### Live Mode

- Trades go to `api.alpaca.markets` — real money
- Requires a funded Alpaca brokerage account
- Requires typing `ENABLE LIVE TRADING` in a confirmation modal to activate
- A red banner appears across the dashboard whenever live mode is active

### Shadow Portfolios (Benchmarks page)

Three comparison portfolios track the same time period as the bot:
- **SPY** — tracks S&P 500 ETF
- **QQQ** — tracks Nasdaq-100 ETF
- **Random** — random buy/sell baseline

Snapshots taken daily at 4:01 PM ET on trading days. All portfolios start at $100,000 virtual NAV.

---

## Deployment (Oracle Cloud Free Tier)

The app runs 24/7 on an Oracle Cloud Always Free ARM VM — no ongoing cost.

### VM Specs (Always Free)

- Shape: `VM.Standard.A1.Flex` — 1 OCPU, 6 GB RAM
- OS: Ubuntu 22.04 aarch64
- Storage: 50 GB boot volume

### One-time Setup

Follow these steps after creating your VM (see `deploy/` for committed config files):

**1. Provision the VM**

In OCI Console: Compute → Instances → Create Instance
- Image: Ubuntu 22.04 (aarch64)
- Shape: VM.Standard.A1.Flex (1 OCPU, 6 GB RAM)
- Upload your SSH public key

**Important:** Also open ports 80 and 443 in the OCI Security List (separate from UFW):
Subnet → Security List → Add Ingress Rules → TCP 80 and TCP 443 from `0.0.0.0/0`

**2. Harden the VM**

```bash
ssh ubuntu@YOUR_PUBLIC_IP

# Disable SSH password auth
sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload sshd

# Firewall — allow only SSH, HTTP, HTTPS
sudo ufw default deny incoming && sudo ufw default allow outgoing
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
sudo ufw --force enable

# Create dedicated app user
sudo useradd --system --create-home --shell /bin/bash trumptrade
sudo usermod -aG sudo trumptrade
sudo mkdir -p /home/trumptrade/.ssh
sudo cp ~/.ssh/authorized_keys /home/trumptrade/.ssh/
sudo chown -R trumptrade:trumptrade /home/trumptrade/.ssh
```

**3. Install runtime dependencies**

```bash
# Python 3.11
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3.11-dev build-essential

# uv (fast package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Nginx and git
sudo apt install -y nginx git
sudo systemctl enable nginx
```

**4. Deploy the app**

```bash
sudo su - trumptrade
cd /home/trumptrade

# Clone repo
git clone https://github.com/YOUR_USERNAME/trump_trade.git
cd trump_trade

# Python virtualenv + install
uv venv --python python3.11 .venv
source .venv/bin/activate
uv pip install -e .

# Write .env (never commit this file)
cat > .env << 'EOF'
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
TRUTH_SOCIAL_USERNAME=...
TRUTH_SOCIAL_PASSWORD=...
ANTHROPIC_API_KEY=...
DB_URL=sqlite+aiosqlite:////home/trumptrade/trumptrade/trumptrade.db
DEBUG=false
EOF
chmod 600 .env

# Alternatively, copy from your local machine:
# scp .env trumptrade@YOUR_IP:/home/trumptrade/trumptrade/.env

# Run migrations
alembic upgrade head

# Build frontend
cd frontend && npm install && npm run build && cd ..
```

**5. Install systemd service and Nginx**

```bash
# systemd service
sudo cp /home/trumptrade/trumptrade/deploy/trumptrade.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable trumptrade
sudo systemctl start trumptrade

# Allow deploy-update.sh to restart the service without a password prompt
echo "trumptrade ALL=(ALL) NOPASSWD: /bin/systemctl restart trumptrade, /bin/systemctl status trumptrade" \
  | sudo tee /etc/sudoers.d/trumptrade-service
sudo chmod 440 /etc/sudoers.d/trumptrade-service

# Nginx
sudo cp /home/trumptrade/trumptrade/deploy/nginx.conf /etc/nginx/sites-available/trumptrade
sudo ln -sf /etc/nginx/sites-available/trumptrade /etc/nginx/sites-enabled/trumptrade
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# Fix permissions so Nginx (www-data) can read the React dist/
sudo chmod o+x /home/trumptrade
sudo chmod -R o+r /home/trumptrade/trumptrade/frontend/dist
```

**6. Verify**

```bash
# Service is running
sudo systemctl is-active trumptrade     # active
sudo systemctl is-enabled trumptrade    # enabled

# Dashboard loads
curl -s http://YOUR_PUBLIC_IP/ | grep -i doctype   # returns HTML

# Reboot test
sudo reboot
# Wait 60s, SSH back in
sudo systemctl is-active trumptrade     # active — confirms auto-restart works
```

Open `http://YOUR_PUBLIC_IP` in your browser — the dashboard should load.

---

## Updating the App

After pushing changes from your local machine:

```bash
# On your local machine
git push origin main

# On the VM (SSH in as trumptrade user)
bash scripts/deploy-update.sh
```

The script runs: `git pull` → `pip install` → `alembic upgrade` → `npm run build` → `systemctl restart`.

For frontend-only changes the Python restart is instant. For backend-only changes the npm build (~30-60s) is the slow step — you can skip it manually if no frontend files changed.

---

## Monitoring

```bash
# Live logs
sudo journalctl -u trumptrade -f

# Last 50 log lines
sudo journalctl -u trumptrade -n 50 --no-pager

# Service status
sudo systemctl status trumptrade

# Check if Truth Social is polling
sudo journalctl -u trumptrade | grep "Truth Social poll"

# Check if Twitter is polling
sudo journalctl -u trumptrade | grep "Twitter poll"
```

Key log messages:
- `Truth Social poll complete: inserted=N skipped=N since_id=...` — every 60s
- `Twitter poll complete: inserted=N skipped=N since_id=...` — every 5m
- `HEARTBEAT: no Truth Social posts in last 30 minutes` — warning if feed is silent
- `get_portfolio: Alpaca API error: ...` — check trading mode / API keys

---

## Project Structure

```
trump_trade/
├── trumptrade/
│   ├── core/           # Config, DB session, SQLAlchemy models, FastAPI app factory
│   ├── ingestion/      # Truth Social + Twitter pollers, filters, heartbeat
│   ├── analysis/       # LLM classifier + keyword rules
│   ├── risk_guard/     # Asyncio queue, position sizing, daily loss cap
│   ├── trading/        # Alpaca executor, kill switch, mode router
│   ├── benchmarks/     # Shadow portfolio snapshots + comparison API
│   ├── dashboard/      # REST endpoints, WebSocket feed
│   └── __main__.py     # Entry point (uvicorn.run)
├── frontend/           # React + Vite SPA
│   └── src/
│       ├── pages/      # FeedPage, TradesPage, PortfolioPage, BenchmarksPage, SettingsPage
│       └── components/ # AppShell, PostCard, LiveModeModal, KillSwitchBtn, etc.
├── alembic/            # Database migrations
├── deploy/             # Server config files (committed to repo)
│   ├── trumptrade.service   # systemd unit
│   └── nginx.conf           # Nginx reverse proxy + static file serving
├── scripts/
│   └── deploy-update.sh     # One-command update script for the VM
└── .env                     # Secrets — never committed
```

---

## Security Notes

- `.env` is in `.gitignore` — secrets are never committed
- App runs as a dedicated `trumptrade` system user (non-root)
- systemd unit has `NoNewPrivileges=yes` and `PrivateTmp=yes`
- SSH password authentication is disabled on the VM — key-only
- UFW restricts inbound to ports 22, 80, 443 only
- The dashboard has no authentication — it's a personal tool on a private IP. Do not expose it publicly without adding auth.
- Live trading mode requires typing an exact confirmation phrase and is protected by a two-gate check (UI + backend)

---

## Cost

| Service | Cost |
|---------|------|
| Oracle Cloud VM (A1.Flex, 1 OCPU 6GB) | Free forever |
| Alpaca paper trading | Free |
| Alpaca live trading | Free (commissions, funded account required) |
| X/Twitter API Basic tier | ~$100/month |
| LLM API (Groq Llama) | ~$0-5/month at this volume |
| LLM API (OpenAI/Anthropic) | ~$5-20/month depending on usage |

X/Twitter API is the main ongoing cost. If you skip it, the bot still works via Truth Social only.
