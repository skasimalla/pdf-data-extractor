# Deployment Guide — MedOrders on Vercel

This guide walks through deploying the MedOrders FastAPI + Next.js application to Vercel with a Supabase PostgreSQL database.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Node.js | ≥ 18 | [nodejs.org](https://nodejs.org) |
| Python | ≥ 3.12 | [python.org](https://python.org) |
| Git | any | [git-scm.com](https://git-scm.com) |
| Vercel CLI | latest | `npm i -g vercel` |

---

## Step 1 — Set up the Database (Supabase)

Vercel serverless functions have an **ephemeral filesystem**, so SQLite cannot be used in production. Supabase provides a free-tier PostgreSQL database.

1. Go to [supabase.com](https://supabase.com) and create a free account.
2. Click **New Project**, choose a name, region, and password.
3. Once the project is ready, navigate to:
   **Project Settings → Database → Connection String → URI**
4. Copy the connection string. It looks like:
   ```
   postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```
5. Modify the scheme for async SQLAlchemy — replace `postgresql://` with `postgresql+asyncpg://`:
   ```
   postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```
   > **Important:** Use port `5432` (direct connection) for Vercel, not the pooler port.

Keep this URL — it becomes your `DATABASE_URL` environment variable.

> The database schema (tables) is created **automatically** on first startup via SQLAlchemy `create_all`. No manual migration step is needed.

---

## Step 2 — Obtain an OpenAI API Key (Optional but Recommended)

The PDF extraction endpoint uses GPT-4o-mini for accurate patient data parsing. Without this key, a regex fallback is used.

1. Go to [platform.openai.com](https://platform.openai.com).
2. Navigate to **API Keys → Create new secret key**.
3. Copy the key (starts with `sk-...`).

---

## Step 3 — Push the Code to GitHub

Vercel deploys from a Git repository.

```bash
cd /path/to/fast-api

git init
git add .
git commit -m "Initial commit"

# Create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/medorders.git
git branch -M main
git push -u origin main
```

---

## Step 4 — Deploy to Vercel

### Option A — Vercel Dashboard (recommended)

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub.
2. Click **Add New → Project**.
3. Select your `medorders` repository and click **Import**.
4. On the configuration screen:
   - **Framework Preset**: `Next.js` (auto-detected)
   - **Root Directory**: leave as `/` (project root)
   - **Build Command**: leave as default (`next build`)
   - **Output Directory**: leave as default (`.next`)
5. Expand **Environment Variables** and add all variables from the table in [Step 5](#step-5--configure-environment-variables).
6. Click **Deploy**.

### Option B — Vercel CLI

```bash
# Install the CLI
npm i -g vercel

# Authenticate
vercel login

# Deploy from the project root
cd /path/to/fast-api
vercel

# Follow the prompts:
#   Set up and deploy? → Y
#   Which scope? → your account
#   Link to existing project? → N
#   Project name? → medorders (or any name)
#   In which directory is your code? → ./
#   Want to override settings? → N

# Set environment variables
vercel env add DATABASE_URL
vercel env add API_KEY
vercel env add NEXT_PUBLIC_API_KEY
vercel env add OPENAI_API_KEY   # optional

# Promote to production
vercel --prod
```

---

## Step 5 — Configure Environment Variables

Set these in the Vercel dashboard under **Project → Settings → Environment Variables**. Apply each to **Production**, **Preview**, and **Development** environments as appropriate.

| Variable | Required | Description | Example |
|---|---|---|---|
| `DATABASE_URL` | **Yes** | Supabase PostgreSQL connection string | `postgresql+asyncpg://postgres:pass@db.xxx.supabase.co:5432/postgres` |
| `API_KEY` | **Yes** | Secret key to authenticate all API requests | `a8f3...` (use a long random string) |
| `NEXT_PUBLIC_API_KEY` | **Yes** | Same value as `API_KEY` — exposed to the Next.js browser client | same as above |
| `OPENAI_API_KEY` | No | Enables GPT-4o-mini for accurate PDF extraction | `sk-proj-...` |
| `ALLOWED_ORIGINS` | No | CORS origins as a JSON array string | `["https://your-app.vercel.app"]` |
| `DEBUG` | No | Enable SQLAlchemy query logging | `false` |

> **Generating a strong API key:**
> ```bash
> python3 -c "import secrets; print(secrets.token_urlsafe(32))"
> ```

---

## Step 6 — Verify the Deployment

Once Vercel finishes building, you'll get a URL like `https://medorders-xyz.vercel.app`.

### Health check
```bash
curl https://your-app.vercel.app/v1/health
# Expected: {"status":"healthy","version":"1.0.0","service":"MedOrders API"}
```

### Create an order
```bash
curl -X POST https://your-app.vercel.app/v1/orders \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_first_name": "Jane",
    "patient_last_name": "Doe",
    "patient_dob": "1985-06-15",
    "status": "pending"
  }'
```

### Upload a PDF
```bash
curl -X POST https://your-app.vercel.app/v1/upload \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "file=@/path/to/patient_form.pdf"
```

### Open the dashboard
Navigate to `https://your-app.vercel.app` in your browser.

### Interactive API docs
Navigate to `https://your-app.vercel.app/docs` for Swagger UI.

---

## How Vercel Routing Works

```
Request: GET /v1/orders
        ↓
vercel.json rewrite: /v1/:path* → /api/index
        ↓
Python serverless function: api/index.py (FastAPI + ASGI)
        ↓
Route handler: GET /v1/orders → returns paginated order list

Request: GET /
        ↓
Next.js framework routing
        ↓
src/app/page.tsx → Dashboard UI
```

The `pyproject.toml` `[tool.vercel]` entry tells Vercel exactly which file is the FastAPI entrypoint, avoiding any ambiguity in discovery.

---

## Local Development

```bash
# 1. Copy environment file
cp .env.example .env
# Edit .env — set API_KEY and optionally OPENAI_API_KEY
# DATABASE_URL defaults to SQLite (no setup required locally)

# 2. Create a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Start the FastAPI server (port 8000)
uvicorn api.index:app --reload --port 8000
# API docs: http://localhost:8000/docs

# 5. In a second terminal, install Node dependencies and start Next.js (port 3000)
npm install
npm run dev
# Dashboard: http://localhost:3000
```

Next.js proxies `/v1/*` → `http://localhost:8000/v1/*` in development (configured in `next.config.ts`), so the frontend and API work together seamlessly.

---

## Troubleshooting

### "No Next.js version detected"
This means Vercel is not finding `package.json`. Two things to check:

**1. Root Directory must be `/` (project root)**

In the Vercel dashboard go to your project → **Settings → General → Root Directory**.
It must be blank or set to `./` — NOT `src`, `frontend`, or any subdirectory.
The `package.json` lives at the repository root alongside `api/` and `src/`.

**2. `vercel.json` must declare the framework explicitly**

When a project contains both a Python function and a Next.js app, Vercel needs a hint.
The `vercel.json` in this repo already includes:
```json
{ "framework": "nextjs", ... }
```
If you edited `vercel.json` and removed that line, add it back.

After fixing either of these, trigger a new deployment from the Vercel dashboard.

### "No FastAPI entrypoint found"
Ensure `pyproject.toml` exists at the project root with:
```toml
[tool.vercel]
entrypoint = "api/index.py"
```

### "Module not found" errors at runtime
All imports inside `api/` use **relative imports** (e.g., `from .config import ...`). If you add new modules, follow the same pattern.

### Database connection errors
- Confirm `DATABASE_URL` uses the `postgresql+asyncpg://` scheme (not `postgresql://`).
- Supabase requires SSL by default — asyncpg handles this automatically.
- Check that the Supabase project isn't paused (free tier pauses after 1 week of inactivity).

### PDF extraction returns low-confidence results
- Set `OPENAI_API_KEY` to enable GPT-4o-mini extraction.
- Without it, regex fallback is used, which may miss unusual document layouts.
- Ensure the PDF has a **text layer** (scanned images without OCR will not extract).

### 401 Unauthorized
- Confirm `API_KEY` on the server matches `NEXT_PUBLIC_API_KEY` in the browser.
- The header must be `X-API-Key: <key>` or `Authorization: Bearer <key>`.

### Vercel function timeout
The `maxDuration` is set to 30 seconds in `vercel.json`. PDF processing with OpenAI may take 5–15 seconds. If timeouts occur, upgrade to Vercel Pro (60s max) or optimize by reducing OpenAI token usage.

---

## Re-deploying After Changes

```bash
# Push changes to main branch — Vercel auto-deploys on every push
git add .
git commit -m "your change"
git push

# OR deploy manually via CLI
vercel --prod
```
