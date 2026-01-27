#!/bin/bash

# Verification script for Claude AI integration

echo "=================================================="
echo "  PDF to Excel Converter - Setup Verification"
echo "=================================================="
echo ""

# Check Python version
echo "1. Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1)
echo "   ✓ $PYTHON_VERSION"
echo ""

# Check Anthropic package
echo "2. Checking Anthropic SDK..."
if python3 -c "import anthropic" 2>/dev/null; then
    VERSION=$(python3 -c "import anthropic; print(anthropic.__version__)")
    echo "   ✓ Anthropic SDK installed (v$VERSION)"
else
    echo "   ✗ Anthropic SDK not found"
    echo "   Run: pip install anthropic"
fi
echo ""

# Check OpenAI package
echo "3. Checking OpenAI SDK..."
if python3 -c "import openai" 2>/dev/null; then
    echo "   ✓ OpenAI SDK installed"
else
    echo "   ⚠ OpenAI SDK not found (optional fallback)"
fi
echo ""

# Check for API keys in .env
echo "4. Checking API keys in backend/.env..."
cd "$(dirname "$0")/backend"

if [ -f .env ]; then
    if grep -q "ANTHROPIC_API_KEY=sk-ant-" .env; then
        echo "   ✓ ANTHROPIC_API_KEY is set"
    else
        echo "   ⚠ ANTHROPIC_API_KEY not configured"
        echo "     Add your key to backend/.env"
    fi

    if grep -q "OPENAI_API_KEY=sk-" .env; then
        echo "   ✓ OPENAI_API_KEY is set (fallback)"
    else
        echo "   ℹ OPENAI_API_KEY not set (optional)"
    fi
else
    echo "   ✗ .env file not found"
    echo "     Create backend/.env from .env.example"
fi
echo ""

# Check required packages
echo "5. Checking other dependencies..."
for pkg in fastapi uvicorn pdfplumber openpyxl; do
    if python3 -c "import $pkg" 2>/dev/null; then
        echo "   ✓ $pkg"
    else
        echo "   ✗ $pkg missing"
    fi
done
echo ""

# Check if server is running
echo "6. Checking if server is running..."
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "   ✓ Server is running on http://localhost:8000"

    # Check server response
    HEALTH=$(curl -s http://localhost:8000/health)
    echo "   Response: $HEALTH"
else
    echo "   ℹ Server is not running"
    echo "     Start with: cd backend && uvicorn app.main:app --reload"
fi
echo ""

echo "=================================================="
echo "  Summary"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Add ANTHROPIC_API_KEY to backend/.env"
echo "2. Start server: cd backend && uvicorn app.main:app --reload"
echo "3. Test: python test_claude.py"
echo "4. Upload PDF: http://localhost:8000/docs"
echo ""
echo "Documentation:"
echo "- Quick Start: QUICK_START.md"
echo "- Claude Setup: CLAUDE_INTEGRATION.md"
echo "- Testing: python test_claude.py"
echo ""
