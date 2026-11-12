# API notes

All endpoints are prefixed with `/api`. FastAPI publishes request schemas at `/docs`.

- Subscription writes validate category, currency (`INR` or `USD`), positive price, billing interval, and status.
- Updating a price in the same currency appends a price history row before saving the new amount.
- Changing a subscription currency in-place is rejected; create a separate record instead.
- Dashboard and savings totals group by currency without conversion.
- `/insights` returns a `provider` label and `notice`; deterministic fallback is explicit.
- `/cancellations/{id}/initiate` returns `manual_cancellation_required`; `/confirm` records user-reported confirmation, not a provider confirmation.
- PayPal `/subscriptions` returns only results returned for the merchant represented by Sandbox credentials.
