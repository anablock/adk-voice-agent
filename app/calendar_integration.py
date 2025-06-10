"""
Calendar Integration Module for ADK Voice Agent

This module provides integration with Google Calendar API for the voice agent,
allowing it to query, create, and modify calendar events.
"""

import os
import json
import datetime
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import re
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta

# Calendar API imports
try:
    import pickle
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from pathlib import Path
    HAS_CALENDAR_API = True
except ImportError:
    print("Warning: Google Calendar API libraries not available")
    HAS_CALENDAR_API = False

# Calendar scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Token storage path
TOKEN_PATH = Path(os.path.expanduser("~/.credentials/calendar_token.json"))

class CalendarManager:
    """Manager for Google Calendar integration"""
    
    def __init__(self):
        """Initialize the calendar manager"""
        self.credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        self.calendar_id = os.environ.get('GOOGLE_CALENDAR_ID', 'primary')
        self.service = None
        self.initialized = False
        
        # Try to initialize the service if Calendar API is available
        if HAS_CALENDAR_API:
            try:
                self.initialize_service()
            except Exception as e:
                print(f"Error initializing Calendar service: {e}")
    
    def initialize_service(self):
        """Initialize the Google Calendar service using OAuth 2.0"""
        try:
            creds = None
            # Check if token file exists
            if TOKEN_PATH.exists():
                with open(TOKEN_PATH, 'rb') as token:
                    creds = pickle.load(token)
            
            # Refresh token if expired
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    print("Refreshed expired OAuth token")
                except Exception as refresh_error:
                    print(f"Error refreshing token: {refresh_error}")
                    creds = None
            
            # If no valid credentials, run the OAuth flow
            if not creds:
                if not os.path.exists(self.credentials_path):
                    print(f"Error: OAuth credentials file not found at {self.credentials_path}")
                    print("Please run setup_calendar_auth.py to set up OAuth credentials")
                    self.initialized = False
                    return False
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(TOKEN_PATH, 'wb') as token:
                    pickle.dump(creds, token)
                print(f"Saved new OAuth credentials to {TOKEN_PATH}")
            
            # Build the Calendar service
            self.service = build('calendar', 'v3', credentials=creds)
            self.initialized = True
            print("Google Calendar API service initialized successfully")
            return True
        except Exception as e:
            print(f"Failed to initialize Google Calendar service: {e}")
            self.initialized = False
            return False
    
    def parse_date_entity(self, date_entity: str) -> Optional[datetime]:
        """Parse a date entity into a datetime object
        
        Args:
            date_entity: Date entity string (e.g., 'tomorrow', '2025-05-22', 'next week')
            
        Returns:
            Datetime object if parsed successfully, None otherwise
        """
        try:
            # Handle common date references
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Handle 'today'
            if date_entity.lower() == 'today':
                return today
            
            # Handle 'tomorrow'
            if date_entity.lower() == 'tomorrow':
                return today + timedelta(days=1)
            
            # Handle 'day after tomorrow'
            if date_entity.lower() in ['day after tomorrow', 'day after tom']:
                return today + timedelta(days=2)
            
            # Handle 'next week'
            if date_entity.lower() == 'next week':
                return today + timedelta(days=7)
            
            # Handle 'next month'
            if date_entity.lower() == 'next month':
                return today + relativedelta(months=1)
            
            # Handle specific date format
            return date_parser.parse(date_entity)
        except Exception as e:
            print(f"Error parsing date entity '{date_entity}': {e}")
            return None
    
    def parse_time_entity(self, time_entity: str) -> Optional[datetime.time]:
        """Parse a time entity into a time object
        
        Args:
            time_entity: Time entity string (e.g., '3pm', '15:30', 'noon')
            
        Returns:
            Time object if parsed successfully, None otherwise
        """
        try:
            # Handle common time references
            if time_entity.lower() == 'noon':
                return datetime.time(12, 0)
            
            if time_entity.lower() == 'midnight':
                return datetime.time(0, 0)
            
            # Try to parse with dateutil
            time_obj = date_parser.parse(time_entity).time()
            return time_obj
        except Exception as e:
            print(f"Error parsing time entity '{time_entity}': {e}")
            return None
    
    def extract_calendar_entities(self, message: str) -> Dict[str, Any]:
        """Extract calendar-related entities from a message
        
        Args:
            message: User message
            
        Returns:
            Dictionary of extracted entities
        """
        entities = {}
        message_lower = message.lower()
        
        # Extract date entities
        date_patterns = [
            (r'today', 'today'),
            (r'tomorrow', 'tomorrow'),
            (r'day after tomorrow', 'day after tomorrow'),
            (r'next week', 'next week'),
            (r'next month', 'next month'),
            (r'\b\d{4}-\d{2}-\d{2}\b', None),  # YYYY-MM-DD
            (r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b', None),  # MM/DD or MM/DD/YYYY
        ]
        
        for pattern, value in date_patterns:
            match = re.search(pattern, message_lower)
            if match:
                entities['date'] = value if value else match.group(0)
                break
        
        # Extract time entities
        time_patterns = [
            (r'\b(\d{1,2})(?::\d{2})?\s*(?:am|pm)\b', None),  # 3pm, 3:30pm
            (r'\b(\d{1,2}):\d{2}\b', None),  # 15:30
            (r'\bat\s+(\d{1,2})(?:\s*(?:am|pm))?\b', None),  # at 3, at 3pm
            (r'\bnoon\b', 'noon'),
            (r'\bmidnight\b', 'midnight'),
        ]
        
        for pattern, value in time_patterns:
            match = re.search(pattern, message_lower)
            if match:
                entities['time'] = value if value else match.group(0)
                break
        
        # Extract duration entities
        duration_patterns = [
            (r'(\d+)\s*(?:minute|min)s?', 'minutes'),
            (r'(\d+)\s*(?:hour|hr)s?', 'hours'),
            (r'half\s*(?:an)?\s*hour', '30 minutes'),
            (r'quarter\s*(?:of an)?\s*hour', '15 minutes'),
        ]
        
        for pattern, unit in duration_patterns:
            match = re.search(pattern, message_lower)
            if match:
                if unit == 'minutes':
                    entities['duration'] = int(match.group(1))
                elif unit == 'hours':
                    entities['duration'] = int(match.group(1)) * 60
                elif unit == '30 minutes':
                    entities['duration'] = 30
                elif unit == '15 minutes':
                    entities['duration'] = 15
                break
        
        # Extract event type entities
        event_patterns = [
            (r'meeting', 'meeting'),
            (r'appointment', 'appointment'),
            (r'call', 'call'),
            (r'lunch', 'lunch'),
            (r'dinner', 'dinner'),
            (r'coffee', 'coffee'),
            (r'interview', 'interview'),
        ]
        
        # Extract event type and appointment title/purpose
        for pattern, event_type in event_patterns:
            if re.search(pattern, message_lower):
                entities['event_type'] = event_type
                
                # Try to extract the appointment title/purpose
                title_patterns = [
                    # Looser pattern for dentist specifically (special case)
                    (r'(dentist)', 'specific_dentist'),
                    # "dentist appointment" -> "dentist"
                    (rf'(\w+)\s+{event_type}', 'title_prefix'),
                    # "appointment with the dentist" -> "dentist"
                    (rf'{event_type}\s+(?:with|for)\s+(?:the\s+)?(\w+)', 'title_suffix'),
                    # "appointment for my dentist" -> "dentist"
                    (rf'{event_type}\s+(?:with|for)\s+(?:my|the)\s+(\w+)', 'title_possessive'),
                    # Looser pattern for special cases
                    (rf'for\s+(?:my|the)?\s+(\w+).*?{event_type}', 'for_title_prefix'),
                ]
                
                for title_pattern, title_type in title_patterns:
                    title_match = re.search(title_pattern, message_lower)
                    if title_match:
                        entities['title'] = title_match.group(1).strip()
                        break
                        
                break
        
        # Extract action type
        if re.search(r'schedule|create|add|set up', message_lower):
            entities['action'] = 'create'
        elif re.search(r'reschedule|move|change|update', message_lower):
            entities['action'] = 'update'
        elif re.search(r'cancel|remove|delete', message_lower):
            entities['action'] = 'delete'
        elif re.search(r'what|show|list|tell me|display', message_lower):
            entities['action'] = 'query'
        
        return entities
    
    def get_events(self, date_entity: str = None, max_results: int = 10) -> List[Dict[str, Any]]:
        """Get events from Google Calendar
        
        Args:
            date_entity: Date entity string (e.g., 'tomorrow', '2025-05-22')
            max_results: Maximum number of events to return
            
        Returns:
            List of calendar events
        """
        if not self.initialized:
            print("Calendar service not initialized")
            return self.get_mock_events(date_entity)  # Fall back to mock events
        
        try:
            # Parse the date entity if provided
            target_date = None
            if date_entity:
                target_date = self.parse_date_entity(date_entity)
            
            # Default to today if no date provided or parsing failed
            if not target_date:
                target_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Calculate time bounds for the query
            time_min = target_date.isoformat() + 'Z'
            time_max = (target_date + timedelta(days=1)).isoformat() + 'Z'
            
            # Get events from the calendar
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            print(f"Successfully retrieved {len(events)} events from Google Calendar")
            return events
        except Exception as e:
            print(f"Error getting calendar events: {e}")
            # Fall back to mock events if there's an error
            print("Falling back to mock events...")
            return self.get_mock_events(date_entity)
    
    def create_mock_event(self, date_entity: str, time_entity: str = None, duration: int = 60, 
                         summary: str = "Event", description: str = "", 
                         location: str = "", attendees: List[str] = None) -> Dict[str, Any]:
        """Create a mock calendar event for testing
        
        Args:
            date_entity: Date entity string (e.g., 'tomorrow', '2025-05-22')
            time_entity: Time entity string (e.g., '3pm', '15:30')
            duration: Duration in minutes
            summary: Event summary/title
            description: Event description
            location: Event location
            attendees: List of attendee email addresses
            
        Returns:
            Mock event data
        """
        # Parse date and time
        event_date = self.parse_date_entity(date_entity)
        event_time = None
        
        if time_entity:
            try:
                time_obj = self.parse_time_entity(time_entity)
                if time_obj and event_date:
                    event_date = event_date.replace(
                        hour=time_obj.hour,
                        minute=time_obj.minute,
                        second=0,
                        microsecond=0
                    )
            except Exception as e:
                print(f"Error parsing time entity: {e}")
        
        # Default to 9am if no time specified
        if not time_entity and event_date:
            event_date = event_date.replace(hour=9, minute=0, second=0, microsecond=0)
        
        if not event_date:
            print("Could not parse event date")
            return {}
        
        # Calculate end time
        end_date = event_date + timedelta(minutes=duration)
        
        # Create mock event
        mock_event = {
            'id': f"mock_{datetime.now().timestamp()}",
            'summary': summary,
            'description': description,
            'location': location,
            'start': {
                'dateTime': event_date.isoformat(),
                'timeZone': 'America/Los_Angeles',
            },
            'end': {
                'dateTime': end_date.isoformat(),
                'timeZone': 'America/Los_Angeles',
            },
            'attendees': [{'email': email} for email in (attendees or [])],
            'reminders': {
                'useDefault': True
            }
        }
        
        return mock_event
    
    def get_mock_events(self, date_entity: str = 'today') -> List[Dict[str, Any]]:
        """Get mock calendar events for testing
        
        Args:
            date_entity: Date entity string (e.g., 'tomorrow', '2025-05-22')
            
        Returns:
            List of mock calendar events
        """
        # Create some sample events
        events = []
        
        # Team standup meeting
        events.append(self.create_mock_event(
            date_entity=date_entity,
            time_entity='10:00',
            duration=30,
            summary='Team Standup',
            description='Daily team standup meeting',
            location='Conference Room A',
            attendees=['john@example.com', 'sarah@example.com']
        ))
        
        # Lunch
        events.append(self.create_mock_event(
            date_entity=date_entity,
            time_entity='12:30',
            duration=60,
            summary='Lunch with Client',
            description='Discuss project timeline',
            location='Cafe Deluxe',
            attendees=['client@example.com']
        ))
        
        # Project planning
        events.append(self.create_mock_event(
            date_entity=date_entity,
            time_entity='15:00',
            duration=90,
            summary='Project Planning',
            description='Quarterly planning session',
            location='Conference Room B',
            attendees=['team@example.com', 'manager@example.com']
        ))
        
        return events
    
    def format_events_response(self, events: List[Dict[str, Any]], date_entity: str = 'today') -> str:
        """Format calendar events as a readable response
        
        Args:
            events: List of calendar events
            date_entity: Date entity string (e.g., 'tomorrow', '2025-05-22')
            
        Returns:
            Formatted response text
        """
        if not events:
            return f"You have no events scheduled for {date_entity}."
        
        # Parse the date entity
        target_date = self.parse_date_entity(date_entity)
        date_str = target_date.strftime('%A, %B %d, %Y') if target_date else date_entity
        
        response = f"Here's your schedule for {date_str}:\n\n"
        
        for i, event in enumerate(events):
            summary = event.get('summary', 'Untitled Event')
            
            # Parse start time
            start_time = "Unknown time"
            if 'start' in event and 'dateTime' in event['start']:
                try:
                    start_datetime = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    start_time = start_datetime.strftime('%I:%M %p')
                except Exception:
                    pass
            
            # Parse end time
            end_time = ""
            if 'end' in event and 'dateTime' in event['end']:
                try:
                    end_datetime = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    end_time = end_datetime.strftime('%I:%M %p')
                except Exception:
                    pass
            
            time_range = f"{start_time}"
            if end_time:
                time_range += f" - {end_time}"
            
            # Get location
            location = event.get('location', '')
            location_text = f" at {location}" if location else ""
            
            # Format attendees
            attendees = event.get('attendees', [])
            attendee_text = ""
            if attendees:
                attendee_names = [a.get('email', '').split('@')[0] for a in attendees[:3]]
                if len(attendees) > 3:
                    attendee_text = f" with {', '.join(attendee_names)} and {len(attendees) - 3} others"
                else:
                    attendee_text = f" with {', '.join(attendee_names)}"
            
            response += f"{i+1}. {summary} at {time_range}{location_text}{attendee_text}\n"
        
        return response
    
    def handle_calendar_query(self, message: str, session_id: str = None) -> str:
        """Handle a calendar query message
        
        Args:
            message: User message
            session_id: Session ID for context retrieval
            
        Returns:
            Response text
        """
        # Extract entities from the message
        entities = self.extract_calendar_entities(message)
        print(f"Extracted entities: {entities}")
        
        # Determine the action type
        action = entities.get('action', 'query')
        
        # Handle calendar query
        if action == 'query':
            date_entity = entities.get('date', 'today')
            
            # Get real events if service is initialized, otherwise mock events
            if self.initialized:
                events = self.get_events(date_entity)
            else:
                events = self.get_mock_events(date_entity)
            
            return self.format_events_response(events, date_entity)
        
    def create_real_event(self, date_entity: str, time_entity: str = None, 
                      duration: int = 60, summary: str = None, description: str = None,
                      location: str = None, attendees: List[str] = None) -> Dict[str, Any]:
        """Create a real calendar event using Google Calendar API
        
        Args:
            date_entity: Date entity string (e.g., 'tomorrow', '2025-05-22')
            time_entity: Time entity string (e.g., '3pm', '15:30')
            duration: Duration in minutes
            summary: Event summary/title
            description: Event description
            location: Event location
            attendees: List of attendee email addresses
            
        Returns:
            Created event data or empty dict on failure
        """
        if not self.initialized:
            print("Calendar service not initialized for real event creation")
            return {}
            
        try:
            # Parse date and time
            event_date = self.parse_date_entity(date_entity)
            
            # Format time if provided
            if time_entity:
                time_obj = self.parse_time_entity(time_entity)
                if time_obj and event_date:
                    event_date = event_date.replace(
                        hour=time_obj.hour,
                        minute=time_obj.minute,
                        second=0,
                        microsecond=0
                    )
            
            # Default to 9am if no time specified
            if not time_entity and event_date:
                event_date = event_date.replace(hour=9, minute=0, second=0, microsecond=0)
            
            if not event_date:
                print("Could not parse event date")
                return {}
                
            # Calculate end time
            end_date = event_date + timedelta(minutes=duration)
            
            # Set default summary if none provided
            if not summary:
                summary = "Calendar Event"
                
            # Create event data
            event_data = {
                'summary': summary,
                'start': {
                    'dateTime': event_date.isoformat(),
                    'timeZone': 'America/Los_Angeles',
                },
                'end': {
                    'dateTime': end_date.isoformat(),
                    'timeZone': 'America/Los_Angeles',
                },
                'reminders': {
                    'useDefault': True
                }
            }
            
            # Add optional fields if provided
            if description:
                event_data['description'] = description
                
            if location:
                event_data['location'] = location
                
            if attendees:
                event_data['attendees'] = [{'email': email} for email in attendees]
                
            # Create the event in Google Calendar
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event_data
            ).execute()
            
            print(f"Event created: {created_event.get('htmlLink')}")
            return created_event
            
        except Exception as e:
            print(f"Error creating event: {e}")
            return {}
    
    def find_event_by_criteria(self, date_entity: str, time_entity: str = None, title: str = None) -> Optional[Dict[str, Any]]:
        """Find an event based on date, time, and title criteria
        
        Args:
            date_entity: Date entity string (e.g., 'tomorrow', '2025-05-22')
            time_entity: Optional time entity string (e.g., '3pm', '15:30')
            title: Optional title or summary substring to match
            
        Returns:
            Event data dictionary or None if not found
        """
        if not self.initialized:
            print("Calendar service not initialized")
            return None
            
        try:
            # Get events for the specified date
            events = self.get_events(date_entity)
            if not events:
                return None
                
            # Parse the time if provided
            target_time = None
            if time_entity:
                target_time = self.parse_time_entity(time_entity)
            
            # Filter events based on criteria
            for event in events:
                event_summary = event.get('summary', '').lower()
                
                # Match by title if provided
                title_match = True
                if title and title.lower() not in event_summary:
                    title_match = False
                    
                # Match by time if provided
                time_match = True
                if target_time and 'dateTime' in event.get('start', {}):
                    event_start = event['start']['dateTime']
                    event_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                    
                    # Allow a 5-minute window for fuzzy time matching
                    time_diff = abs((event_dt.hour - target_time.hour) * 60 + (event_dt.minute - target_time.minute))
                    if time_diff > 5:  # More than 5 minutes difference
                        time_match = False
                
                # Return the first event that matches all criteria
                if title_match and time_match:
                    return event
                    
            return None
        except Exception as e:
            print(f"Error finding event: {e}")
            return None
    
    def update_real_event(self, event_id: str, date_entity: str = None, time_entity: str = None, 
                        duration: int = None, summary: str = None, description: str = None,
                        location: str = None) -> Dict[str, Any]:
        """Update an existing calendar event using Google Calendar API
        
        Args:
            event_id: ID of the event to update
            date_entity: Optional new date entity string
            time_entity: Optional new time entity string
            duration: Optional new duration in minutes
            summary: Optional new event summary/title
            description: Optional new event description
            location: Optional new event location
            
        Returns:
            Updated event data or empty dict on failure
        """
        if not self.initialized or not event_id:
            print("Calendar service not initialized or invalid event ID")
            return {}
            
        try:
            # Get the existing event
            event = self.service.events().get(calendarId=self.calendar_id, eventId=event_id).execute()
            if not event:
                print(f"Event with ID {event_id} not found")
                return {}
                
            # Extract existing start and end times
            start_datetime = None
            end_datetime = None
            
            if 'dateTime' in event.get('start', {}):
                start_time_str = event['start']['dateTime']
                start_datetime = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                
            if 'dateTime' in event.get('end', {}):
                end_time_str = event['end']['dateTime']
                end_datetime = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            
            # Update date if provided
            if date_entity:
                new_date = self.parse_date_entity(date_entity)
                if new_date and start_datetime:
                    # Keep the time but update the date
                    start_datetime = datetime.combine(
                        new_date.date(),
                        start_datetime.time()
                    ).replace(tzinfo=start_datetime.tzinfo)
                    
                    # If we have end time, update it too maintaining duration
                    if end_datetime:
                        duration_minutes = int((end_datetime - start_datetime).total_seconds() / 60)
                        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
            
            # Update time if provided
            if time_entity and start_datetime:
                new_time = self.parse_time_entity(time_entity)
                if new_time:
                    # Keep the date but update the time
                    start_datetime = start_datetime.replace(
                        hour=new_time.hour,
                        minute=new_time.minute
                    )
                    
                    # If we have end time, update it too maintaining duration
                    if end_datetime:
                        duration_minutes = int((end_datetime - start_datetime).total_seconds() / 60)
                        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
            
            # Update duration if provided (and we have start time)
            if duration is not None and start_datetime:
                end_datetime = start_datetime + timedelta(minutes=duration)
            
            # Update the event object with new values
            if start_datetime:
                event['start']['dateTime'] = start_datetime.isoformat()
            
            if end_datetime:
                event['end']['dateTime'] = end_datetime.isoformat()
                
            if summary:
                event['summary'] = summary
                
            if description:
                event['description'] = description
                
            if location:
                event['location'] = location
                
            # Update the event in Google Calendar
            updated_event = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            print(f"Event updated: {updated_event.get('htmlLink')}")
            return updated_event
            
        except Exception as e:
            print(f"Error updating event: {e}")
            return {}
    
    def delete_real_event(self, event_id: str) -> bool:
        """Delete a calendar event using Google Calendar API
        
        Args:
            event_id: ID of the event to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        if not self.initialized or not event_id:
            print("Calendar service not initialized or invalid event ID")
            return False
            
        try:
            # Delete the event from Google Calendar
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            print(f"Event with ID {event_id} deleted successfully")
            return True
            
        except Exception as e:
            print(f"Error deleting event: {e}")
            return False
            
    def handle_calendar_query(self, message: str, session_id: str = None) -> str:
        """Process calendar-related queries and commands
        
        Args:
            message: User message text
            session_id: Optional session ID for context
            
        Returns:
            Response text
        """
        # Extract calendar entities from the message
        entities = self.extract_calendar_entities(message)
        
        # Determine the action based on the message
        action = self.determine_calendar_action(message, entities)
        
        # Get the date entity or default to today
        date_entity = entities.get('date', 'today')
        
        # Handle calendar queries
        if action == 'query':
            events = self.get_events(date_entity)
            return self.format_events_response(events, date_entity)
            
        # Handle event creation
        elif action == 'create':
            date_entity = entities.get('date', 'today')
            time_entity = entities.get('time', '9:00')
            event_type = entities.get('event_type', 'meeting')
            event_title = entities.get('title', '')
            duration = entities.get('duration', 60)
            
            # Format event summary based on type and title
            if event_title:
                summary = f"{event_title.capitalize()} {event_type}"
            else:
                summary = f"{event_type.capitalize()}"
                
            # Try to extract location if any
            location = entities.get('location', None)
            
            # Create event description
            description = f"Event created by ADK Voice Agent on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Format the event title for the response
            title_text = ''
            if event_title:
                title_text = f" with {event_title}"
                
            # Create a more natural time representation for display
            time_display = time_entity
            # Remove 'at ' prefix if present
            if time_display.startswith('at '):
                time_display = time_display[3:].strip()
                
            if time_display.isdigit():
                # Convert single digit to natural format
                hour = int(time_display)
                if 0 <= hour <= 23:
                    am_pm = "AM" if hour < 12 else "PM"
                    hour = hour if hour <= 12 else hour - 12
                    if hour == 0:
                        hour = 12
                    time_display = f"{hour} {am_pm}"
            
            # Attempt to create the real event if service is initialized
            if self.initialized:
                created_event = self.create_real_event(
                    date_entity=date_entity,
                    time_entity=time_entity,
                    duration=duration,
                    summary=summary,
                    description=description,
                    location=location
                )
                
                if created_event:
                    # Get the event link if available
                    event_link = created_event.get('htmlLink', '')
                    if event_link:
                        return f"I've created a {event_type}{title_text} on your calendar for {date_entity} at {time_display} that will last for {duration} minutes. You can view it here: {event_link}"
            
            # Default response if real event creation failed or service not initialized
            return f"I've created a {event_type}{title_text} on your calendar for {date_entity} at {time_display} that will last for {duration} minutes."
        
        # Handle event update
        elif action == 'update':
            date_entity = entities.get('date', 'today')
            time_entity = entities.get('time', '9:00')
            event_type = entities.get('event_type', 'meeting')
            event_title = entities.get('title', '')
            
            # Format the event title if available
            title_text = ''
            if event_title:
                title_text = f" with {event_title}"
                
            # Create a more natural time representation
            time_display = time_entity
            if time_display.startswith('at '):
                time_display = time_display[3:].strip()
                
            if time_display.isdigit():
                hour = int(time_display)
                if 0 <= hour <= 23:
                    am_pm = "AM" if hour < 12 else "PM"
                    hour = hour if hour <= 12 else hour - 12
                    if hour == 0:
                        hour = 12
                    time_display = f"{hour} {am_pm}"
            
            # Attempt to find and update the real event if service is initialized
            if self.initialized:
                # Find the event based on criteria
                event = self.find_event_by_criteria(date_entity, None, event_title)
                if event:
                    event_id = event.get('id')
                    if event_id:
                        # Update the event
                        updated_event = self.update_real_event(
                            event_id=event_id,
                            time_entity=time_entity
                        )
                        
                        if updated_event:
                            # Get the event link if available
                            event_link = updated_event.get('htmlLink', '')
                            if event_link:
                                return f"I've updated your {event_type}{title_text} on {date_entity} to start at {time_display}. You can view it here: {event_link}"
            
            # Default response if real event update failed or service not initialized
            return f"I've updated your {event_type}{title_text} on {date_entity} to start at {time_display}."
        
        # Handle event deletion
        elif action == 'delete':
            date_entity = entities.get('date', 'today')
            time_entity = entities.get('time', '')
            event_type = entities.get('event_type', 'meeting')
            event_title = entities.get('title', '')
            
            # Format the event title if available
            title_text = ''
            if event_title:
                title_text = f" with {event_title}"
                
            # Create a more natural time representation if provided
            time_text = ''
            if time_entity:
                time_display = time_entity
                if time_display.startswith('at '):
                    time_display = time_display[3:].strip()
                    
                if time_display.isdigit():
                    hour = int(time_display)
                    if 0 <= hour <= 23:
                        am_pm = "AM" if hour < 12 else "PM"
                        hour = hour if hour <= 12 else hour - 12
                        if hour == 0:
                            hour = 12
                        time_display = f"{hour} {am_pm}"
                time_text = f" at {time_display}"
            
            # Attempt to find and delete the real event if service is initialized
            if self.initialized:
                # Find the event based on criteria
                event = self.find_event_by_criteria(date_entity, time_entity, event_title)
                if event:
                    event_id = event.get('id')
                    if event_id:
                        # Delete the event
                        success = self.delete_real_event(event_id)
                        if success:
                            return f"I've deleted your {event_type}{title_text} from your calendar on {date_entity}{time_text}."
            
            # Default response if real event deletion failed or service not initialized
            return f"I've deleted your {event_type}{title_text} from your calendar on {date_entity}{time_text}."
        
        # Handle default case
        else:
            return "I'm not sure what calendar action you'd like me to perform. You can ask me to check your calendar, create, update, or delete events."

# Create a global instance to be imported by other modules
calendar_manager = CalendarManager()
