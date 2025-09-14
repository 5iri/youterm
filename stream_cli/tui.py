"""Textual-based TUI application for stream-cli.

Run via:
    stream-cli         # launches TUI

Key bindings (when focused in results/list view):
    Enter   – play selected track
    /       – focus search input
    Space   – pause/resume during playback
    n       – next track
    q       – quit app
"""
from __future__ import annotations

import asyncio
import signal
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional

import yt_dlp
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, Static

# ffplay command; fallback path can be customised later
FFPLAY_CMD = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
RESULTS_DEFAULT = 10


@dataclass
class Track:
    title: str
    audio_url: str


class SearchComplete(Message):
    """Message containing search results."""

    def __init__(self, tracks: List[Track]):
        super().__init__()
        self.tracks = tracks


class PlayerStatus(Message):
    """Message for player status updates (paused/resumed/finished)."""

    def __init__(self, status: str):
        super().__init__()
        self.status = status


class ResultsView(Static):
    """Widget to display search results."""

    tracks: reactive[List[Track]] = reactive([])
    selected_index: reactive[int] = reactive(0)

    def render(self):  # type: ignore[override]
        if not self.tracks:
            return "No results. Enter a query and press Enter."
        lines = []
        for idx, track in enumerate(self.tracks):
            prefix = "➜" if idx == self.selected_index else " "
            lines.append(f"{prefix} {idx+1:2}. {track.title}")
        return "\n".join(lines)

    def key_up(self):  # noqa: N802
        if self.tracks:
            self.selected_index = max(0, self.selected_index - 1)

    def key_down(self):  # noqa: N802
        if self.tracks:
            self.selected_index = min(len(self.tracks) - 1, self.selected_index + 1)


class StreamCLIApp(App):
    TITLE = "stream-cli"
    CSS_PATH = None  # no external CSS yet

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("/", "focus_search", "Search"),
        ("n", "next_track", "Next"),
        ("space", "toggle_pause", "Pause/Resume"),
    ]

    # Reactive state
    _tracks: List[Track] = []
    _player_proc: Optional[subprocess.Popen] = None
    _current_index: int = -1
    _paused: bool = False

    def compose(self) -> ComposeResult:  # noqa: D401
        yield Header()
        with Container():
            # Vertical stack: input + results
            with Vertical():
                self.input = Input(placeholder="Type search query and press Enter…")
                yield self.input
                self.results_view = ResultsView()
                yield self.results_view
        yield Footer()

    async def on_mount(self) -> None:
        self.set_focus(self.input)

    async def action_focus_search(self) -> None:
        self.set_focus(self.input)

    async def action_next_track(self) -> None:
        if self._player_proc:
            self._player_proc.kill()

    async def action_toggle_pause(self) -> None:
        if not self._player_proc:
            return
        if self._paused:
            self._player_proc.send_signal(signal.SIGCONT)
            self._paused = False
            self.post_message(PlayerStatus("resumed"))
        else:
            self._player_proc.send_signal(signal.SIGSTOP)
            self._paused = True
            self.post_message(PlayerStatus("paused"))

    async def on_input_submitted(self, event: Input.Submitted) -> None:  # noqa: D401
        query = event.value.strip()
        if not query:
            return
        self._tracks = await asyncio.to_thread(self._search_youtube, query)
        self.post_message(SearchComplete(self._tracks))

    async def on_search_complete(self, message: SearchComplete) -> None:  # noqa: D401
        self.results_view.tracks = message.tracks
        self.results_view.selected_index = 0
        self.refresh()

    def on_key(self, event: events.Key) -> None:  # noqa: D401
        # Delegate arrow keys to results view
        if event.key in {"up", "down"}:
            if event.key == "up":
                self.results_view.key_up()
            else:
                self.results_view.key_down()
            self.refresh()
        elif event.key == "enter":
            self._current_index = self.results_view.selected_index
            asyncio.create_task(self._play_current())

    def _search_youtube(self, query: str) -> List[Track]:
        tracks: List[Track] = []
        ydl_search_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
        }
        with yt_dlp.YoutubeDL(ydl_search_opts) as ydl:
            search_result = ydl.extract_info(f"ytsearch{RESULTS_DEFAULT}:{query}", download=False)
        if not search_result or "entries" not in search_result:
            return tracks
        ydl_extract_opts = {"quiet": True, "skip_download": True, "format": "bestaudio"}
        with yt_dlp.YoutubeDL(ydl_extract_opts) as ydl:
            for entry in search_result["entries"]:
                video_url = entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry['id']}"
                info = ydl.extract_info(video_url, download=False)
                tracks.append(Track(info.get("title", "Unknown"), info["url"]))
        return tracks

    async def _play_current(self):
        if not (0 <= self._current_index < len(self._tracks)):
            return
        track = self._tracks[self._current_index]
        self.results_view.selected_index = self._current_index
        self.refresh()
        # Kill previous proc
        if self._player_proc:
            self._player_proc.kill()
        self._paused = False
        cmd = FFPLAY_CMD + [track.audio_url]
        self._player_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for completion asynchronously
        await asyncio.to_thread(self._player_proc.wait)
        # Auto-next when finished
        self._current_index += 1
        if self._current_index < len(self._tracks):
            await self._play_current()
        else:
            self._player_proc = None

    async def on_shutdown_request(self) -> None:
        if self._player_proc:
            self._player_proc.kill()


def main() -> None:  # entry point
    try:
        StreamCLIApp().run()
    except KeyboardInterrupt:
        print("Exiting stream-cli.")
        sys.exit(0)
