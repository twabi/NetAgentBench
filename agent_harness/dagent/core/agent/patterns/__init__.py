"""
Design patterns for multi-agent orchestration against NetAgentBench MCP.

Adaptive pattern is omitted in this snapshot (experiments use the remaining structures).
"""

from .base import BasePattern
from .single import SingleAgentPattern
from .sequential import SequentialPattern
from .concurrent import ConcurrentPattern
from .debate import DebatePattern
from .group_chat import GroupChatPattern

__all__ = [
    "BasePattern",
    "SingleAgentPattern",
    "SequentialPattern",
    "ConcurrentPattern",
    "DebatePattern",
    "GroupChatPattern",
]
