#!/bin/bash
# NEXUS — Install git hooks for safe collaboration
# Run once: bash scripts/install_hooks.sh

HOOK_DIR="$(git rev-parse --git-dir)/hooks"

echo "Installing NEXUS git hooks..."

# PRE-PUSH HOOK — Blocks broken code from reaching main
cat > "$HOOK_DIR/pre-push" << 'HOOK'
#!/bin/bash
# NEXUS pre-push hook: syntax check before push

echo "🔍 NEXUS pre-push: checking syntax..."

errors=0
for f in $(find . -name "*.py" -not -path "./.git/*" -not -path "./venv/*" -not -path "./.venv/*"); do
    if ! python3 -m py_compile "$f" 2>/dev/null; then
        echo "❌ SYNTAX ERROR: $f"
        python3 -m py_compile "$f" 2>&1
        errors=$((errors + 1))
    fi
done

if [ $errors -gt 0 ]; then
    echo ""
    echo "🚫 PUSH BLOCKED: $errors files with syntax errors"
    echo "   Fix the errors above before pushing."
    exit 1
fi

# Check for secrets
if grep -rq "sk-ant-\|ghp_" --include="*.py" --include="*.yaml" --include="*.yml" . 2>/dev/null; then
    echo "🚫 PUSH BLOCKED: Possible secret/API key in code!"
    echo "   Remove any API keys before pushing."
    grep -rn "sk-ant-\|ghp_" --include="*.py" --include="*.yaml" --include="*.yml" . 2>/dev/null
    exit 1
fi

echo "✅ All checks passed. Pushing..."
HOOK

chmod +x "$HOOK_DIR/pre-push"

# PRE-COMMIT HOOK — Quick sanity check
cat > "$HOOK_DIR/pre-commit" << 'HOOK'
#!/bin/bash
# NEXUS pre-commit hook: prevent common mistakes

# Check if settings.yaml is being committed (has API keys)
if git diff --cached --name-only | grep -q "config/settings.yaml$"; then
    echo "🚫 COMMIT BLOCKED: config/settings.yaml contains API keys!"
    echo "   Use config/settings.yaml.example instead."
    echo "   Run: git reset HEAD config/settings.yaml"
    exit 1
fi

# Check for debug prints left in code
if git diff --cached --diff-filter=ACM --name-only -- '*.py' | xargs grep -n "breakpoint()\|import pdb" 2>/dev/null; then
    echo "⚠️  WARNING: Debug breakpoints found. Remove before commit."
    exit 1
fi
HOOK

chmod +x "$HOOK_DIR/pre-commit"

echo "✅ Hooks installed:"
echo "   pre-push  → blocks syntax errors + secret leaks"
echo "   pre-commit → blocks settings.yaml + debug breakpoints"
echo ""
echo "Both devs should run this after cloning."
