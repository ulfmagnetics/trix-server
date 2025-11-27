#!/bin/bash
# Build script to compile CircuitPython modules to .mpy for memory optimization
# This reduces RAM usage by ~37% per module and eliminates compilation-time fragmentation

# Configuration
SRC_DIR="matrixportal"
BUILD_DIR="matrixportal/build"
MPY_CROSS="/usr/local/bin/mpy-cross"  # Adjust if installed elsewhere

# Files to exclude from compilation (must stay as .py)
EXCLUDE_FILES=("code.py" "boot.py" "secrets.py" "config.py")

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== CircuitPython mpy-cross Build Script ===${NC}"
echo "Compiling .py modules to .mpy bytecode for memory optimization"
echo ""

# Check if mpy-cross is installed
if [ ! -f "$MPY_CROSS" ]; then
    echo -e "${RED}Error: mpy-cross not found at $MPY_CROSS${NC}"
    echo ""
    echo "Please install mpy-cross 10.0.3 first:"
    echo "  cd ~"
    echo "  wget https://adafruit-circuit-python.s3.amazonaws.com/bin/mpy-cross/linux-amd64/mpy-cross-linux-amd64-10.0.3.static"
    echo "  mv mpy-cross-linux-amd64-10.0.3.static mpy-cross"
    echo "  chmod +x mpy-cross"
    echo "  sudo mv mpy-cross /usr/local/bin/"
    exit 1
fi

# Verify mpy-cross version
echo -e "${BLUE}Checking mpy-cross version...${NC}"
$MPY_CROSS --version || echo -e "${YELLOW}Warning: Could not verify mpy-cross version${NC}"
echo ""

# Function to check if file should be excluded
should_exclude() {
    local file="$1"
    local basename=$(basename "$file")
    for exclude in "${EXCLUDE_FILES[@]}"; do
        if [ "$basename" = "$exclude" ]; then
            return 0
        fi
    done
    return 1
}

# Create build directory structure
echo -e "${BLUE}[1/3] Creating build directory structure...${NC}"
mkdir -p "$BUILD_DIR/routes"
echo -e "  ${GREEN}✓${NC} Created $BUILD_DIR/"
echo -e "  ${GREEN}✓${NC} Created $BUILD_DIR/routes/"
echo ""

# Compile root-level Python files
echo -e "${BLUE}[2/3] Compiling root-level modules...${NC}"
compiled_count=0
for py_file in "$SRC_DIR"/*.py; do
    if [ -f "$py_file" ] && ! should_exclude "$py_file"; then
        basename=$(basename "$py_file")
        mpy_name="${basename%.py}.mpy"
        echo -e "  ${GREEN}→${NC} Compiling $basename → $mpy_name"

        if "$MPY_CROSS" -o "$BUILD_DIR/$mpy_name" "$py_file" 2>&1; then
            size_py=$(stat -c%s "$py_file" 2>/dev/null || stat -f%z "$py_file" 2>/dev/null)
            size_mpy=$(stat -c%s "$BUILD_DIR/$mpy_name" 2>/dev/null || stat -f%z "$BUILD_DIR/$mpy_name" 2>/dev/null)
            savings=$(( (size_py - size_mpy) * 100 / size_py ))
            echo -e "    ${GREEN}✓${NC} Success (${savings}% smaller on disk)"
            ((compiled_count++))
        else
            echo -e "    ${RED}✗${NC} Failed to compile $basename"
        fi
    fi
done
echo ""

# Compile routes package
echo -e "${BLUE}[3/3] Compiling routes package...${NC}"
routes_count=0
for py_file in "$SRC_DIR/routes"/*.py; do
    if [ -f "$py_file" ]; then
        basename=$(basename "$py_file")
        mpy_name="${basename%.py}.mpy"
        echo -e "  ${GREEN}→${NC} Compiling routes/$basename → routes/$mpy_name"

        if "$MPY_CROSS" -o "$BUILD_DIR/routes/$mpy_name" "$py_file" 2>&1; then
            size_py=$(stat -c%s "$py_file" 2>/dev/null || stat -f%z "$py_file" 2>/dev/null)
            size_mpy=$(stat -c%s "$BUILD_DIR/routes/$mpy_name" 2>/dev/null || stat -f%z "$BUILD_DIR/routes/$mpy_name" 2>/dev/null)
            savings=$(( (size_py - size_mpy) * 100 / size_py ))
            echo -e "    ${GREEN}✓${NC} Success (${savings}% smaller on disk)"
            ((routes_count++))
        else
            echo -e "    ${RED}✗${NC} Failed to compile routes/$basename"
        fi
    fi
done
echo ""

# Summary
total_compiled=$((compiled_count + routes_count))
echo -e "${GREEN}=== Build Complete ===${NC}"
echo -e "Compiled ${GREEN}$total_compiled${NC} modules successfully"
echo -e "Expected RAM savings: ${GREEN}~9-14 KB${NC} (37% per module)"
echo ""

# Deployment instructions
echo -e "${BLUE}=== Deployment Instructions ===${NC}"
echo ""
echo "1. Copy compiled modules to CIRCUITPY drive:"
echo "   - Copy all files from: $BUILD_DIR/*.mpy → CIRCUITPY/"
echo "   - Copy all files from: $BUILD_DIR/routes/*.mpy → CIRCUITPY/routes/"
echo ""
echo "2. Copy non-compiled files:"
echo "   - $SRC_DIR/code.py → CIRCUITPY/code.py"
echo "   - $SRC_DIR/boot.py → CIRCUITPY/boot.py (if exists)"
echo "   - $SRC_DIR/secrets.py → CIRCUITPY/secrets.py (if exists)"
echo ""
echo -e "${YELLOW}3. CRITICAL: Delete old .py files that now have .mpy versions:${NC}"
echo "   - Delete: CIRCUITPY/display.py"
echo "   - Delete: CIRCUITPY/context.py"
echo "   - Delete: CIRCUITPY/crash_logger.py"
echo "   - Delete: CIRCUITPY/utils.py"
echo "   - Delete: CIRCUITPY/routes/display.py"
echo "   - Delete: CIRCUITPY/routes/fetch.py"
echo "   - Delete: CIRCUITPY/routes/clear.py"
echo "   - Delete: CIRCUITPY/routes/crash.py"
echo "   - Delete: CIRCUITPY/routes/__init__.py"
echo ""
echo -e "${YELLOW}   Note: CircuitPython prefers .py over .mpy if both exist!${NC}"
echo ""
echo "4. Test the deployment:"
echo "   - Connect to serial console"
echo "   - import gc; gc.collect(); print(gc.mem_free())"
echo "   - Expect 9-14 KB more free memory than before"
echo ""
