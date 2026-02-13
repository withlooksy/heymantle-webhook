"""
Heymantle Webhook Server
Receives subscription events and posts to Mission Control
"""

import os
import json
import hmac
import hashlib
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
import httpx
import uvicorn

app = FastAPI(title="Heymantle Webhook Handler")

# Config
MC_URL = os.getenv("MISSION_CONTROL_URL", "https://capable-leopard-644.convex.site")
WEBHOOK_SECRET = os.getenv("HEYMANTLE_WEBHOOK_SECRET", "")

def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify Heymantle webhook signature"""
    if not WEBHOOK_SECRET:
        return True  # Skip verification if no secret configured
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

def format_mc_alert(event_type: str, data: dict) -> dict:
    """Format alert for Mission Control"""
    customer = data.get("customer", {})
    subscription = data.get("subscription", {})
    
    if event_type == "subscription.created":
        return {
            "title": f"🎉 New Subscription: {customer.get('name', 'Unknown')}",
            "content": f"**Plan:** {subscription.get('planId', 'N/A')}\n**Amount:** ${subscription.get('amount', 0)/100:.2f}\n**Customer:** {customer.get('email', 'N/A')}",
            "priority": "P2",
            "tags": ["revenue", "new-subscription"]
        }
    elif event_type == "subscription.cancelled":
        return {
            "title": f"⚠️ Cancellation: {customer.get('name', 'Unknown')}",
            "content": f"**Plan:** {subscription.get('planId', 'N/A')}\n**Reason:** {data.get('cancellationReason', 'Not provided')}\n**Customer:** {customer.get('email', 'N/A')}",
            "priority": "P1",
            "tags": ["revenue", "churn", "urgent"]
        }
    elif event_type == "subscription.updated":
        return {
            "title": f"📝 Subscription Updated: {customer.get('name', 'Unknown')}",
            "content": f"**New Plan:** {subscription.get('planId', 'N/A')}\n**New Amount:** ${subscription.get('amount', 0)/100:.2f}",
            "priority": "P2",
            "tags": ["revenue", "expansion"]
        }
    else:
        return {
            "title": f"📊 Heymantle Event: {event_type}",
            "content": json.dumps(data, indent=2),
            "priority": "P3",
            "tags": ["revenue", "webhook"]
        }

async def post_to_mc(alert: dict):
    """Post alert to Mission Control"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MC_URL}/api/events/fire",
                json={
                    "agentName": "heymantle-webhook",
                    "kind": "revenue_event",
                    "title": alert["title"],
                    "content": alert["content"],
                    "tags": alert["tags"]
                },
                timeout=10.0
            )
            return response.status_code == 200
    except Exception as e:
        print(f"Failed to post to MC: {e}")
        return False

@app.post("/webhook/heymantle")
async def heymantle_webhook(
    request: Request,
    x_heymantle_signature: str = Header(None)
):
    """Receive Heymantle webhook events"""
    body = await request.body()
    
    # Verify signature if secret is configured
    if WEBHOOK_SECRET and x_heymantle_signature:
        if not verify_signature(body, x_heymantle_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        data = json.loads(body)
        event_type = data.get("type", "unknown")
        
        print(f"[{datetime.utcnow().isoformat()}] Received: {event_type}")
        
        # Format and post to Mission Control
        alert = format_mc_alert(event_type, data)
        await post_to_mc(alert)
        
        return JSONResponse({"status": "received", "event": event_type})
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal error")

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Heymantle Webhook Handler",
        "version": "1.0.0",
        "endpoints": ["/webhook/heymantle", "/health"]
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
