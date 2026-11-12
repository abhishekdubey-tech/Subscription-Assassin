from datetime import date
from collections import defaultdict

INTERVAL_MONTHLY = {"monthly": 1, "yearly": 1 / 12, "weekly": 52 / 12, "custom": 1}

def monthly_cost(sub):
    return sub.price * INTERVAL_MONTHLY.get(sub.billing_interval, 1)

def risk(sub, today=None):
    today = today or date.today()
    score, reasons = 0, []
    amount = monthly_cost(sub)
    if amount >= 1000:
        score += 22; reasons.append("High recurring cost compared with a typical subscription")
    elif amount >= 500:
        score += 12; reasons.append("Above-average recurring cost")
    if sub.prices:
        latest = sub.prices[-1]
        if latest.old_price > 0 and latest.new_price > latest.old_price:
            pct = (latest.new_price-latest.old_price)/latest.old_price*100
            score += min(35, round(pct * .6)); reasons.append(f"Price increased {pct:.1f}% ({latest.currency} {latest.old_price:g} → {latest.new_price:g})")
    if sub.usage_frequency in ("never", "rarely"):
        score += 30; reasons.append(f"Usage marked as {sub.usage_frequency}")
    elif sub.usage_frequency == "unknown":
        score += 8; reasons.append("Usage has not been recorded")
    if sub.next_billing_date:
        days = (sub.next_billing_date-today).days
        if 0 <= days <= 7:
            score += 12; reasons.append(f"Renews in {days} day{'s' if days != 1 else ''}")
    return min(score, 100), reasons

def dashboard(subs):
    active = [s for s in subs if s.status == "active"]
    totals = defaultdict(float)
    monthly, attention = 0.0, 0
    for s in active:
        m = monthly_cost(s); monthly += m; totals[s.category] += m
        if risk(s)[0] >= 40: attention += 1
    currencies = {s.currency for s in active}
    # Keep currency totals separate in response; no implicit conversion.
    by_currency = {}
    for currency in currencies:
        selected = [s for s in active if s.currency == currency]
        monthly_total = round(sum(monthly_cost(s) for s in selected), 2)
        potential_monthly = round(sum(monthly_cost(s) for s in selected if s.usage_frequency in ("never", "rarely")), 2)
        by_currency[currency] = {
            "monthly": monthly_total,
            "annual": round(monthly_total * 12, 2),
            "potential_annual_savings": round(potential_monthly * 12, 2),
            "categories": {k: round(sum(monthly_cost(s) for s in selected if s.category == k), 2) for k in {x.category for x in selected}},
        }
    upcoming = sorted([s for s in active if s.next_billing_date and (s.next_billing_date-date.today()).days >= 0], key=lambda s:s.next_billing_date)[:5]
    return {"active_count":len(active),"attention_count":attention,"by_currency":by_currency,"upcoming":[{"id":s.id,"name":s.name,"merchant":s.merchant,"price":s.price,"currency":s.currency,"date":s.next_billing_date.isoformat(),"category":s.category,"days_remaining":(s.next_billing_date-date.today()).days} for s in upcoming]}
