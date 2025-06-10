"""
Persistent Memory Module for ADK Voice Agent

This module extends the conversation memory capabilities to provide persistence
across different WebSocket connections with the same session ID.
"""

import os
import json
import time
import pickle
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

# Memory directory
MEMORY_DIR = Path(os.path.dirname(os.path.dirname(__file__))) / "memory_store"
if not MEMORY_DIR.exists():
    MEMORY_DIR.mkdir(parents=True)

class PersistentMemory:
    """Persistent memory store for the ADK Voice Agent"""
    
    def __init__(self, max_history: int = 20):
        """Initialize the persistent memory store
        
        Args:
            max_history: Maximum number of messages to store per session
        """
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.max_history = max_history
        self._load_all_sessions()
    
    def _get_session_file_path(self, session_id: str) -> Path:
        """Get the file path for a session
        
        Args:
            session_id: The unique session identifier
            
        Returns:
            Path object for the session file
        """
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return MEMORY_DIR / f"session_{safe_id}.pkl"
    
    def _load_session(self, session_id: str) -> None:
        """Load a session from disk if it exists
        
        Args:
            session_id: The unique session identifier
        """
        file_path = self._get_session_file_path(session_id)
        if file_path.exists():
            try:
                with open(file_path, 'rb') as f:
                    session_data = pickle.load(f)
                    self.sessions[session_id] = session_data
                    print(f"[MEMORY] Loaded session {session_id} from disk with {len(session_data.get('messages', []))} messages")
            except Exception as e:
                print(f"[ERROR] Failed to load session {session_id} from disk: {e}")
    
    def _save_session(self, session_id: str) -> None:
        """Save a session to disk
        
        Args:
            session_id: The unique session identifier
        """
        if session_id not in self.sessions:
            return
        
        file_path = self._get_session_file_path(session_id)
        try:
            with open(file_path, 'wb') as f:
                pickle.dump(self.sessions[session_id], f)
                print(f"[MEMORY] Saved session {session_id} to disk with {len(self.sessions[session_id].get('messages', []))} messages")
        except Exception as e:
            print(f"[ERROR] Failed to save session {session_id} to disk: {e}")
    
    def _load_all_sessions(self) -> None:
        """Load all sessions from disk"""
        try:
            for file_path in MEMORY_DIR.glob("session_*.pkl"):
                try:
                    session_id = file_path.stem.replace("session_", "")
                    with open(file_path, 'rb') as f:
                        self.sessions[session_id] = pickle.load(f)
                except Exception as e:
                    print(f"[ERROR] Failed to load session from {file_path}: {e}")
            
            print(f"[MEMORY] Loaded {len(self.sessions)} sessions from disk")
        except Exception as e:
            print(f"[ERROR] Failed to load sessions: {e}")
    
    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a message to the conversation memory
        
        Args:
            session_id: The unique session identifier
            role: Message role ('user', 'model', or 'system')
            content: Message content
        """
        # Load session if not already in memory
        if session_id not in self.sessions:
            self._load_session(session_id)
        
        # Initialize session if it doesn't exist
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
        
        # Save to disk
        self._save_session(session_id)
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get the conversation history for a session
        
        Args:
            session_id: The unique session identifier
            
        Returns:
            List of messages in the conversation
        """
        # Load session if not already in memory
        if session_id not in self.sessions:
            self._load_session(session_id)
        
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
        # Load session if not already in memory
        if session_id not in self.sessions:
            self._load_session(session_id)
        
        if session_id not in self.sessions:
            self.add_message(session_id, "system", "Session initialized")
        
        # Initialize entities dict if not present
        if "entities" not in self.sessions[session_id]:
            self.sessions[session_id]["entities"] = {}
        
        # Store or update the entity
        self.sessions[session_id]["entities"][entity_type] = entity_value
        self.sessions[session_id]["last_updated"] = time.time()
        
        # Save to disk
        self._save_session(session_id)
    
    def get_entity(self, session_id: str, entity_type: str) -> Optional[Any]:
        """Get an entity from the conversation memory
        
        Args:
            session_id: The unique session identifier
            entity_type: Type of entity to retrieve
            
        Returns:
            Entity value if found, None otherwise
        """
        # Load session if not already in memory
        if session_id not in self.sessions:
            self._load_session(session_id)
        
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
        # Load session if not already in memory
        if session_id not in self.sessions:
            self._load_session(session_id)
        
        if session_id not in self.sessions:
            self.add_message(session_id, "system", "Session initialized")
        
        # Initialize preferences dict if not present
        if "preferences" not in self.sessions[session_id]:
            self.sessions[session_id]["preferences"] = {}
        
        # Store or update the preference
        self.sessions[session_id]["preferences"][preference_key] = preference_value
        self.sessions[session_id]["last_updated"] = time.time()
        
        # Save to disk
        self._save_session(session_id)
    
    def get_preference(self, session_id: str, preference_key: str) -> Optional[Any]:
        """Get a user preference from the conversation memory
        
        Args:
            session_id: The unique session identifier
            preference_key: Preference key to retrieve
            
        Returns:
            Preference value if found, None otherwise
        """
        # Load session if not already in memory
        if session_id not in self.sessions:
            self._load_session(session_id)
        
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
        # Load session if not already in memory
        if session_id not in self.sessions:
            self._load_session(session_id)
        
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        return {
            "message_count": len(self.sessions[session_id].get("messages", [])),
            "created_at": datetime.fromtimestamp(self.sessions[session_id]["created_at"]).isoformat(),
            "last_updated": datetime.fromtimestamp(self.sessions[session_id]["last_updated"]).isoformat(),
            "entities": list(self.sessions[session_id].get("entities", {}).keys()),
            "preferences": list(self.sessions[session_id].get("preferences", {}).keys()),
            "file_path": str(self._get_session_file_path(session_id))
        }
    
    def clear_session(self, session_id: str) -> None:
        """Clear a session from the conversation memory
        
        Args:
            session_id: The unique session identifier
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
        
        # Delete file if it exists
        file_path = self._get_session_file_path(session_id)
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"[MEMORY] Deleted session file for {session_id}")
            except Exception as e:
                print(f"[ERROR] Failed to delete session file for {session_id}: {e}")

# Create a global instance to be imported by other modules
persistent_memory = PersistentMemory()
