"""Small, dependency-free helpers for readable console output."""

from __future__ import annotations


def print_header(title: str, width: int = 64) -> None:
    """Print a prominent section heading."""
    print("=" * width)
    print(title)
    print("=" * width)


def print_subheader(title: str, width: int = 64) -> None:
    """Print a secondary heading."""
    print()
    print(title)
    print("-" * min(width, max(len(title), 12)))


def print_success(message: str) -> None:
    """Print a successful check."""
    print(f"[OK] {message}")


def print_warning(message: str) -> None:
    """Print a warning."""
    print(f"[WARNING] {message}")


def print_error(message: str) -> None:
    """Print an error."""
    print(f"[ERROR] {message}")
