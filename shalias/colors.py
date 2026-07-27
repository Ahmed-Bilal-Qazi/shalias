"""
Terminal color helpers.
All output goes through _g / _r / _y / _b / _d / _cy so that
NO_COLOR and non-tty environments are handled in one place.
"""
import os
import sys

_USE_COLOR = None


def _use_color() -> bool:
    global _USE_COLOR
    if _USE_COLOR is None:
        _USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    return _USE_COLOR


_CODES = {
    "green":  "\033[32m",
    "yellow": "\033[33m",
    "red":    "\033[31m",
    "cyan":   "\033[36m",
    "bold":   "\033[1m",
    "dim":    "\033[2m",
    "reset":  "\033[0m",
}


def _col(name: str, s: str) -> str:
    return f"{_CODES[name]}{s}{_CODES['reset']}" if _use_color() else s


def _g(s: str) -> str:  return _col("green",  s)
def _r(s: str) -> str:  return _col("red",    s)
def _y(s: str) -> str:  return _col("yellow", s)
def _b(s: str) -> str:  return _col("bold",   s)
def _d(s: str) -> str:  return _col("dim",    s)
def _cy(s: str) -> str: return _col("cyan",   s)
