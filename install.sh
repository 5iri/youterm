#!/bin/bash
set -e

# youterm Simple Installer
REPO="5iri/youterm"
TAG="v0.3.0"
INSTALL_DIR="$HOME/.local/bin"
LIB_DIR="$HOME/.local/lib/youterm"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check requirements
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required"
    exit 1
fi

if ! command -v ffplay &> /dev/null; then
    print_error "ffplay is required. Install with: brew install ffmpeg (macOS) or sudo apt install ffmpeg (Ubuntu)"
    exit 1
fi

# Check if uv is available, install if not
if ! command -v uv &> /dev/null; then
    print_info "uv not found. Installing uv..."
    if command -v curl &> /dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        source $HOME/.cargo/env 2>/dev/null || true
    else
        print_error "curl is required to install uv. Please install curl or install uv manually: https://github.com/astral-sh/uv"
        exit 1
    fi
fi

print_info "Installing youterm..."

# Create directories
mkdir -p "$INSTALL_DIR" "$LIB_DIR"

# Download and extract youterm
TEMP_DIR="/tmp/youterm-install-$$"
mkdir -p "$TEMP_DIR"

if command -v curl &> /dev/null; then
    curl -L "https://github.com/${REPO}/archive/${TAG}.tar.gz" | tar xz -C "$TEMP_DIR" --strip-components=1
else
    wget -O- "https://github.com/${REPO}/archive/${TAG}.tar.gz" | tar xz -C "$TEMP_DIR" --strip-components=1
fi

# Copy source
cp -r "$TEMP_DIR/stream_cli" "$LIB_DIR/"

# Create temporary virtual environment and install dependencies
print_info "Installing Python dependencies with uv..."
TEMP_VENV="$LIB_DIR/.venv"
uv venv "$TEMP_VENV"
uv pip install --python "$TEMP_VENV" readchar yt-dlp

# Download yt-dlp as backup
mkdir -p "$LIB_DIR/bin"
curl -L "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp" -o "$LIB_DIR/bin/yt-dlp"
chmod +x "$LIB_DIR/bin/yt-dlp"

# Create executables
cat > "$INSTALL_DIR/youterm" << 'EOF'
#!/bin/bash
LIB_DIR="$HOME/.local/lib/youterm"
export PATH="$LIB_DIR/bin:$PATH"
export PYTHONPATH="$LIB_DIR:$PYTHONPATH"
export VIRTUAL_ENV="$LIB_DIR/.venv"
export PATH="$LIB_DIR/.venv/bin:$PATH"
cd "$LIB_DIR"
exec "$LIB_DIR/.venv/bin/python" -m stream_cli.cli "$@"
EOF

chmod +x "$INSTALL_DIR/youterm"

# Create additional command wrappers
cat > "$INSTALL_DIR/youterm-discover" << 'EOF'
#!/bin/bash
LIB_DIR="$HOME/.local/lib/youterm"
export PATH="$LIB_DIR/bin:$PATH"
export PYTHONPATH="$LIB_DIR:$PYTHONPATH"
export VIRTUAL_ENV="$LIB_DIR/.venv"
export PATH="$LIB_DIR/.venv/bin:$PATH"
cd "$LIB_DIR"
exec "$LIB_DIR/.venv/bin/python" -m stream_cli.discovery "$@"
EOF

chmod +x "$INSTALL_DIR/youterm-discover"

cat > "$INSTALL_DIR/youterm-queue" << 'EOF'
#!/bin/bash
LIB_DIR="$HOME/.local/lib/youterm"
export PATH="$LIB_DIR/bin:$PATH"
export PYTHONPATH="$LIB_DIR:$PYTHONPATH"
export VIRTUAL_ENV="$LIB_DIR/.venv"
export PATH="$LIB_DIR/.venv/bin:$PATH"
cd "$LIB_DIR"
exec "$LIB_DIR/.venv/bin/python" -m stream_cli.smart_queue "$@"
EOF

chmod +x "$INSTALL_DIR/youterm-queue"

# Create uninstaller
cat > "$INSTALL_DIR/youterm-uninstall" << 'EOF'
#!/bin/bash
echo "Removing youterm..."
rm -rf "$HOME/.local/lib/youterm"
rm -f "$HOME/.local/bin/youterm" "$HOME/.local/bin/youterm-discover" "$HOME/.local/bin/youterm-queue" "$HOME/.local/bin/youterm-uninstall"
echo "youterm uninstalled successfully!"
EOF

chmod +x "$INSTALL_DIR/youterm-uninstall"

# Update PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc 2>/dev/null || true
fi

# Cleanup
rm -rf "$TEMP_DIR"

print_info "youterm installed successfully!"
print_info ""
print_info "To start using youterm:"
print_info "1. Restart your terminal OR run: export PATH=\"\$HOME/.local/bin:\$PATH\""
print_info "2. Run: youterm 'your favorite music'"
print_info ""
print_info "Available commands:"
print_info "  youterm           - Main streaming interface"
print_info "  youterm-discover  - Advanced search and discovery"
print_info "  youterm-queue     - Queue management"
print_info "  youterm-uninstall - Remove youterm"
