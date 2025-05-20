# ADK Voice Agent Project Documentation

## Project Overview

The ADK Voice Agent is an intelligent voice assistant application that integrates with Google Calendar to provide seamless scheduling capabilities through natural language interaction. The assistant can be interacted with via both voice and text interfaces, making it accessible across different interaction modalities.

## Business Value

### Problem Addressed
- **Calendar Management Friction**: Traditional calendar management requires manual navigation of interfaces and multiple clicks
- **Time Constraints**: Busy professionals need quick ways to check and update their schedules
- **Accessibility**: Text-based interfaces can be inaccessible for certain users or contexts

### Value Proposition
- **Efficiency**: Reduce time spent on calendar management by up to 70% through voice commands
- **Accessibility**: Provide hands-free scheduling for mobile or accessibility scenarios
- **Natural Interaction**: Eliminate learning curve with natural language processing
- **Reduced Context Switching**: Allow checking schedules without interrupting workflow

### Target Users
- Executives and managers with packed schedules
- Field workers who need hands-free operation
- Accessibility-focused organizations
- General office workers managing multiple meetings

## Technical Architecture

### Technology Stack
- **Frontend**: HTML, CSS, JavaScript (with WebSocket support)
- **Backend**: Python FastAPI server
- **AI**: Google's Agent Development Kit (ADK) with Gemini 2.0 Flash model
- **APIs**: Google Calendar API
- **Authentication**: OAuth 2.0 for Google services

### System Components

1. **Web Interface**
   - Provides text and voice interfaces
   - Handles audio recording and playback
   - Communicates with backend via WebSockets

2. **FastAPI Server**
   - Routes requests between client and agent
   - Manages WebSocket connections
   - Handles authentication with Google services

3. **ADK Agent Framework**
   - Processes natural language with Gemini AI
   - Manages conversation flow
   - Dispatches to appropriate tools

4. **Calendar Tools**
   - `list_events`: Retrieves and displays calendar events
   - `create_event`: Creates new calendar events
   - `edit_event`: Modifies existing events
   - `delete_event`: Removes events from calendar

5. **Authentication System**
   - Handles Google OAuth flow
   - Securely stores authentication tokens
   - Manages API access permissions

### Data Flow

```
User Input (Voice/Text) → Web Interface → WebSocket → FastAPI Server → ADK Agent 
→ Gemini AI Processing → Calendar Tools → Google Calendar API → Response Generation 
→ WebSocket → Web Interface → User Output (Voice/Text)
```

## Development Information

### Prerequisites
- Python 3.8+
- Google Cloud Project with Calendar API enabled
- Gemini API key
- OAuth 2.0 credentials

### Local Development Setup
1. Clone the repository
2. Create virtual environment: `python -m venv .venv`
3. Install dependencies: `pip install -r requirements.txt`
4. Set up environment variables in `.env` file:
   ```
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```
5. Run the OAuth setup: `python setup_calendar_auth.py`
6. Start the server: `uvicorn main:app --reload`

### Key Files and Directories
- `/app/main.py`: Main application server and WebSocket handling
- `/app/jarvis/agent.py`: ADK agent configuration
- `/app/jarvis/tools/`: Calendar integration tools
- `/app/static/`: Web interface assets

### Agent Configuration
The ADK agent is configured in `app/jarvis/agent.py` with:
- Model: Gemini 2.0 Flash
- Tools: Calendar operations (list, create, edit, delete)
- Instructions: Guidelines for handling calendar queries

## Deployment Guidelines

### Production Requirements
- HTTPS for secure communication
- Proper OAuth consent screen configuration for production
- Rate limiting for API calls
- Error monitoring and logging

### Deployment Options
1. **Cloud Run/App Engine**: Containerized deployment on Google Cloud
2. **Kubernetes**: For scalable, multi-instance deployment
3. **VM/VPS**: Traditional server deployment

## Roadmap and Future Enhancements

### Short-term Enhancements
- Multiple calendar support
- Meeting reminders and notifications
- Find free time slot functionality
- Meeting notes integration

### Long-term Vision
- Integration with other productivity tools (email, tasks)
- Multi-user meeting scheduling
- Advanced natural language understanding for complex requests
- Mobile application integration

## Support and Troubleshooting

### Common Issues
- Authentication errors (see README.md for reset instructions)
- Permission issues with Google Calendar
- API quota limitations
- Package dependency conflicts

### Support Resources
- Project README for setup troubleshooting
- Google ADK Documentation
- Google Calendar API Documentation

## Maintenance Guidelines

### Code Standards
- PEP 8 for Python code
- Comprehensive docstrings
- Unit tests for critical components

### Update Procedures
1. Regular dependency updates with security patches
2. ADK version compatibility checks
3. Google Calendar API version monitoring

---

Document Version: 1.0
Last Updated: May 19, 2025
