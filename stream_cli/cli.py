#!/usr/bin/env python
"""Command-line interface for youterm with Spotify-like features.

Usage:
  youterm           # launches interactive mode with automatic discovery
  youterm <query>   # plays search results with continuous auto-discovery

Enhanced Controls while playing:
  p – pause (SIGSTOP)
  r – resume (SIGCONT)
  n – next auto-discovered track
  s – search and switch to new music (resets context)
  a – switch to current artist (resets context)
  m – cycle through shuffle modes (smart/random/sequential/mood)
  q – quit program

Search Strategies:
  mixed   – intelligent combination of all strategies (default)
  direct  – standard search with quality filtering
  artist  – find songs by specific artists
  related – discover similar artists and genres
  genre   – search by mood or genre

Features:
  * Automatic background discovery - finds new music as you listen
  * Smart discovery engine with quality filtering
  * Intelligent queue management and recommendations
  * Listening history tracking and preference learning
  * Multiple shuffle algorithms for optimal flow
  * Automatic quality scoring and duplicate removal
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import random
import time
from typing import List, Optional

import readchar
import yt_dlp
from .discovery import music_discovery
from .smart_queue import smart_queue
from .auto_discovery import auto_discovery

RESULTS_DEFAULT = 20
RELATED_DEFAULT = 20


def check_prerequisites() -> None:
    """Ensure external dependencies (ffplay) are available."""
    if shutil.which("ffplay") is None:
        print("Error: ffplay executable not found in PATH. Please install ffmpeg/ffplay.", file=sys.stderr)
        sys.exit(1)


def search_youtube(query: str, limit: int = RESULTS_DEFAULT, strategy: str = "mixed", related_to: str = None) -> List[dict]:
    """Enhanced search using the music discovery engine.

    Args:
        query: Search query
        limit: Maximum number of results to return
        strategy: Search strategy ('direct', 'artist', 'related', 'genre', 'mixed')
        related_to: Video ID for related search
    """
    try:
        if related_to:
            return get_related_tracks(related_to, limit)

        # Use the enhanced discovery engine
        raw_tracks = music_discovery.search_with_strategy(query, strategy, limit)

        # Convert to expected format without immediate audio URL fetching
        tracks = []
        for track_dict in raw_tracks:
            converted = {
                "id": track_dict.get("id"),
                "title": track_dict.get("title", "Unknown Title"),
                "audio_url": "",  # Will be fetched when needed
                "duration": track_dict.get("duration", 0),
                "channel": track_dict.get("channel", ""),
                "quality_score": track_dict.get("quality_score", 0.5),
                "metadata": track_dict.get("metadata"),
                "_needs_audio_url": True
            }
            tracks.append(converted)

        return tracks

    except Exception as e:
        print(f"Enhanced search failed, falling back to basic search: {e}", file=sys.stderr)
        return _fallback_search(query, limit)


def _fallback_search(query: str, limit: int) -> List[dict]:
    """Fallback to basic search if enhanced search fails."""
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "ignoreerrors": True,
    }

    tracks = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            search_str = f"ytsearch{limit + 5}:{query}"
            result = ydl.extract_info(search_str, download=False)

            if not result or "entries" not in result:
                return []

            for entry in result["entries"]:
                if not entry or not isinstance(entry, dict):
                    continue

                tracks.append({
                    "id": entry.get("id"),
                    "title": entry.get("title", "Unknown Title"),
                    "audio_url": entry.get("url"),
                    "duration": entry.get("duration", 0)
                })

                if len(tracks) >= limit:
                    break

        except Exception as e:
            print(f"Fallback search failed: {e}", file=sys.stderr)

    return tracks


def _normalize_title(title: str) -> str:
    """Normalize track title for deduplication."""
    if not title:
        return ""

    # Remove version indicators and common suffixes
    version_patterns = [
        r'\(?:(?:official|lyrics?|hd|hq|4k|1080p|720p|full.*?version|with.*?lyrics?)\)',
        r'\[.*?\]',
        r'\b(?:by\s+[\w\s]+|ft\.?|feat\.?|prod\.?|cover|version|remix|original|audio|video)\b',
        r'[\[\](){}|\\`~!@#$%^&*_\-+=;:\'\",.<>/?]',
    ]

    title = title.lower()
    for pattern in version_patterns:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)

    # Remove common prefixes/suffixes and extra spaces
    title = re.sub(r'^\s*(?:\d+[.\-]?\s*)?', '', title)  # Track numbers
    title = re.sub(r'\s+', ' ', title).strip()

    # Remove common song indicators
    common_suffixes = [
        'official video', 'official audio', 'lyrics', 'lyric video',
        'hq audio', 'hd video', '4k video', 'full song', 'full hd',
        'original mix', 'official music video', 'official hd video'
    ]

    for suffix in common_suffixes:
        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()

    return title


def _extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL."""
    patterns = [r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', r'^([0-9A-Za-z_-]{11})$']
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_related_tracks(video_id: str, limit: int = RELATED_DEFAULT) -> List[dict]:
    """Fetch related tracks using YouTube's recommendations and smart discovery."""
    try:
        # Try YouTube's mix playlist first
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "ignoreerrors": True,
        }

        tracks = []

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Try mix playlist
            mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
            result = ydl.extract_info(mix_url, download=False)

            if result and "entries" in result:
                for entry in result["entries"][:limit]:
                    if entry and entry.get("id") != video_id:  # Skip the original
                        enhanced = music_discovery.enhance_track_info({
                            "id": entry.get("id"),
                            "title": entry.get("title", "Unknown Title"),
                            "duration": entry.get("duration", 0)
                        })

                        if enhanced.get("audio_url"):
                            tracks.append({
                                "id": enhanced.get("id"),
                                "title": enhanced.get("title"),
                                "audio_url": enhanced.get("audio_url"),
                                "duration": enhanced.get("duration", 0)
                            })

        # If we didn't get enough tracks, supplement with discovery engine
        if len(tracks) < limit // 2:
            # Get info about the original video to create better related searches
            video_info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            if video_info:
                title = video_info.get("title", "")
                metadata = music_discovery.extract_metadata(title, video_info.get("uploader", ""))

                if metadata.artist:
                    related_query = f"{metadata.artist}"
                else:
                    related_query = metadata.title

                additional = music_discovery.search_with_strategy(related_query, "related", limit - len(tracks))
                for track_dict in additional:
                    enhanced = music_discovery.enhance_track_info(track_dict)
                    if enhanced.get("audio_url") and enhanced.get("id") != video_id:
                        tracks.append({
                            "id": enhanced.get("id"),
                            "title": enhanced.get("title"),
                            "audio_url": enhanced.get("audio_url"),
                            "duration": enhanced.get("duration", 0)
                        })

        return tracks[:limit]

    except Exception as e:
        print(f"Error getting related tracks: {e}", file=sys.stderr)
        return []


def play_tracks(tracks: List[dict]) -> None:
    """Play tracks continuously with automatic discovery and smart queue management."""
    import select

    try:
        # Start automatic discovery service
        auto_discovery.start()

        # Clear existing queue and reset discovery context for fresh start
        print("Starting fresh with new tracks...")
        smart_queue.main_queue.clear()
        smart_queue.priority_queue.clear()
        smart_queue.clear_played_history()
        auto_discovery.reset_context()

        # Add new tracks to smart queue
        if tracks:
            smart_queue.add_tracks(tracks)
            # Seed the discovery system with initial tracks
            for track in tracks[:3]:  # Use first 3 tracks as seeds
                auto_discovery.add_seed_track(track)

        played_ids = set()

        while True:  # Outer loop to restart if queue runs out
            # Get next track from smart queue (auto-discovery keeps it filled)
            track = smart_queue.get_next_track()
            if not track:
                print("No more tracks available. Discovery system may be starting up...")
                time.sleep(2)  # Give discovery a moment
                track = smart_queue.get_next_track()

                if not track:
                    print("Unable to discover new tracks. Please try a new search.")
                    break

            # Check if track was already played in this session
            if track.get('id') in played_ids:
                continue

            title = track.get("title", "Unknown Title")
            audio_url = track.get("audio_url")

            # Fetch audio URL if not already available
            if not audio_url and track.get("_needs_audio_url"):
                print(f"Loading {title}...")
                enhanced = music_discovery.enhance_track_info(track)
                audio_url = enhanced.get("audio_url", "")
                track["audio_url"] = audio_url
                track["_needs_audio_url"] = False

            if not audio_url or not audio_url.startswith('http'):
                print(f"Skipping invalid track: {title}")
                continue

            # Show additional info if available
            channel = track.get("channel", "")
            quality_score = track.get("quality_score", 0)
            queue_info = smart_queue.get_queue_info()
            display_title = f"{title}"
            if channel:
                display_title += f" [{channel}]"
            if quality_score > 0:
                stars = "*" * int(quality_score * 5)
                display_title += f" {stars}"

            print(f"\nNow playing (Queue: {queue_info['total_tracks']} tracks): {display_title}")

            # Add to played IDs and feed discovery system
            if 'id' in track:
                played_ids.add(track['id'])

                # Feed the auto-discovery system
                auto_discovery.add_seed_track(track)

                # Record play in history
                smart_queue.history.record_play(track)

            # Start playbook time tracking
            start_time = time.time()

            # Start playback with ffplay
            try:
                proc = subprocess.Popen(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", audio_url],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                print(f"Error starting playback: {e}")
                continue

            # Handle user input during playback
            while proc.poll() is None:
                try:
                    print("\r[p]ause / [r]esume / [n]ext / [s]witch music / [a]rtist / [m]ode / [q]uit? ", end="", flush=True)
                    if sys.stdin in select.select([sys.stdin], [], [], 1)[0]:
                        key = sys.stdin.read(1).lower()
                        print()

                        if key == "p":
                            proc.send_signal(signal.SIGSTOP)
                            print("Paused")
                        elif key == "r":
                            proc.send_signal(signal.SIGCONT)
                            print("Resumed")
                        elif key == "n":
                            # Record skip and get next auto-discovered track
                            play_duration = int(time.time() - start_time)
                            smart_queue.history.record_skip(track, play_duration)
                            proc.terminate()
                            print("Next track (auto-discovered)...")
                            break
                        elif key == "s":
                            query = input("Switch to (search query): ").strip()
                            if query:
                                strategy = input("Strategy [mixed/direct/artist/related/genre]: ").strip() or "mixed"
                                print(f"Searching for '{query}'...")

                                # Clear everything and start fresh with new search
                                print("Switching to new search - clearing previous context...")
                                smart_queue.main_queue.clear()
                                smart_queue.priority_queue.clear()
                                smart_queue.clear_played_history()
                                auto_discovery.reset_context()

                                new_tracks = search_youtube(query, strategy=strategy, limit=12)
                                if new_tracks:
                                    smart_queue.add_tracks(new_tracks)
                                    # Seed discovery with new tracks immediately
                                    for new_track in new_tracks[:3]:
                                        auto_discovery.add_seed_track(new_track)
                                    print(f"Started fresh with {len(new_tracks)} tracks from '{query}'")
                                    # Skip current track to start playing new search immediately
                                    proc.terminate()
                                    print("Switching to new music...")
                                    break
                                else:
                                    print("No tracks found.")
                            else:
                                print("Empty query, ignored.")
                        elif key == "a":
                            # Search by artist of current track and reset context to focus on this artist
                            metadata = track.get("metadata")
                            if metadata and metadata.artist:
                                print(f"Switching to {metadata.artist} - clearing previous context...")

                                # Clear everything and focus on this artist
                                smart_queue.main_queue.clear()
                                smart_queue.priority_queue.clear()
                                smart_queue.clear_played_history()
                                auto_discovery.reset_context()

                                artist_tracks = search_youtube(metadata.artist, strategy="artist", limit=12)
                                if artist_tracks:
                                    smart_queue.add_tracks(artist_tracks)
                                    # Seed discovery with artist tracks immediately
                                    for artist_track in artist_tracks[:3]:
                                        auto_discovery.add_seed_track(artist_track)
                                    print(f"Started fresh with {len(artist_tracks)} tracks by {metadata.artist}")
                                    # Skip current track to start playing artist's music immediately
                                    proc.terminate()
                                    print("Switching to artist's music...")
                                    break
                                else:
                                    print("No tracks found for this artist.")
                            else:
                                print("No artist information available for current track.")
                        elif key == "m":
                            # Change shuffle mode and discovery rate
                            current_mode = smart_queue.shuffle_mode
                            modes = ["smart", "random", "sequential", "mood"]
                            try:
                                current_idx = modes.index(current_mode)
                                next_mode = modes[(current_idx + 1) % len(modes)]
                                smart_queue.set_shuffle_mode(next_mode)

                                # Adjust discovery rate based on mode
                                if next_mode == "smart":
                                    auto_discovery.adjust_discovery_rate("moderate")
                                elif next_mode == "random":
                                    auto_discovery.adjust_discovery_rate("aggressive")
                                else:
                                    auto_discovery.adjust_discovery_rate("conservative")

                                print(f"Shuffle mode: {current_mode} → {next_mode}")
                                print(f"Discovery rate adjusted for {next_mode} mode")
                            except ValueError:
                                smart_queue.set_shuffle_mode("smart")
                                auto_discovery.adjust_discovery_rate("moderate")
                                print("Shuffle mode: smart")
                        elif key == "q":
                            proc.terminate()
                            auto_discovery.stop()
                            print("\nQuitting...")
                            return
                except (IOError, OSError):
                    # Handle any I/O errors during input
                    continue

            # Record successful play
            play_duration = int(time.time() - start_time)
            smart_queue.history.record_play(track, play_duration)

    except KeyboardInterrupt:
        print("\nStopping playback...")
        auto_discovery.stop()
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        auto_discovery.stop()
        raise


def main():
    """Main entry point for the CLI."""
    check_prerequisites()

    if len(sys.argv) > 1:
        # Play search results from command line argument
        query = " ".join(sys.argv[1:])
        print(f"Searching for: {query}")
        tracks = search_youtube(query, limit=15)
        if tracks:
            print(f"Found {len(tracks)} tracks, starting playback...")
            play_tracks(tracks)
        else:
            print("No tracks found.")
    else:
        # Interactive mode
        while True:
            try:
                print("\nYOUTERM - Spotify-like Terminal Music")
                print("Tip: Try searches like 'indie rock', 'jazz piano', or your favorite artist")
                print("Auto-discovery will continuously find new music as you listen!")
                query = input("\nEnter search query (or 'q' to quit): ").strip()
                if not query or query.lower() == 'q':
                    break

                print(f"Searching for: {query}")

                # Reset discovery context for completely new search
                print("Starting fresh search - clearing previous context...")
                if auto_discovery.is_running:
                    auto_discovery.stop()
                smart_queue.main_queue.clear()
                smart_queue.priority_queue.clear()
                smart_queue.clear_played_history()
                auto_discovery.reset_context()

                tracks = search_youtube(query, limit=12)
                if not tracks:
                    print("No tracks found. Please try a different search.")
                    print("Try broader terms like 'rock music' or 'pop songs'")
                    continue

                print(f"Found {len(tracks)} tracks, starting playback...")
                print("Press 'n' for next - discovery finds new music automatically!")
                play_tracks(tracks)

            except KeyboardInterrupt:
                print("\nReturning to search...")
                continue


if __name__ == "__main__":
    main()
