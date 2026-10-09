"""Readline-backed REPL input with persistent command history."""

from __future__ import annotations

import atexit
from pathlib import Path
from typing import Callable

_READLINE_ENABLED = False
_SETUP_DONE = False


def setup_repl_readline(history_name: str = "netagentbench") -> bool:
    """
    Enable GNU readline for ``input()`` (Up/Down history, line editing).

    Returns True when readline is active, False when unavailable (e.g. Windows
    without pyreadline).
    """
    global _READLINE_ENABLED, _SETUP_DONE

    if _SETUP_DONE:
        return _READLINE_ENABLED

    _SETUP_DONE = True

    try:
        import readline
    except ImportError:
        return False

    history_path = Path.home() / f".{history_name}_history"
    try:
        if history_path.exists():
            readline.read_history_file(history_path)
    except (OSError, FileNotFoundError):
        pass

    readline.set_history_length(2000)

    def _save_history() -> None:
        try:
            readline.write_history_file(history_path)
        except OSError:
            pass

    atexit.register(_save_history)
    _READLINE_ENABLED = True
    return True


def default_repl_input(prompt: str) -> str:
    """Default prompt reader; readline hooks in when setup ran successfully."""
    return input(prompt)


def create_repl_input_fn(history_name: str = "netagentbench") -> Callable[[str], str]:
    """Return an input function with readline history enabled when possible."""
    setup_repl_readline(history_name)
    return default_repl_input
