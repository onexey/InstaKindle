"""Tests for the email sender module."""

from __future__ import annotations

import shutil
import smtplib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from instakindle.sender import KindleSender, SenderError

if TYPE_CHECKING:
    from unittest.mock import MagicMock


class TestKindleSender:
    """Tests for the KindleSender."""

    def _make_sender(self) -> KindleSender:
        return KindleSender(
            smtp_host="smtp.test.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            sender_email="from@test.com",
            kindle_email="kindle@kindle.com",
        )

    def test_send_epub_file_not_found(self) -> None:
        """Should raise FileNotFoundError for missing EPUB."""
        sender = self._make_sender()
        with pytest.raises(FileNotFoundError):
            sender.send_epub(Path("/nonexistent/file.epub"), "Test")

    def test_send_epub_success(self, mock_smtp: MagicMock) -> None:
        """Should send email with EPUB attachment successfully."""
        work_dir = Path(tempfile.mkdtemp(prefix="instakindle_test_"))
        try:
            epub_file = work_dir / "test.epub"
            epub_file.write_bytes(b"fake epub content")

            sender = self._make_sender()
            sender.send_epub(epub_file, "Test Article")

            mock_smtp.ehlo.assert_called()
            mock_smtp.starttls.assert_called_once()
            mock_smtp.login.assert_called_once_with("user", "pass")
            mock_smtp.send_message.assert_called_once()
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_send_epub_smtp_error(self, mock_smtp: MagicMock) -> None:
        """Should raise SenderError on SMTP failures."""
        work_dir = Path(tempfile.mkdtemp(prefix="instakindle_test_"))
        try:
            epub_file = work_dir / "test.epub"
            epub_file.write_bytes(b"fake epub content")

            mock_smtp.send_message.side_effect = smtplib.SMTPException("Send failed")

            sender = self._make_sender()
            with pytest.raises(SenderError, match="Failed to send email"):
                sender.send_epub(epub_file, "Test Article")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_build_message(self) -> None:
        """Should build a proper MIME message with attachment."""
        work_dir = Path(tempfile.mkdtemp(prefix="instakindle_test_"))
        try:
            epub_file = work_dir / "article.epub"
            epub_file.write_bytes(b"fake epub data")

            sender = self._make_sender()
            msg = sender._build_message(epub_file, "Great Article")

            assert msg["From"] == "from@test.com"
            assert msg["To"] == "kindle@kindle.com"
            assert msg["Subject"] == "Great Article"

            # Should have 2 parts: text body + attachment
            payloads = msg.get_payload()
            assert len(payloads) == 2
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_build_message_quotes_filename(self) -> None:
        """Content-Disposition filename should be properly quoted/encoded.

        Regression test: titles with apostrophes produced malformed
        Content-Disposition headers that caused silent delivery failures.
        """
        work_dir = Path(tempfile.mkdtemp(prefix="instakindle_test_"))
        try:
            epub_file = work_dir / "Why I'm Not Worried.epub"
            epub_file.write_bytes(b"fake epub data")

            sender = self._make_sender()
            msg = sender._build_message(epub_file, "Why I'm Not Worried")

            attachment = msg.get_payload()[1]
            content_disp = attachment["Content-Disposition"]
            quoted_filename = 'filename="Why I\'m Not Worried.epub"'
            # The filename must be serialized as a quoted string or an
            # RFC 2231 encoded parameter, not as a bare unquoted value.
            assert quoted_filename in content_disp or "filename*=" in content_disp
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
