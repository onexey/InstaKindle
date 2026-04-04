"""CLI entry point for InstaKindle."""

from __future__ import annotations

import argparse
import logging
import sys

from instakindle import __version__
from instakindle.config import load_config
from instakindle.pipeline import Pipeline, PipelineShutdownError

logger = logging.getLogger("instakindle")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="instakindle",
        description="Fetch Instapaper articles, convert to ebooks, deliver to Kindle.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"InstaKindle {__version__}",
    )

    # Instapaper credentials
    parser.add_argument("--instapaper-key", help="Instapaper OAuth consumer key")
    parser.add_argument("--instapaper-secret", help="Instapaper OAuth consumer secret")
    parser.add_argument("--instapaper-username", help="Instapaper account email/username")
    parser.add_argument("--instapaper-password", help="Instapaper account password")

    # Kindle
    parser.add_argument("--kindle-email", help="Kindle Send-to-Kindle email address")

    # SMTP
    parser.add_argument("--smtp-host", help="SMTP server hostname")
    parser.add_argument("--smtp-port", type=int, help="SMTP server port (default: 587)")
    parser.add_argument("--smtp-username", help="SMTP login username")
    parser.add_argument("--smtp-password", help="SMTP login password")
    parser.add_argument("--sender-email", help="Email address to send from")

    # Runtime
    parser.add_argument(
        "--poll-interval",
        type=int,
        help="Seconds between fetch cycles (default: 900)",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warn", "error"],
        help="Logging verbosity (default: info)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Convert argparse namespace to dict, mapping CLI flag names to config field names
    cli_overrides = {
        key.replace("-", "_"): value for key, value in vars(args).items() if value is not None
    }

    # Load configuration
    config = load_config(cli_overrides)

    # Set up logging
    logging.basicConfig(
        level=config.log_level_int,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )

    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(error)
        return 1

    # Run the pipeline
    try:
        pipeline = Pipeline(config)
        pipeline.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except PipelineShutdownError:
        logger.critical("Pipeline shut down due to repeated failures")
        return 1
    except Exception:
        logger.exception("Fatal error")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
