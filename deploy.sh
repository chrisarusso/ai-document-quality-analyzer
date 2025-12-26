#!/bin/bash
# Deploy script for Document Quality Analyzer
# Usage: ./deploy.sh [--verify-only]

set -e

EC2_HOST="ubuntu@3.142.219.101"
EC2_KEY="$HOME/.ssh/AWS-created-nov-27-2025.pem"
LOCAL_DIR="/Users/chris/web/savas-things/AI/projects/document-quality-analyzer"
REMOTE_DIR="/home/ubuntu/document-quality-analyzer"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Document Quality Analyzer Deploy Script${NC}"
echo "========================================"

# Verify-only mode
if [ "$1" == "--verify-only" ]; then
    echo -e "${YELLOW}Verifying local vs EC2 sync status...${NC}"

    echo -e "\n${GREEN}Local changes (uncommitted):${NC}"
    git status --short

    echo -e "\n${GREEN}Comparing key files with EC2:${NC}"
    for file in src/doc_analyzer/api.py src/doc_analyzer/cli.py src/doc_analyzer/extractors/google_docs.py src/doc_analyzer/extractors/google_slides.py; do
        LOCAL_HASH=$(md5 -q "$LOCAL_DIR/$file" 2>/dev/null || echo "missing")
        REMOTE_HASH=$(ssh -i "$EC2_KEY" "$EC2_HOST" "md5sum $REMOTE_DIR/$file 2>/dev/null | cut -d' ' -f1" || echo "missing")
        if [ "$LOCAL_HASH" == "$REMOTE_HASH" ]; then
            echo -e "  ${GREEN}✓${NC} $file (in sync)"
        else
            echo -e "  ${RED}✗${NC} $file (differs)"
        fi
    done
    exit 0
fi

# Step 1: Rsync files to EC2
echo -e "\n${YELLOW}Step 1: Syncing files to EC2...${NC}"
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' \
    -e "ssh -i $EC2_KEY" \
    "$LOCAL_DIR/" "$EC2_HOST:$REMOTE_DIR/"

# Step 2: Copy token if it exists
if [ -f "$LOCAL_DIR/token.json" ]; then
    echo -e "\n${YELLOW}Step 2: Syncing OAuth token...${NC}"
    scp -i "$EC2_KEY" "$LOCAL_DIR/token.json" "$EC2_HOST:$REMOTE_DIR/"
fi

# Step 3: Restart the app
echo -e "\n${YELLOW}Step 3: Restarting app on EC2...${NC}"
ssh -i "$EC2_KEY" "$EC2_HOST" "pkill -f 'uvicorn doc_analyzer.api' || true; sleep 1; cd $REMOTE_DIR && nohup uv run uvicorn doc_analyzer.api:app --host 127.0.0.1 --port 8002 > /tmp/doc-analyzer.log 2>&1 &"

# Step 4: Wait and verify
echo -e "\n${YELLOW}Step 4: Verifying deployment...${NC}"
sleep 4
HEALTH=$(curl -s https://secret-savas.savaslabs.com/doc-analyzer/health 2>/dev/null || echo "failed")
if [[ "$HEALTH" == *"ok"* ]]; then
    echo -e "${GREEN}✓ Deployment successful!${NC}"
    echo -e "\n${GREEN}App URL:${NC} https://secret-savas.savaslabs.com/doc-analyzer/"
else
    echo -e "${RED}✗ Health check failed. Check logs with:${NC}"
    echo "  ssh -i $EC2_KEY $EC2_HOST 'tail -50 /tmp/doc-analyzer.log'"
fi
