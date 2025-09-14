#!/bin/bash

# youterm Installer - No pip required
# Terminal YouTube streaming with Spotify-like discovery

set -e

YOUTERM_VERSION="0.2.0"
REPO="5iri/youterm"
TAG="v0.2.0"
INSTALL_DIR="$HOME/.local/bin"
LIB_DIR="$HOME/.local/lib/youterm"
CONFIG_DIR="$HOME/.config/youterm"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    print_status "Checking requirements..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi

    # Check Python version
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    min_version="3.8"
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
        print_error "Python 3.8+ is required, found Python $python_version"
        exit 1
    fi

    # Check ffplay
    if ! command -v ffplay &> /dev/null; then
        print_warning "ffplay not found. Please install ffmpeg:"
        echo "  macOS: brew install ffmpeg"
        echo "  Ubuntu/Debian: sudo apt install ffmpeg"
        echo "  CentOS/RHEL: sudo yum install ffmpeg"
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    print_success "Requirements check passed"
}

install_dependencies() {
    print_status "Installing dependencies..."

    # Download yt-dlp executable directly
    mkdir -p "$LIB_DIR/bin"
    curl -L "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp" -o "$LIB_DIR/bin/yt-dlp"
    chmod +x "$LIB_DIR/bin/yt-dlp"

    print_success "Dependencies installed"
}

create_directories() {
    print_status "Creating directories..."

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$LIB_DIR"
    mkdir -p "$CONFIG_DIR"

    print_success "Directories created"
}

install_source() {
    print_status "Installing youterm source code..."

    # If stream_cli exists locally, use it
    if [[ -d "stream_cli" ]]; then
        print_status "Using local source code..."
        cp -r stream_cli "$LIB_DIR/"
    else
        print_status "Downloading source code from GitHub..."

        # Create temp directory
        mkdir -p "$TEMP_DIR"

        # Download and extract source
        if command -v curl &> /dev/null; then
            curl -L "https://github.com/${REPO}/archive/${TAG}.tar.gz" | tar xz -C "$TEMP_DIR" --strip-components=1
        elif command -v wget &> /dev/null; then
            wget -O- "https://github.com/${REPO}/archive/${TAG}.tar.gz" | tar xz -C "$TEMP_DIR" --strip-components=1
        else
            print_error "curl or wget required to download source code"
            exit 1
        fi

        if [[ ! -d "$TEMP_DIR/stream_cli" ]]; then
            print_error "Failed to download source code"
            exit 1
        fi

        # Copy source to install location
        cp -r "$TEMP_DIR/stream_cli" "$LIB_DIR/"
    fi

    print_success "Source code installed"
}

install_youterm() {
    print_status "Creating executables..."

    # Create main executable
    cat > "$INSTALL_DIR/youterm" << 'EOF'
#!/bin/bash
LIB_DIR="$HOME/.local/lib/youterm"
export PATH="$LIB_DIR/bin:$PATH"
export PYTHONPATH="$LIB_DIR:$PYTHONPATH"
cd "$LIB_DIR"
exec python3 -m stream_cli.cli "$@"
EOF

    # Create discovery tool
    cat > "$INSTALL_DIR/youterm-discover" << 'EOF'
#!/bin/bash
LIB_DIR="$HOME/.local/lib/youterm"
export PATH="$LIB_DIR/bin:$PATH"
export PYTHONPATH="$LIB_DIR:$PYTHONPATH"
cd "$LIB_DIR"
exec python3 -m stream_cli.discovery "$@"
EOF

    # Create queue management tool
    cat > "$INSTALL_DIR/youterm-queue" << 'EOF'
#!/bin/bash
LIB_DIR="$HOME/.local/lib/youterm"
export PATH="$LIB_DIR/bin:$PATH"
export PYTHONPATH="$LIB_DIR:$PYTHONPATH"
cd "$LIB_DIR"
exec python3 -m stream_cli.smart_queue "$@"
EOF

    # Make executables
    chmod +x "$INSTALL_DIR/youterm"
    chmod +x "$INSTALL_DIR/youterm-discover"
    chmod +x "$INSTALL_DIR/youterm-queue"

    print_success "youterm installed"
}

update_path() {
    print_status "Updating PATH..."

    # Check if ~/.local/bin is in PATH
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        # Add to shell profile
        for shell_profile in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
            if [[ -f "$shell_profile" ]]; then
                if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$shell_profile"; then
                    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$shell_profile"
                    print_success "Added to PATH in $shell_profile"
                fi
            fi
        done

        print_warning "Please run: export PATH=\"\$HOME/.local/bin:\$PATH\""
        print_warning "Or restart your terminal to use youterm commands"
    else
        print_success "PATH already configured"
    fi
}

create_uninstaller() {
    print_status "Creating uninstaller..."

    cat > "$INSTALL_DIR/youterm-uninstall" << EOF
#!/bin/bash
echo "Uninstalling youterm..."
rm -rf "$LIB_DIR"
rm -f "$INSTALL_DIR/youterm"
rm -f "$INSTALL_DIR/youterm-discover"
rm -f "$INSTALL_DIR/youterm-queue"
rm -f "$INSTALL_DIR/youterm-uninstall"
echo "youterm uninstalled successfully"
echo "Configuration files remain in: $CONFIG_DIR"
echo "To remove config: rm -rf $CONFIG_DIR"
EOF

    chmod +x "$INSTALL_DIR/youterm-uninstall"

    print_success "Uninstaller created"
}

show_usage() {
    print_success "Installation complete!"
    echo ""
    echo "Usage:"
    echo "  youterm                    # Interactive mode"
    echo "  youterm 'search query'     # Direct search"
    echo "  youterm-discover 'query'   # Advanced discovery"
    echo "  youterm-queue status       # Queue management"
    echo ""
    echo "Examples:"
    echo "  youterm 'indie rock'"
    echo "  youterm 'joe rogan'"
    echo "  youterm 'vishnu sahasranamam'"
    echo ""
    echo "During playback:"
    echo "  p - pause    r - resume    n - next track"
    echo "  s - switch music (new search)"
    echo "  a - more by artist    q - quit"
    echo ""
    echo "Configuration: $CONFIG_DIR"
    echo "Uninstall: youterm-uninstall"
}

main() {
    echo "youterm v$YOUTERM_VERSION Installer"
    echo "Terminal YouTube streaming with Spotify-like discovery"
    echo "=============================================="
    echo ""



    check_requirements
    create_directories
    install_dependencies
    install_source
    install_youterm
    update_path
    create_uninstaller
    show_usage

    echo ""
    print_success "youterm is ready to use!"

    # Test if PATH is working
    if command -v youterm &> /dev/null; then
        print_success "Try: youterm 'your favorite music'"
    else
        print_warning "Run: export PATH=\"\$HOME/.local/bin:\$PATH\""
        print_warning "Then try: youterm 'your favorite music'"
    fi
}

main "$@"
