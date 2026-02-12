#!/bin/bash
#
# Deploy Heymantle Webhook → Mission Control Integration
#

set -e

echo "🚀 Deploying Heymantle Webhook Integration..."

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Check for required env vars
if [ -z "$HEYMANTLE_WEBHOOK_SECRET" ]; then
  echo "⚠️  Warning: HEYMANTLE_WEBHOOK_SECRET not set"
  echo "   Webhook verification will be skipped (dev mode)"
fi

# Create systemd service file for Linux or launchd for macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
  echo "🍎 Creating launchd service..."
  
  PLIST_PATH="$HOME/Library/LaunchAgents/com.openclaw.heymantle-webhook.plist"
  
  cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.openclaw.heymantle-webhook</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which node)</string>
        <string>$(pwd)/server.js</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$(pwd)</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$(pwd)/webhook.log</string>
    <key>StandardErrorPath</key>
    <string>$(pwd)/webhook-error.log</string>
</dict>
</plist>
PLIST

  launchctl load "$PLIST_PATH" 2>/dev/null || true
  launchctl start com.openclaw.heymantle-webhook 2>/dev/null || true
  
  echo "✅ Launchd service installed and started"
  echo "   Logs: $(pwd)/webhook.log"
  
else
  echo "🐧 Creating systemd service..."
  
  sudo tee /etc/systemd/system/heymantle-webhook.service > /dev/null << SERVICE
[Unit]
Description=Heymantle → Mission Control Webhook
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$(which node) $(pwd)/server.js
Restart=always
RestartSec=10
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
SERVICE

  sudo systemctl daemon-reload
  sudo systemctl enable heymantle-webhook
  sudo systemctl start heymantle-webhook
  
  echo "✅ Systemd service installed and started"
  echo "   Logs: sudo journalctl -u heymantle-webhook -f"
fi

echo ""
echo "📝 Next steps:"
echo "   1. Copy .env.example to .env and fill in HEYMANTLE_WEBHOOK_SECRET"
echo "   2. Get webhook URL from ngrok or deploy to Render/Railway"
echo "   3. Add webhook URL to Heymantle dashboard"
echo "   4. Test with a sample event"
echo ""
echo "✨ Deployment complete!"
