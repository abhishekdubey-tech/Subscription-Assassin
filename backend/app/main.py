import asyncio
from datetime import UTC, date, datetime
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, selectinload
from app.database import Base, engine, get_db
from app.models.subscription import Subscription, PriceHistory, CancellationRecord
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate, SubscriptionOut, ChatRequest
from app.services.analytics import dashboard, risk, monthly_cost
from app.integrations import paypal, gemini
from app.core.config import settings

Base.metadata.create_all(bind=engine)
app=FastAPI(title="Subscription Assassin API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.frontend_origins.split(",")],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

def load_subs(db): return db.query(Subscription).options(selectinload(Subscription.prices),selectinload(Subscription.cancellations)).order_by(Subscription.id).all()
def serialize(s):
    score,reasons=risk(s)
    return {**SubscriptionOut.model_validate(s).model_dump(mode="json"),"monthly_cost":round(monthly_cost(s),2),"risk_score":score,"risk_label":"High attention" if score>=65 else "Review" if score>=35 else "Low","risk_reasons":reasons,"price_history":[{"id":p.id,"old_price":p.old_price,"new_price":p.new_price,"currency":p.currency,"change_date":p.change_date.isoformat()} for p in s.prices],"cancellation_status":s.cancellations[-1].status if s.cancellations else None}

@app.get("/api/health")
def health(): return {"status":"ok","database":"connected","mode":"demo"}

@app.get("/api/dashboard")
def get_dashboard(db:Session=Depends(get_db)): return dashboard(load_subs(db))

@app.get("/api/subscriptions")
def get_subscriptions(search:str|None=None,category:str|None=None,status:str|None=None,db:Session=Depends(get_db)):
    subs=load_subs(db)
    if search: subs=[s for s in subs if search.casefold() in s.name.casefold() or search.casefold() in s.merchant.casefold()]
    if category: subs=[s for s in subs if s.category==category]
    if status: subs=[s for s in subs if s.status==status]
    return [serialize(s) for s in subs]

@app.get("/api/subscriptions/{sid}")
def get_subscription(sid:int,db:Session=Depends(get_db)):
    s=db.query(Subscription).options(selectinload(Subscription.prices),selectinload(Subscription.cancellations)).filter_by(id=sid).first()
    if not s: raise HTTPException(404,"Subscription not found")
    return serialize(s)

@app.post("/api/subscriptions",status_code=201)
def create_subscription(body:SubscriptionCreate,db:Session=Depends(get_db)):
    s=Subscription(**body.model_dump()); db.add(s); db.commit(); db.refresh(s); return serialize(s)

@app.put("/api/subscriptions/{sid}")
def update_subscription(sid:int,body:SubscriptionUpdate,db:Session=Depends(get_db)):
    s=db.query(Subscription).options(selectinload(Subscription.prices)).filter_by(id=sid).first()
    if not s: raise HTTPException(404,"Subscription not found")
    values=body.model_dump()
    if values["price"]!=s.price or values["currency"]!=s.currency:
        if values["currency"]!=s.currency: raise HTTPException(422,"Changing currency requires a separate subscription record.")
        s.prices.append(PriceHistory(old_price=s.price,new_price=values["price"],currency=s.currency))
    for k,v in values.items(): setattr(s,k,v)
    db.commit(); db.refresh(s); return serialize(s)

@app.delete("/api/subscriptions/{sid}",status_code=204)
def delete_subscription(sid:int,db:Session=Depends(get_db)):
    s=db.get(Subscription,sid)
    if not s: raise HTTPException(404,"Subscription not found")
    db.delete(s); db.commit()

@app.get("/api/price-history/{sid}")
def get_price_history(sid:int,db:Session=Depends(get_db)):
    s=db.query(Subscription).options(selectinload(Subscription.prices)).filter_by(id=sid).first()
    if not s: raise HTTPException(404,"Subscription not found")
    return [{"id":p.id,"old_price":p.old_price,"new_price":p.new_price,"currency":p.currency,"change_date":p.change_date.isoformat(),"percentage":round((p.new_price-p.old_price)/p.old_price*100,2) if p.old_price else None} for p in s.prices]

@app.post("/api/price-history/{sid}",status_code=201)
def add_price_history(sid:int,body:dict,db:Session=Depends(get_db)):
    s=db.get(Subscription,sid)
    if not s: raise HTTPException(404,"Subscription not found")
    old=float(body.get("old_price",0)); new=float(body.get("new_price",0))
    if old<=0 or new<=0: raise HTTPException(422,"Prices must be greater than zero")
    p=PriceHistory(subscription_id=sid,old_price=old,new_price=new,currency=s.currency); db.add(p); db.commit(); db.refresh(p); return {"id":p.id,"percentage":round((new-old)/old*100,2)}

@app.get("/api/insights")
async def get_insights(db:Session=Depends(get_db)): return await gemini.analyze(load_subs(db))

@app.post("/api/insights/chat")
async def chat(body:ChatRequest,db:Session=Depends(get_db)):
    subs=load_subs(db); active=[s for s in subs if s.status=="active"]; question=body.message.casefold()
    currencies=sorted({s.currency for s in active})
    totals={cur:round(sum(monthly_cost(s) for s in active if s.currency==cur),2) for cur in currencies}
    annual={cur:round(total*12,2) for cur,total in totals.items()}
    if any(w in question for w in ["renew","next week","upcoming"]):
        due=sorted([s for s in active if s.next_billing_date and 0<=(s.next_billing_date-date.today()).days<=7],key=lambda s:s.next_billing_date)
        answer="Renewing in the next seven days: "+("; ".join(f"{s.name} ({s.currency} {s.price:,.2f}, {s.next_billing_date})" for s in due) or "none in the saved data")+"."
    elif any(w in question for w in ["increase","increased","price hike","price change"]):
        changes=[(s,p) for s in active for p in s.prices if p.old_price>0 and p.new_price!=p.old_price]
        answer="Recorded price changes: "+("; ".join(f"{s.name}: {p.currency} {p.old_price:,.2f} → {p.currency} {p.new_price:,.2f} ({(p.new_price-p.old_price)/p.old_price*100:+.1f}%)" for s,p in changes) or "none in the saved price history")+"."
    elif any(w in question for w in ["saving","save","unused","rarely used"]):
        potential={cur:round(sum(monthly_cost(s)*12 for s in active if s.currency==cur and s.usage_frequency in ("never","rarely")),2) for cur in currencies}
        answer="Potential annual savings from subscriptions you marked rarely or never used: "+("; ".join(f"{cur} {amount:,.2f}" for cur,amount in potential.items() if amount>0) or "none recorded")+". Potential savings are estimates, not confirmed savings."
    elif any(w in question for w in ["cancel","cancellation","stop paying"]):
        candidates=sorted([s for s in active if s.usage_frequency in ("never","rarely")],key=lambda s:monthly_cost(s)*12,reverse=True)[:3]
        if candidates:
            details=[]
            for s in candidates:
                annualized=monthly_cost(s)*12
                why="you marked it as never used" if s.usage_frequency=="never" else "you marked it as rarely used"
                details.append(f"{s.name} ({s.currency} {annualized:,.2f}/year potential; {why})")
            answer="Based only on your saved usage notes, review these first: "+"; ".join(details)+". These are candidates to review, not an instruction to cancel; confirm the service is no longer needed first."
        else:
            answer="I found no active subscriptions marked rarely or never used, so I can't identify a cancellation candidate from your saved usage data."
    elif any(w in question for w in ["review","look at","risk","score","first"]):
        ranked=sorted([(s,risk(s)[0],risk(s)[1]) for s in active],key=lambda item:item[1],reverse=True)[:3]
        answer="Subscriptions to review first by the transparent review score: "+("; ".join(f"{s.name} ({score}/100: {reasons[0] if reasons else 'no elevated factor recorded'})" for s,score,reasons in ranked) or "no active subscriptions")+". Scores are review prompts, not financial advice."
    elif any(w in question for w in ["expensive","most","top","cost the most"]):
        top=sorted(active,key=monthly_cost,reverse=True)[:3]
        answer="Highest monthly-equivalent subscription costs: "+("; ".join(f"{s.name} ({s.currency} {monthly_cost(s):,.2f}/month)" for s in top) or "no active subscriptions")+"."
    elif any(w in question for w in ["annual","yearly","per year","year"]):
        answer="Annualized active subscription spending at current prices: "+("; ".join(f"{cur} {amount:,.2f}" for cur,amount in annual.items()) or "zero")+"."
    elif any(w in question for w in ["monthly","per month","each month","spend","cost"]):
        answer="Your saved active subscriptions total "+("; ".join(f"{cur} {amount:,.2f} per month" for cur,amount in totals.items()) or "zero")+". Annualized, that is "+("; ".join(f"{cur} {amount:,.2f}" for cur,amount in annual.items()) or "zero")+"."
    else:
        try:
            # Keep known financial questions instant via deterministic branches above;
            # give genuine open-ended prompts enough time for a real Gemini response.
            data=await asyncio.wait_for(gemini.analyze(subs,body.message),timeout=8)
            if data.get("provider")=="gemini" and data.get("answer"):
                return data
        except (asyncio.TimeoutError,Exception):
            pass
        answer="I can quickly calculate spending, top costs, renewals, price changes, low-use savings, and review scores from your saved data. Ask about one of those."
        return {"provider":"rule_based","answer":answer,"notice":"This fallback uses deterministic calculations from your saved data. Gemini was unavailable or did not respond within 8 seconds."}
    return {"provider":"rule_based","answer":answer,"notice":"Fast answer calculated from your saved subscription data; no external AI request was needed."}

@app.get("/api/cancellations")
def cancellations(db:Session=Depends(get_db)):
    records=db.query(CancellationRecord).all()
    return [{"id":r.id,"subscription_id":r.subscription_id,"status":r.status,"initiated_at":r.initiated_at.isoformat(),"confirmed_at":r.confirmed_at.isoformat() if r.confirmed_at else None,"method":r.method,"result_message":r.result_message} for r in records]

@app.post("/api/cancellations/{sid}/initiate",status_code=201)
def initiate_cancellation(sid:int,db:Session=Depends(get_db)):
    s=db.get(Subscription,sid)
    if not s: raise HTTPException(404,"Subscription not found")
    if s.status!="active": raise HTTPException(409,"Only active subscriptions can enter cancellation workflow")
    method="official_merchant_link" if s.cancellation_url else "manual"
    msg="Open the merchant's cancellation page and complete the steps there. This app cannot cancel it directly." if s.cancellation_url else "No verified merchant cancellation URL is saved. Use the merchant's official app or website to find its cancellation instructions."
    r=CancellationRecord(subscription_id=sid,status="manual_cancellation_required",method=method,result_message=msg); db.add(r); db.commit(); db.refresh(r)
    return {"id":r.id,"subscription":s.name,"status":r.status,"method":r.method,"result_message":r.result_message,"cancellation_url":s.cancellation_url}

@app.post("/api/cancellations/{sid}/confirm")
def confirm_cancellation(sid:int,db:Session=Depends(get_db)):
    s=db.query(Subscription).options(selectinload(Subscription.cancellations)).filter_by(id=sid).first()
    if not s: raise HTTPException(404,"Subscription not found")
    if not s.cancellations or s.cancellations[-1].status!="manual_cancellation_required": raise HTTPException(409,"Start the manual cancellation workflow first")
    r=s.cancellations[-1]; r.status="cancellation_confirmed"; r.confirmed_at=datetime.now(UTC).replace(tzinfo=None); r.result_message="User confirmed that cancellation was completed with the merchant."; s.status="canceled"; db.commit()
    return {"status":r.status,"subscription":serialize(s),"message":"Recorded from your confirmation. The merchant's cancellation was not executed or independently verified by this app."}

@app.get("/api/savings")
def savings(db:Session=Depends(get_db)):
    subs=load_subs(db); d=dashboard(subs)
    confirmed={}
    for currency in {s.currency for s in subs}:
        confirmed[currency]=round(sum(monthly_cost(s)*12 for s in subs if s.currency==currency and s.status=="canceled"),2)
    return {"by_currency":d["by_currency"],"confirmed_savings":confirmed,"potential_is_not_confirmed":True}

@app.get("/api/paypal/status")
async def paypal_status(): return await paypal.status()

@app.get("/api/ai/status")
def ai_status():
    return {"provider":"gemini","configured":bool(settings.gemini_api_key),"model":settings.gemini_model if settings.gemini_api_key else None,"fallback":"rule_based"}

@app.post("/api/ai/check")
async def check_ai_connection():
    return await gemini.check_connection()

@app.post("/api/paypal/connect")
async def paypal_connect():
    await paypal.token(); return {"connected":True,"mode":settings.paypal_mode,"scope":"merchant account represented by Sandbox credentials"}

@app.get("/api/paypal/subscriptions")
async def paypal_subscriptions(): return await paypal.list_subscriptions()
