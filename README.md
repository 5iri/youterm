# youterm

Terminal audio streaming with Spotify-like discovery. Search YouTube from your terminal and stream best-quality audio through ffplay with intelligent recommendations and smart queue management.

## Features

### Core Playback
* Search YouTube (`yt-dlp`) and fetch best-audio URLs
* Plays audio via `ffplay` (part of FFmpeg) with no GUI
* Interactive controls during playback:
  * `p` – pause
  * `r` – resume
  * `n` – next track
  * `s` – search and add new tracks
  * `a` – find more songs by current artist
  * `q` – quit program

### Spotify-like Discovery Engine
* **Smart Search Strategies**: Multiple search approaches for better variety
  * `direct` – Standard YouTube search with quality filtering
  * `artist` – Find songs by specific artists
  * `related` – Discover similar artists and genres
  * `genre` – Search by mood or genre
  * `mixed` – Intelligent combination of all strategies
* **Advanced Metadata Extraction**: Automatically identifies artists, titles, and song info
* **Quality Scoring**: Filters out low-quality content, covers, and duplicates
* **Smart Deduplication**: Avoids the same song from different channels

### Intelligent Queue Management
* **Smart Shuffling**: Maintains musical flow while avoiding repetition
* **Auto-Recommendations**: Continuously fills queue based on listening history
* **Artist Variety**: Prevents clustering of songs from the same artist
* **Listening History**: Tracks preferences and improves recommendations over time
* **Priority Queue**: Add urgent tracks that play next

### Enhanced Controls
* **Multiple Search Modes**: Choose your discovery strategy on the fly
* **Real-time Queue Management**: Add, remove, and reorganize tracks while playing
* **Session Persistence**: Remembers your preferences across sessions
* **Quality Indicators**: See track quality scores and channel info

## Requirements

* Python ≥ 3.8
* `ffplay` available in `$PATH` (install the `ffmpeg` package)
* `yt-dlp` available in `$PATH` (install the `yt-dlp` package)
* Internet connection

**Install ffmpeg:**
* **macOS**: `brew install ffmpeg`
* **Ubuntu/Debian**: `sudo apt install ffmpeg`
* **CentOS/RHEL**: `sudo yum install ffmpeg`
* **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/)

The installer automatically handles Python dependencies:
* `yt-dlp` (YouTube downloading)
* `readchar` (keyboard input)

## Installation

### Install (One Command)

```bash
# Download installer and run locally
curl -O https://raw.githubusercontent.com/5iri/youterm/main/install.sh
chmod +x install.sh
./install.sh
```

The installer automatically handles dependency management using `uv` and creates an isolated environment. It will install `uv` if it's not already available on your system.

## Usage

### Basic Usage

```bash
# Interactive mode with smart discovery
youterm

# One-shot search & play with auto-recommendations
youterm "lofi hip hop"
```

### Enhanced Controls

When tracks are playing you will see:

```
[p]ause / [r]esume / [n]ext / [s]witch music / [a]rtist / [m]ode / [q]uit?
```

* `p` – pause current track
* `r` – resume playback
* `n` – skip to next track
* `s` – search and switch to new music (resets context)
* `a` – switch to current artist (resets context)
* `q` – quit program

### Advanced Discovery Tools

```bash
# Test different search strategies
youterm-discover "indie rock" --strategy artist --limit 15

# Manage your queue
youterm-queue add "jazz piano" --strategy genre --limit 20
youterm-queue status
youterm-queue shuffle smart
youterm-queue recommendations

# View listening history and preferences
youterm-queue history --artists
```

### Search Strategy Examples

```bash
# Find specific songs (default)
youterm "Bohemian Rhapsody"

# Discover an artist's catalog
youterm-discover "Radiohead" --strategy artist

# Explore a genre or mood
youterm-discover "chill electronic" --strategy genre

# Find music similar to a query
youterm-discover "Pink Floyd" --strategy related

# Mixed approach for maximum variety
youterm-discover "90s alternative" --strategy mixed
```

## Configuration

Youterm automatically creates configuration files in `~/.config/youterm/`:

* `listening_history.json` – Your play history and preferences
* `preferences.json` – Customizable settings

### Preference Options

```json
{
  "preferred_duration_range": [120, 360],
  "skip_threshold": 0.3,
  "shuffle_strategy": "smart",
  "preferred_quality": 0.6
}
```

## Command Reference

### Main Commands

* `youterm [query]` – Main streaming interface
* `youterm-discover <query>` – Advanced search and discovery tool
* `youterm-queue <command>` – Queue management utility

### Discovery Options

* `--strategy {mixed,direct,artist,related,genre}` – Search approach
* `--limit <number>` – Maximum results
* `--quality-filter` – Show quality scores
* `--test-metadata` – Test metadata extraction

### Queue Commands

* `status` – Show current queue state
* `add <query>` – Add tracks to queue
* `shuffle <mode>` – Set shuffle behavior
* `clear` – Clear queue or played history
* `recommendations` – Get queue suggestions
* `history` – View listening patterns

## Alternative Installation Methods

### From Source (Development)
```bash
git clone https://github.com/5iri/youterm.git
cd youterm
# Use uv for development (recommended)
uv sync
uv run youterm

# Or use the installer
./install.sh
```

### From PyPI (when available)
```bash
pip install youterm
```

## Troubleshooting

### Installation Issues

**Permission denied error:**
```bash
chmod +x install.sh
./install.sh
```

**ffplay not found:**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Check installation
ffplay -version
```

**Python version issues:**
```bash
# Check Python version
python3 --version

# If too old, install newer Python
# Ubuntu: sudo apt install python3.8
# macOS: brew install python@3.8
```

**PATH not working after install:**
```bash
# Add to your shell profile
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Or use full path
$HOME/.local/bin/youterm "test"
```

### Runtime Issues

**No audio playback:**
- Check audio output device is working
- Try: `ffplay -f lavfi -i testsrc2=duration=5:size=320x240:rate=30`

**Search returns no results:**
- Check internet connection
- Try different search terms
- Use quotes for exact phrases

## Uninstallation

### Remove youterm
```bash
# If installed with install.sh
youterm-uninstall

# Manual removal
rm -rf ~/.local/lib/youterm
rm -f ~/.local/bin/youterm*
```

### Remove configuration (optional)
```bash
rm -rf ~/.config/youterm
```

## How It Works

### Smart Discovery Pipeline

1. **Query Analysis**: Understands search intent and extracts context
2. **Multi-Strategy Search**: Uses different approaches based on query type
3. **Metadata Extraction**: Identifies artists, titles, and song characteristics
4. **Quality Scoring**: Evaluates tracks based on duration, source, and content
5. **Deduplication**: Removes same songs from different channels
6. **Intelligent Shuffling**: Organizes queue for optimal listening flow

### Recommendation Engine

* **Listening History**: Tracks what you play, skip, and enjoy
* **Artist Preferences**: Learns your favorite artists over time
* **Smart Variety**: Balances familiarity with discovery
* **Contextual Suggestions**: Considers current queue and recent plays

## Development

For developers who want to build packages:

```bash
git clone https://github.com/5iri/youterm.git
cd youterm
python -m pip install --upgrade build
python -m build
ls dist/
# youterm-0.2.0-py3-none-any.whl
# youterm-0.2.0.tar.gz
```

## Roadmap

* **Audio Analysis**: Extract tempo, key, and mood from tracks
* **Playlist Import**: Support for Spotify/YouTube playlist imports
* **Social Features**: Share queues and discover friends' music
* **Advanced Filters**: Genre, decade, language, and mood filters
* **Desktop Integration**: System notifications and media key support
* **Streaming Services**: Expand beyond YouTube to other platforms
* **Mobile Companion**: Web interface for remote control

---
MIT License © 2025 Your Name
