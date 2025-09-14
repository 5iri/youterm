"""Automatic background music discovery system for youterm.

This module provides seamless, automatic music discovery that runs in the background
to continuously fill the queue with new, varied content based on what's currently playing.
When user presses 'next', they get freshly discovered music without any manual intervention.
"""

import threading
import time
import random
from collections import deque, defaultdict
from typing import List, Dict, Optional, Set
import queue as queue_module

from .discovery import music_discovery
from .smart_queue import smart_queue


class BackgroundDiscovery:
    """Automatic background music discovery engine."""

    def __init__(self, target_queue_size: int = 30, discovery_batch_size: int = 5):
        self.target_queue_size = target_queue_size
        self.discovery_batch_size = discovery_batch_size

        # Background processing
        self.discovery_queue = queue_module.Queue(maxsize=3)  # Limit queue size
        self.is_running = False
        self.discovery_thread = None

        # Discovery state
        self.seed_tracks: deque = deque(maxlen=5)  # Fewer tracks for faster processing
        self.discovered_artists: Set[str] = set()
        self.discovery_strategies = ["artist", "related"]  # Remove slower genre strategy
        self.strategy_weights = {"artist": 0.6, "related": 0.4}

        # Rate limiting - more aggressive
        self.last_discovery_time = 0
        self.min_discovery_interval = 10  # Longer interval

        # Discovery context
        self.current_mood = "mixed"
        self.genre_hints = []
        self.artist_exploration_depth = {}  # track how deep we've explored each artist

    def start(self):
        """Start the background discovery service."""
        if self.is_running:
            return

        self.is_running = True
        self.discovery_thread = threading.Thread(target=self._discovery_worker, daemon=True)
        self.discovery_thread.start()
        print("Background discovery service started")

    def stop(self):
        """Stop the background discovery service."""
        self.is_running = False
        if self.discovery_thread:
            self.discovery_thread.join(timeout=2)
        print("Background discovery service stopped")

    def add_seed_track(self, track: Dict):
        """Add a track that was just played to inform future discovery."""
        self.seed_tracks.append(track)

        # Extract context from the track
        metadata = track.get("metadata")
        if metadata and metadata.artist:
            artist = metadata.artist
            if artist:  # Only add non-empty artists
                self.discovered_artists.add(artist)

                # Track exploration depth
                if artist not in self.artist_exploration_depth:
                    self.artist_exploration_depth[artist] = 0

            # Only trigger discovery if queue is very low
            queue_info = smart_queue.get_queue_info()
            if queue_info['total_tracks'] < 5:  # Much lower threshold
                self._trigger_discovery("low_queue")

    def reset_context(self):
        """Reset discovery context for fresh start with new search."""
        self.seed_tracks.clear()
        self.discovered_artists.clear()
        self.artist_exploration_depth.clear()
        self.genre_hints.clear()

        # Clear any pending discovery requests
        while not self.discovery_queue.empty():
            try:
                self.discovery_queue.get_nowait()
            except queue_module.Empty:
                break

        print("Discovery context reset for new search")

    def _trigger_discovery(self, reason: str = "manual"):
        """Trigger background discovery."""
        # Rate limiting
        current_time = time.time()
        if current_time - self.last_discovery_time < self.min_discovery_interval:
            return

        self.last_discovery_time = current_time

        try:
            self.discovery_queue.put(reason, timeout=0.1)  # Don't wait long
        except queue_module.Full:
            pass  # Discovery already queued

    def _discovery_worker(self):
        """Background worker thread for music discovery."""
        while self.is_running:
            try:
                # Wait for discovery trigger
                reason = self.discovery_queue.get(timeout=1)

                if not self.is_running:
                    break

                # Perform discovery
                self._perform_discovery(reason)

            except queue_module.Empty:
                # Less frequent checks for better performance
                time.sleep(5)
                continue
            except Exception as e:
                print(f"Discovery worker error: {e}")
                time.sleep(5)  # Brief pause on error

    def _perform_discovery(self, reason: str):
        """Perform actual music discovery."""
        if not self.seed_tracks:
            # No context yet, do a general discovery
            self._discover_without_context()
            return

        # Choose discovery strategy based on current context
        strategy = self._choose_discovery_strategy()

        # Generate discovery queries
        queries = self._generate_discovery_queries(strategy)

        # Discover new tracks - limit to first query for speed
        new_tracks = []
        if queries:
            batch = self._discover_batch(queries[0], strategy)  # Only use first query
            new_tracks.extend(batch[:self.discovery_batch_size])  # Limit results

        # Filter and add to queue
        if new_tracks:
            filtered_tracks = self._filter_discovered_tracks(new_tracks)
            if filtered_tracks:
                smart_queue.add_tracks(filtered_tracks)
                print(f"Auto-discovered {len(filtered_tracks)} new tracks using {strategy} strategy")

    def _choose_discovery_strategy(self) -> str:
        """Choose the best discovery strategy based on current context."""
        if not self.seed_tracks:
            return "mixed"

        recent_track = self.seed_tracks[-1]
        metadata = recent_track.get("metadata")

        # Artist-based discovery if we haven't explored this artist much
        if metadata and metadata.artist:
            artist = metadata.artist
            exploration_depth = self.artist_exploration_depth.get(artist, 0)

            if exploration_depth < 3:  # Haven't explored this artist much
                return "artist"

        # Related discovery for variety
        if len(self.discovered_artists) < 10:
            return "related"

        # Genre-based for broader exploration
        return "genre"

    def _generate_discovery_queries(self, strategy: str) -> List[str]:
        """Generate search queries based on strategy and context."""
        queries = []

        if not self.seed_tracks:
            return ["popular music", "indie songs", "alternative rock"]

        recent_tracks = list(self.seed_tracks)[-3:]  # Last 3 tracks

        if strategy == "artist":
            # Find more songs by recent artists
            for track in recent_tracks:
                metadata = track.get("metadata")
                if metadata and metadata.artist:
                    artist = metadata.artist

                    # Increment exploration depth
                    self.artist_exploration_depth[artist] = self.artist_exploration_depth.get(artist, 0) + 1

                    queries.append(artist)  # Just the artist name for speed

        elif strategy == "related":
            # Find similar artists and songs
            for track in recent_tracks:
                metadata = track.get("metadata")
                if metadata:
                    if metadata.artist:
                        queries.append(f"artists like {metadata.artist}")  # Single query

                    # Use song titles for similarity
                    # Skip title-based queries for speed
                    pass

        elif strategy == "genre":
            # Infer genre from recent tracks and explore
            inferred_genres = self._infer_genres_from_tracks(recent_tracks)
            for genre in inferred_genres:
                queries.extend([
                    f"{genre} music",
                    f"best {genre} songs",
                    f"{genre} playlist"
                ])

        # Add some randomness
        random.shuffle(queries)
        return queries[:5]  # Limit queries

    def _infer_genres_from_tracks(self, tracks: List[Dict]) -> List[str]:
        """Infer possible genres from track metadata."""
        genres = []

        for track in tracks:
            metadata = track.get("metadata")
            if not metadata:
                continue

            title = metadata.normalized_title.lower()

            # Simple genre inference based on title keywords
            if any(word in title for word in ["rock", "metal", "punk"]):
                genres.append("rock")
            elif any(word in title for word in ["jazz", "blues", "swing"]):
                genres.append("jazz")
            elif any(word in title for word in ["electronic", "edm", "techno", "house"]):
                genres.append("electronic")
            elif any(word in title for word in ["folk", "acoustic", "country"]):
                genres.append("folk")
            elif any(word in title for word in ["classical", "orchestra", "symphony"]):
                genres.append("classical")
            elif any(word in title for word in ["hip hop", "rap", "beats"]):
                genres.append("hip hop")
            elif any(word in title for word in ["indie", "alternative"]):
                genres.append("indie")
            else:
                genres.append("alternative")  # Default fallback

        # Remove duplicates and return most common
        genre_counts = defaultdict(int)
        for genre in genres:
            genre_counts[genre] += 1

        return sorted(genre_counts.keys(), key=lambda x: genre_counts[x], reverse=True)[:3]

    def _discover_batch(self, query: str, strategy: str) -> List[Dict]:
        """Discover a batch of tracks for a given query."""
        try:
            tracks = music_discovery.search_with_strategy(
                query,
                strategy,
                limit=3  # Very small batch size for speed
            )
            return tracks
        except Exception as e:
            # Silent errors for speed
            return []

    def _filter_discovered_tracks(self, tracks: List[Dict]) -> List[Dict]:
        """Filter discovered tracks to avoid duplicates and ensure quality."""
        # Get existing track IDs
        existing_ids = set()

        # Check queue
        for track in smart_queue.main_queue + list(smart_queue.priority_queue):
            if track.get("id"):
                existing_ids.add(track["id"])

        # Check recent seeds
        for track in self.seed_tracks:
            if track.get("id"):
                existing_ids.add(track["id"])

        # Filter tracks
        filtered = []
        for track in tracks:
            track_id = track.get("id")
            quality_score = track.get("quality_score", 0)

            # Skip if duplicate or low quality
            if track_id in existing_ids or quality_score < 0.4:
                continue

            # Enhance with audio URL
            enhanced = music_discovery.enhance_track_info(track)
            if enhanced.get("audio_url"):
                filtered.append({
                    "id": enhanced.get("id"),
                    "title": enhanced.get("title"),
                    "audio_url": enhanced.get("audio_url"),
                    "duration": enhanced.get("duration", 0),
                    "channel": enhanced.get("channel", ""),
                    "quality_score": enhanced.get("quality_score", 0.5),
                    "metadata": enhanced.get("metadata"),
                    "auto_discovered": True  # Mark as auto-discovered
                })
                existing_ids.add(track_id)

        return filtered

    def _discover_without_context(self):
        """Discover music when we have no context (initial state)."""
        general_queries = [
            "popular songs 2024",
            "indie rock",
            "alternative music",
            "chill music",
            "acoustic songs"
        ]

        new_tracks = []
        for query in general_queries:
            batch = music_discovery.search_with_strategy(query, "mixed", limit=3)
            new_tracks.extend(batch)

        if new_tracks:
            filtered = self._filter_discovered_tracks(new_tracks)
            if filtered:
                smart_queue.add_tracks(filtered)
                print(f"Auto-discovered {len(filtered)} initial tracks")

    def _check_queue_health(self):
        """Periodically check if queue needs more content."""
        queue_info = smart_queue.get_queue_info()

        # Only trigger if queue is very low
        if queue_info['total_tracks'] < 3:
            self._trigger_discovery("periodic_check")

        # Less frequent cleanup
        if len(self.artist_exploration_depth) > 50:
            # Keep fewer artists for speed
            sorted_artists = sorted(
                self.artist_exploration_depth.items(),
                key=lambda x: x[1],
                reverse=True
            )
            self.artist_exploration_depth = dict(sorted_artists[:20])

    def get_discovery_stats(self) -> Dict:
        """Get statistics about the discovery system."""
        return {
            "is_running": self.is_running,
            "seed_tracks_count": len(self.seed_tracks),
            "discovered_artists_count": len(self.discovered_artists),
            "artists_explored": len(self.artist_exploration_depth),
            "queue_size": smart_queue.get_queue_info()['total_tracks'],
            "target_queue_size": self.target_queue_size
        }

    def adjust_discovery_rate(self, rate: str):
        """Adjust how aggressively discovery happens."""
        if rate == "conservative":
            self.target_queue_size = 15
            self.discovery_batch_size = 3
            self.min_discovery_interval = 15
        elif rate == "moderate":
            self.target_queue_size = 30
            self.discovery_batch_size = 5
            self.min_discovery_interval = 10
        elif rate == "aggressive":
            self.target_queue_size = 50
            self.discovery_batch_size = 8
            self.min_discovery_interval = 5

        print(f"Discovery rate set to {rate}")


# Global instance for easy importing
auto_discovery = BackgroundDiscovery()
