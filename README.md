# Mandi Automation Assistant

**e-Mandi (मध्य प्रदेश) trader portal automation** — automatically logs into the e-Mandi trader portal, fetches today's purchase bills, prints each bill on **one A4 page** to your Windows default printer, and shows everything in a mobile-friendly web app (English + Hindi).

![Stack](https://img.shields.io/badge/Stack-FastAPI%20%7C%20React%20%7C%20SQLite-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Auto-login** to the e-Mandi portal (user ID + password + PIN) with automatic CAPTCHA OCR (manual fallback from your phone if OCR fails)
- **Today's Bills** — fetch & parse daily anubandh sheets with full mandi math (hammali, toul, payable amounts)
- **One bill = one print** — bills print on a single A4 page at the configured scale (default **96%**) via your Windows default printer
- **Summary & Stock** — crop-wise totals, avg rates, tax-paid stock, mandi balance
- **10-day price trend** — pie charts for सोयाबीन (soybean) & चना (chana) daily avg rates
- **Reports** — gatepass taul count + auction detail data (ASP.NET form handling)
- **Optional "AI brain"** — NVIDIA NIM (OpenAI-compatible) chat + CAPTCHA vision reading. OPTIONAL and disabled by default
- **Web app** — desktop dashboard + mobile UI (Hindi) for bills, summary, reports, settings
- **Security** — JWT auth (admin/operator/accountant/inspector), e-Mandi credentials **encrypted at rest** (Fernet), no secrets in the repo

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI · SQLAlchemy (async) · SQLite · Playwright · JWT · bcrypt · Fernet |
| Frontend | React 19 · Vite · TypeScript · Tailwind CSS · TanStack Query/Table · Recharts · Zustand |
| Automation | Playwright page objects · OCR CAPTCHA solver (RapidOCR) · state machine |

---

## How the Automation Flow Works

1. The web app calls `POST /api/automation/print-url` (or "Print" on a bill).
2. Playwright opens a real (headful) Chromium window and logs into the e-Mandi portal.
3. It opens the bill's printable page (`IndPrintBhugtanPatra.aspx`), clicks the portal's own **Print** button, which opens a printable tab.
4. It verifies the printable tab actually received the bill content, sets the print scale to **96%** (so the whole bill fits one A4 page), then triggers exactly one print with `window.print()`.
5. Chromium runs with `--kiosk-printing`, so the print goes **directly to your Windows default printer** — no dialog, no PDF.

---

## Project Structure

```
Mandi-bill-project/
├── backend/                  # FastAPI app (Python 3.11+)
│   ├── .env.example          # copy to .env and fill in your values
│   ├── requirements.txt
│   └── app/
│       ├── api/routes/       # automation, bills, settings, logs, ai, etc.
│       ├── services/         # Playwright automation, CAPTCHA solver, AI brain
│       │   └── pages/        # page objects (login, bills, printing, popups)
│       ├── domain/           # auth, audit, stock, farmers, traders…
│       ├── models/           # SQLAlchemy models
│       ├── schemas/          # Pydantic schemas
│       ├── config.py         # pydantic-settings (MANDI_ prefix, .env)
│       └── seed.py           # first-boot seeding (env-driven credentials)
├── frontend/                 # React 19 + Vite + TS (already built → frontend/dist)
├── run_server.bat            # portable auto-start script (used by autostart)
├── launch_mandi_server.vbs   # hidden launcher used by Windows autostart
├── Dockerfile / docker-compose.yml   # optional container deployment (Linux/Xvfb)
└── README.md
```

> **Note:** the repo ships a **pre-built frontend** (`frontend/dist`). You do **not** need Node.js to run it — the backend serves the UI at `http://localhost:8000`. Node is only needed if you want to modify/rebuild the UI.

---

## Setup on a New Laptop (step by step)

Follow these steps **in order**. Windows 10/11 is the primary supported OS.

### Step 0 — Install Python

1. Go to <https://www.python.org/downloads/>
2. Download **Python 3.12.x** (64-bit) and run the installer.
3. **IMPORTANT:** tick **"Add Python to PATH"** at the bottom of the first screen, then click *Install Now*.
4. Verify it worked — open Command Prompt (Win+R → `cmd`) and run:
   ```
   python --version
   ```
   You should see `Python 3.12.x`.

### Step 1 — Download the project

**Option A — Git clone** (recommended):
```
git clone https://github.com/surbhitraders09-wq/Mandi-bill-project.git
cd Mandi-bill-project
```

**Option B — ZIP download** (no Git needed):
1. Open <https://github.com/surbhitraders09-wq/Mandi-bill-project>
2. Click the green **Code ▾ → Download ZIP**
3. Extract the ZIP (e.g. to `C:\Mandi-bill-project`)

> Put the project somewhere permanent, e.g. `C:\Mandi-bill-project` or `Documents\Mandi-bill-project`. Moving it later is fine — the scripts derive all paths from their own location.

### Step 2 — Create a virtual environment

Open Command Prompt **inside the project folder**:
```
cd <path-to-project>\backend
python -m venv venv
venv\Scripts\activate
```
Your prompt should now start with `(venv)`.

### Step 3 — Install backend dependencies

```
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
```
This installs the Python packages and the Chromium browser that Playwright drives.

### Step 4 — Configure credentials (.env)

Inside `backend`, copy the example file to `.env`:
```
cd <path-to-project>\backend
copy .env.example .env
```
Open `.env` with Notepad and fill in **your** values:

```env
MANDI_E_MANDI_USERNAME=YOUR_TRADER_ID      <- your e-Mandi trader user ID
MANDI_E_MANDI_PASSWORD=YOUR_TRADER_PASSWORD <- your e-Mandi password
MANDI_E_MANDI_PIN=0000                       <- your 4-digit PIN
MANDI_E_MANDI_URL=https://eanugya.mp.gov.in/Trader.aspx

MANDI_ADMIN_PASSWORD=admin123                <- app admin password (change this!)
```

> The app seeds these into the database **encrypted** on first boot. You can also change them later from the **Settings** page (gear icon → admin unlock).

### Step 5 — Start the server (first time)

```
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Keep this window open. Then open your browser at **http://localhost:8000**.

### Step 6 — Login to the app

- Username: `admin`
- Password: the value of `MANDI_ADMIN_PASSWORD` (default `admin123`)

Log in, open **Settings** and confirm your e-Mandi credentials are correct. Try a bill search / print — a Chromium window will appear, log into the portal automatically, and print your bill.

---

## Running the Server

| Situation | Command |
|---|---|
| Manual start (foreground) | `cd backend` → `venv\Scripts\activate` → `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| One-click start (double-click) | run `run_server.bat` |
| Autostart on login | see **Autostart** below |

`run_server.bat` is **portable and idempotent**:
- derives every path from its own location (works wherever the folder lives)
- auto-detects `backend\venv` (falls back to plain `python`)
- **skips** if port `:8000` is already in use (never double-binds)

---

## Autostart on Boot (Windows)

Two easy methods. Pick **one**.

### Method A — Startup folder shortcut (recommended)

1. Press **Win + R**, type `shell:startup`, press Enter. The Startup folder opens.
2. Create a shortcut:
   - Right-click inside the Startup folder → **New → Shortcut**
   - Location: browse to `launch_mandi_server.vbs` inside your project folder
   - Name it `Mandi Server`
3. Done. On **every login**, Windows runs the VBS hidden, which starts `run_server.bat` (which starts uvicorn if port 8000 isn't already in use).

### Method B — Task Scheduler (start on boot, before login)

1. Press **Win + R**, type `taskschd.msc`, press Enter.
2. **Create Task** (right pane):
   - *General*: Name `Mandi Server`, tick **Run whether user is logged on or not**, tick **Run with highest privileges**.
   - *Triggers*: **New…** → Begin the task: **At startup** (or *At log on*).
   - *Actions*: **New…** → Action: **Start a program** → Program/script: `wscript.exe` → Add arguments: `"<path-to-project>\launch_mandi_server.vbs"`.
   - *Conditions*: untick "Start the task only if the computer is on AC power".
3. Click **OK**. The server starts automatically on every startup, hidden.

> `launch_mandi_server.vbs` runs `run_server.bat` **hidden** (no console window flashes) and is location-independent — it gets the batch path from its own file location, so you can move the project folder anywhere.

---

## Using the Web App

| Route | Purpose |
|---|---|
| `/` | Desktop dashboard (bills, stock, farmers, traders, audit, settings) |
| `/mobile` | Mobile UI — today's bills, search & trigger printing |
| `/mobile/summary` | Crop summary + 10-day price trend pies |
| `/mobile/reports` | Gatepass taul count reports |
| `/mobile/settings` | Edit e-Mandi credentials (admin unlock) |
| `/docs` | Swagger API documentation (FastAPI) |
| `/api/health` | Health check |

### Mobile access from your phone

1. Your laptop and phone must be on the **same Wi-Fi network**.
2. Find your laptop's IP: Command Prompt → `ipconfig` → look up `IPv4 Address` (e.g. `192.168.1.7`).
3. Open **Windows Defender Firewall**: *Allow an app through firewall* → **Allow another app** → browse to your `venv\Scripts\python.exe` and allow **Private** network.
4. On the phone, open `http://<laptop-ip>:8000`.

---

## Printing Bills (what "print" does)

- The app clicks the **portal's own Print button**, waits for the printable tab, verifies the bill content arrived, sets the print scale, and triggers a single `window.print()`.
- Chromium runs with `--kiosk-printing` → output goes **directly to your Windows default printer** (set the printer you want as *Default* in *Settings → Devices → Printers*).
- The scale that makes the whole bill fit on **one page** is `PRINT_SCALE` in `backend/app/config.py` (currently `0.96`). If a bill spills onto a second page, lower it (e.g. `0.94`); if it looks too small, raise it. Restart the server after changing.

---

## Configuration Reference (`backend/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `MANDI_E_MANDI_USERNAME` | — | e-Mandi trader user ID |
| `MANDI_E_MANDI_PASSWORD` | — | e-Mandi password |
| `MANDI_E_MANDI_PIN` | — | e-Mandi 4-digit PIN |
| `MANDI_E_MANDI_URL` | `https://eanugya.mp.gov.in/Trader.aspx` | portal address |
| `MANDI_ADMIN_PASSWORD` | `admin123` | app admin password (**change it**) |
| `MANDI_SECRET_KEY` | auto | JWT signing secret (set a long random string) |
| `MANDI_ENCRYPTION_KEY` | auto | Fernet key; auto-created in `backend/encryption.key` on first boot |
| `MANDI_HAMMALI_RATE` | `12.05` | default hammali rate |
| `MANDI_CASH_THRESHOLD` | `200000` | cash threshold used in summaries |
| `MANDI_AUTOMATION_TIMEOUT` | `60` | automation step timeout (s) |
| `MANDI_AUTO_CLOSE_BROWSER` | `true` | auto-close browser after automation |
| `MANDI_NVIDIA_API_KEY` | *(empty)* | optional AI brain key (see below) |
| `MANDI_NVIDIA_MODEL` / `MANDI_NVIDIA_VISION_MODEL` | `meta/llama-3.2-11b-vision-instruct` | optional AI model IDs |

---

## Security — What Is and Isn't in the Repo

| Item | In repo? |
|---|---|
| Source code | ✅ Yes |
| Pre-built frontend (`frontend/dist`) | ✅ Yes |
| `.env.example` (placeholders only) | ✅ Yes |
| Real `.env` (your user ID / password / PIN) | ❌ **Never** — gitignored |
| `encryption.key` | ❌ **Never** — gitignored, auto-generated on first boot |
| Runtime logs / databases | ❌ gitignored |

- Your e-Mandi credentials live only in `backend/.env` (or the encrypted DB) **on your laptop** — never in GitHub.
- If you publish or share this repo, `git push` will not send `.env`, `encryption.key`, logs, or databases.

---

## Optional: AI Brain (NVIDIA NIM)

The app has an optional OpenAI-compatible AI layer (chat + CAPTCHA vision OCR). It is **disabled by default** and never blocks normal automation. To enable, add to `backend/.env`:

```env
MANDI_NVIDIA_API_KEY=<your NIM api key>
```

If the key is missing/blocked, the app silently falls back to local RapidOCR + manual CAPTCHA.

---

## Optional: Run with Docker (Linux)

```bash
cp .env.example backend/.env    # set real credentials
docker compose up -d --build    # http://localhost:8000
```

The image runs uvicorn under Xvfb so the headful Playwright automation works in a container. SQLite data, printed output and the encryption key persist in named volumes.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` not recognized | Re-run the Python installer and tick **Add Python to PATH**; reopen the terminal |
| `playwright` command not found | Re-activate the venv (`venv\Scripts\activate`), run `playwright install chromium` |
| Port 8000 already in use | `netstat -ano | findstr :8000` → kill that PID, or use `run_server.bat` (skips safely) |
| Login to portal fails / CAPTCHA appears | OCR usually solves it; if not, the app shows a CAPTCHA box you can solve from your phone |
| Portal very slow / timeout | The e-Mandi portal is slow at peak times; just retry the print |
| Bill prints on 2 pages | Lower `PRINT_SCALE` in `backend/app/config.py` and restart |
| Prints go to the wrong printer | In Windows *Settings → Devices → Printers*, set the right printer as **Default** |
| Mobile page won't open | Same Wi-Fi + allow `python.exe` through Windows Firewall + use the laptop's LAN IP |

---

## Tests (optional)

```bash
cd backend
venv\Scripts\activate
pytest
```

```bash
cd frontend
npm install
npm run lint
npm run build
```

---

## License

MIT — see `LICENSE`.