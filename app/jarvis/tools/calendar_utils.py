"""
Utility functions for Google Calendar integration.
"""

import base64
import json
import os
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Define scopes needed for Google Calendar
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Path for token storage
TOKEN_PATH = Path(os.path.expanduser("~/.credentials/calendar_token.json"))
CREDENTIALS_PATH = Path("credentials.json")


def get_calendar_service():
    """
    Authenticate and create a Google Calendar service object.
    Supports both local token file and environment variable credential storage.

    Returns:
        A Google Calendar service object or None if authentication fails
    """
    creds = None

    # Check if base64-encoded credentials exist in environment variable (for Heroku)
    base64_creds = os.environ.get('CALENDAR_CREDENTIALS_BASE64')
    
    if base64_creds:
        try:
            # Decode base64 string to JSON
            decoded_creds = base64.b64decode(base64_creds).decode('utf-8')
            creds_json = json.loads(decoded_creds)
            creds = Credentials.from_authorized_user_info(creds_json, SCOPES)
            print("Using credentials from environment variable")
        except Exception as e:
            print(f"Error parsing credentials from environment: {e}")
    
    # If no environment credentials, check if token exists locally and is valid
    if not creds and TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_info(
                json.loads(TOKEN_PATH.read_text()), SCOPES
            )
            print("Using credentials from local token file")
        except Exception as e:
            print(f"Error loading token file: {e}")

    # If credentials don't exist or are invalid, refresh or get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("Refreshed expired credentials")
                
                # If we're in a writable environment (not Heroku), save to file
                if not base64_creds:
                    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
                    TOKEN_PATH.write_text(creds.to_json())
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                return None
        else:
            # Only try local OAuth flow if we're not on Heroku
            if not os.environ.get('DYNO'):  # 'DYNO' is present on Heroku
                # If credentials.json doesn't exist, we can't proceed with OAuth flow
                if not CREDENTIALS_PATH.exists():
                    print(
                        f"Error: {CREDENTIALS_PATH} not found. Please follow setup instructions."
                    )
                    return None

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                    creds = flow.run_local_server(port=0)
                    
                    # Save the credentials for the next run
                    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
                    TOKEN_PATH.write_text(creds.to_json())
                    
                    # Output the base64 encoded credentials that can be used in Heroku
                    print("\nFor Heroku deployment, add this to your environment variables:\n")
                    print(f"CALENDAR_CREDENTIALS_BASE64={base64.b64encode(creds.to_json().encode()).decode()}\n")
                except Exception as e:
                    print(f"Error in OAuth flow: {e}")
                    return None
            else:
                print("No valid credentials available. Cannot authenticate on Heroku without CALENDAR_CREDENTIALS_BASE64.")
                return None

    # Create and return the Calendar service
    return build("calendar", "v3", credentials=creds)


def format_event_time(event_time):
    """
    Format an event time into a human-readable string.

    Args:
        event_time (dict): The event time dictionary from Google Calendar API

    Returns:
        str: A human-readable time string
    """
    if "dateTime" in event_time:
        # This is a datetime event
        dt = datetime.fromisoformat(event_time["dateTime"].replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %I:%M %p")
    elif "date" in event_time:
        # This is an all-day event
        return f"{event_time['date']} (All day)"
    return "Unknown time format"


def parse_datetime(datetime_str):
    """
    Parse a datetime string into a datetime object.

    Args:
        datetime_str (str): A string representing a date and time

    Returns:
        datetime: A datetime object or None if parsing fails
    """
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y",
        "%B %d, %Y %H:%M",
        "%B %d, %Y %I:%M %p",
        "%B %d, %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue

    return None


def get_current_time() -> dict:
    """
    Get the current time and date
    """
    now = datetime.now()

    # Format date as MM-DD-YYYY
    formatted_date = now.strftime("%m-%d-%Y")

    return {
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "formatted_date": formatted_date,
    }
