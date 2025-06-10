"""
Gemini-powered Calendar Integration

This module uses Google's Gemini API to handle calendar operations through function calling.
It maintains compatibility with the existing Voice Assistant backend while adding calendar functionality.
"""

import os
import json
import datetime
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta

import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Set up Gemini API
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("Warning: GOOGLE_API_KEY not set. Gemini functionality will be limited.")

# Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
HAS_CALENDAR_API = True

class GeminiCalendarManager:
    """Calendar manager using Gemini API for understanding and Google Calendar API for execution"""
    
    def __init__(self):
        """Initialize the Gemini Calendar Manager"""
        self.credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        self.calendar_id = os.environ.get('GOOGLE_CALENDAR_ID', 'primary')
        self.service = None
        self.initialized = False
        self.gemini_model = None
        
        # Initialize Gemini model
        if GOOGLE_API_KEY:
            try:
                # Use Gemini 1.5 Pro for understanding calendar queries
                self.gemini_model = genai.GenerativeModel('gemini-1.5-pro')
                print("Gemini model initialized successfully")
            except Exception as e:
                print(f"Error initializing Gemini model: {e}")
        
        # Try to initialize the Calendar service
        if self.credentials_path and os.path.exists(self.credentials_path) and HAS_CALENDAR_API:
            try:
                self.initialize_service()
            except Exception as e:
                print(f"Error initializing Calendar service: {e}")
    
    def initialize_service(self):
        """Initialize the Google Calendar service using service account credentials"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=SCOPES)
            
            self.service = build('calendar', 'v3', credentials=credentials)
            self.initialized = True
            print("Google Calendar API service initialized successfully")
            return True
        except Exception as e:
            print(f"Failed to initialize Google Calendar service: {e}")
            self.initialized = False
            return False
    
    def format_date(self, date_obj: datetime) -> str:
        """Format a datetime object into a human-readable string"""
        today = datetime.now().date()
        date = date_obj.date()
        
        if date == today:
            return "today"
        elif date == today + timedelta(days=1):
            return "tomorrow"
        elif date == today - timedelta(days=1):
            return "yesterday"
        else:
            # Format as "Monday, January 1st" or similar
            return date_obj.strftime("%A, %B %d")
    
    def format_time(self, dt: datetime) -> str:
        """Format a datetime object into a readable time string"""
        return dt.strftime("%I:%M %p").lstrip("0")
    
    def get_events(self, date_str: str = None, max_results: int = 10) -> List[Dict[str, Any]]:
        """Get events from Google Calendar for a specific date"""
        if not self.initialized:
            print("Calendar service not initialized")
            return []
        
        try:
            # Convert date string to datetime object
            if not date_str or date_str.lower() in ['today', 'now']:
                target_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_str.lower() == 'tomorrow':
                target_date = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                # Try to parse the date string
                try:
                    target_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    # Default to today if parsing fails
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
            return []
    
    def create_event(self, title: str, start_time: str, 
                    end_time: str = None, description: str = None,
                    location: str = None) -> Dict[str, Any]:
        """Create a calendar event"""
        if not self.initialized:
            print("Calendar service not initialized")
            return {}
        
        try:
            # Parse start time
            start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            
            # If no end time provided, default to 1 hour after start
            if not end_time:
                end_datetime = start_datetime + timedelta(hours=1)
            else:
                end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            # Create event data
            event_data = {
                'summary': title,
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'America/Los_Angeles',
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
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
    
    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event"""
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
    
    def update_event(self, event_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a calendar event with new information"""
        if not self.initialized or not event_id:
            print("Calendar service not initialized or invalid event ID")
            return {}
        
        try:
            # Get the existing event
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            # Apply updates to the event
            for key, value in updates.items():
                if key == 'title' or key == 'summary':
                    event['summary'] = value
                elif key == 'location':
                    event['location'] = value
                elif key == 'description':
                    event['description'] = value
                elif key == 'start_time' and value:
                    start_datetime = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    event['start'] = {
                        'dateTime': start_datetime.isoformat(),
                        'timeZone': 'America/Los_Angeles'
                    }
                elif key == 'end_time' and value:
                    end_datetime = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    event['end'] = {
                        'dateTime': end_datetime.isoformat(),
                        'timeZone': 'America/Los_Angeles'
                    }
            
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
    
    def find_events_by_title(self, title_query: str, date_str: str = None) -> List[Dict[str, Any]]:
        """Find events by matching title"""
        events = self.get_events(date_str)
        return [e for e in events if title_query.lower() in e.get('summary', '').lower()]
    
    def format_events_response(self, events: List[Dict[str, Any]], date_str: str = None) -> str:
        """Format a list of events into a readable response"""
        if not events:
            if date_str and date_str.lower() != 'today':
                return f"You have no events scheduled for {date_str}."
            return "You have no events scheduled for today."
        
        # Format date for display
        if not date_str or date_str.lower() == 'today':
            date_display = "today"
        elif date_str.lower() == 'tomorrow':
            date_display = "tomorrow"
        else:
            date_display = date_str
        
        response = f"Here are your events for {date_display}:\n\n"
        
        for i, event in enumerate(events, 1):
            summary = event.get('summary', 'Untitled event')
            
            # Format start time
            if 'dateTime' in event.get('start', {}):
                start_time = datetime.fromisoformat(
                    event['start']['dateTime'].replace('Z', '+00:00')
                )
                time_str = self.format_time(start_time)
            else:
                time_str = "All day"
            
            # Add location if available
            location = event.get('location', '')
            location_str = f" at {location}" if location else ""
            
            # Format the event line
            response += f"{i}. {summary} - {time_str}{location_str}\n"
        
        return response
    
    def handle_calendar_query(self, message: str, session_id: str = None) -> str:
        """Process calendar-related queries using Gemini API for understanding"""
        if not self.gemini_model:
            return "I'm sorry, but the calendar functionality is currently unavailable."
        
        try:
            # Define functions that Gemini can call
            tools = [
                {
                    "name": "get_calendar_events",
                    "description": "Get events from the user's calendar for a specific date",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {
                                "type": "string",
                                "description": "The date to get events for. Can be 'today', 'tomorrow', or a date string like '2025-05-22'"
                            }
                        },
                        "required": ["date"]
                    }
                },
                {
                    "name": "create_calendar_event",
                    "description": "Create a new event on the user's calendar",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "The title or summary of the event"
                            },
                            "date": {
                                "type": "string",
                                "description": "The date of the event in YYYY-MM-DD format"
                            },
                            "start_time": {
                                "type": "string",
                                "description": "The start time of the event in 24-hour format (HH:MM)"
                            },
                            "duration_minutes": {
                                "type": "integer",
                                "description": "Duration of the event in minutes"
                            },
                            "location": {
                                "type": "string",
                                "description": "Optional location for the event"
                            }
                        },
                        "required": ["title", "date", "start_time"]
                    }
                },
                {
                    "name": "update_calendar_event",
                    "description": "Update an existing calendar event",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_description": {
                                "type": "string",
                                "description": "Description of the event to update, including date, time and title"
                            },
                            "update_fields": {
                                "type": "object",
                                "description": "Fields to update and their new values",
                                "properties": {
                                    "title": {"type": "string"},
                                    "date": {"type": "string"},
                                    "start_time": {"type": "string"},
                                    "duration_minutes": {"type": "integer"},
                                    "location": {"type": "string"}
                                }
                            }
                        },
                        "required": ["event_description", "update_fields"]
                    }
                },
                {
                    "name": "delete_calendar_event",
                    "description": "Delete a calendar event",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_description": {
                                "type": "string",
                                "description": "Description of the event to delete, including date, time and title"
                            }
                        },
                        "required": ["event_description"]
                    }
                }
            ]
            
            # Get Gemini's response with function calling
            response = self.gemini_model.generate_content(
                [message],
                generation_config={"temperature": 0.1},
                tools=tools
            )
            
            # Check if there's a function call
            if hasattr(response, 'candidates') and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call'):
                            function_call = part.function_call
                            function_name = function_call.name
                            function_args = json.loads(function_call.args)
                            
                            # Handle different function calls
                            if function_name == "get_calendar_events":
                                date = function_args.get("date", "today")
                                events = self.get_events(date)
                                return self.format_events_response(events, date)
                            
                            elif function_name == "create_calendar_event":
                                title = function_args.get("title")
                                date = function_args.get("date")
                                time = function_args.get("start_time")
                                duration = function_args.get("duration_minutes", 60)
                                location = function_args.get("location")
                                
                                # Format datetime for API
                                dt_str = f"{date}T{time}:00"
                                start_time = datetime.fromisoformat(dt_str)
                                end_time = start_time + timedelta(minutes=duration)
                                
                                # Create the event
                                result = self.create_event(
                                    title=title,
                                    start_time=start_time.isoformat(),
                                    end_time=end_time.isoformat(),
                                    location=location
                                )
                                
                                if result:
                                    date_display = self.format_date(start_time)
                                    time_display = self.format_time(start_time)
                                    return f"I've scheduled '{title}' for {date_display} at {time_display}."
                                else:
                                    return "I wasn't able to create that event. Please try again."
                            
                            elif function_name == "update_calendar_event":
                                event_desc = function_args.get("event_description")
                                updates = function_args.get("update_fields", {})
                                
                                # First, find the event based on description
                                # This is simplified; in a real implementation, you would
                                # need more sophisticated event matching
                                if "today" in event_desc.lower():
                                    date = "today"
                                elif "tomorrow" in event_desc.lower():
                                    date = "tomorrow"
                                else:
                                    date = None
                                
                                # Extract potential title keywords from description
                                potential_title = ' '.join([word for word in event_desc.split() 
                                                          if word.lower() not in ['the', 'at', 'on', 'for', 'with']])
                                
                                # Find matching events
                                events = self.get_events(date)
                                matching_events = []
                                for event in events:
                                    if potential_title.lower() in event.get('summary', '').lower():
                                        matching_events.append(event)
                                
                                if not matching_events:
                                    return f"I couldn't find any events matching '{event_desc}'."
                                
                                # Update the first matching event
                                event_to_update = matching_events[0]
                                event_id = event_to_update.get('id')
                                
                                # Convert updates to format expected by update_event
                                api_updates = {}
                                if 'title' in updates:
                                    api_updates['summary'] = updates['title']
                                if 'location' in updates:
                                    api_updates['location'] = updates['location']
                                if 'date' in updates and 'start_time' in updates:
                                    dt_str = f"{updates['date']}T{updates['start_time']}:00"
                                    start_time = datetime.fromisoformat(dt_str)
                                    api_updates['start_time'] = start_time.isoformat()
                                    
                                    # Also update end time to maintain duration
                                    if 'duration_minutes' in updates:
                                        duration = updates['duration_minutes']
                                    else:
                                        # Try to maintain original duration
                                        original_start = datetime.fromisoformat(
                                            event_to_update['start']['dateTime'].replace('Z', '+00:00')
                                        )
                                        original_end = datetime.fromisoformat(
                                            event_to_update['end']['dateTime'].replace('Z', '+00:00')
                                        )
                                        duration = int((original_end - original_start).total_seconds() / 60)
                                    
                                    end_time = start_time + timedelta(minutes=duration)
                                    api_updates['end_time'] = end_time.isoformat()
                                
                                # Update the event
                                result = self.update_event(event_id, api_updates)
                                if result:
                                    return f"I've updated the event '{event_to_update.get('summary')}'."
                                else:
                                    return f"I wasn't able to update that event. Please try again."
                            
                            elif function_name == "delete_calendar_event":
                                event_desc = function_args.get("event_description")
                                
                                # Find the event based on description
                                # Similar simplified approach as update
                                if "today" in event_desc.lower():
                                    date = "today"
                                elif "tomorrow" in event_desc.lower():
                                    date = "tomorrow"
                                else:
                                    date = None
                                
                                # Extract potential title keywords from description
                                potential_title = ' '.join([word for word in event_desc.split() 
                                                          if word.lower() not in ['the', 'at', 'on', 'for', 'with']])
                                
                                # Find matching events
                                events = self.get_events(date)
                                matching_events = []
                                for event in events:
                                    if potential_title.lower() in event.get('summary', '').lower():
                                        matching_events.append(event)
                                
                                if not matching_events:
                                    return f"I couldn't find any events matching '{event_desc}'."
                                
                                # Delete the first matching event
                                event_to_delete = matching_events[0]
                                event_id = event_to_delete.get('id')
                                event_summary = event_to_delete.get('summary')
                                
                                result = self.delete_event(event_id)
                                if result:
                                    return f"I've deleted the event '{event_summary}'."
                                else:
                                    return f"I wasn't able to delete that event. Please try again."
            
            # If no function call or general response
            return response.text
        
        except Exception as e:
            print(f"Error processing calendar query with Gemini: {e}")
            return f"I'm sorry, I had trouble processing your calendar request. Please try again."

# Create a global instance
calendar_manager = GeminiCalendarManager()
