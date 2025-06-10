"""
Conversation Memory Module for ADK Voice Agent

This module implements memory capabilities for multi-turn conversations with the
Google Calendar integration assistant.
"""

import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

# Memory store for conversations
class ConversationMemory:
    """Conversation memory store for the ADK Voice Agent"""
    
    def __init__(self, max_history: int = 10):
        """Initialize the conversation memory store
        
        Args:
            max_history: Maximum number of messages to store per session
        """
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.max_history = max_history
    
    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a message to the conversation memory
        
        Args:
            session_id: The unique session identifier
            role: Message role ('user' or 'model')
            content: Message content
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "messages": [],
                "created_at": time.time(),
                "last_updated": time.time(),
                "entities": {},
                "preferences": {}
            }
        
        # Add message with timestamp
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        # Update the session
        self.sessions[session_id]["messages"].append(message)
        self.sessions[session_id]["last_updated"] = time.time()
        
        # Trim history if needed
        if len(self.sessions[session_id]["messages"]) > self.max_history:
            self.sessions[session_id]["messages"] = self.sessions[session_id]["messages"][-self.max_history:]
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get the conversation history for a session
        
        Args:
            session_id: The unique session identifier
            
        Returns:
            List of messages in the conversation
        """
        if session_id not in self.sessions:
            return []
        
        return self.sessions[session_id]["messages"]
    
    def add_entity(self, session_id: str, entity_type: str, entity_value: Any) -> None:
        """Add an entity to the conversation memory
        
        Args:
            session_id: The unique session identifier
            entity_type: Type of entity (e.g., 'event', 'date', 'time')
            entity_value: Entity value
        """
        if session_id not in self.sessions:
            self.add_message(session_id, "system", "Session initialized")
        
        # Initialize entities dict if not present
        if "entities" not in self.sessions[session_id]:
            self.sessions[session_id]["entities"] = {}
        
        # Store or update the entity
        self.sessions[session_id]["entities"][entity_type] = entity_value
        self.sessions[session_id]["last_updated"] = time.time()
    
    def get_entity(self, session_id: str, entity_type: str) -> Optional[Any]:
        """Get an entity from the conversation memory
        
        Args:
            session_id: The unique session identifier
            entity_type: Type of entity to retrieve
            
        Returns:
            Entity value if found, None otherwise
        """
        if (session_id not in self.sessions or 
            "entities" not in self.sessions[session_id] or
            entity_type not in self.sessions[session_id]["entities"]):
            return None
        
        return self.sessions[session_id]["entities"][entity_type]
    
    def set_preference(self, session_id: str, preference_key: str, preference_value: Any) -> None:
        """Set a user preference in the conversation memory
        
        Args:
            session_id: The unique session identifier
            preference_key: Preference key
            preference_value: Preference value
        """
        if session_id not in self.sessions:
            self.add_message(session_id, "system", "Session initialized")
        
        # Initialize preferences dict if not present
        if "preferences" not in self.sessions[session_id]:
            self.sessions[session_id]["preferences"] = {}
        
        # Store or update the preference
        self.sessions[session_id]["preferences"][preference_key] = preference_value
        self.sessions[session_id]["last_updated"] = time.time()
    
    def get_preference(self, session_id: str, preference_key: str) -> Optional[Any]:
        """Get a user preference from the conversation memory
        
        Args:
            session_id: The unique session identifier
            preference_key: Preference key to retrieve
            
        Returns:
            Preference value if found, None otherwise
        """
        if (session_id not in self.sessions or 
            "preferences" not in self.sessions[session_id] or
            preference_key not in self.sessions[session_id]["preferences"]):
            return None
        
        return self.sessions[session_id]["preferences"][preference_key]
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of the session including messages, entities, and preferences
        
        Args:
            session_id: The unique session identifier
            
        Returns:
            Session summary dictionary
        """
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        return {
            "message_count": len(self.sessions[session_id].get("messages", [])),
            "created_at": datetime.fromtimestamp(self.sessions[session_id]["created_at"]).isoformat(),
            "last_updated": datetime.fromtimestamp(self.sessions[session_id]["last_updated"]).isoformat(),
            "entities": list(self.sessions[session_id].get("entities", {}).keys()),
            "preferences": list(self.sessions[session_id].get("preferences", {}).keys())
        }
    
    def clear_session(self, session_id: str) -> None:
        """Clear a session from the conversation memory
        
        Args:
            session_id: The unique session identifier
        """
        if session_id in self.sessions:
            del self.sessions[session_id]

# Create a global instance to be imported by other modules
conversation_memory = ConversationMemory()
