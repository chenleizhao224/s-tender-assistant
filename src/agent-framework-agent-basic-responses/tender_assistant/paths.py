"""Stable service paths, independent of module depth or working directory."""
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent.parent
