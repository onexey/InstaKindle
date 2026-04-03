"""Email sender for delivering EPUB files to Kindle."""

from __future__ import annotations

import logging
import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class SenderError(Exception):
    """Raised when email sending fails."""


class KindleSender:
    """Send EPUB files to Kindle via SMTP email."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        sender_email: str,
        kindle_email: str,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_username = smtp_username
        self._smtp_password = smtp_password
        self._sender_email = sender_email
        self._kindle_email = kindle_email

    def send_epub(self, epub_path: Path, title: str) -> None:
        """Send an EPUB file to the Kindle email address.

        Args:
            epub_path: Path to the EPUB file to send.
            title: Article title (used in the email subject).

        Raises:
            SenderError: If the email could not be sent.
            FileNotFoundError: If the EPUB file does not exist.
        """
        if not epub_path.exists():
            raise FileNotFoundError(f"EPUB file not found: {epub_path}")

        msg = self._build_message(epub_path, title)

        try:
            logger.info("Sending '%s' to %s...", title, self._kindle_email)
            context = ssl.create_default_context()

            with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=60) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(self._smtp_username, self._smtp_password)
                server.send_message(msg)

            logger.info("Successfully sent '%s' to Kindle", title)

        except smtplib.SMTPException as e:
            raise SenderError(f"Failed to send email: {e}") from e
        except OSError as e:
            raise SenderError(f"Network error while sending email: {e}") from e

    def _build_message(self, epub_path: Path, title: str) -> MIMEMultipart:
        """Build the email message with EPUB attachment.

        Args:
            epub_path: Path to the EPUB file.
            title: Article title for the email subject.

        Returns:
            Constructed MIME message.
        """
        msg = MIMEMultipart()
        msg["From"] = self._sender_email
        msg["To"] = self._kindle_email
        msg["Subject"] = title

        # Amazon's Send-to-Kindle service uses the subject line as the book title
        body = f"Sent by InstaKindle: {title}"
        msg.attach(MIMEText(body, "plain"))

        # Attach the EPUB file
        with open(epub_path, "rb") as f:
            attachment = MIMEBase("application", "epub+zip")
            attachment.set_payload(f.read())

        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            f"attachment; filename={epub_path.name}",
        )
        msg.attach(attachment)

        return msg
