"""Compatibility exports for the `shopfront` package during package split."""

from importlib import import_module

__all__ = ["recommendations"]


def __getattr__(name: str):
    if name == "recommendations":
        return import_module(".recommendation.heuristics", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
