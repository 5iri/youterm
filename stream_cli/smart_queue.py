"""Smart queue management for youterm.

This module provides intelligent queue management including:
- Smart shuffling that maintains flow
- Queue optimization based on user preferences
- Listening history tracking
- Mood-based queue organization
"""

import json
import os
import random
import time
from collections import defaultdict, deque
from typing import List, Dict, Optional, Set
from pathlib import Path


class ListeningHistory:
    """Tracks user listening patterns and preferences."""

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.path.expanduser("~/.config/youterm")

        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.history_file = self.config_dir / "listening_history.json"
        self.preferences_file = self.config_dir / "preferences.json"

        self.history = self._load_history()
        self.preferences = self._load_preferences()

    def _load_history(self) -> Dict:
        """Load listening history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        return {
            "tracks": {},  # track_id -> play_count, last_played, skip_count
            "artists": {},  # artist -> play_count, preference_score
            "genres": {},  # genre -> play_count, preference_score
            "sessions": []  # list of session data
        }

    def _load_preferences(self) -> Dict:
        """Load user preferences from file."""
        if self.preferences_file.exists():
            try:
                with open(self.preferences_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        return {
            "preferred_duration_range": [120, 360],  # 2-6 minutes
            "skip_threshold": 0.3,  # Skip if less than 30% played
            "mood_preferences": {},
            "artist_blacklist": [],
            "preferred_quality": 0.6,
            "shuffle_strategy": "smart"  # smart, random, mood-based
        }

    def save(self):
        """Save history and preferences to files."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)

            with open(self.preferences_file, 'w') as f:
                json.dump(self.preferences, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save listening data: {e}")

    def record_play(self, track: Dict, duration_played: int = None):
        """Record a track play in history."""
        track_id = track.get("id")
        if not track_id:
            return

        metadata = track.get("metadata")
        artist = metadata.artist if metadata else ""

        current_time = int(time.time())

        # Update track history
        if track_id not in self.history["tracks"]:
            self.history["tracks"][track_id] = {
                "play_count": 0,
                "skip_count": 0,
                "last_played": 0,
                "total_duration_played": 0,
                "title": track.get("title", ""),
                "artist": artist
            }

        track_data = self.history["tracks"][track_id]
        track_data["play_count"] += 1
        track_data["last_played"] = current_time

        if duration_played:
            track_data["total_duration_played"] += duration_played

        # Update artist preferences
        if artist:
            if artist not in self.history["artists"]:
                self.history["artists"][artist] = {
                    "play_count": 0,
                    "preference_score": 0.5
                }

            self.history["artists"][artist]["play_count"] += 1
            # Increase preference score slightly with each play
            current_score = self.history["artists"][artist]["preference_score"]
            self.history["artists"][artist]["preference_score"] = min(1.0, current_score + 0.01)

        self.save()

    def record_skip(self, track: Dict, time_played: int):
        """Record a track skip."""
        track_id = track.get("id")
        if not track_id:
            return

        if track_id in self.history["tracks"]:
            self.history["tracks"][track_id]["skip_count"] += 1

            # Decrease artist preference if skipped early
            metadata = track.get("metadata")
            if metadata and metadata.artist:
                artist = metadata.artist
                track_duration = track.get("duration", 180)
                skip_ratio = time_played / track_duration if track_duration > 0 else 0

                if skip_ratio < self.preferences["skip_threshold"] and artist in self.history["artists"]:
                    current_score = self.history["artists"][artist]["preference_score"]
                    self.history["artists"][artist]["preference_score"] = max(0.0, current_score - 0.02)

        self.save()

    def get_artist_preference(self, artist: str) -> float:
        """Get preference score for an artist (0-1)."""
        if not artist:
            return 0.5

        return self.history["artists"].get(artist, {}).get("preference_score", 0.5)

    def get_track_score(self, track: Dict) -> float:
        """Calculate a score for a track based on history and preferences."""
        track_id = track.get("id")
        metadata = track.get("metadata")

        base_score = track.get("quality_score", 0.5)

        # Artist preference bonus
        if metadata and metadata.artist:
            artist_pref = self.get_artist_preference(metadata.artist)
            base_score = (base_score + artist_pref) / 2

        # Duration preference
        duration = track.get("duration", 0)
        min_dur, max_dur = self.preferences["preferred_duration_range"]
        if min_dur <= duration <= max_dur:
            base_score += 0.1
        elif duration < min_dur * 0.5 or duration > max_dur * 2:
            base_score -= 0.2

        # Penalize recently played tracks
        if track_id and track_id in self.history["tracks"]:
            last_played = self.history["tracks"][track_id]["last_played"]
            hours_since = (time.time() - last_played) / 3600

            if hours_since < 2:  # Played in last 2 hours
                base_score -= 0.3
            elif hours_since < 24:  # Played in last day
                base_score -= 0.1

        return max(0.0, min(1.0, base_score))


class SmartQueue:
    """Intelligent queue management with smart shuffling and organization."""

    def __init__(self, history: ListeningHistory = None):
        self.history = history or ListeningHistory()
        self.tracks: List[Dict] = []
        self.current_index: int = 0
        self.played_tracks: Set[str] = set()
        self.shuffle_mode: str = "smart"  # smart, random, sequential, mood

        # Queue segments for better organization
        self.priority_queue: deque = deque()  # High priority tracks
        self.main_queue: List[Dict] = []      # Main queue
        self.buffer_queue: List[Dict] = []    # Background buffer

    def add_tracks(self, tracks: List[Dict], priority: bool = False):
        """Add tracks to the queue with optional priority."""
        if priority:
            self.priority_queue.extend(tracks)
        else:
            self.main_queue.extend(tracks)

        self._reorganize_queue()

    def add_track(self, track: Dict, priority: bool = False, position: str = "end"):
        """Add a single track to the queue.

        Args:
            track: Track dictionary
            priority: If True, add to priority queue
            position: 'next', 'end', or 'random'
        """
        if priority:
            if position == "next":
                self.priority_queue.appendleft(track)
            else:
                self.priority_queue.append(track)
        else:
            if position == "next":
                self.main_queue.insert(0, track)
            elif position == "random":
                pos = random.randint(0, len(self.main_queue))
                self.main_queue.insert(pos, track)
            else:  # end
                self.main_queue.append(track)

        self._reorganize_queue()

    def get_next_track(self) -> Optional[Dict]:
        """Get the next track to play based on current strategy."""
        # First check priority queue
        if self.priority_queue:
            track = self.priority_queue.popleft()
            self._mark_as_played(track)
            return track

        # Then check main queue
        if self.shuffle_mode == "sequential":
            return self._get_next_sequential()
        elif self.shuffle_mode == "random":
            return self._get_next_random()
        elif self.shuffle_mode == "smart":
            return self._get_next_smart()
        elif self.shuffle_mode == "mood":
            return self._get_next_mood_based()

        return None

    def _get_next_sequential(self) -> Optional[Dict]:
        """Get next track in sequential order."""
        if self.current_index < len(self.main_queue):
            track = self.main_queue[self.current_index]
            self.current_index += 1
            self._mark_as_played(track)
            return track
        return None

    def _get_next_random(self) -> Optional[Dict]:
        """Get next track randomly."""
        available = [t for t in self.main_queue if t.get("id") not in self.played_tracks]
        if available:
            track = random.choice(available)
            self._mark_as_played(track)
            return track
        return None

    def _get_next_smart(self) -> Optional[Dict]:
        """Get next track using smart algorithm."""
        available = [t for t in self.main_queue if t.get("id") not in self.played_tracks]
        if not available:
            return None

        # Score tracks based on various factors
        scored_tracks = []
        for track in available:
            score = self.history.get_track_score(track)

            # Add variety bonus (avoid same artist in a row)
            if hasattr(self, 'last_played_track') and self.last_played_track:
                last_metadata = self.last_played_track.get("metadata")
                current_metadata = track.get("metadata")

                if (last_metadata and current_metadata and
                    last_metadata.artist and current_metadata.artist and
                    last_metadata.artist == current_metadata.artist):
                    score -= 0.2  # Penalty for same artist

            scored_tracks.append((track, score))

        # Sort by score and add some randomness to top choices
        scored_tracks.sort(key=lambda x: x[1], reverse=True)

        # Select from top 30% with weighted randomness
        top_count = max(1, len(scored_tracks) // 3)
        top_tracks = scored_tracks[:top_count]

        # Weighted selection from top tracks
        weights = [score for _, score in top_tracks]
        if sum(weights) > 0:
            track = random.choices([t for t, _ in top_tracks], weights=weights)[0]
        else:
            track = top_tracks[0][0]

        self._mark_as_played(track)
        self.last_played_track = track
        return track

    def _get_next_mood_based(self) -> Optional[Dict]:
        """Get next track based on mood continuity."""
        # This is a simplified mood-based selection
        # In a real implementation, you'd analyze audio features
        available = [t for t in self.main_queue if t.get("id") not in self.played_tracks]
        if not available:
            return None

        # For now, use smart selection as base
        return self._get_next_smart()

    def _mark_as_played(self, track: Dict):
        """Mark a track as played."""
        if track.get("id"):
            self.played_tracks.add(track["id"])

    def _reorganize_queue(self):
        """Reorganize queue for optimal playback flow."""
        if self.shuffle_mode == "smart":
            # Group similar tracks and spread them out
            self._smart_shuffle()

    def _smart_shuffle(self):
        """Perform smart shuffling to avoid clustering similar content."""
        if len(self.main_queue) < 3:
            return

        # Group tracks by artist
        artist_groups = defaultdict(list)
        no_artist = []

        for track in self.main_queue:
            metadata = track.get("metadata")
            if metadata and metadata.artist:
                artist_groups[metadata.artist].append(track)
            else:
                no_artist.append(track)

        # Interleave tracks from different artists
        shuffled = []
        artist_queues = {artist: deque(tracks) for artist, tracks in artist_groups.items()}

        # Shuffle each artist's tracks
        for queue in artist_queues.values():
            temp_list = list(queue)
            random.shuffle(temp_list)
            queue.clear()
            queue.extend(temp_list)

        # Interleave tracks
        while artist_queues or no_artist:
            # Add a track from a random artist group
            if artist_queues:
                artists_with_tracks = [a for a, q in artist_queues.items() if q]
                if artists_with_tracks:
                    chosen_artist = random.choice(artists_with_tracks)
                    track = artist_queues[chosen_artist].popleft()
                    shuffled.append(track)

                    # Remove empty queues
                    if not artist_queues[chosen_artist]:
                        del artist_queues[chosen_artist]

            # Occasionally add a track with no artist info
            if no_artist and (not artist_queues or random.random() < 0.2):
                shuffled.append(no_artist.pop())

        self.main_queue = shuffled

    def set_shuffle_mode(self, mode: str):
        """Set the shuffle mode.

        Args:
            mode: 'smart', 'random', 'sequential', or 'mood'
        """
        if mode in ["smart", "random", "sequential", "mood"]:
            self.shuffle_mode = mode
            if mode in ["smart", "random"]:
                self._reorganize_queue()

    def get_queue_info(self) -> Dict:
        """Get information about the current queue state."""
        return {
            "total_tracks": len(self.main_queue) + len(self.priority_queue),
            "priority_tracks": len(self.priority_queue),
            "main_tracks": len(self.main_queue),
            "played_count": len(self.played_tracks),
            "shuffle_mode": self.shuffle_mode,
            "current_index": self.current_index
        }

    def clear_played_history(self):
        """Clear the played tracks history for this session."""
        self.played_tracks.clear()
        self.current_index = 0

    def remove_track(self, track_id: str) -> bool:
        """Remove a track from the queue.

        Returns:
            True if track was found and removed, False otherwise
        """
        # Check priority queue
        for i, track in enumerate(self.priority_queue):
            if track.get("id") == track_id:
                del self.priority_queue[i]
                return True

        # Check main queue
        for i, track in enumerate(self.main_queue):
            if track.get("id") == track_id:
                del self.main_queue[i]
                # Adjust current index if necessary
                if i < self.current_index:
                    self.current_index -= 1
                return True

        return False

    def move_track(self, track_id: str, new_position: int) -> bool:
        """Move a track to a new position in the main queue.

        Returns:
            True if track was found and moved, False otherwise
        """
        track = None
        old_index = -1

        # Find the track
        for i, t in enumerate(self.main_queue):
            if t.get("id") == track_id:
                track = t
                old_index = i
                break

        if track is None:
            return False

        # Remove from old position
        del self.main_queue[old_index]

        # Adjust current index
        if old_index < self.current_index:
            self.current_index -= 1

        # Insert at new position
        new_position = max(0, min(new_position, len(self.main_queue)))
        self.main_queue.insert(new_position, track)

        # Adjust current index again
        if new_position <= self.current_index:
            self.current_index += 1

        return True

    def get_recommendations_for_queue(self) -> List[str]:
        """Get recommendations for improving the current queue."""
        recommendations = []

        if not self.main_queue:
            return ["Add some tracks to get started!"]

        # Check for artist diversity
        artists = set()
        for track in self.main_queue:
            metadata = track.get("metadata")
            if metadata and metadata.artist:
                artists.add(metadata.artist)

        artist_diversity = len(artists) / len(self.main_queue) if self.main_queue else 0

        if artist_diversity < 0.3:
            recommendations.append("Consider adding more variety - many tracks are from the same artists")

        # Check queue length
        if len(self.main_queue) < 10:
            recommendations.append("Queue is running low - consider adding more tracks")
        elif len(self.main_queue) > 100:
            recommendations.append("Queue is very long - consider trimming some tracks")

        # Check for quality
        avg_quality = sum(t.get("quality_score", 0.5) for t in self.main_queue) / len(self.main_queue)
        if avg_quality < 0.4:
            recommendations.append("Queue contains many low-quality tracks - consider filtering")

        return recommendations if recommendations else ["Queue looks good!"]


# Global instance for easy importing
smart_queue = SmartQueue()


def main():
    """Main entry point for the queue management CLI tool."""
    import sys
    import argparse
    try:
        from .discovery import music_discovery
    except ImportError:
        # Direct execution fallback
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from discovery import music_discovery

    parser = argparse.ArgumentParser(description="Queue management tool for youterm")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show queue status")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add tracks to queue")
    add_parser.add_argument("query", help="Search query")
    add_parser.add_argument("-s", "--strategy", default="mixed",
                           choices=["direct", "artist", "related", "genre", "mixed"],
                           help="Search strategy")
    add_parser.add_argument("-l", "--limit", type=int, default=10,
                           help="Number of tracks to add")
    add_parser.add_argument("-p", "--priority", action="store_true",
                           help="Add to priority queue")

    # Shuffle command
    shuffle_parser = subparsers.add_parser("shuffle", help="Set shuffle mode")
    shuffle_parser.add_argument("mode", choices=["smart", "random", "sequential", "mood"],
                               help="Shuffle mode")

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear queue or played history")
    clear_parser.add_argument("--played", action="store_true",
                             help="Clear only played history")

    # Recommendations command
    rec_parser = subparsers.add_parser("recommendations", help="Get queue recommendations")

    # History command
    history_parser = subparsers.add_parser("history", help="Show listening history")
    history_parser.add_argument("--artists", action="store_true",
                               help="Show artist preferences")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "status":
            info = smart_queue.get_queue_info()
            print(f"Queue Status:")
            print(f"  Total tracks: {info['total_tracks']}")
            print(f"  Priority tracks: {info['priority_tracks']}")
            print(f"  Main tracks: {info['main_tracks']}")
            print(f"  Played this session: {info['played_count']}")
            print(f"  Shuffle mode: {info['shuffle_mode']}")
            print(f"  Current index: {info['current_index']}")

            # Show discovery status if available
            try:
                from .auto_discovery import auto_discovery
                discovery_stats = auto_discovery.get_discovery_stats()
                print(f"\nAuto-Discovery Status:")
                print(f"  Service running: {discovery_stats['is_running']}")
                print(f"  Artists discovered: {discovery_stats['discovered_artists_count']}")
                print(f"  Learning from tracks: {discovery_stats['seed_tracks_count']}")
            except ImportError:
                pass

        elif args.command == "add":
            print(f"Searching for '{args.query}' using {args.strategy} strategy...")
            tracks = music_discovery.search_with_strategy(args.query, args.strategy, args.limit)

            if not tracks:
                print("No tracks found.")
                return

            # Enhance tracks with audio URLs
            enhanced_tracks = []
            for track in tracks:
                enhanced = music_discovery.enhance_track_info(track)
                if enhanced.get("audio_url"):
                    enhanced_tracks.append({
                        "id": enhanced.get("id"),
                        "title": enhanced.get("title"),
                        "audio_url": enhanced.get("audio_url"),
                        "duration": enhanced.get("duration", 0),
                        "channel": enhanced.get("channel", ""),
                        "quality_score": enhanced.get("quality_score", 0.5),
                        "metadata": enhanced.get("metadata")
                    })

            smart_queue.add_tracks(enhanced_tracks, priority=args.priority)
            queue_type = "priority" if args.priority else "main"
            print(f"Added {len(enhanced_tracks)} tracks to {queue_type} queue.")

        elif args.command == "shuffle":
            smart_queue.set_shuffle_mode(args.mode)
            print(f"Shuffle mode set to: {args.mode}")

        elif args.command == "clear":
            if args.played:
                smart_queue.clear_played_history()
                print("Cleared played history for this session.")
            else:
                smart_queue.main_queue.clear()
                smart_queue.priority_queue.clear()
                smart_queue.clear_played_history()
                print("Cleared entire queue.")

        elif args.command == "recommendations":
            recommendations = smart_queue.get_recommendations_for_queue()
            print("Queue Recommendations:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")

        elif args.command == "history":
            history = smart_queue.history
            if args.artists:
                print("Artist Preferences:")
                artists = history.history.get("artists", {})
                if artists:
                    sorted_artists = sorted(artists.items(),
                                          key=lambda x: x[1]["preference_score"],
                                          reverse=True)
                    for artist, data in sorted_artists[:20]:  # Top 20
                        score = data["preference_score"]
                        plays = data["play_count"]
                        stars = "*" * int(score * 5)
                        print(f"  {artist}: {score:.2f} {stars} ({plays} plays)")
                else:
                    print("  No artist data available.")
            else:
                tracks = history.history.get("tracks", {})
                if tracks:
                    print("Recent Listening History:")
                    sorted_tracks = sorted(tracks.items(),
                                         key=lambda x: x[1]["last_played"],
                                         reverse=True)
                    for track_id, data in sorted_tracks[:10]:  # Last 10
                        title = data.get("title", "Unknown")
                        artist = data.get("artist", "Unknown Artist")
                        plays = data["play_count"]
                        skips = data["skip_count"]
                        print(f"  {title} by {artist} ({plays} plays, {skips} skips)")
                else:
                    print("  No listening history available.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
