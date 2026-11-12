# Subscription Assassin

**Hunt down hidden subscriptions. Take back your money.**

Subscription Assassin is a subscription intelligence prototype built for clear, evidence-based recurring-payment reviews. It includes a cinematic product site and a working local application for tracking subscriptions, price history, renewal dates, review scores, savings estimates, and cancellation progress.

> **Demo data is simulated.** The sample merchants, usage notes, amounts, dates, and price changes are illustrative. The application does not connect to a personal bank or PayPal account by default.

## What it does

- Calculates monthly-equivalent and annualized costs from the stored subscription records.
- Uses USD for the US-focused demo and supports INR; currency totals remain separate and no exchange rates are assumed.
- Adds, edits, searches, sorts, filters, and removes subscription records.
- Records price changes when an existing subscription price is edited and shows the percentage change.
- Computes an explainable 0–100 review score from transparent rules. It is a prompt to review, not a validated financial metric.
- Shows evidence-backed deterministic insights when Gemini is unavailable; Gemini output is labeled when configured.
- Guides manual cancellation. The app does not cancel a merchant subscription. It marks a record canceled only after the user explicitly confirms the merchant accepted cancellation.
- Uses PayPal Sandbox OAuth credentials server-side. PayPal subscription lookup is scoped to the merchant represented by those credentials, not a user's complete personal subscription list.

## Architecture

- `frontend/`: React, Vite, TypeScript, TanStack Query, React Router, Recharts, React Hook Form, Zod, Framer Motion dependency, and custom CSS design system.
- `backend/`: FastAPI, Pydantic, SQLAlchemy, SQLite by default, optional PostgreSQL via `DATABASE_URL`, Gemini SDK, and PayPal REST OAuth.
- `backend/app/services/analytics.py`: monthly equivalents, dashboard aggregation, and deterministic risk scores.
- `backend/app/integrations/`: provider-specific Gemini and PayPal logic; credentials never go to the browser.
- `backend/seed.py`: idempotent starter records for a local demo.

## Requirements

- Node.js 20 or newer and npm
- Python 3.11 or newer

## Run locally on Windows PowerShell

Open two PowerShell terminals in the project folder.

### 1. Backend

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python seed.py
python -m uvicorn app.main:app --reload --port 8000
```

The API starts at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`. If PowerShell blocks virtual environment activation, run the venv interpreter directly as shown below or adjust the execution policy for the current user.

```powershell
.\.venv\Scripts\python.exe seed.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`. The default API URL is `http://localhost:8000/api`. Update `frontend/.env` only if the API uses a different address.

## Environment variables

Backend settings are documented in `backend/.env.example`:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL; defaults to local SQLite. Use a PostgreSQL URL in deployment. |
| `FRONTEND_ORIGINS` | Comma-separated allowed frontend origins for CORS. |
| `GEMINI_API_KEY` | Optional server-side Gemini API key. Empty means labeled deterministic insights. |
| `GEMINI_MODEL` | Gemini model name supported by the installed Google Gen AI SDK. |
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` | Optional server-side PayPal Sandbox app credentials. |
| `PAYPAL_BASE_URL` | Defaults to `https://api-m.sandbox.paypal.com`. |
| `PAYPAL_MODE` | Defaults to `sandbox`; live transactions are not enabled. |

Frontend settings are in `frontend/.env.example`. Never put Gemini or PayPal secrets in frontend variables.

## Provider setup and limits

### PayPal Sandbox

Create a Sandbox REST app in the PayPal developer dashboard and put its Client ID and Secret in `backend/.env`. Keep the Sandbox base URL. The API obtains a server-side OAuth token and can query the supported subscriptions endpoint for the merchant account represented by the credentials. It does **not** enumerate all subscriptions in a user's personal PayPal account. No live payments or cancellations are implemented. The settings page reports whether credentials are configured; the connect endpoint performs OAuth before claiming a connection.

The endpoints follow PayPal's official [Subscriptions API](https://developer.paypal.com/docs/api/subscriptions/v1/) and [OAuth API](https://developer.paypal.com/api/rest/authentication/).

### Gemini

Set `GEMINI_API_KEY` in the backend environment. Gemini receives only the subscription dataset needed to answer the current analysis or question. The response is requested as JSON and validated before display. On provider errors or invalid output, the API returns deterministic, labeled calculations instead.

## API overview

- `GET /api/health`, `/api/dashboard`, `/api/subscriptions`, `/api/subscriptions/{id}`
- `POST /api/subscriptions`, `PUT /api/subscriptions/{id}`, `DELETE /api/subscriptions/{id}`
- `GET /api/price-history/{id}`, `POST /api/price-history/{id}`
- `GET /api/insights`, `POST /api/insights/chat`
- `GET /api/cancellations`, `POST /api/cancellations/{id}/initiate`, `POST /api/cancellations/{id}/confirm`
- `GET /api/savings`
- `GET /api/paypal/status`, `POST /api/paypal/connect`, `GET /api/paypal/subscriptions`

## Storage and deployment

The default SQLite file is `backend/subscriptions.db` and is ignored by Git. For a hosted setup, configure PostgreSQL through `DATABASE_URL` (for example a Supabase PostgreSQL connection string) and set `FRONTEND_ORIGINS` to the deployed frontend origin. Deploy the FastAPI service to Render with a start command such as `uvicorn app.main:app --host 0.0.0.0 --port $PORT`; deploy `frontend/` to Vercel with `npm run build` and output directory `dist`, setting `VITE_API_URL` to the hosted API's `/api` base URL. Set provider secrets in the backend platform's secret manager, never in source control. Production use needs migrations, authentication, per-user data isolation, and an appropriate persistent database before real customer data is stored.

## Tests and build checks

Backend focused tests:

```powershell
cd backend
python -m pytest
```

Frontend production build:

```powershell
cd frontend
npm run build
```

The current MVP intentionally keeps provider credentials optional so the demo can run without them. The local demo database is initialized with `python seed.py`.

## Screenshots

Add screenshots of the landing page, dashboard, insights, and cancellation workflow here after running the app.

## Known limitations

- This prototype has a single local workspace and does not implement authentication or multi-user isolation.
- Sample values and dates are simulated. Demo records are labeled in the app.
- PayPal support is Sandbox and merchant-scoped; personal account-wide subscription discovery is unavailable through this integration.
- Cancellation is a manual workflow. The app cannot verify a merchant action; user confirmation is recorded as user-reported.
- Historical monthly charts are illustrative demo trend points; current financial totals are derived from current subscription records.
- Gemini needs a backend API key and network access. Deterministic insights remain available without it.
- Currency conversion is not performed.
- Alembic migrations and production authentication are future work; local development initializes tables automatically.

## Next improvements

Add authenticated per-user workspaces, Alembic migrations, secure database-backed provider connections, verified merchant cancellation workflows, bank data integrations with consent, and non-illustrative transaction-derived spending history.
