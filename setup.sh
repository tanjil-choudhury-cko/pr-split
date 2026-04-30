#!/usr/bin/env bash
set -e

REPO="tanjil-choudhury-cko/pr-split"
BRANCH="main"
RAW="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
TOOL_DIR="$HOME/.pr-split"

echo ""
echo "==> pr-split setup"
echo ""

# ── Homebrew ────────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
  echo "Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
  echo "✓ Homebrew already installed"
fi

# ── gh ──────────────────────────────────────────────────────────────────────
if ! command -v gh &>/dev/null; then
  echo "Installing GitHub CLI..."
  brew install gh
else
  echo "✓ gh already installed"
fi

# ── AWS CLI ─────────────────────────────────────────────────────────────────
if ! command -v aws &>/dev/null; then
  echo "Installing AWS CLI..."
  brew install awscli
else
  echo "✓ aws already installed"
fi

# ── Download tool to ~/.pr-split ────────────────────────────────────────────
echo "Downloading pr-split to $TOOL_DIR..."
mkdir -p "$TOOL_DIR"
curl -fsSL "${RAW}/pr_split.py"      -o "$TOOL_DIR/pr_split.py"
curl -fsSL "${RAW}/requirements.txt" -o "$TOOL_DIR/requirements.txt"
echo "✓ Downloaded to $TOOL_DIR"

# ── Python dependencies ─────────────────────────────────────────────────────
echo "Installing Python dependencies..."
pip3 install -q -r "$TOOL_DIR/requirements.txt" --break-system-packages
echo "✓ Python dependencies installed"

# ── Shell config (~/.zshrc) ─────────────────────────────────────────────────
ZSHRC="$HOME/.zshrc"
MARKER="# pr-split (added by setup.sh)"

if grep -q "$MARKER" "$ZSHRC" 2>/dev/null; then
  echo "✓ Shell config already set"
else
  cat >> "$ZSHRC" <<'EOF'

# pr-split (added by setup.sh)
export AWS_DEFAULT_REGION=eu-north-1
export AWS_PROFILE=playground14
export ANTHROPIC_MODEL=eu.anthropic.claude-sonnet-4-5-20250929-v1:0
# Re-authenticate when credentials expire (~8h): aws login --profile playground14 --region eu-west-1

prsplit() {
  unset AWS_BEARER_TOKEN_BEDROCK
  python3 ~/.pr-split/pr_split.py "$@"
}
EOF
  echo "✓ Added 'prsplit' command and Bedrock config to ~/.zshrc"
fi

source "$ZSHRC" 2>/dev/null || true

# ── AWS login ────────────────────────────────────────────────────────────────
echo ""
echo "==> Logging in to AWS (playground14)..."
aws login --profile playground14 --region eu-west-1

# ── GitHub login ─────────────────────────────────────────────────────────────
if ! gh auth status &>/dev/null; then
  echo ""
  echo "==> Logging in to GitHub..."
  gh auth login --git-protocol https
else
  echo "✓ GitHub CLI already authenticated"
fi

echo ""
echo "✓ All done. Open a new terminal tab and run: prsplit"
echo "   Works from any git repo — no setup needed per project."
echo ""
echo "   To update the tool later, re-run:"
echo "   curl -fsSL https://raw.githubusercontent.com/${REPO}/${BRANCH}/setup.sh | bash"
echo ""
