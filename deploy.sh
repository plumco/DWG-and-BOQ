#!/bin/bash
# Quick deploy to Streamlit Cloud

echo "🚀 Huliot AutoBOQ Deployment Script"
echo "===================================="
echo ""

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "📦 Initializing Git repository..."
    git init
fi

# Add files
echo "📁 Adding files..."
git add app.py requirements.txt README.md
git commit -m "Huliot AutoBOQ - Auto SH marker + BOQ generator"

echo ""
echo "✅ Files ready!"
echo ""
echo "Next steps:"
echo "1. Create GitHub repo: https://github.com/new"
echo "2. Run: git remote add origin YOUR_REPO_URL"
echo "3. Run: git push -u origin main"
echo "4. Deploy: https://share.streamlit.io"
echo "   - Connect GitHub"
echo "   - Select repo"
echo "   - Main file: app.py"
echo "   - Deploy!"
echo ""
echo "OR run locally:"
echo "pip install -r requirements.txt"
echo "streamlit run app.py"
