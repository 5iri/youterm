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

* Python ≥ 3.7
* `ffplay` available in `$PATH` (install the `ffmpeg` package on your distro)

The package automatically installs Python deps:
* `yt-dlp` (YouTube downloading)
* `readchar` (keyboard input)
* `textual` (enhanced TUI support)

## Installation

### From PyPI (recommended once released)

```bash
pip install stream-cli            # system or --user
```

### From source (development)

```bash
git clone https://github.com/youruser/stream-cli.git
cd stream-cli
pip install -e .  # editable install for hacking
```

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

## Installation

```bash
# Install from source
git clone https://github.com/youruser/youterm.git
cd youterm
pip install -e .
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

## Packaging & Distribution

The project is PEP 517 compliant via `pyproject.toml`.

Build wheels / sdist locally:

```bash
python -m pip install --upgrade build
python -m build
ls dist/
# stream_cli-0.1.0-py3-none-any.whl
# stream-cli-0.1.0.tar.gz
```

Upload to PyPI (requires `twine`):

```bash
python -m pip install twine
python -m twine upload dist/*
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
