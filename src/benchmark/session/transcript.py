"""Helpers for persisting full session command transcripts."""

from __future__ import annotations

from typing import List, Tuple

from benchmark.models.results import CommandTranscriptEntry
from benchmark.session.models import CommandType


def build_saved_command_logs(
    entries: List[Tuple[str, str, CommandType, bool]],
) -> tuple[List[CommandTranscriptEntry], List[str]]:
    """
    Build structured and string forms of the full command transcript.

    ``execution_log`` strings use ``node | type | command | status`` so every
    executed command (config and read) is recoverable from JSON.
    """
    transcript: List[CommandTranscriptEntry] = []
    execution_log: List[str] = []

    for node, command, command_type, success in entries:
        type_str = (
            command_type.value
            if isinstance(command_type, CommandType)
            else str(command_type)
        )
        status = "ok" if success else "fail"
        transcript.append(
            CommandTranscriptEntry(
                node=node,
                command=command,
                command_type=type_str,
                success=success,
            )
        )
        execution_log.append(f"{node} | {type_str} | {command} | {status}")

    return transcript, execution_log
