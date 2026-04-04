"""Allow running instakindle as a module: python -m instakindle."""

import sys

from instakindle.cli import main

sys.exit(main())
