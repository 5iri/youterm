"""
yt-dlp wrapper for youterm standalone installation.
This module provides a Python interface to the yt-dlp executable.
"""

import subprocess
import json
import os
import sys
import shlex
import shutil
from typing import Dict, List, Optional, Any


class YoutubeDL:
    """Wrapper for yt-dlp executable that mimics the Python module interface."""

    def __init__(self, params: Optional[Dict] = None):
        self.params = params or {}
        self.ytdlp_path = self._find_ytdlp_executable()

    def _find_ytdlp_executable(self) -> str:
        """Find yt-dlp executable in various locations."""
        # Check if yt-dlp is in PATH
        ytdlp_path = shutil.which("yt-dlp")
        if ytdlp_path:
            return ytdlp_path

        # Check local installation
        lib_dir = os.path.expanduser("~/.local/lib/youterm/bin/yt-dlp")
        if os.path.exists(lib_dir):
            return lib_dir

        # Check in same directory as this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_ytdlp = os.path.join(script_dir, "../bin/yt-dlp")
        if os.path.exists(local_ytdlp):
            return local_ytdlp

        # Fallback to system yt-dlp
        return "yt-dlp"

    def extract_info(self, url: str, download: bool = True) -> Optional[Dict]:
        """Extract information from URL using yt-dlp executable."""
        cmd = [self.ytdlp_path]

        # Add parameters based on options
        if not download or self.params.get('skip_download'):
            cmd.append('--skip-download')

        if self.params.get('quiet'):
            cmd.extend(['--quiet', '--no-warnings'])

        if self.params.get('extract_flat'):
            cmd.append('--flat-playlist')
        else:
            cmd.append('--no-flat-playlist')

        if self.params.get('ignoreerrors'):
            cmd.append('--ignore-errors')

        # Format selection
        format_selector = self.params.get('format', 'best')
        cmd.extend(['--format', format_selector])

        # Always dump JSON for parsing
        cmd.append('--dump-single-json')

        # Add URL
        cmd.append(url)

        try:
            # Run yt-dlp and capture output
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False
            )

            if result.returncode != 0:
                if not self.params.get('quiet'):
                    print(f"yt-dlp error: {result.stderr}", file=sys.stderr)
                return None

            # Parse JSON output
            if result.stdout.strip():
                data = json.loads(result.stdout)

                # Handle playlist vs single video
                if data.get('_type') == 'playlist':
                    return {
                        'entries': data.get('entries', []),
                        '_type': 'playlist',
                        'title': data.get('title', ''),
                        'id': data.get('id', '')
                    }
                else:
                    # Single video
                    return data

        except subprocess.TimeoutExpired:
            if not self.params.get('quiet'):
                print("yt-dlp timeout", file=sys.stderr)
        except json.JSONDecodeError as e:
            if not self.params.get('quiet'):
                print(f"JSON decode error: {e}", file=sys.stderr)
        except Exception as e:
            if not self.params.get('quiet'):
                print(f"yt-dlp execution error: {e}", file=sys.stderr)

        return None

    def download(self, url_list: List[str]) -> int:
        """Download videos (placeholder - not used in youterm)."""
        return 0


# For compatibility with existing code
def YoutubeDL(params: Optional[Dict] = None) -> YoutubeDL:
    """Factory function for YoutubeDL instances."""
    return YoutubeDL(params)
