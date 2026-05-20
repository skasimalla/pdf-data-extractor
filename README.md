# MedOrders — Medical Patient Order API

A full-stack, production-ready REST API and dashboard for managing patient orders, with PDF data extraction and full activity logging. Built with **FastAPI** (Python) + **Next.js** (TypeScript), deployed on **Vercel**.

## Live Demo

> After deployment, your public URL will be: `https://your-app.vercel.app`
>
> API Docs: `https://your-app.vercel.app/docs`

---

## Features

| Feature | Details |
|---|---|
| **CRUD Orders** | Create, read, update, delete patient orders (paginated, filterable, searchable) |
| **PDF Extraction** | Upload any PDF → extracts patient First Name, Last Name, DOB (OpenAI GPT-4o-mini with regex fallback) |
| **Activity Logging** | Every API request logged to DB with method, path, status, latency, IP |
| **API Authentication** | Bearer token / `X-API-Key` header on all endpoints |
| **Input Validation** | Pydantic v2 schemas with field-level errors |
| **Stats Endpoint** | Aggregate order counts by status for the dashboard |
| **API Versioning** | All routes under `/v1/` |
| **Interactive Docs** | Swagger UI at `/docs`, ReDoc at `/redoc` |
| **Beautiful UI** | Next.js 15 + Tailwind CSS dashboard with real-time activity feed |
| **Vercel Deployment** | Python serverless + Next.js in a single project |

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.115, Python 3.12 |
| ORM | SQLAlchemy 2.0 (async) |
| Database | SQLite (local) / PostgreSQL via Supabase (production) |
| PDF Parsing | pdfplumber |
| LLM Extraction | OpenAI GPT-4o-mini |
| Frontend | Next.js 15, React 19, TypeScript |
| Styling | Tailwind CSS v4, Radix UI |
| Data Fetching | SWR |
| Deployment | Vercel (Python serverless + Next.js) |

---

## Local Development

### 1 — Clone and install

```bash
git clone <your-repo-url>
cd fast-api

# Python dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Node dependencies
npm install
```

### 2 — Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set API_KEY and optionally OPENAI_API_KEY
```

### 3 — Start the API server

```bash
uvicorn api.index:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.
Swagger UI: `http://localhost:8000/docs`

### 4 — Start the frontend

```bash
npm run dev
```

Dashboard: `http://localhost:3000`

> In development, Next.js proxies `/v1/*` → `http://localhost:8000/v1/*` (configured in `next.config.ts`).

---

## API Reference

All endpoints require authentication. Pass the API key as:
- Header: `X-API-Key: <key>`
- Bearer token: `Authorization: Bearer <key>`

### Orders

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/orders` | List orders (paginated, filterable by `status`, searchable) |
| `POST` | `/v1/orders` | Create a new order |
| `GET` | `/v1/orders/{id}` | Get a single order |
| `PUT` | `/v1/orders/{id}` | Update an order |
| `DELETE` | `/v1/orders/{id}` | Delete an order |
| `GET` | `/v1/orders/stats` | Aggregate counts by status |

### Upload

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/upload` | Upload a PDF, extract patient info, and create an order |

### Activity Logs

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/logs` | List all activity logs (paginated) |

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/health` | Health check (no auth required) |

### Example — Create Order

```bash
curl -X POST https://your-app.vercel.app/v1/orders \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_first_name": "Jane",
    "patient_last_name": "Doe",
    "patient_dob": "1985-06-15",
    "status": "pending",
    "notes": "Initial consultation"
  }'
```

### Example — Upload PDF

```bash
curl -X POST https://your-app.vercel.app/v1/upload \
  -H "X-API-Key: your-api-key" \
  -F "file=@patient_form.pdf"
```

---

## Deploying to Vercel

### Option A — One-click via Vercel CLI

```bash
npm i -g vercel
vercel
```

Follow the prompts, then set environment variables in the Vercel dashboard.

### Option B — GitHub Integration

1. Push this repo to GitHub
2. Go to [vercel.com](https://vercel.com) → **New Project** → Import repo
3. Set **Framework Preset** to `Next.js`
4. Add environment variables (see below)
5. Deploy

### Required Environment Variables (Vercel Dashboard)

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (e.g., Supabase) |
| `API_KEY` | Secret key to authenticate API requests |
| `OPENAI_API_KEY` | OpenAI key for GPT-4o-mini PDF extraction |
| `NEXT_PUBLIC_API_KEY` | Same as `API_KEY` — exposed to the browser |

### Setting up Supabase (free PostgreSQL)

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **Settings → Database → Connection string**
3. Copy the **URI** (use the `Transaction` mode port `6543` for serverless)
4. Replace `postgresql://` with `postgresql+asyncpg://`
5. Set as `DATABASE_URL` in Vercel

The database schema is created automatically on first startup via SQLAlchemy `create_all`.

---

## Project Structure

```
fast-api/
├── api/                    # Python FastAPI backend
│   ├── index.py            # App entry point (Vercel ASGI handler)
│   ├── config.py           # Pydantic settings
│   ├── database.py         # SQLAlchemy async engine + session
│   ├── models.py           # ORM models (Order, ActivityLog)
│   ├── schemas.py          # Pydantic request/response schemas
│   ├── dependencies.py     # Auth dependency
│   ├── middleware.py       # Activity logging middleware
│   └── routes/
│       ├── orders.py       # CRUD + stats endpoints
│       ├── upload.py       # PDF upload + extraction
│       └── logs.py         # Activity log endpoint
├── src/                    # Next.js frontend (App Router)
│   ├── app/
│   │   ├── layout.tsx      # Root layout
│   │   └── page.tsx        # Dashboard page
│   ├── components/
│   │   ├── ui/             # Primitive UI components
│   │   ├── StatsCards.tsx  # KPI cards
│   │   ├── OrderTable.tsx  # Main table with CRUD
│   │   ├── OrderForm.tsx   # Create/edit form
│   │   ├── UploadModal.tsx # PDF drag-and-drop upload
│   │   └── ActivityFeed.tsx# Live activity log
│   └── lib/
│       ├── api.ts          # Typed API client
│       ├── types.ts        # TypeScript interfaces
│       └── utils.ts        # Utility functions
├── requirements.txt        # Python dependencies
├── package.json            # Node dependencies
├── vercel.json             # Vercel routing config
├── next.config.ts          # Next.js config (dev proxy)
└── .env.example            # Environment variable template
```

---

## Architecture Decisions

**Why FastAPI?** Async-native, Pydantic-powered validation, auto-generated OpenAPI docs, and excellent Vercel serverless support via ASGI.

**Why SQLite locally / PostgreSQL in production?** Zero-config for development; Vercel serverless functions can't write to the filesystem, so a remote PostgreSQL (Supabase) is used in production.

**Why OpenAI with regex fallback?** GPT-4o-mini handles diverse document layouts and extracts accurately. The regex fallback ensures the endpoint works even when no OpenAI key is configured.

**Why SWR?** Lightweight, built-in cache invalidation, and `keepPreviousData` keeps the UI smooth during pagination.

**Why Bearer + X-API-Key auth?** Practical for both programmatic access (curl/scripts) and browser fetch calls without implementing a full OAuth flow for this MVP scope.
# pdf-data-extractor
