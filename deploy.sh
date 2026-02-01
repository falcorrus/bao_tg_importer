#!/bin/bash

echo "🚀 Starting deploy process..."

# 1. Local Git Push
echo "📦 Committing and pushing local changes..."
git add .
timestamp=$(date "+%Y-%m-%d %H:%M:%S")
git commit -m "Auto-deploy update: $timestamp"
git push origin master

if [ $? -ne 0 ]; then
    echo "❌ Git push failed. Aborting."
    exit 1
fi

# 2. Remote Git Pull
echo "🌍 Updating server (VPS)..."
ssh -i ~/.ssh/id_ed25519_reloto_2026 -o StrictHostKeyChecking=no vps "cd /root/scripts/bao_tg_importer && git pull && source venv/bin/activate && pip3 install -r requirements.txt"

if [ $? -eq 0 ]; then
    echo "✅ Deploy successful!"
else
    echo "❌ Server update failed."
    exit 1
fi
