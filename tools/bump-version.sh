#!/usr/bin/env bash
# bump-version.sh — Increment version across all plugin files and commit
#
# Usage:
#   ./tools/bump-version.sh          # patch bump: 0.1.0 → 0.1.1
#   ./tools/bump-version.sh minor    # minor bump: 0.1.1 → 0.2.0
#   ./tools/bump-version.sh major    # major bump: 0.2.0 → 1.0.0
#   ./tools/bump-version.sh 2.0.0    # set exact version
#
# Updates all 4 files that contain the version string:
#   - package.json
#   - .claude-plugin/plugin.json
#   - .claude-plugin/marketplace.json
#   - contracts/contract_registry.yaml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Read current version from package.json
CURRENT=$(grep -oP '"version":\s*"\K[^"]+' "$ROOT_DIR/package.json" | head -1)

if [ -z "$CURRENT" ]; then
    echo "ERROR: Could not read current version from package.json"
    exit 1
fi

IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

# Determine new version
BUMP_TYPE="${1:-patch}"

case "$BUMP_TYPE" in
    patch)
        PATCH=$((PATCH + 1))
        NEW_VERSION="$MAJOR.$MINOR.$PATCH"
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        NEW_VERSION="$MAJOR.$MINOR.$PATCH"
        ;;
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        NEW_VERSION="$MAJOR.$MINOR.$PATCH"
        ;;
    *)
        # Treat as exact version (e.g., "2.0.0")
        if [[ "$BUMP_TYPE" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            NEW_VERSION="$BUMP_TYPE"
        else
            echo "Usage: bump-version.sh [patch|minor|major|X.Y.Z]"
            exit 1
        fi
        ;;
esac

echo "Bumping version: $CURRENT → $NEW_VERSION"

# Update all 4 files
sed -i "s/\"version\": \"$CURRENT\"/\"version\": \"$NEW_VERSION\"/" "$ROOT_DIR/package.json"
sed -i "s/\"version\": \"$CURRENT\"/\"version\": \"$NEW_VERSION\"/" "$ROOT_DIR/.claude-plugin/plugin.json"
sed -i "s/\"version\": \"$CURRENT\"/\"version\": \"$NEW_VERSION\"/" "$ROOT_DIR/.claude-plugin/marketplace.json"
sed -i "s/# Version: $CURRENT/# Version: $NEW_VERSION/" "$ROOT_DIR/contracts/contract_registry.yaml"

# Verify all files updated
echo ""
echo "Verifying:"
for f in package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json contracts/contract_registry.yaml; do
    if grep -q "$NEW_VERSION" "$ROOT_DIR/$f"; then
        echo "  ✓ $f → $NEW_VERSION"
    else
        echo "  ✗ $f — FAILED TO UPDATE"
        exit 1
    fi
done

echo ""
echo "Done. Version is now $NEW_VERSION across all files."
echo "Run 'git add -A && git commit' to commit the bump."
