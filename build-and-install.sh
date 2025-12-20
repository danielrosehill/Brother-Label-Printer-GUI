#!/bin/bash
# Build and install Brother Label Printer Debian package

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Brother Label Printer - Build and Install ===${NC}"
echo

# Check if running as root for install
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please do not run this script as root!${NC}"
    echo "The script will ask for sudo when needed."
    exit 1
fi

# Function to check if package is installed
check_dependency() {
    if ! dpkg -l | grep -q "^ii  $1 "; then
        echo -e "${RED}Missing dependency: $1${NC}"
        echo "Please install it with: sudo apt install $1"
        return 1
    fi
    return 0
}

# Check build dependencies
echo -e "${BLUE}Checking build dependencies...${NC}"
MISSING_DEPS=0

for dep in debhelper dh-python python3 python3-setuptools; do
    if ! check_dependency "$dep"; then
        MISSING_DEPS=1
    fi
done

if [ $MISSING_DEPS -eq 1 ]; then
    echo
    echo -e "${RED}Missing dependencies. Install them with:${NC}"
    echo "sudo apt install debhelper dh-python python3 python3-setuptools"
    exit 1
fi

echo -e "${GREEN}All build dependencies satisfied${NC}"
echo

# Clean previous builds
echo -e "${BLUE}Cleaning previous builds...${NC}"
rm -rf debian/brother-label-printer
rm -rf debian/.debhelper
rm -rf debian/files
rm -rf debian/debhelper-build-stamp
rm -rf debian/*.substvars
rm -rf debian/*.log
rm -f ../*.deb
rm -f ../*.buildinfo
rm -f ../*.changes

# Build the package
echo -e "${BLUE}Building Debian package...${NC}"
dpkg-buildpackage -us -uc -b

echo
echo -e "${GREEN}Package built successfully!${NC}"
echo

# Find the generated .deb file
DEB_FILE=$(ls -t ../*.deb 2>/dev/null | head -1)

if [ -z "$DEB_FILE" ]; then
    echo -e "${RED}Error: Could not find generated .deb file${NC}"
    exit 1
fi

echo -e "${BLUE}Generated package: ${GREEN}$(basename "$DEB_FILE")${NC}"
echo

# Ask to install
read -p "Do you want to install the package now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Installing package...${NC}"
    sudo dpkg -i "$DEB_FILE"

    # Check if there are missing dependencies
    if ! sudo apt-get install -f -y; then
        echo -e "${RED}Failed to install dependencies${NC}"
        exit 1
    fi

    echo
    echo -e "${GREEN}Installation complete!${NC}"
    echo
    echo -e "${BLUE}You can now run the application with:${NC}"
    echo "  brother-label-printer-gui"
    echo
    echo "Or find it in your application menu as 'Brother Label Printer'"
else
    echo
    echo -e "${BLUE}Package created but not installed.${NC}"
    echo "To install later, run:"
    echo "  sudo dpkg -i $(basename "$DEB_FILE")"
fi

echo
echo -e "${GREEN}Done!${NC}"
