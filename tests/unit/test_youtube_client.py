"""Unit tests for YouTube client."""

import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ssmcp.exceptions import YoutubeError
from ssmcp.youtube_client import FALLBACK_LANGUAGE, YouTubeClient

# Test constants
EXPECTED_YTDLP_CALLS = 2  # One for extract_info, one for download
EXPECTED_OVERLAP_NORMAL = 2
EXPECTED_OVERLAP_NONE = 0
EXPECTED_OVERLAP_MULTI = 2
EXPECTED_DEDUPLICATED_LEN = 3


class TestYouTubeClient:
    """Test YouTube client functionality."""

    @pytest.fixture
    def client(self) -> YouTubeClient:
        """Create a YouTube client for testing."""
        return YouTubeClient(language="en")

    def test_find_overlap(self, client: YouTubeClient) -> None:
        """Test overlap detection between two strings."""
        text1 = "Hello world today"
        text2 = "world today is great"
        overlap = client._find_overlap(text1, text2)
        assert overlap == EXPECTED_OVERLAP_NORMAL  # "world today"

        text1 = "Hello world"
        text2 = "Goodbye world"
        overlap = client._find_overlap(text1, text2)
        assert overlap == EXPECTED_OVERLAP_NONE

        text1 = "one two three"
        text2 = "two three four"
        overlap = client._find_overlap(text1, text2)
        assert overlap == EXPECTED_OVERLAP_MULTI

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
        result = client._deduplicate_cues(raw_cues)
        assert len(result) == EXPECTED_DEDUPLICATED_LEN
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

    @patch("ssmcp.youtube_client.yt_dlp.YoutubeDL")
    async def test_get_subtitles_file_not_found(
        self,
        mock_ytdl: MagicMock,
        client: YouTubeClient
    ) -> None:
        """Test that YoutubeError is raised when subtitle file is not found after download."""
        mock_instance = mock_ytdl.return_value.__enter__.return_value
        mock_instance.extract_info.return_value = {
            "subtitles": {"en": [{"url": "http://example.com/en.vtt"}]},
            "automatic_captions": {}
        }

        # Mock TemporaryDirectory to return an empty directory (no .vtt files)
        with patch("tempfile.TemporaryDirectory") as mock_td:
            td = tempfile.mkdtemp()
            mock_td.return_value.__enter__.return_value = td
            # Do NOT create any .vtt files in the temp directory

            with pytest.raises(YoutubeError, match="Subtitle file not found after download"):
                await client.get_subtitles("https://youtube.com/watch?v=123")

            # Clean up
            shutil.rmtree(td)

    @patch("ssmcp.youtube_client.yt_dlp.YoutubeDL")
    async def test_get_subtitles_empty_parsed_result(
        self,
        mock_ytdl: MagicMock,
        client: YouTubeClient
    ) -> None:
        """Test that YoutubeError is raised when parsing results in empty text."""
        mock_instance = mock_ytdl.return_value.__enter__.return_value
        mock_instance.extract_info.return_value = {
            "subtitles": {"en": [{"url": "http://example.com/en.vtt"}]},
            "automatic_captions": {}
        }

        with patch("tempfile.TemporaryDirectory") as mock_td:
            td = tempfile.mkdtemp()
            mock_td.return_value.__enter__.return_value = td

            # Create a VTT file with only empty/whitespace cues that will be filtered out
            vtt_file = Path(td) / "test.vtt"
            vtt_text = (
                "WEBVTT\n\n"
                "00:00:01.000 --> 00:00:02.000\n   \n\n"
                "00:00:03.000 --> 00:00:04.000\n\t\n"
            )
            vtt_file.write_text(vtt_text, encoding="utf-8")

            with pytest.raises(YoutubeError, match="Subtitle parsing resulted in empty text"):
                await client.get_subtitles("https://youtube.com/watch?v=123")

            # Clean up
            shutil.rmtree(td)

    @patch("ssmcp.youtube_client.yt_dlp.YoutubeDL")
    async def test_get_subtitles_with_cookies_file(
        self,
        mock_ytdl: MagicMock,
    ) -> None:
        """Test that cookies file is passed to yt-dlp when it exists."""
        # Create a temporary cookies file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("# Netscape HTTP Cookie File\n")
            cookies_path = f.name

        try:
            client = YouTubeClient(language="en", cookies_path=cookies_path)

            mock_instance = mock_ytdl.return_value.__enter__.return_value
            mock_instance.extract_info.return_value = {
                "subtitles": {"en": [{"url": "http://example.com/en.vtt"}]},
                "automatic_captions": {}
            }

            with patch("tempfile.TemporaryDirectory") as mock_td:
                td = tempfile.mkdtemp()
                mock_td.return_value.__enter__.return_value = td

                vtt_file = Path(td) / "test.vtt"
                vtt_text = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello world"
                vtt_file.write_text(vtt_text, encoding="utf-8")

                await client.get_subtitles("https://youtube.com/watch?v=123")

                # Verify that YoutubeDL was called twice (extract_info + download)
                assert mock_ytdl.call_count == EXPECTED_YTDLP_CALLS

                # First call - YoutubeDL is called with positional args (options dict)
                first_call_args, _first_call_kwargs = mock_ytdl.call_args_list[0]
                opts = first_call_args[0]  # First positional argument is the options dict
                assert "cookiefile" in opts
                assert opts["cookiefile"] == cookies_path

                # Clean up
                shutil.rmtree(td)
        finally:
            # Clean up cookies file
            Path(cookies_path).unlink(missing_ok=True)

    @patch("ssmcp.youtube_client.yt_dlp.YoutubeDL")
    async def test_get_subtitles_without_cookies_file(
        self,
        mock_ytdl: MagicMock,
    ) -> None:
        """Test that cookies file is not passed when it doesn't exist."""
        client = YouTubeClient(language="en", cookies_path="/nonexistent/path/cookies.txt")

        mock_instance = mock_ytdl.return_value.__enter__.return_value
        mock_instance.extract_info.return_value = {
            "subtitles": {"en": [{"url": "http://example.com/en.vtt"}]},
            "automatic_captions": {}
        }

        with patch("tempfile.TemporaryDirectory") as mock_td:
            td = tempfile.mkdtemp()
            mock_td.return_value.__enter__.return_value = td

            vtt_file = Path(td) / "test.vtt"
            vtt_text = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello world"
            vtt_file.write_text(vtt_text, encoding="utf-8")

            await client.get_subtitles("https://youtube.com/watch?v=123")

            # Verify that YoutubeDL was called twice (extract_info + download)
            assert mock_ytdl.call_count == EXPECTED_YTDLP_CALLS

            # First call - YoutubeDL is called with positional args (options dict)
            first_call_args, _first_call_kwargs = mock_ytdl.call_args_list[0]
            opts = first_call_args[0]  # First positional argument is the options dict
            assert "cookiefile" not in opts

            # Clean up
            shutil.rmtree(td)

    def test_select_language_configured_available(self, client: YouTubeClient) -> None:
        """Test that _select_language returns configured language when available."""
        subtitles: dict[str, Any] = {"en": [{"url": "http://example.com/en.vtt"}]}
        auto_captions: dict[str, Any] = {}

        result = client._select_language(subtitles, auto_captions)

        assert result == "en"

    def test_select_language_falls_back_to_fallback(self, client: YouTubeClient) -> None:
        """Test fallback to 'en' when configured language not available."""
        client._language = "es"  # Spanish not available
        subtitles: dict[str, Any] = {"en": [{"url": "http://example.com/en.vtt"}]}
        auto_captions: dict[str, Any] = {}

        result = client._select_language(subtitles, auto_captions)

        assert result == FALLBACK_LANGUAGE  # Should fall back to "en"

    def test_select_language_prefers_auto_captions(self, client: YouTubeClient) -> None:
        """Test that auto-captions are used when no manual subtitles available."""
        subtitles: dict[str, Any] = {}
        auto_captions: dict[str, Any] = {"en": [{"url": "http://example.com/auto.vtt"}]}

        result = client._select_language(subtitles, auto_captions)

        assert result == "en"

    def test_select_language_falls_back_to_any_subtitle(self, client: YouTubeClient) -> None:
        """Test fallback to any available subtitle when neither configured nor fallback."""
        client._language = "de"  # German not available
        # French available
        subtitles: dict[str, Any] = {"fr": [{"url": "http://example.com/fr.vtt"}]}
        auto_captions: dict[str, Any] = {}

        result = client._select_language(subtitles, auto_captions)

        assert result == "fr"

    def test_select_language_falls_back_to_any_auto(self, client: YouTubeClient) -> None:
        """Test fallback to any available auto-caption when no subtitles at all."""
        client._language = "de"
        subtitles: dict[str, Any] = {}
        # Spanish auto
        auto_captions: dict[str, Any] = {"es": [{"url": "http://example.com/es.vtt"}]}

        result = client._select_language(subtitles, auto_captions)

        assert result == "es"

    def test_select_language_returns_none_when_empty(self, client: YouTubeClient) -> None:
        """Test that None is returned when no subtitles or auto-captions available."""
        subtitles: dict[str, Any] = {}
        auto_captions: dict[str, Any] = {}

        result = client._select_language(subtitles, auto_captions)

        assert result is None

    def test_select_language_prefers_configured(self, client: YouTubeClient) -> None:
        """Test that configured language is preferred over fallback when both available."""
        client._language = "es"
        subtitles: dict[str, Any] = {
            "es": [{"url": "http://example.com/es.vtt"}],
            "en": [{"url": "http://example.com/en.vtt"}],
        }
        auto_captions: dict[str, Any] = {}

        result = client._select_language(subtitles, auto_captions)

        # Should prefer Spanish (configured) over English (fallback)
        assert result == "es"

    def test_select_language_prefers_subtitles(self, client: YouTubeClient) -> None:
        """Test that manual subtitles are preferred over auto-captions."""
        subtitles: dict[str, Any] = {"en": [{"url": "http://example.com/en.vtt"}]}
        auto_captions: dict[str, Any] = {"en": [{"url": "http://example.com/auto.vtt"}]}

        result = client._select_language(subtitles, auto_captions)

        # Returns en, and subtitles take precedence in implementation
        assert result == "en"


@pytest.fixture
def youtube_client() -> YouTubeClient:
    """Create a YouTube client for VTT parsing tests."""
    return YouTubeClient(language="en")


class TestYouTubeVTTParsing:
    """Test YouTube VTT subtitle parsing."""

    def test_parse_vtt_basic(self, youtube_client: YouTubeClient) -> None:
        """Test basic VTT parsing."""
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:05.000
Hello world

00:00:06.000 --> 00:00:10.000
This is a test"""

        result = youtube_client._parse_vtt(vtt_content)

        assert "[00:00:01.000] Hello world" in result
        assert "[00:00:06.000] This is a test" in result

    def test_parse_vtt_with_cue_settings(self, youtube_client: YouTubeClient) -> None:
        """Test VTT parsing with cue settings (position, alignment)."""
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:05.000 position:50% align:middle
Content with settings

00:00:06.000 --> 00:00:10.000 line:90%
More content"""

        result = youtube_client._parse_vtt(vtt_content)

        assert "Content with settings" in result
        assert "More content" in result

    def test_parse_vtt_empty_cues_skipped(self, youtube_client: YouTubeClient) -> None:
        """Test VTT parsing skips empty/whitespace cues."""
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:05.000

00:00:06.000 --> 00:00:10.000
Valid text"""

        result = youtube_client._parse_vtt(vtt_content)

        # Empty cues should be skipped
        assert "Valid text" in result
        # Should only have one line (empty cue skipped)
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == 1

    def test_parse_vtt_multiline_cues_joined(self, youtube_client: YouTubeClient) -> None:
        """Test VTT parsing with multiline cues."""
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:05.000
Line 1
Line 2
Line 3"""

        result = youtube_client._parse_vtt(vtt_content)

        # Should join lines with spaces
        assert "Line 1 Line 2 Line 3" in result

    def test_parse_vtt_with_deduplication(self, youtube_client: YouTubeClient) -> None:
        """Test VTT parsing with rolling caption deduplication."""
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:03.000
Hello world today

00:00:03.000 --> 00:00:05.000
world today is great

00:00:05.000 --> 00:00:07.000
today is wonderful"""

        result = youtube_client._parse_vtt(vtt_content)

        # Should deduplicate overlapping text
        assert "[00:00:01.000] Hello world today" in result
        # Overlapping words should be removed
        assert "is great" in result
        assert "is wonderful" in result

    def test_parse_vtt_empty_content(self, youtube_client: YouTubeClient) -> None:
        """Test VTT parsing with empty content."""
        vtt_content = "WEBVTT\n"

        result = youtube_client._parse_vtt(vtt_content)

        # Empty VTT should return empty string
        assert result == ""

    def test_parse_vtt_with_html_tags(self, youtube_client: YouTubeClient) -> None:
        """Test VTT parsing with HTML tags in cues."""
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:05.000
<b>Bold text</b> and <i>italic</i>

00:00:06.000 --> 00:00:10.000
Text with <c.colorE5E5E5>color</c>"""

        result = youtube_client._parse_vtt(vtt_content)

        # HTML tags should be preserved in output (webvtt handles them)
        assert "Bold text" in result
        assert "italic" in result
        assert "color" in result
