#!/bin/bash
# Update version and rebuild package

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

if [ -z "$1" ]; then
    echo -e "${RED}Usage: $0 <new-version>${NC}"
    echo "Example: $0 1.1.0"
    exit 1
fi

NEW_VERSION="$1"

echo -e "${BLUE}=== Updating Brother Label Printer to version ${NEW_VERSION} ===${NC}"
echo

# Update debian/changelog
echo -e "${BLUE}Updating debian/changelog...${NC}"

# Create new changelog entry
TEMP_CHANGELOG=$(mktemp)
cat > "$TEMP_CHANGELOG" <<EOF
brother-label-printer (${NEW_VERSION}) unstable; urgency=medium

  * Version ${NEW_VERSION}
  * Update release

 -- Daniel Rosehill <public@danielrosehill.com>  $(date -R)

EOF

# Append old changelog
cat debian/changelog >> "$TEMP_CHANGELOG"
mv "$TEMP_CHANGELOG" debian/changelog

echo -e "${GREEN}Version updated to ${NEW_VERSION}${NC}"
echo

# Commit changes
echo -e "${BLUE}Committing version bump...${NC}"
git add debian/changelog
git commit -m "Bump version to ${NEW_VERSION}"

echo -e "${GREEN}Changes committed${NC}"
echo

# Build and install
echo -e "${BLUE}Running build and install script...${NC}"
./build-and-install.sh
