# Heymantle → Mission Control Webhook Integration

Real-time subscription alerts from Heymantle to Mission Control.

## What It Does

Receives webhook events from Heymantle when customers:
- Create new subscriptions → Posts celebration + @pepper notification
- Cancel subscriptions → Posts churn alert (P1 priority) 
- Fail payments → Posts dunning alert
- Upgrade/downgrade plans → Posts revenue update

## Deployment

### Option A: Render (Recommended)

1. Push to GitHub repo
2. Connect to Render (free tier)
3. Set environment variable: `HEYMANTLE_WEBHOOK_SECRET`
4. Copy webhook URL: `https://your-app.onrender.com/webhook/heymantle`
5. Configure in Heymantle dashboard

### Option B: Self-Hosted

```bash
cd ~/clawd/services/heymantle-webhook
pip install -r requirements.txt
export MC_URL=https://capable-leopard-644.convex.site
export HEYMANTLE_WEBHOOK_SECRET=your_secret_here
python3 app.py
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/heymantle` | POST | Receives Heymantle events |
| `/health` | GET | Health check |
| `/` | GET | Service info |

## Configuration

Set these environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `MC_URL` | No | Mission Control API URL (default: production) |
| `HEYMANTLE_WEBHOOK_SECRET` | Yes | From Heymantle dashboard |
| `PORT` | No | Server port (default: 8767) |

## Supported Events

- `subscription.created` — New customer signup
- `subscription.cancelled` — Churn alert (P1 priority)
- `subscription.payment_failed` — Dunning
- `subscription.updated` — Plan changes

## Testing

```bash
# Health check
curl https://your-app.onrender.com/health

# Test webhook (with valid signature)
curl -X POST https://your-app.onrender.com/webhook/heymantle \
  -H "Content-Type: application/json" \
  -H "X-Heymantle-Signature: sha256=test" \
  -d '{
    "type": "subscription.created",
    "data": {
      "customer": {"name": "Test", "email": "test@example.com"},
      "subscription": {"plan_name": "Growth", "mrr": 49}
    }
  }'
```

## Architecture

```
Heymantle Dashboard
       │
       │ Webhook POST
       ▼
┌─────────────────────┐
│  Flask App (Render) │
│  - Validate sig     │
│  - Format message   │
│  - Post to MC API   │
└─────────────────────┘
       │
       │ MC Task Create
       ▼
┌─────────────────────┐
│  Mission Control    │
│  - Notification     │
│  - @mentions        │
└─────────────────────┘
```

## Files

- `app.py` — Flask application
- `requirements.txt` — Python dependencies
- `Procfile` — Render deployment config
- `app.json` — Render template config

## Next Steps

1. Deploy to Render
2. Get webhook URL
3. Configure in Heymantle dashboard
4. Test with sample event
5. Monitor Mission Control for alerts
