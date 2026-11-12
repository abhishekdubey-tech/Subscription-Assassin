import json
import logging
import asyncio
from pydantic import BaseModel
from app.core.config import settings

logger = logging.getLogger(__name__)

class InsightItem(BaseModel):
    type: str
    title: str
    description: str
    evidence: list[str]

class AnalysisResponse(BaseModel):
    answer: str
    insights: list[InsightItem]

def fallback(subscriptions):
    active=[s for s in subscriptions if s.status=="active"]
    by_cur={}
    for cur in {s.currency for s in active}:
        items=[s for s in active if s.currency==cur]
        monthly=sum(s.price*{"monthly":1,"yearly":1/12,"weekly":52/12,"custom":1}.get(s.billing_interval,1) for s in items)
        unused=[s for s in items if s.usage_frequency in ("never","rarely")]
        by_cur[cur]={"monthly":round(monthly,2),"annual":round(monthly*12,2),"unused":unused}
    insights=[]
    for cur, data in by_cur.items():
        insights.append({"type":"spending","title":f"Your recurring spend is {cur} {data['monthly']:,.2f} per month", "description":f"Based on {len(active)} active subscriptions in the saved dataset. This annualizes to {cur} {data['annual']:,.2f}.","source":"rule_based","evidence":[f"{len(active)} active subscriptions"]})
        if data["unused"]:
            save=sum(s.price*{"monthly":1,"yearly":1/12,"weekly":52/12,"custom":1}.get(s.billing_interval,1)*12 for s in data["unused"])
            insights.append({"type":"review","title":f"Review {len(data['unused'])} low-use subscriptions", "description":f"You marked {', '.join(s.name for s in data['unused'])} as rarely or never used. Their combined annualized cost is {cur} {save:,.2f}; this is potential, not confirmed, savings.","source":"rule_based","evidence":[s.name for s in data["unused"]]})
    hikes=[(s,s.prices[-1]) for s in active if s.prices and s.prices[-1].new_price>s.prices[-1].old_price]
    for s,p in hikes:
        pct=(p.new_price-p.old_price)/p.old_price*100 if p.old_price else 0
        insights.append({"type":"price_increase","title":f"{s.name} has a recorded price increase", "description":f"Saved history shows {s.currency} {p.old_price:g} to {s.currency} {p.new_price:g} ({pct:.1f}%).","source":"rule_based","evidence":["Stored price history"]})
    return {"provider":"rule_based","notice":"Gemini is not configured; these deterministic insights use only your saved subscription data.","insights":insights}

async def analyze(subscriptions, question=None):
    if not settings.gemini_api_key:
        return fallback(subscriptions)
    try:
        from google import genai
        from google.genai import types
        client=genai.Client(api_key=settings.gemini_api_key,http_options=types.HttpOptions(timeout=settings.gemini_timeout_ms))
        rows=[{"name":s.name,"merchant":s.merchant,"category":s.category,"price":s.price,"currency":s.currency,"interval":s.billing_interval,"status":s.status,"usage":s.usage_frequency,"prices":[{"old":p.old_price,"new":p.new_price,"currency":p.currency} for p in s.prices]} for s in subscriptions]
        prompt="Use only this subscription data. Do not guess missing prices, history, policies, refunds, or cancellation outcomes. For the request, give one concise evidence-based answer and at most 4 useful insights. Keep descriptions brief and list evidence from supplied records. If data is insufficient, say so. Request: "+(question or "Find the most useful spending patterns.")+"\nSUBSCRIPTIONS="+json.dumps(rows,separators=(",",":"))
        # Gemini 3 models recommend their default temperature; forcing a low value can
        # cause degraded or invalid output for reasoning models.
        response=await client.aio.models.generate_content(model=settings.gemini_model,contents=prompt,config=types.GenerateContentConfig(response_mime_type="application/json",response_schema=AnalysisResponse,max_output_tokens=1200))
        parsed=response.parsed
        if isinstance(parsed,BaseModel):
            result=parsed.model_dump()
        elif isinstance(parsed,dict):
            result=parsed
        else:
            result=json.loads(response.text or "")
        if not isinstance(result,dict) or not isinstance(result.get("answer"),str) or not isinstance(result.get("insights",[]),list): raise ValueError("invalid structured response")
        result["provider"]="gemini"; result["notice"]="AI analysis is grounded in the subscription data supplied; review evidence before acting."
        return result
    except Exception as exc:
        logger.warning("Gemini request failed (%s, code=%s); using deterministic fallback", type(exc).__name__, getattr(exc, "code", None))
        result=fallback(subscriptions); result["notice"]="Gemini is configured, but its request failed. These are rule-based insights from saved data; open Settings and test the live Gemini connection for the provider status."
        return result

async def check_connection():
    """Make a tiny real provider request; never return key/token or raw provider text."""
    if not settings.gemini_api_key:
        return {"configured":False,"connected":False,"model":None,"message":"No Gemini API key is configured on the backend."}
    try:
        from google import genai
        from google.genai import types
        client=genai.Client(api_key=settings.gemini_api_key,http_options=types.HttpOptions(timeout=12000))
        response=await asyncio.wait_for(client.aio.models.generate_content(
            model=settings.gemini_model,
            contents="Reply with OK.",
            config=types.GenerateContentConfig(max_output_tokens=8),
        ),timeout=12)
        if not (response.text or "").strip():
            return {"configured":True,"connected":False,"model":settings.gemini_model,"message":"Gemini responded without text. Check model access and API limits."}
        return {"configured":True,"connected":True,"model":settings.gemini_model,"message":"Gemini API key accepted; a live generation request succeeded."}
    except asyncio.TimeoutError:
        return {"configured":True,"connected":False,"model":settings.gemini_model,"message":"Gemini request timed out. Check network access and retry."}
    except Exception as exc:
        code=getattr(exc,"code",None)
        status=getattr(exc,"status_code",None) or (code if isinstance(code,int) else None)
        if status in (401,403): message="Gemini rejected this key or the project does not have API access. Verify the key in Google AI Studio."
        elif status==404: message="The configured Gemini model is not available to this key/project. Check the model setting."
        elif status==429: message="Google returned HTTP 429: this API project has reached a Gemini request limit or quota. The key is present, but generation is currently blocked. Check the project’s limits and usage in Google AI Studio."
        elif status: message=f"Gemini request failed with provider status {status}. Check key permissions and project limits."
        else: message=f"Gemini connection failed ({type(exc).__name__}). Check the backend log and network connection."
        logger.warning("Gemini connection check failed (%s, code=%s)",type(exc).__name__,status)
        return {"configured":True,"connected":False,"model":settings.gemini_model,"message":message}
