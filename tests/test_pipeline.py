"""Tests for the main pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from instakindle.converter.base import ConversionResult
from instakindle.instapaper import (
    Article,
    InstapaperArticleUnavailableError,
    InstapaperError,
)
from instakindle.pipeline import (
    _MAX_BACKOFF_SECONDS,
    FAILED_FOLDER,
    MAX_CONSECUTIVE_FAILURES,
    SENT_FOLDER,
    Pipeline,
    PipelineIterationError,
    PipelineShutdownError,
    _write_healthcheck,
)
from instakindle.sender import SenderError

if TYPE_CHECKING:
    from instakindle.config import Config


class TestPipeline:
    """Tests for the Pipeline orchestrator."""

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_no_articles(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
    ) -> None:
        """run_once should return 0 when no articles found."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = []

        pipeline = Pipeline(sample_config)
        count = pipeline.run_once()

        assert count == 0
        mock_client.get_bookmarks.assert_called_once()

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_processes_articles(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
        sample_article: Article,
    ) -> None:
        """run_once should process all articles."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = [sample_article]
        mock_client.get_article_html.return_value = "<p>Content</p>"
        mock_client.get_or_create_folder.return_value = "42"

        mock_converter = mock_converter_cls.return_value
        mock_converter.convert.return_value = ConversionResult(
            epub_path=Path("/tmp/test.epub"),
            title=sample_article.title,
            success=True,
        )

        mock_sender = mock_sender_cls.return_value

        pipeline = Pipeline(sample_config)
        count = pipeline.run_once()

        assert count == 1
        mock_client.get_article_html.assert_called_once_with(sample_article.bookmark_id)
        mock_converter.convert.assert_called_once()
        mock_sender.send_epub.assert_called_once()
        mock_client.get_or_create_folder.assert_called_once_with(SENT_FOLDER)
        mock_client.move_bookmark.assert_called_once_with(sample_article.bookmark_id, "42")

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_conversion_failure(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
        sample_article: Article,
    ) -> None:
        """run_once should raise when all articles fail conversion."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = [sample_article]
        mock_client.get_article_html.return_value = "<p>Content</p>"

        mock_converter = mock_converter_cls.return_value
        mock_converter.convert.return_value = ConversionResult(
            epub_path=Path("/tmp/test.epub"),
            title=sample_article.title,
            success=False,
            error="Conversion error",
        )

        mock_sender = mock_sender_cls.return_value

        pipeline = Pipeline(sample_config)

        with pytest.raises(PipelineIterationError):
            pipeline.run_once()

        mock_sender.send_epub.assert_not_called()
        mock_client.move_bookmark.assert_not_called()

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_empty_html(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
        sample_article: Article,
    ) -> None:
        """run_once should quarantine articles with empty HTML."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = [sample_article]
        mock_client.get_article_html.return_value = ""
        mock_client.get_or_create_folder.return_value = "failed-folder"

        mock_converter = mock_converter_cls.return_value

        pipeline = Pipeline(sample_config)

        count = pipeline.run_once()

        assert count == 0
        mock_converter.convert.assert_not_called()
        mock_client.get_or_create_folder.assert_called_once_with(FAILED_FOLDER)
        mock_client.move_bookmark.assert_called_once_with(
            sample_article.bookmark_id,
            "failed-folder",
        )

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_send_failure(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
        sample_article: Article,
    ) -> None:
        """Articles that fail sending should not be tagged/archived."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = [sample_article]
        mock_client.get_article_html.return_value = "<p>Content</p>"

        mock_converter = mock_converter_cls.return_value
        mock_converter.convert.return_value = ConversionResult(
            epub_path=Path("/tmp/test.epub"),
            title=sample_article.title,
            success=True,
        )

        mock_sender = mock_sender_cls.return_value
        mock_sender.send_epub.side_effect = SenderError("SMTP failed")

        pipeline = Pipeline(sample_config)

        with pytest.raises(PipelineIterationError):
            pipeline.run_once()

        mock_client.move_bookmark.assert_not_called()

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_multiple_articles_partial_failure(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
    ) -> None:
        """Should continue processing other articles if one fails."""
        article1 = Article(bookmark_id=1, title="Article 1", url="https://a.com")
        article2 = Article(bookmark_id=2, title="Article 2", url="https://b.com")

        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = [article1, article2]
        mock_client.get_article_html.side_effect = [
            InstapaperError("API error"),  # article1 fails
            "<p>Content 2</p>",  # article2 succeeds
        ]
        mock_client.get_or_create_folder.return_value = "42"

        mock_converter = mock_converter_cls.return_value
        mock_converter.convert.return_value = ConversionResult(
            epub_path=Path("/tmp/test.epub"),
            title="Article 2",
            success=True,
        )

        pipeline = Pipeline(sample_config)
        count = pipeline.run_once()

        assert count == 1  # Only article2 succeeded

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_quarantines_permanent_fetch_errors(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
        sample_article: Article,
    ) -> None:
        """Non-retriable fetch failures should be quarantined without failing the run."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = [sample_article]
        mock_client.get_article_html.side_effect = InstapaperArticleUnavailableError(
            "Instapaper could not provide HTML for bookmark 12345 (status=400)"
        )
        mock_client.get_or_create_folder.return_value = "failed-folder"

        pipeline = Pipeline(sample_config)
        count = pipeline.run_once()

        assert count == 0
        mock_client.get_or_create_folder.assert_called_once_with(FAILED_FOLDER)
        mock_client.move_bookmark.assert_called_once_with(
            sample_article.bookmark_id,
            "failed-folder",
        )


class TestPipelineCleanup:
    """Tests for pipeline cleanup behavior."""

    def test_cleanup_removes_temp_dir(self) -> None:
        """Should remove temp directories under /tmp."""
        import tempfile

        temp_dir = Path(tempfile.mkdtemp(prefix="instakindle_"))
        (temp_dir / "test.epub").write_bytes(b"data")

        Pipeline._cleanup(temp_dir)
        assert not temp_dir.exists()

    def test_cleanup_ignores_non_tmp_dir(self) -> None:
        """Should not remove directories outside /tmp."""

        # Create a temp directory under the user's home, not under /tmp
        home = Path.home()
        test_dir = home / ".instakindle_test_cleanup"
        test_dir.mkdir(exist_ok=True)
        test_file = test_dir / "file.txt"
        test_file.write_text("keep")

        try:
            Pipeline._cleanup(test_dir)
            assert test_dir.exists()
        finally:
            import shutil

            shutil.rmtree(test_dir, ignore_errors=True)


class TestRunForever:
    """Tests for run_forever backoff, failure tracking, and shutdown."""

    @patch("instakindle.pipeline.time.sleep")
    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_exits_after_max_consecutive_failures(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_sleep: MagicMock,
        sample_config: Config,
    ) -> None:
        """run_forever should raise PipelineShutdownError after MAX_CONSECUTIVE_FAILURES."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.side_effect = InstapaperError("auth failed")

        pipeline = Pipeline(sample_config)

        with pytest.raises(PipelineShutdownError):
            pipeline.run_forever()
        assert mock_client.get_bookmarks.call_count == MAX_CONSECUTIVE_FAILURES

    @patch("instakindle.pipeline.time.sleep")
    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_failure_counter_resets_on_success(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_sleep: MagicMock,
        sample_config: Config,
    ) -> None:
        """A successful run_once should reset the consecutive failure counter."""
        call_count = 0

        mock_client = mock_client_cls.return_value

        def fake_get_bookmarks() -> list[Article]:
            nonlocal call_count
            call_count += 1
            # Fail 9 times (just under the limit), succeed on call 10,
            # then fail once more and use escape hatch on call 12.
            if call_count == MAX_CONSECUTIVE_FAILURES:
                return []  # success — resets counter
            if call_count == MAX_CONSECUTIVE_FAILURES + 2:
                raise SystemExit(99)  # escape hatch
            raise InstapaperError("API error")

        mock_client.get_bookmarks.side_effect = fake_get_bookmarks

        pipeline = Pipeline(sample_config)

        with (
            patch("instakindle.pipeline._write_healthcheck"),
            pytest.raises(SystemExit) as exc_info,
        ):
            pipeline.run_forever()

        # Should have hit our escape hatch, not the MAX_CONSECUTIVE_FAILURES exit
        assert exc_info.value.code == 99
        assert call_count == MAX_CONSECUTIVE_FAILURES + 2

    @patch("instakindle.pipeline.time.sleep")
    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_exponential_backoff_on_failures(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_sleep: MagicMock,
        sample_config: Config,
    ) -> None:
        """Sleep time should increase exponentially on consecutive failures."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.side_effect = InstapaperError("API error")

        pipeline = Pipeline(sample_config)

        with pytest.raises(PipelineShutdownError):
            pipeline.run_forever()

        poll = sample_config.poll_interval
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]

        # First failure: poll * 2^1, second: poll * 2^2, etc.
        assert sleep_calls[0] == poll * 2  # 2^1
        assert sleep_calls[1] == poll * 4  # 2^2
        assert sleep_calls[2] == poll * 8  # 2^3
        assert sleep_calls[3] == poll * 16  # 2^4

    @patch("instakindle.pipeline.time.sleep")
    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_backoff_capped_at_max(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_sleep: MagicMock,
        sample_config: Config,
    ) -> None:
        """Backoff should never exceed _MAX_BACKOFF_SECONDS."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.side_effect = InstapaperError("API error")

        pipeline = Pipeline(sample_config)

        with pytest.raises(PipelineShutdownError):
            pipeline.run_forever()

        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        for sleep_val in sleep_calls:
            assert sleep_val <= _MAX_BACKOFF_SECONDS

    @patch("instakindle.pipeline.time.sleep")
    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_no_backoff_on_success(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_sleep: MagicMock,
        sample_config: Config,
    ) -> None:
        """On success, sleep should be the normal poll_interval (poll_interval * 2^0)."""
        call_count = 0

        mock_client = mock_client_cls.return_value

        def fake_get_bookmarks() -> list[Article]:
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                raise SystemExit(0)
            return []  # success

        mock_client.get_bookmarks.side_effect = fake_get_bookmarks

        pipeline = Pipeline(sample_config)

        with patch("instakindle.pipeline._write_healthcheck"), pytest.raises(SystemExit):
            pipeline.run_forever()

        poll = sample_config.poll_interval
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        # consecutive_failures is 0, so sleep = poll_interval directly
        for s in sleep_calls:
            assert s == poll

    @patch("instakindle.pipeline.time.sleep")
    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_generic_exception_also_increments_counter(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_sleep: MagicMock,
        sample_config: Config,
    ) -> None:
        """Non-InstapaperError exceptions should also count as failures."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.side_effect = RuntimeError("unexpected")

        pipeline = Pipeline(sample_config)

        with pytest.raises(PipelineShutdownError):
            pipeline.run_forever()

        assert mock_client.get_bookmarks.call_count == MAX_CONSECUTIVE_FAILURES

    @patch("instakindle.pipeline.time.sleep")
    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_all_articles_failing_increments_counter(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_sleep: MagicMock,
        sample_config: Config,
        sample_article: Article,
    ) -> None:
        """When all articles fail processing, run_forever should count as failure."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = [sample_article]
        mock_client.get_article_html.return_value = "<p>Content</p>"

        mock_converter = mock_converter_cls.return_value
        mock_converter.convert.return_value = ConversionResult(
            epub_path=Path("/tmp/test.epub"),
            title=sample_article.title,
            success=False,
            error="Conversion error",
        )

        pipeline = Pipeline(sample_config)

        with pytest.raises(PipelineShutdownError):
            pipeline.run_forever()

        assert mock_client.get_bookmarks.call_count == MAX_CONSECUTIVE_FAILURES

    @patch("instakindle.pipeline.time.sleep")
    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_quarantined_articles_do_not_increment_failure_counter(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_sleep: MagicMock,
        sample_config: Config,
        sample_article: Article,
    ) -> None:
        """A quarantined article should count as handled, not as a failed iteration."""
        call_count = 0
        mock_client = mock_client_cls.return_value
        mock_client.get_or_create_folder.return_value = "failed-folder"

        def fake_get_bookmarks() -> list[Article]:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise SystemExit(0)
            return [sample_article]

        mock_client.get_bookmarks.side_effect = fake_get_bookmarks
        mock_client.get_article_html.side_effect = InstapaperArticleUnavailableError(
            "Instapaper could not provide HTML for bookmark 12345 (status=400)"
        )

        pipeline = Pipeline(sample_config)

        with patch("instakindle.pipeline._write_healthcheck"), pytest.raises(SystemExit):
            pipeline.run_forever()

        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_calls == [sample_config.poll_interval]


class TestWriteHealthcheck:
    """Tests for the healthcheck file writer."""

    def test_writes_timestamp_file(self, tmp_path: Path) -> None:
        """_write_healthcheck should create a file with timestamp and poll interval."""
        hc_file = tmp_path / "healthcheck"
        fixed_timestamp = 1_700_000_000.0
        with (
            patch("instakindle.pipeline.HEALTHCHECK_FILE", hc_file),
            patch("instakindle.pipeline.time.time", return_value=fixed_timestamp),
        ):
            _write_healthcheck(900)

        assert hc_file.exists()
        parts = hc_file.read_text().split()
        ts = float(parts[0])
        interval = int(parts[1])
        assert ts == fixed_timestamp
        assert interval == 900

    @patch("instakindle.pipeline.time.sleep")
    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.EbooklibConverter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_forever_writes_healthcheck_on_success(
        self,
        mock_client_cls: MagicMock,
        mock_converter_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_sleep: MagicMock,
        sample_config: Config,
        tmp_path: Path,
    ) -> None:
        """run_forever should write the healthcheck file after a successful run."""
        call_count = 0
        mock_client = mock_client_cls.return_value

        def fake_get_bookmarks() -> list[Article]:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise SystemExit(0)
            return []  # success

        mock_client.get_bookmarks.side_effect = fake_get_bookmarks

        hc_file = tmp_path / "healthcheck"
        pipeline = Pipeline(sample_config)

        with patch("instakindle.pipeline.HEALTHCHECK_FILE", hc_file), pytest.raises(SystemExit):
            pipeline.run_forever()

        assert hc_file.exists()
