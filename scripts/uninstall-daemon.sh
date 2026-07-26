#!/bin/bash
# Stop and remove the Jarvis LaunchAgent. Run: bash scripts/uninstall-daemon.sh
LABEL="com.jarvis.assistant"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✅ Jarvis daemon stopped and removed. (Re-install: bash scripts/install-daemon.sh)"
