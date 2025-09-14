"""Music discovery and recommendation engine for youterm.

This module provides enhanced music discovery capabilities including:
- Multi-source search strategies
- Audio feature analysis
- Artist/genre-based recommendations
- Smart duplicate filtering
- Quality scoring for tracks
"""

import re
import random
import time
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
try:
    import yt_dlp
except ImportError:
    # Use wrapper for standalone installation
    from . import ytdlp_wrapper as yt_dlp
import threading
from functools import lru_cache

# This import is handled at the end of the file to avoid circular imports


class MusicMetadata:
    """Container for extracted music metadata."""

    def __init__(self, title: str, artist: str = "", album: str = "", genre: str = "", year: int = 0):
        self.title = title
        self.artist = artist
        self.album = album
        self.genre = genre
        self.year = year
        self.normalized_title = self._normalize_title(title)
        self.normalized_artist = self._normalize_artist(artist)

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        # Remove common prefixes/suffixes
        clean = re.sub(r'\s*\(.*?\)\s*', '', title.lower())
        clean = re.sub(r'\s*\[.*?\]\s*', '', clean)
        clean = re.sub(r'\s*(official|music|video|audio|lyric|lyrics)\s*', ' ', clean)
        clean = re.sub(r'\s*(hd|4k|hq|high quality)\s*', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def _normalize_artist(self, artist: str) -> str:
        """Normalize artist name for comparison."""
        clean = re.sub(r'\s*(official|music|records|entertainment)\s*', ' ', artist.lower())
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def similarity_score(self, other: 'MusicMetadata') -> float:
        """Calculate similarity score with another track (0-1)."""
        if not other:
            return 0.0

        # Title similarity (most important)
        title_sim = self._string_similarity(self.normalized_title, other.normalized_title)

        # Artist similarity
        artist_sim = self._string_similarity(self.normalized_artist, other.normalized_artist)

        # If artists match closely, titles should be different (avoid duplicates)
        if artist_sim > 0.8 and title_sim > 0.8:
            return 0.0  # Likely duplicate

        return title_sim * 0.3 + artist_sim * 0.7

    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity using Jaccard index of bigrams."""
        if not s1 or not s2:
            return 0.0

        def get_bigrams(s: str) -> Set[str]:
            return set(s[i:i+2] for i in range(len(s)-1))

        bigrams1 = get_bigrams(s1)
        bigrams2 = get_bigrams(s2)

        if not bigrams1 and not bigrams2:
            return 1.0
        if not bigrams1 or not bigrams2:
            return 0.0

        intersection = len(bigrams1 & bigrams2)
        union = len(bigrams1 | bigrams2)

        return intersection / union if union > 0 else 0.0


class TrackQualityFilter:
    """Filters and scores tracks based on quality indicators."""

    # Patterns that indicate low quality content
    LOW_QUALITY_PATTERNS = [
        r'#shorts?\b', r'\bshort\b', r'\bstatus\b', r'\bmeme\b',
        r'\breaction\b', r'\breview\b', r'\bcompilation\b',
        r'\bmix\b(?!.*album)', r'\bremix\b(?=.*\d+)', r'\bbeat\b(?=.*\d+)',
        r'\binstrumental\b(?=.*\d+)', r'\bkaraoke\b', r'\bcover\b(?=.*\d+)',
        r'\blive\b(?=.*\d+)', r'\bconcert\b(?=.*\d+)', r'\btutorial\b',
        r'\bhow\s+to\b', r'\blyrics?\s+video\b', r'\bfan\s+made\b'
    ]

    # Patterns that indicate high quality
    HIGH_QUALITY_PATTERNS = [
        r'\bofficial\b', r'\boriginal\b', r'\balbum\b',
        r'\bstudio\b(?=.*version)', r'\bfull\s+song\b',
        r'\bcomplete\b', r'\bdeluxe\b', r'\bremastered\b'
    ]

    def score_track(self, title: str, channel: str, duration: int, view_count: int = 0) -> float:
        """Score track quality from 0.0 to 1.0."""
        score = 0.5  # Base score

        title_lower = title.lower()
        channel_lower = channel.lower()

        # Check content type for appropriate duration handling
        long_form_keywords = ["sahasranamam", "bhajan", "devotional", "mantra", "chant", "classical", "full version", "complete",
                             "interview", "talk", "lecture", "discussion", "episode", "audiobook", "documentary", "speech"]

        # Detect podcasts/interviews by channel patterns and content indicators
        podcast_indicators = ["podcast" in channel_lower, "interview" in channel_lower, "talk" in channel_lower,
                             "radio" in channel_lower, "show" in channel_lower, "cast" in channel_lower,
                             duration and duration > 900]  # Anything over 15 minutes might be long-form

        is_long_form = any(keyword in title_lower for keyword in long_form_keywords) or any(podcast_indicators)

        # Duration scoring - no upper limits, encourage longer content when appropriate
        if is_long_form:
            # For long-form content - no upper limit, encourage longer durations
            if duration and duration >= 300:  # 5+ minutes gets bonus
                score += 0.2
            elif duration and 120 <= duration < 300:  # 2-5 minutes
                score += 0.1
            elif duration and duration < 60:
                score -= 0.3  # Still penalize very short clips
        else:
            # Standard duration scoring for regular music
            if duration and 120 <= duration <= 480:  # 2-8 minutes
                score += 0.2
            elif duration and duration < 60:
                score -= 0.3
            elif duration and duration > 600:  # Slight penalty for very long music
                score -= 0.1

        # Title quality patterns
        for pattern in self.LOW_QUALITY_PATTERNS:
            if re.search(pattern, title_lower):
                score -= 0.15

        for pattern in self.HIGH_QUALITY_PATTERNS:
            if re.search(pattern, title_lower):
                score += 0.15

        # Channel indicators
        if any(word in channel_lower for word in ['official', 'records', 'music']):
            score += 0.1
        elif any(word in channel_lower for word in ['compilation', 'mix', 'covers']):
            score -= 0.1

        # View count (if available)
        if view_count > 0:
            if view_count > 1000000:  # 1M+ views
                score += 0.05
            elif view_count < 1000:  # < 1k views
                score -= 0.05

        return max(0.0, min(1.0, score))


class MusicDiscovery:
    """Advanced music discovery engine."""

    def __init__(self):
        self.quality_filter = TrackQualityFilter()
        self.seen_tracks: Set[str] = set()
        self.artist_cache: Dict[str, List[str]] = {}
        self.genre_cache: Dict[str, List[str]] = defaultdict(list)
        self._search_cache: Dict[str, List[Dict]] = {}
        self._cache_lock = threading.Lock()
        self._cache_max_size = 100

    def extract_metadata(self, title: str, channel: str = "") -> MusicMetadata:
        """Extract metadata from title and channel."""
        # Common patterns for "Artist - Title" or "Title by Artist"
        patterns = [
            r'^(.+?)\s*-\s*(.+)$',  # Artist - Title
            r'^(.+?)\s*by\s+(.+)$',  # Title by Artist
            r'^(.+?)\s*\|\s*(.+)$',  # Artist | Title
            r'^(.+?)\s*:\s*(.+)$',   # Artist: Title
        ]

        artist = ""
        clean_title = title

        for pattern in patterns:
            match = re.match(pattern, title, re.IGNORECASE)
            if match:
                part1, part2 = match.groups()
                # Heuristic: shorter part is usually the artist
                if len(part1.strip()) < len(part2.strip()):
                    artist = part1.strip()
                    clean_title = part2.strip()
                else:
                    artist = part2.strip()
                    clean_title = part1.strip()
                break

        # If no artist found in title, try to extract from channel
        if not artist and channel:
            # Remove common channel suffixes
            channel_clean = re.sub(r'\s*(official|music|records|entertainment|vevo)\s*$',
                                 '', channel, flags=re.IGNORECASE).strip()
            if channel_clean and len(channel_clean) < 50:  # Reasonable length
                artist = channel_clean

        return MusicMetadata(clean_title, artist)

    def search_with_strategy(self, query: str, strategy: str = "mixed", limit: int = 20) -> List[Dict]:
        """Search using different strategies for better variety."""
        # Check cache first
        cache_key = f"{strategy}:{query}:{limit}"
        with self._cache_lock:
            if cache_key in self._search_cache:
                return self._search_cache[cache_key].copy()

        strategies = {
            "direct": self._search_direct,
            "artist": self._search_by_artist,
            "related": self._search_related_artists,
            "genre": self._search_by_genre,
            "mixed": self._search_mixed
        }

        search_func = strategies.get(strategy, self._search_mixed)
        results = search_func(query, limit)

        # Cache results
        with self._cache_lock:
            if len(self._search_cache) >= self._cache_max_size:
                # Remove oldest entries
                oldest_keys = list(self._search_cache.keys())[:10]
                for key in oldest_keys:
                    del self._search_cache[key]
            self._search_cache[cache_key] = results.copy()

        return results

    def _search_direct(self, query: str, limit: int) -> List[Dict]:
        """Direct search with quality filtering."""
        # Always search exact query first, then add variations only if needed
        search_variations = [f"{query}"]

        tracks = []
        seen_ids = set()

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "ignoreerrors": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search exact query first
            for i, search_term in enumerate(search_variations):
                if len(tracks) >= limit:
                    break

                try:
                    search_str = f"ytsearch{limit + 3}:{search_term}"
                    result = ydl.extract_info(search_str, download=False)

                    if not result or "entries" not in result:
                        continue

                    for entry in result["entries"]:
                        if not entry or entry.get("id") in seen_ids or len(tracks) >= limit * 2:
                            continue

                        video_id = entry.get("id")
                        title = entry.get("title", "")
                        channel = entry.get("uploader", "")
                        duration = entry.get("duration") or 0

                        # Quick quality check - detect long-form content automatically
                        long_form_keywords = ["sahasranamam", "bhajan", "devotional", "mantra", "chant", "classical", "full version", "complete",
                                             "interview", "talk", "lecture", "discussion", "episode", "audiobook", "documentary", "speech"]

                        # Auto-detect podcasts/interviews by channel and duration
                        podcast_indicators = ["podcast" in channel.lower(), "interview" in channel.lower(), "talk" in channel.lower(),
                                             "radio" in channel.lower(), "show" in channel.lower(), "cast" in channel.lower(),
                                             duration and duration > 900]  # Anything over 15 minutes might be long-form

                        is_long_form = any(keyword in title.lower() for keyword in long_form_keywords) or any(podcast_indicators)

                        if duration and duration < 60:  # Only skip very short clips
                            continue
                        # No upper duration limits - let all content through
                        if any(bad in title.lower() for bad in ["#shorts", "reaction", "review"]):
                            continue

                        # Full quality scoring only for promising tracks
                        quality_score = self.quality_filter.score_track(
                            title, channel, duration, entry.get("view_count") or 0
                        )

                        if quality_score > 0.3:
                            metadata = self.extract_metadata(title, channel)
                            tracks.append({
                                "id": video_id,
                                "title": title,
                                "channel": channel,
                                "duration": duration,
                                "quality_score": quality_score,
                                "metadata": metadata,
                                "url": f"https://www.youtube.com/watch?v={video_id}"
                            })
                            seen_ids.add(video_id)

                except Exception as e:
                    print(f"Search error for '{search_term}': {e}")
                    continue

            # Add official variation if we don't have enough results
            if len(tracks) < limit // 2:
                try:
                    search_str = f"ytsearch{limit + 3}:{query} official"
                    result = ydl.extract_info(search_str, download=False)

                    if result and "entries" in result:
                        for entry in result["entries"]:
                            if not entry or entry.get("id") in seen_ids or len(tracks) >= limit * 2:
                                continue

                            video_id = entry.get("id")
                            title = entry.get("title", "")
                            channel = entry.get("uploader", "")
                            duration = entry.get("duration") or 0

                            # Quick quality check
                            if duration and (duration < 60 or duration > 600):
                                continue
                            if any(bad in title.lower() for bad in ["#shorts", "reaction", "review"]):
                                continue

                            quality_score = self.quality_filter.score_track(
                                title, channel, duration, entry.get("view_count") or 0
                            )

                            if quality_score > 0.3:
                                metadata = self.extract_metadata(title, channel)
                                tracks.append({
                                    "id": video_id,
                                    "title": title,
                                    "channel": channel,
                                    "duration": duration,
                                    "quality_score": quality_score,
                                    "metadata": metadata,
                                    "url": f"https://www.youtube.com/watch?v={video_id}"
                                })
                                seen_ids.add(video_id)

                except Exception as e:
                    print(f"Search error for '{query} official': {e}")

        # Quick deduplication and sort by relevance
        unique_tracks = {t["id"]: t for t in tracks if t.get("id")}
        tracks = list(unique_tracks.values())

        # Sort by relevance to search query first, then quality
        def relevance_score(track):
            title = track.get("title", "").lower()
            query_lower = query.lower()
            query_words = query_lower.split()

            # Filter out common words
            important_words = [word for word in query_words if word not in ["and", "the", "a", "an", "of", "to", "in", "on", "at", "for", "with", "by"]]
            if not important_words:
                important_words = query_words

            # Exact phrase match gets highest score
            if query_lower in title:
                position = title.find(query_lower)
                relevance = 1.0 - (position / len(title)) if len(title) > 0 else 1.0
            else:
                # Check if ALL important words are present
                missing_words = [word for word in important_words if word not in title]

                # Require ALL important words to be present
                if not missing_words:  # All important words found
                    # Calculate position-based score
                    word_positions = [title.find(word) for word in important_words]
                    avg_position = sum(word_positions) / len(word_positions) if word_positions else len(title)
                    relevance = 0.8 - (avg_position / len(title)) * 0.3
                else:
                    relevance = 0  # Reject if any important word is missing

            # Combine relevance and quality (heavily favor relevance)
            quality = track.get("quality_score", 0.5)
            return relevance * 0.95 + quality * 0.05

        tracks.sort(key=relevance_score, reverse=True)
        return tracks[:limit]

    def _search_by_artist(self, artist_name: str, limit: int) -> List[Dict]:
        """Search for songs by a specific artist."""
        if artist_name in self.artist_cache:
            # Use cached results with some randomization
            cached = self.artist_cache[artist_name]
            random.shuffle(cached)
            return cached[:limit]

        search_terms = [
            f"{artist_name} songs",
            f"{artist_name} best songs",
            f"{artist_name} top hits",
            f"{artist_name} album"
        ]

        tracks = []
        for term in search_terms:
            batch = self._search_direct(term, limit // 2)
            tracks.extend(batch)

        # Cache results
        self.artist_cache[artist_name] = tracks
        return tracks[:limit]

    def _search_related_artists(self, query: str, limit: int) -> List[Dict]:
        """Find similar artists and their songs."""
        # First, find the main artist
        initial_tracks = self._search_direct(query, 5)
        if not initial_tracks:
            return []

        # Extract artist from best result
        best_track = max(initial_tracks, key=lambda x: x["quality_score"])
        main_artist = best_track["metadata"].artist

        if not main_artist:
            return initial_tracks[:limit]

        # Search for similar artists (this would ideally use a music database)
        # For now, we'll use genre-based searches
        related_searches = [
            f"artists like {main_artist}",
            f"{main_artist} similar music",
            f"songs similar to {query}"
        ]

        all_tracks = initial_tracks.copy()
        for search_term in related_searches:
            batch = self._search_direct(search_term, limit // 3)
            all_tracks.extend(batch)

        return self._remove_duplicates(all_tracks)[:limit]

    def _search_by_genre(self, query: str, limit: int) -> List[Dict]:
        """Search by genre or mood."""
        genre_searches = [
            f"{query} playlist",
            f"best {query} songs",
            f"{query} music 2024",
            f"top {query} hits"
        ]

        tracks = []
        for search_term in genre_searches:
            batch = self._search_direct(search_term, limit // 2)
            tracks.extend(batch)

        return self._remove_duplicates(tracks)[:limit]

    def _search_mixed(self, query: str, limit: int) -> List[Dict]:
        """Mixed strategy combining multiple approaches."""
        strategies_weights = [
            ("direct", 0.4),
            ("artist", 0.3),
            ("related", 0.2),
            ("genre", 0.1)
        ]

        all_tracks = []
        for strategy, weight in strategies_weights:
            strategy_limit = max(1, int(limit * weight))
            if strategy != "mixed":  # Avoid recursion
                batch = self.search_with_strategy(query, strategy, strategy_limit)
                all_tracks.extend(batch)

        # Sort by relevance instead of random shuffle for mixed strategy
        def relevance_score(track):
            title = track.get("title", "").lower()
            query_lower = query.lower()
            query_words = query_lower.split()

            # Filter out common words
            important_words = [word for word in query_words if word not in ["and", "the", "a", "an", "of", "to", "in", "on", "at", "for", "with", "by"]]
            if not important_words:
                important_words = query_words

            # Exact phrase match gets highest score
            if query_lower in title:
                position = title.find(query_lower)
                relevance = 1.0 - (position / len(title)) if len(title) > 0 else 1.0
            else:
                # Check if ALL important words are present
                missing_words = [word for word in important_words if word not in title]

                # Require ALL important words to be present
                if not missing_words:  # All important words found
                    # Calculate position-based score
                    word_positions = [title.find(word) for word in important_words]
                    avg_position = sum(word_positions) / len(word_positions) if word_positions else len(title)
                    relevance = 0.8 - (avg_position / len(title)) * 0.3
                else:
                    relevance = 0  # Reject if any important word is missing

            quality = track.get("quality_score", 0.5)
            return relevance * 0.95 + quality * 0.05

        all_tracks.sort(key=relevance_score, reverse=True)
        return self._remove_duplicates(all_tracks)[:limit]

    def _remove_duplicates(self, tracks: List[Dict]) -> List[Dict]:
        """Remove duplicate tracks using metadata similarity."""
        if not tracks:
            return tracks

        unique_tracks = []
        seen_signatures = set()

        for track in tracks:
            metadata = track.get("metadata")
            if not metadata:
                continue

            # Create signature for deduplication
            signature = f"{metadata.normalized_artist}:{metadata.normalized_title}"

            # Check for near-duplicates with existing tracks
            is_duplicate = False
            for existing_sig in seen_signatures:
                existing_artist, existing_title = existing_sig.split(":", 1)
                similarity = metadata._string_similarity(
                    metadata.normalized_title, existing_title
                )
                artist_similarity = metadata._string_similarity(
                    metadata.normalized_artist, existing_artist
                )

                if similarity > 0.8 and artist_similarity > 0.8:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_tracks.append(track)
                seen_signatures.add(signature)

        return unique_tracks

    def get_recommendations(self, seed_tracks: List[Dict], limit: int = 20) -> List[Dict]:
        """Generate recommendations based on seed tracks."""
        if not seed_tracks:
            return []

        recommendations = []

        # Extract artists and search for their other songs
        artists = set()
        for track in seed_tracks[-3:]:  # Use last 3 tracks
            metadata = track.get("metadata")
            if metadata and metadata.artist:
                artists.add(metadata.artist)

        # Get recommendations for each artist
        for artist in list(artists)[:2]:  # Limit to prevent too many requests
            artist_tracks = self._search_by_artist(artist, limit // len(artists) + 2)

            # Filter out tracks we already have
            existing_ids = {t.get("id") for t in seed_tracks}
            new_tracks = [t for t in artist_tracks if t.get("id") not in existing_ids]
            recommendations.extend(new_tracks)

        # Add some variety with related searches
        if seed_tracks:
            last_track = seed_tracks[-1]
            metadata = last_track.get("metadata")
            if metadata:
                query = f"{metadata.artist} {metadata.title}" if metadata.artist else metadata.title
                related = self._search_related_artists(query, limit // 3)
                recommendations.extend(related)

        return self._remove_duplicates(recommendations)[:limit]

    @lru_cache(maxsize=50)
    def _get_audio_url(self, video_id: str) -> str:
        """Cached audio URL extraction."""
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "ignoreerrors": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                url = f"https://www.youtube.com/watch?v={video_id}"
                info = ydl.extract_info(url, download=False)
                return info.get("url") or ""
        except Exception:
            return ""

    def enhance_track_info(self, track_dict: Dict) -> Dict:
        """Enhance track dictionary with audio URL and additional metadata."""
        video_id = track_dict.get("id")
        if not video_id:
            return track_dict

        # Use cached audio URL extraction
        audio_url = self._get_audio_url(video_id)
        track_dict["audio_url"] = audio_url

        return track_dict


# Global instance for easy importing
music_discovery = MusicDiscovery()

# Import smart_queue here to avoid circular imports
try:
    from .smart_queue import smart_queue
except ImportError:
    # Direct execution fallback
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from smart_queue import smart_queue


def main():
    """Main entry point for the discovery CLI tool."""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Music discovery tool for youterm")
    parser.add_argument("query", help="Search query")
    parser.add_argument("-s", "--strategy",
                       choices=["direct", "artist", "related", "genre", "mixed"],
                       default="mixed",
                       help="Search strategy (default: mixed)")
    parser.add_argument("-l", "--limit", type=int, default=20,
                       help="Number of results (default: 20)")
    parser.add_argument("--test-metadata", action="store_true",
                       help="Test metadata extraction")
    parser.add_argument("--quality-filter", action="store_true",
                       help="Show quality scores")

    args = parser.parse_args()

    if args.test_metadata:
        # Test metadata extraction
        metadata = music_discovery.extract_metadata(args.query)
        print(f"Title: {metadata.title}")
        print(f"Artist: {metadata.artist}")
        print(f"Normalized Title: {metadata.normalized_title}")
        print(f"Normalized Artist: {metadata.normalized_artist}")
        return

    print(f"Searching for '{args.query}' using {args.strategy} strategy...")

    try:
        tracks = music_discovery.search_with_strategy(args.query, args.strategy, args.limit)

        if not tracks:
            print("No tracks found.")
            return

        print(f"\nFound {len(tracks)} tracks:\n")

        for i, track in enumerate(tracks, 1):
            title = track.get("title", "Unknown")
            channel = track.get("channel", "")
            duration = track.get("duration") or 0
            quality = track.get("quality_score") or 0

            duration_str = f"{int(duration)//60}:{int(duration)%60:02d}" if duration and duration > 0 else "??:??"

            print(f"{i:2d}. {title}")
            if channel:
                print(f"    Channel: {channel}")
            print(f"    Duration: {duration_str}")

            if args.quality_filter:
                stars = "*" * int(quality * 5) if quality else ""
                print(f"    Quality: {quality:.2f} {stars}")

            metadata = track.get("metadata")
            if metadata:
                if metadata.artist:
                    print(f"    Artist: {metadata.artist}")
                print(f"    Clean Title: {metadata.normalized_title}")

            print()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
