#!/bin/bash
# Install Jarvis as a macOS LaunchAgent: starts at login, restarts if it crashes,
# keeps all models warm so replies are instant. Run: bash scripts/install-daemon.sh
set -e

JARVIS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$JARVIS_DIR/.venv/bin/python"
LABEL="com.jarvis.assistant"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

[ -x "$VENV_PY" ] || { echo "venv python not found at $VENV_PY — run setup first"; exit 1; }
mkdir -p "$JARVIS_DIR/logs" "$HOME/Library/LaunchAgents"
: > "$JARVIS_DIR/logs/daemon.out.log"; : > "$JARVIS_DIR/logs/daemon.err.log"   # fresh logs each install

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV_PY</string>
    <string>$JARVIS_DIR/src/listen.py</string>
  </array>
  <key>WorkingDirectory</key><string>$JARVIS_DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>$JARVIS_DIR/logs/daemon.out.log</string>
  <key>StandardErrorPath</key><string>$JARVIS_DIR/logs/daemon.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <!-- launchd has a minimal PATH; add Homebrew so whisper-cli is found -->
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load -w "$PLIST"
echo "✅ Jarvis daemon installed and started (also runs at every login)."
echo "   Logs:  $JARVIS_DIR/logs/daemon.out.log  (and .err.log)"
echo "   Stop:  bash scripts/uninstall-daemon.sh   |   Restart: launchctl kickstart -k gui/\$(id -u)/$LABEL"
echo
echo "⚠️  First run needs MIC permission: System Settings → Privacy & Security →"
echo "   Microphone → enable it for the prompt that appears (or add your terminal)."
