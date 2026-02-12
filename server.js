/**
 * Heymantle → Mission Control Webhook Integration
 * 
 * Receives subscription events from Heymantle and creates
 * Mission Control tasks/notifications for the team.
 */

const express = require('express');
const crypto = require('crypto');
const axios = require('axios');

const app = express();
app.use(express.json());

// Configuration
const MC_BASE_URL = process.env.MC_BASE_URL || 'https://capable-leopard-644.convex.site';
const MC_AGENT_ID = process.env.MC_AGENT_ID || 'j978jcgdtjgkrw2qhab7m88nxd80pdn4'; // friday
const HEYMANTLE_WEBHOOK_SECRET = process.env.HEYMANTLE_WEBHOOK_SECRET;

// Agent IDs for mentions
const AGENTS = {
  pepper: 'j97e9degfcq4mhmyw53rwgq5p180p23j',  // CRO - for upgrades/expansions
  fury: 'j97bsx853qne8faxe9srk2scj180pav4',    // CCO - for churn risk
  shuri: 'j9783sgjs2247j82x62fbk8ja980s8na',   // CPO - for product insights
  loki: 'j971kyj5j6c3ywgckq89h7s50s80pj0m',    // CMO - for case studies
  brain: 'j9755gxzqq5jh6ncsnxrxv714980qjn0'    // COO - for strategic decisions
};

/**
 * Verify Heymantle webhook signature
 */
function verifySignature(payload, signature, secret) {
  if (!secret) {
    console.warn('No webhook secret configured — skipping verification');
    return true;
  }
  const expected = crypto
    .createHmac('sha256', secret)
    .update(payload, 'utf8')
    .digest('hex');
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected)
  );
}

/**
 * Create Mission Control task
 */
async function createMCTask(title, description, priority = 2, assignee = null) {
  try {
    const payload = {
      title,
      description,
      agentName: 'friday',
      priority,
      tags: ['auto-generated', 'heymantle', 'subscription'],
      deliverable: 'Review and take action as needed'
    };
    
    if (assignee) {
      payload.assigneeIds = [assignee];
    }
    
    const response = await axios.post(`${MC_BASE_URL}/api/tasks/create`, payload);
    console.log('✅ MC task created:', response.data.taskId);
    return response.data.taskId;
  } catch (err) {
    console.error('❌ Failed to create MC task:', err.message);
    return null;
  }
}

/**
 * Post comment to Mission Control task
 */
async function postMCMessage(taskId, content) {
  try {
    await axios.post(`${MC_BASE_URL}/api/messages/post`, {
      taskId,
      agentId: MC_AGENT_ID,
      content
    });
    console.log('✅ MC message posted');
  } catch (err) {
    console.error('❌ Failed to post MC message:', err.message);
  }
}

/**
 * Handle subscription.created event
 */
async function handleSubscriptionCreated(event) {
  const { customer, subscription } = event.data;
  
  const title = `🎉 New Subscription: ${customer.name || customer.email}`;
  const description = `
**New customer subscribed to Looksy!**

| Field | Value |
|-------|-------|
| Customer | ${customer.name || 'N/A'} |
| Email | ${customer.email} |
| Plan | ${subscription.planName || subscription.planId} |
| MRR | $${subscription.mrr || subscription.amount} |
| Started | ${new Date(subscription.startedAt).toISOString()} |

**Actions:**
- @pepper — Consider outreach for onboarding/setup assistance
- @fury — Add to customer health tracking
- @loki — Potential case study candidate in 30 days
  `;
  
  const taskId = await createMCTask(title, description, 2, AGENTS.pepper);
  if (taskId) {
    await postMCMessage(taskId, `@pepper New subscription alert — $${subscription.mrr || subscription.amount}/mo from ${customer.email}`);
  }
}

/**
 * Handle subscription.updated event (upgrades)
 */
async function handleSubscriptionUpdated(event) {
  const { customer, subscription, previousValues } = event.data;
  
  // Check if this is an upgrade (MRR increased)
  const previousMrr = previousValues?.mrr || 0;
  const currentMrr = subscription.mrr || subscription.amount;
  
  if (currentMrr > previousMrr) {
    const title = `⬆️ Subscription Upgrade: ${customer.name || customer.email}`;
    const description = `
**Customer upgraded their plan!**

| Field | Value |
|-------|-------|
| Customer | ${customer.name || 'N/A'} |
| Email | ${customer.email} |
| Previous MRR | $${previousMrr} |
| New MRR | $${currentMrr} |
| Increase | +$${currentMrr - previousMrr}/mo |

**Actions:**
- @pepper — Excellent expansion opportunity, consider thank you note
- @shuri — Track feature usage that drove upgrade
- @fury — Update health score (positive signal)
    `;
    
    const taskId = await createMCTask(title, description, 2, AGENTS.pepper);
    if (taskId) {
      await postMCMessage(taskId, `@pepper Upgrade alert! ${customer.email} increased from $${previousMrr} to $${currentMrr}/mo 🎉`);
    }
  }
}

/**
 * Handle subscription.cancelled event
 */
async function handleSubscriptionCancelled(event) {
  const { customer, subscription } = event.data;
  
  const title = `⚠️ Subscription Cancelled: ${customer.name || customer.email}`;
  const description = `
**Customer cancelled their subscription**

| Field | Value |
|-------|-------|
| Customer | ${customer.name || 'N/A'} |
| Email | ${customer.email} |
| Plan | ${subscription.planName || subscription.planId} |
| Lost MRR | $${subscription.mrr || subscription.amount} |
| Cancelled | ${new Date().toISOString()} |

**Actions:**
- @fury — Immediate outreach for exit interview/retention
- @shuri — Analyze usage patterns leading to churn
- @pepper — Review for win-back campaign eligibility
  `;
  
  const taskId = await createMCTask(title, description, 1, AGENTS.fury); // P1 for churn
  if (taskId) {
    await postMCMessage(taskId, `@fury Churn alert — ${customer.email} cancelled ($${subscription.mrr || subscription.amount}/mo). Immediate outreach recommended.`);
  }
}

// Webhook endpoint
app.post('/webhook/heymantle', async (req, res) => {
  const signature = req.headers['x-heymantle-signature'];
  const payload = JSON.stringify(req.body);
  
  // Verify signature if secret is configured
  if (HEYMANTLE_WEBHOOK_SECRET && !verifySignature(payload, signature, HEYMANTLE_WEBHOOK_SECRET)) {
    console.error('Invalid webhook signature');
    return res.status(401).json({ error: 'Invalid signature' });
  }
  
  const { event, data } = req.body;
  
  console.log(`📩 Received Heymantle event: ${event}`);
  console.log(`   Customer: ${data?.customer?.email || 'N/A'}`);
  
  try {
    switch (event) {
      case 'subscription.created':
        await handleSubscriptionCreated(req.body);
        break;
      case 'subscription.updated':
        await handleSubscriptionUpdated(req.body);
        break;
      case 'subscription.cancelled':
        await handleSubscriptionCancelled(req.body);
        break;
      default:
        console.log(`Unhandled event type: ${event}`);
    }
    
    res.status(200).json({ received: true });
  } catch (err) {
    console.error('Error processing webhook:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Health check
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    service: 'heymantle-mc-webhook'
  });
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 Heymantle → Mission Control webhook server running on port ${PORT}`);
  console.log(`   Webhook URL: http://localhost:${PORT}/webhook/heymantle`);
  console.log(`   Health check: http://localhost:${PORT}/health`);
});
