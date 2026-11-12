from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client=TestClient(app)

def test_health_and_dashboard_are_available():
    assert client.get("/api/health").status_code==200
    response=client.get("/api/dashboard")
    assert response.status_code==200
    data=response.json()
    assert data["active_count"]>=12
    assert data["by_currency"]["USD"]["monthly"]>0

def test_subscription_validation_and_price_change_history():
    bad=client.post("/api/subscriptions",json={"name":"Bad","merchant":"Bad","category":"Other","price":0,"currency":"INR"})
    assert bad.status_code==422
    payload={"name":"Test Record","merchant":"Test Merchant","category":"Software","price":100,"currency":"INR","billing_interval":"monthly","next_billing_date":(date.today()+timedelta(days=10)).isoformat(),"start_date":date.today().isoformat(),"status":"active","payment_method":"Card","website":None,"cancellation_url":None,"notes":"test","usage_frequency":"often"}
    created=client.post("/api/subscriptions",json=payload)
    assert created.status_code==201
    record=created.json(); assert record["monthly_cost"]==100
    payload["price"]=125
    updated=client.put(f"/api/subscriptions/{record['id']}",json=payload)
    assert updated.status_code==200
    history=client.get(f"/api/price-history/{record['id']}").json()
    assert history[0]["percentage"]==25
    assert client.delete(f"/api/subscriptions/{record['id']}").status_code==204

def test_cancellation_is_manual_and_requires_user_report():
    payload={"name":"Manual Flow Test","merchant":"Example","category":"Software","price":20,"currency":"INR","billing_interval":"monthly","next_billing_date":None,"start_date":None,"status":"active","payment_method":"Card","website":None,"cancellation_url":None,"notes":"","usage_frequency":"never"}
    created=client.post("/api/subscriptions",json=payload).json()
    sid=created["id"]
    initiation=client.post(f"/api/cancellations/{sid}/initiate")
    assert initiation.status_code==201
    assert initiation.json()["status"]=="manual_cancellation_required"
    assert client.get(f"/api/subscriptions/{sid}").json()["status"]=="active"
    confirmed=client.post(f"/api/cancellations/{sid}/confirm")
    assert confirmed.status_code==200
    assert "not executed or independently verified" in confirmed.json()["message"]
    assert client.get(f"/api/subscriptions/{sid}").json()["status"]=="canceled"
    client.delete(f"/api/subscriptions/{sid}")

def test_provider_status_is_honest_without_credentials(monkeypatch):
    monkeypatch.setattr(settings,"gemini_api_key","")
    status=client.get("/api/paypal/status").json()
    assert isinstance(status["configured"], bool)
    assert "personal account-wide" in status["capability"]
    insights=client.get("/api/insights").json()
    assert insights["provider"] in ("rule_based", "gemini")

def test_ai_status_never_returns_the_secret():
    status=client.get("/api/ai/status")
    assert status.status_code==200
    data=status.json()
    assert data["provider"]=="gemini"
    assert isinstance(data["configured"],bool)
    assert "key" not in data

