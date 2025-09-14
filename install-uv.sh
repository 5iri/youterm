#!/bin/bash
set -e

# youterm UV-based Installer
REPO="5iri/youterm"
TAG="v0.3.0"
INSTALL_DIR="$HOME/.local/bin"
UV_ENV_DIR="$HOME/.local/lib/youterm-env"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

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
    print_warning "uv not found. Installing uv..."
    if command -v curl &> /dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        source $HOME/.cargo/env
    else
        print_error "curl is required to install uv. Please install curl or install uv manually: https://github.com/astral-sh/uv"
        exit 1
    fi
fi

print_info "Installing youterm with uv..."

# Create directories
mkdir -p "$INSTALL_DIR"

# Download and extract youterm
TEMP_DIR="/tmp/youterm-install-$$"
mkdir -p "$TEMP_DIR"

if command -v curl &> /dev/null; then
    curl -L "https://github.com/${REPO}/archive/${TAG}.tar.gz" | tar xz -C "$TEMP_DIR" --strip-components=1
else
    wget -O- "https://github.com/${REPO}/archive/${TAG}.tar.gz" | tar xz -C "$TEMP_DIR" --strip-components=1
fi

# Create isolated environment and install
print_info "Creating isolated Python environment..."
cd "$TEMP_DIR"
uv venv "$UV_ENV_DIR"
uv pip install --python "$UV_ENV_DIR" .

# Create wrapper script
print_info "Creating youterm executable..."
cat > "$INSTALL_DIR/youterm" << EOF
#!/bin/bash
export VIRTUAL_ENV="$UV_ENV_DIR"
export PATH="$UV_ENV_DIR/bin:\$PATH"
exec "$UV_ENV_DIR/bin/python" -m stream_cli.cli "\$@"
EOF

chmod +x "$INSTALL_DIR/youterm"

# Create additional command wrappers
cat > "$INSTALL_DIR/youterm-discover" << EOF
#!/bin/bash
export VIRTUAL_ENV="$UV_ENV_DIR"
export PATH="$UV_ENV_DIR/bin:\$PATH"
exec "$UV_ENV_DIR/bin/python" -m stream_cli.discovery "\$@"
EOF

chmod +x "$INSTALL_DIR/youterm-discover"

cat > "$INSTALL_DIR/youterm-queue" << EOF
#!/bin/bash
export VIRTUAL_ENV="$UV_ENV_DIR"
export PATH="$UV_ENV_DIR/bin:\$PATH"
exec "$UV_ENV_DIR/bin/python" -m stream_cli.smart_queue "\$@"
EOF

chmod +x "$INSTALL_DIR/youterm-queue"

# Create uninstaller
cat > "$INSTALL_DIR/youterm-uninstall" << EOF
#!/bin/bash
echo "Removing youterm..."
rm -rf "$UV_ENV_DIR"
rm -f "$INSTALL_DIR/youterm" "$INSTALL_DIR/youterm-discover" "$INSTALL_DIR/youterm-queue" "$INSTALL_DIR/youterm-uninstall"
echo "youterm uninstalled successfully!"
EOF

chmod +x "$INSTALL_DIR/youterm-uninstall"

# Update PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc 2>/dev/null || true
    print_info "Added $HOME/.local/bin to PATH in shell config files"
fi

# Cleanup
rm -rf "$TEMP_DIR"

print_info "youterm installed successfully with uv!"
print_info "All dependencies are isolated in: $UV_ENV_DIR"
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
