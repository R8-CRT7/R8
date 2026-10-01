"""360 SMART - AI Driving Theory Assistant."""

__version__ = "0.5.0-alpha.3"
APP_NAME = "360 SMART"
TAGLINE = "AI Driving Theory Assistant"

try:  # written by the CI build (commit + run), absent in a source checkout
    from smart360._build import BUILD  # type: ignore[import-not-found]
except ImportError:
    BUILD = "dev (source checkout)"
