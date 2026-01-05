#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📂 Course root: $REPO_ROOT"

cd "$REPO_ROOT/sam"

echo "🔧 Creating virtual environment..."
python3 -m venv .venv

echo "⚡ Activating virtual environment..."
source .venv/bin/activate

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "🎭 Installing Playwright..."
playwright install

echo "🚀 Initializing SAM..."
sam init --skip

# Sync with shared .env file
SHARED_ENV="../../.env.config"
SAM_ENV="$REPO_ROOT/sam/.env"

if [ -f "$SHARED_ENV" ]; then
  echo "🔁 Syncing root .env → sam/.env"
  cp "$SHARED_ENV" "$SAM_ENV"
else
  echo "⚠️ Root .env not found, skipping env sync"
fi

echo "✅ Setup complete"
set +e

sam run
