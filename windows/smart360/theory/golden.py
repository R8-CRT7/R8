"""Backwards-compatible names for the internal golden set (see splits.py)."""

from smart360.theory.splits import GOLDEN_DIR
from smart360.theory.splits import load_golden_internal as load_golden

__all__ = ["GOLDEN_DIR", "load_golden"]
