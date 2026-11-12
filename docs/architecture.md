# Architecture

The frontend is a React single-page application with a separate marketing landing route and the working product under `/app`. TanStack Query reads and invalidates API data so successful edits and cancellation confirmations refresh dashboard figures. The presentation layer labels demo data and provider limitations.

FastAPI owns calculations and persistence. SQLAlchemy stores subscription records plus related price history and cancellation records. SQLite is the default for local development; `DATABASE_URL` can point to PostgreSQL for deployment. The default app is one local workspace and does not provide authentication or user isolation.

Risk scores are deterministic and expose their factors. Savings distinguish current annualized outflow, potential annualized low-use cost, and annualized amounts for records the user marked canceled. All currency totals are kept separate. Gemini receives a bounded JSON representation of the current dataset; its JSON response is validated and falls back to deterministic insights on failure. PayPal OAuth credentials and access tokens remain server-side; Sandbox lookup is merchant-scoped.

Cancellation initiation records a manual workflow and never contacts a merchant. The confirmation route changes local status only after the user asserts the merchant accepted cancellation and returns a message explaining that the app did not independently verify it.
