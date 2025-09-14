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

# Install Python dependencies
print_info "Installing Python dependencies..."
python3 -m pip install --user readchar yt-dlp

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
cd "$LIB_DIR"
exec python3 -m stream_cli.cli "$@"
EOF

chmod +x "$INSTALL_DIR/youterm"

# Update PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc 2>/dev/null || true
fi

# Cleanup
rm -rf "$TEMP_DIR"

print_info "youterm installed successfully!"
print_info "Run: export PATH=\"\$HOME/.local/bin:\$PATH\""
print_info "Then: youterm 'your favorite music'"
