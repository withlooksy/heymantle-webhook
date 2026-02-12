#!/usr/bin/env python3
"""
Heymantle Webhook Receiver → Mission Control Integration

Receives subscription events from Heymantle and posts real-time alerts
to Mission Control for immediate action by revenue/customer teams.
"""

import os
import sys
import json
import hmac
import hashlib
import requests
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configuration
MC_URL = os.getenv('MC_URL', 'https://capable-leopard-644.convex.site')
HEYMANTLE_WEBHOOK_SECRET = os.getenv('HEYMANTLE_WEBHOOK_SECRET', '')

# Event type → urgency mapping
EVENT_URGENCY = {
    'subscription.created': 'high',      # New revenue
    'subscription.cancelled': 'critical', # Churn risk
    'subscription.payment_failed': 'high', # Payment issue
    'subscription.updated': 'medium',     # Plan change
}

EVENT_EMOJI = {
    'subscription.created': '🎉',
    'subscription.cancelled': '⚠️',
    'subscription.payment_failed': '💳',
    'subscription.updated': '📊',
}


def verify_signature(payload: str, signature: str) -> bool:
    """Verify Heymantle webhook signature."""
    if not HEYMANTLE_WEBHOOK_SECRET:
        return True  # Skip verification if secret not set (dev mode)
    
    expected = hmac.new(
        HEYMANTLE_WEBHOOK_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected}", signature)


def format_event_message(event_type: str, data: dict) -> str:
    """Format event data into readable MC message."""
    emoji = EVENT_EMOJI.get(event_type, '📬')
    
    if event_type == 'subscription.created':
        customer = data.get('customer', {})
        subscription = data.get('subscription', {})
        return f"""{emoji} **New Subscription Created**

**Customer:** {customer.get('name', 'Unknown')}
**Email:** {customer.get('email', 'N/A')}
**Plan:** {subscription.get('plan_name', 'Unknown')}
**MRR:** ${subscription.get('mrr', 0)}
**Started:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

@pepper — New paying customer to onboard!
@shuri — Add to revenue tracking"""

    elif event_type == 'subscription.cancelled':
        customer = data.get('customer', {})
        subscription = data.get('subscription', {})
        return f"""{emoji} **Subscription Cancelled — Churn Alert**

**Customer:** {customer.get('name', 'Unknown')}
**Email:** {customer.get('email', 'N/A')}
**Plan:** {subscription.get('plan_name', 'Unknown')}
**Previous MRR:** ${subscription.get('mrr', 0)}
**Cancelled:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

@pepper — Immediate outreach needed! Save this customer.
@fury — Flag for exit interview."""

    elif event_type == 'subscription.payment_failed':
        customer = data.get('customer', {})
        return f"""{emoji} **Payment Failed — Dunning Alert**

**Customer:** {customer.get('name', 'Unknown')}
**Email:** {customer.get('email', 'N/A')}
**Amount:** ${data.get('amount', 'N/A')}
**Failed:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

@pepper — Follow up on payment method.
@fury — Support ticket may be incoming."""

    elif event_type == 'subscription.updated':
        customer = data.get('customer', {})
        subscription = data.get('subscription', {})
        change = data.get('change', 'modified')
        return f"""{emoji} **Subscription Updated**

**Customer:** {customer.get('name', 'Unknown')}
**Email:** {customer.get('email', 'N/A')}
**New Plan:** {subscription.get('plan_name', 'Unknown')}
**New MRR:** ${subscription.get('mrr', 0)}
**Change Type:** {change}
**Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

@pepper — {'Upsell opportunity!' if change == 'upgraded' else 'Check-in on plan change'}
@shuri — Revenue tracking update needed."""

    else:
        return f"""{emoji} **Heymantle Event: {event_type}**

```json
{json.dumps(data, indent=2)[:500]}
```

Received: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"""


def post_to_mission_control(title: str, message: str, priority: int = 2) -> bool:
    """Create a notification task in Mission Control."""
    try:
        # Create a task in MC
        payload = {
            'title': title,
            'description': message,
            'agentName': 'friday',
            'priority': priority,
            'tags': ['heymantle', 'subscription', 'automated'],
        }
        
        resp = requests.post(
            f"{MC_URL}/api/tasks/create",
            json=payload,
            timeout=10
        )
        
        return resp.status_code == 200
    except Exception as e:
        print(f"Failed to post to MC: {e}")
        return False


@app.route('/webhook/heymantle', methods=['POST'])
def heymantle_webhook():
    """Receive and process Heymantle webhook events."""
    # Get raw body for signature verification
    raw_body = request.get_data(as_text=True)
    
    # Verify signature
    signature = request.headers.get('X-Heymantle-Signature', '')
    if not verify_signature(raw_body, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse event
    try:
        event = request.json
    except Exception:
        return jsonify({'error': 'Invalid JSON'}), 400
    
    event_type = event.get('type', 'unknown')
    data = event.get('data', {})
    
    # Format and post to MC
    title = f"Heymantle: {event_type.replace('.', ' ').title()}"
    message = format_event_message(event_type, data)
    priority = 1 if event_type == 'subscription.cancelled' else 2
    
    success = post_to_mission_control(title, message, priority)
    
    return jsonify({
        'received': True,
        'event_type': event_type,
        'posted_to_mc': success
    })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'heymantle-webhook',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/', methods=['GET'])
def root():
    """Root endpoint with info."""
    return jsonify({
        'service': 'Heymantle → Mission Control Webhook Bridge',
        'endpoints': {
            'webhook': '/webhook/heymantle',
            'health': '/health'
        },
        'events_supported': list(EVENT_URGENCY.keys())
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8767))
    app.run(host='0.0.0.0', port=port, debug=False)
