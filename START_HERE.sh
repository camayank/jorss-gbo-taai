#!/bin/bash
# Quick Start Script - See Your Branded Platform!

echo "================================================"
echo "🎨 Jorss-Gbo Tax Platform - Custom Branding"
echo "================================================"
echo ""

# Check if dependencies are installed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -q fastapi uvicorn pydantic sqlalchemy aiosqlite python-multipart python-jose[cryptography]
    echo "✅ Dependencies installed"
    echo ""
fi

# Set custom branding (YOU CAN CHANGE THESE!)
export PLATFORM_NAME="Your Tax Platform"
export COMPANY_NAME="Your Company Name, CPAs"
export TAGLINE="Professional Tax Filing Made Simple"
export BRAND_PRIMARY_COLOR="#1e40af"  # Deep blue
export BRAND_ACCENT_COLOR="#f59e0b"   # Gold accent
export SUPPORT_EMAIL="support@yourcompany.com"

echo "🎨 Branding Applied:"
echo "   Platform Name: $PLATFORM_NAME"
echo "   Company Name: $COMPANY_NAME"
echo "   Primary Color: $BRAND_PRIMARY_COLOR"
echo "   Accent Color: $BRAND_ACCENT_COLOR"
echo ""

echo "🚀 Starting server..."
echo ""
echo "================================================"
echo "✨ Visit your platform at:"
echo "   http://localhost:8000/"
echo ""
echo "   You should see YOUR branding everywhere!"
echo "================================================"
echo ""

# Start the server
cd "$(dirname "$0")"
python3 -m uvicorn src.web.app:app --reload --host 0.0.0.0 --port 8000
