"""YouTube client for downloading subtitles using yt-dlp."""

import asyncio
import logging
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

import webvtt
import yt_dlp

from ssmcp.exceptions import YoutubeError
from ssmcp.logger import logger
from ssmcp.timing import timer

FALLBACK_LANGUAGE = "en"


class YouTubeClient:
    """Downloads and parses subtitles from YouTube videos using yt-dlp."""

    def __init__(self, language: str, cookies_path: str | None = None) -> None:
        """Initialize the YouTube client.

        Args:
            language: Language code to use for subtitles (e.g., 'en', 'es', 'fr').
            cookies_path: Path to the YouTube cookies file.

        """
        self._language = language
        self._cookies_path = Path(cookies_path) if cookies_path else None

    def _find_overlap(self, text1: str, text2: str) -> int:
        """Find the length of overlapping words between the end of text1 and the start of text2.

        This is used to detect 'rolling' captions where each new segment repeats the
        previous words before adding new ones.
        """
        words1 = text1.split()
        words2 = text2.split()

        max_overlap = 0
        max_range = min(len(words1), len(words2)) + 1
        for i in range(1, max_range):
            if words1[-i:] == words2[:i]:
                max_overlap = i

        return max_overlap

    def _deduplicate_cues(self, raw_cues: list[tuple[str, str]]) -> list[str]:
        """Remove overlapping and duplicate cues from raw VTT subtitles.

        YouTube's automated captions often arrive in 'rolling' bursts where segment B
        contains segment A plus a few new words. This algorithm identifies those
        overlaps to produce a clean, readable transcript.
        """
        result: list[str] = []
        prev_text = ""

        for i, (timestamp, current_text) in enumerate(raw_cues):
            # Skip indices where the current text is just a subset of the next burst
            if i + 1 < len(raw_cues):
                next_text = raw_cues[i + 1][1]
                if next_text.startswith(current_text):
                    continue

            # Identify if the previous burst ended with the same words this one starts with
            cleaned_text = current_text
            if prev_text:
                overlap_words = self._find_overlap(prev_text, current_text)
                if overlap_words > 0:
                    words = current_text.split()
                    cleaned_text = " ".join(words[overlap_words:])

                    if not cleaned_text.strip():
                        continue

            result.append(f"[{timestamp}] {cleaned_text}")
            prev_text = current_text

        return result

    def _parse_vtt(self, vtt_content: str) -> str:
        """Parse VTT subtitle content into readable text with timestamps."""
        raw_cues: list[tuple[str, str]] = []

        buffer = StringIO(vtt_content)
        for caption in webvtt.from_buffer(buffer):
            text = " ".join(caption.text.split())
            if not text:
                continue
            raw_cues.append((caption.start, text))

        result = self._deduplicate_cues(raw_cues)
        return "\n".join(result)

    async def get_subtitles(self, url: str) -> str:
        """Download and parse subtitles from a YouTube video.

        Args:
            url: YouTube video URL.

        Returns:
            String containing parsed subtitles with timestamps.

        """
        logger.debug("Fetching subtitles...")
        # yt-dlp is a synchronous library performing blocking I/O (network/file).
        # We wrap it in a thread to prevent blocking the main event loop.
        return await asyncio.to_thread(self._get_subtitles_sync, url)

    def _get_subtitles_sync(self, url: str) -> str:
        """Perform subtitle retrieval using yt-dlp synchronously.

        Args:
            url: YouTube video URL.

        Returns:
            String containing parsed subtitles with timestamps, or error.

        """
        ydl_opts: dict[str, Any] = {
            "skip_download": True,  # We only want metadata and subtitle files
            "quiet": True,
            "no_warnings": True,
        }

        if self._cookies_path and self._cookies_path.exists():
            ydl_opts["cookiefile"] = str(self._cookies_path)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            with timer("ydl.extract_info call", logging.DEBUG):
                info = ydl.extract_info(url, download=False)
            subtitles = info.get("subtitles", {})
            auto_captions = info.get("automatic_captions", {})

        selected_lang = self._select_language(subtitles, auto_captions)
        if not selected_lang:
            raise YoutubeError(f"No subtitles available for: {url}")

        # yt-dlp doesn't have a 'return subtitles as string' option, so we
        # download them to a temporary scratchpad and read them back.
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            ydl_opts.update(
                {
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": [selected_lang],
                    "subtitlesformat": "vtt",
                    "outtmpl": str(temp_path / "%(id)s.%(ext)s"),
                }
            )

            with yt_dlp.YoutubeDL(ydl_opts) as ydl, timer("ydl.download", logging.DEBUG):
                ydl.download([url])

            vtt_files = list(temp_path.glob("*.vtt"))
            if not vtt_files:
                raise YoutubeError(f"Subtitle file not found after download for: {url}")

            vtt_content = vtt_files[0].read_text(encoding="utf-8")
            parsed_subtitles = self._parse_vtt(vtt_content)

        if not parsed_subtitles:
            raise YoutubeError(f"Subtitle parsing resulted in empty text for: {url}")

        return parsed_subtitles

    def _select_language(
        self, subtitles: dict[str, Any], auto_captions: dict[str, Any]
    ) -> str | None:
        """Select the best available language for subtitles."""
        for lang in [self._language, FALLBACK_LANGUAGE]:
            if lang in subtitles or lang in auto_captions:
                logger.debug("Language set to %s", lang)
                return lang

        # Fallback to any available
        if subtitles:
            logger.debug("Language not found. Selecting any available subtitle...")
            return str(next(iter(subtitles.keys())))
        if auto_captions:
            logger.debug("Language not found. Selecting any available auto caption...")
            return str(next(iter(auto_captions.keys())))

        return None
