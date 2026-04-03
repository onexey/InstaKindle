"""Tests for the CLI entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from instakindle.cli import build_parser, main


class TestBuildParser:
    """Tests for CLI argument parser."""

    def test_parser_has_version(self) -> None:
        parser = build_parser()
        # Version action should be registered
        assert any(
            "--version" in action.option_strings for action in parser._actions
        )

    def test_parser_accepts_all_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "--instapaper-key", "key",
            "--instapaper-secret", "secret",
            "--instapaper-username", "user",
            "--instapaper-password", "pass",
            "--kindle-email", "k@kindle.com",
            "--smtp-host", "smtp.test.com",
            "--smtp-port", "465",
            "--smtp-username", "smtp_u",
            "--smtp-password", "smtp_p",
            "--sender-email", "from@test.com",
            "--poll-interval", "300",
            "--log-level", "debug",
            "--converter", "pandoc",
        ])
        assert args.instapaper_key == "key"
        assert args.smtp_port == 465
        assert args.converter == "pandoc"

    def test_parser_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.instapaper_key is None
        assert args.smtp_port is None


class TestMain:
    """Tests for the main entry point."""

    @patch("instakindle.cli.Pipeline")
    @patch("instakindle.cli.load_config")
    def test_main_validation_failure(
        self, mock_load_config: MagicMock, mock_pipeline: MagicMock
    ) -> None:
        """Should return 1 when config validation fails."""
        from instakindle.config import Config

        mock_load_config.return_value = Config()  # Missing required fields

        exit_code = main([])
        assert exit_code == 1
        mock_pipeline.assert_not_called()

    @patch("instakindle.cli.Pipeline")
    @patch("instakindle.cli.load_config")
    def test_main_keyboard_interrupt(
        self, mock_load_config: MagicMock, mock_pipeline_cls: MagicMock
    ) -> None:
        """Should handle KeyboardInterrupt gracefully."""
        from instakindle.config import Config

        mock_load_config.return_value = Config(
            instapaper_key="k",
            instapaper_secret="s",
            instapaper_username="u",
            instapaper_password="p",
            kindle_email="k@kindle.com",
            smtp_host="smtp.test.com",
            smtp_username="su",
            smtp_password="sp",
            sender_email="f@test.com",
        )

        mock_pipeline_cls.return_value.run_forever.side_effect = KeyboardInterrupt

        exit_code = main([])
        assert exit_code == 0
