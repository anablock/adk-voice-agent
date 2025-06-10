"""
Memory initialization module for the ADK Voice Agent

This module ensures the conversation memory module is properly initialized
at application startup and accessible throughout the application.

It uses the persistent memory system to ensure sessions are preserved
across server restarts and different WebSocket connections.
"""

try:
    # First try to import the persistent memory module
    from app.persistent_memory import persistent_memory
    MEMORY = persistent_memory
    MEMORY_TYPE = 'persistent'
    print("Persistent conversation memory module loaded successfully")
except ImportError:
    # Fall back to in-memory conversation memory if persistent not available
    try:
        from app.conversation_memory import conversation_memory
        MEMORY = conversation_memory
        MEMORY_TYPE = 'in-memory'
        print("Warning: Using non-persistent conversation memory (sessions will be lost on restart)")
    except ImportError:
        print("ERROR: Could not load any conversation memory module")
        raise

def get_memory():
    """Get the global memory instance"""
    return MEMORY

def add_system_message(session_id, message):
    """Add a system message to the conversation memory"""
    return MEMORY.add_message(session_id, "system", message)

def get_session_summary(session_id):
    """Get a summary of the session memory"""
    return MEMORY.get_session_summary(session_id)

def clear_session(session_id):
    """Clear a session from memory"""
    return MEMORY.clear_session(session_id)

def get_memory_type():
    """Get the type of memory being used (persistent or in-memory)"""
    return MEMORY_TYPE

# Initialize with diagnostics
print(f"Conversation memory module initialized successfully ({MEMORY_TYPE} storage)")
