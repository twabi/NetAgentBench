"""
Conversation Manager for Multi-Agent System.

Manages conversation IDs and message history for benchmark runs,
supporting both multi-turn (persistent) and single-turn (fresh) modes.
"""

import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from autogen_core.models import LLMMessage


@dataclass
class Conversation:
    """
    Represents a single conversation context.
    
    Attributes:
        id: Unique conversation identifier
        messages: List of LLM messages in the conversation
        metadata: Additional context data (task info, etc.)
    """
    id: str
    messages: List[LLMMessage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def clear_messages(self) -> None:
        """Clear all messages from conversation history."""
        self.messages = []
    
    def add_message(self, message: LLMMessage) -> None:
        """Add a message to the conversation history."""
        self.messages.append(message)
    
    def get_messages(self) -> List[LLMMessage]:
        """Get all messages in conversation order."""
        return self.messages.copy()


class ConversationManager:
    """
    Manages conversation IDs and history for benchmark runs.
    
    Supports:
    - Multi-turn mode: Same conversation ID across multiple task iterations
    - Single-turn mode: Fresh conversation per task, no history leakage
    
    Example usage:
        manager = ConversationManager()
        
        # Single-turn: new conversation per task
        conv_id = manager.new_conversation(task_id="task_001")
        
        # Multi-turn: reuse conversation
        conv = manager.get_or_create("session_123")
        conv.add_message(user_message)
    """
    
    def __init__(self):
        self._conversations: Dict[str, Conversation] = {}
        self._current_id: Optional[str] = None
    
    def new_conversation(self, task_id: str = None) -> Conversation:
        """
        Create a new conversation with fresh ID and empty history.
        
        Args:
            task_id: Optional task ID to use as conversation ID
            
        Returns:
            New Conversation object
        """
        conv_id = task_id or str(uuid.uuid4())
        conversation = Conversation(id=conv_id)
        self._conversations[conv_id] = conversation
        self._current_id = conv_id
        return conversation
    
    def get_or_create(self, conversation_id: str) -> Conversation:
        """
        Get existing conversation or create new one.
        
        Used for multi-turn mode where the same conversation
        persists across multiple iterations.
        
        Args:
            conversation_id: ID to look up or create
            
        Returns:
            Existing or new Conversation object
        """
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = Conversation(id=conversation_id)
        self._current_id = conversation_id
        return self._conversations[conversation_id]
    
    def get_current(self) -> Optional[Conversation]:
        """Get the current active conversation."""
        if self._current_id and self._current_id in self._conversations:
            return self._conversations[self._current_id]
        return None
    
    def append_message(
        self, 
        message: LLMMessage, 
        conversation_id: str = None
    ) -> None:
        """
        Append message to conversation history.
        
        Args:
            message: LLM message to append
            conversation_id: Target conversation (uses current if not specified)
        """
        cid = conversation_id or self._current_id
        if cid and cid in self._conversations:
            self._conversations[cid].add_message(message)
    
    def get_history(self, conversation_id: str = None) -> List[LLMMessage]:
        """
        Get conversation history.
        
        Args:
            conversation_id: Target conversation (uses current if not specified)
            
        Returns:
            List of messages in conversation order
        """
        cid = conversation_id or self._current_id
        if cid and cid in self._conversations:
            return self._conversations[cid].get_messages()
        return []
    
    def clear(self, conversation_id: str = None) -> None:
        """
        Clear conversation history.
        
        Used in single-turn mode to reset between tasks.
        
        Args:
            conversation_id: Target conversation (uses current if not specified)
        """
        cid = conversation_id or self._current_id
        if cid and cid in self._conversations:
            self._conversations[cid].clear_messages()
    
    def delete(self, conversation_id: str) -> bool:
        """
        Delete a conversation entirely.
        
        Args:
            conversation_id: ID of conversation to delete
            
        Returns:
            True if deleted, False if not found
        """
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            if self._current_id == conversation_id:
                self._current_id = None
            return True
        return False
    
    @property
    def active_conversations(self) -> int:
        """Number of active conversations being tracked."""
        return len(self._conversations)
