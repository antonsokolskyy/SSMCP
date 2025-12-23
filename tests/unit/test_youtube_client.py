"""Unit tests for YouTube client."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ssmcp.exceptions import YoutubeError
from ssmcp.youtube_client import YouTubeClient


class TestYouTubeClient:
    """Test YouTube client functionality."""

    @pytest.fixture
    def client(self) -> YouTubeClient:
        """Create a YouTube client for testing."""
        return YouTubeClient(language="en")

    def test_find_overlap(self, client: YouTubeClient) -> None:
        """Test overlap detection between two strings."""
        expected_overlap_normal = 2
        text1 = "Hello world today"
        text2 = "world today is great"
        overlap = client._find_overlap(text1, text2)
        assert overlap == expected_overlap_normal  # "world today"

        expected_overlap_none = 0
        text1 = "Hello world"
        text2 = "Goodbye world"
        overlap = client._find_overlap(text1, text2)
        assert overlap == expected_overlap_none

        expected_overlap_multi = 2
        text1 = "one two three"
        text2 = "two three four"
        overlap = client._find_overlap(text1, text2)
        assert overlap == expected_overlap_multi

    def test_deduplicate_cues(self, client: YouTubeClient) -> None:
        """Test deduplication of subtitle cues."""
        raw_cues = [
            ("00:01", "Hello world"),
            ("00:02", "world today is"),
            ("00:03", "today is great"),
        ]
        # Step by step:
        # 1. "Hello world" -> result: ["[00:01] Hello world"]
        # 2. "world today is" overlaps with "Hello world" by 1 word ("world")
        #    -> cleaned: "today is" -> result: ["[00:01] Hello world", "[00:02] today is"]
        # 3. "today is great" overlaps with "world today is" by 2 words ("today is")
        #    -> cleaned: "great" -> result: ["[00:01] Hello world",
        #                                   "[00:02] today is",
        #                                   "[00:03] great"]
        expected_len = 3
        result = client._deduplicate_cues(raw_cues)
        assert len(result) == expected_len
        assert "[00:01] Hello world" in result[0]
        assert "today is" in result[1]
        assert "great" in result[2]

    @patch("ssmcp.youtube_client.yt_dlp.YoutubeDL")
    async def test_get_subtitles_no_subtitles(
        self, mock_ytdl: MagicMock, client: YouTubeClient
    ) -> None:
        """Test handling when no subtitles are available."""
        mock_instance = mock_ytdl.return_value.__enter__.return_value
        mock_instance.extract_info.return_value = {"subtitles": {}, "automatic_captions": {}}

        with pytest.raises(YoutubeError, match="No subtitles available"):
            await client.get_subtitles("https://youtube.com/watch?v=123")

    @patch("ssmcp.youtube_client.yt_dlp.YoutubeDL")
    async def test_get_subtitles_success(
        self,
        mock_ytdl: MagicMock,
        client: YouTubeClient
    ) -> None:
        """Test successful subtitle retrieval."""
        # Mock available subtitles
        mock_instance = mock_ytdl.return_value.__enter__.return_value
        mock_instance.extract_info.return_value = {
            "subtitles": {"en": [{"url": "http://example.com/en.vtt"}]},
            "automatic_captions": {}
        }

        # We need to mock download to actually create a file in the temp dir
        def mock_download(urls: list[str]) -> None:
            # The client uses tempfile.TemporaryDirectory() internally.
            # This is hard to mock without mocking TemporaryDirectory itself.
            # Let's mock TemporaryDirectory but make it return a real TD.
            pass

        with patch("tempfile.TemporaryDirectory") as mock_td:
            td = tempfile.mkdtemp()
            mock_td.return_value.__enter__.return_value = td

            vtt_file = Path(td) / "test.vtt"
            vtt_text = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello world"
            vtt_file.write_text(vtt_text, encoding="utf-8")

            result = await client.get_subtitles("https://youtube.com/watch?v=123")

            # Clean up
            shutil.rmtree(td)

        assert isinstance(result, str)
        assert "[00:00:01.000] Hello world" in result
