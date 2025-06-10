# Google Calendar Integration Setup Guide

This guide will help you set up the Google Calendar integration for the ADK Voice Agent. The agent can interact with your real Google Calendar to create, query, edit, and delete events.

## Prerequisites

1. A Google Cloud Platform account
2. A project with the Google Calendar API enabled
3. OAuth 2.0 credentials for the Google Calendar API

## Setup Steps

### 1. Create a Google Cloud Platform Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Calendar API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Calendar API"
   - Click on it and then click "Enable"

### 2. Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Select "Desktop app" as the application type
4. Enter a name for your OAuth client (e.g., "ADK Voice Agent")
5. Click "Create"
6. Download the credentials JSON file
7. Move the downloaded file to the root of this project and rename it to `credentials.json`

### 3. Set Environment Variables

Add the following environment variables to your system:

```bash
# Path to your OAuth 2.0 credentials file
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/adk-voice-agent/credentials.json"

# Calendar ID to use (use 'primary' for your main calendar)
export GOOGLE_CALENDAR_ID="primary"
```

You can add these to your `.bashrc`, `.zshrc`, or equivalent shell configuration file.

### 4. Run the Setup Script

Run the setup script to authenticate with Google and create an access token:

```bash
python setup_calendar_auth.py
```

This will:
1. Open a browser window for you to log in to your Google account
2. Ask for permission to access your Google Calendar
3. Save the access token to `~/.credentials/calendar_token.json`
4. Test the connection to your Google Calendar

## Using the Calendar Integration

Once the setup is complete, restart the ADK Voice Agent server:

```bash
python app/main_audio_config_fix.py
```

You can now interact with your Google Calendar using voice or text commands:

- **Query events**: "What's on my calendar tomorrow?"
- **Create events**: "Schedule a meeting with John at 3pm on Friday"
- **Update events**: "Move my meeting with John to 4pm"
- **Delete events**: "Delete my 4pm meeting on Friday"

## Troubleshooting

### Token Expired or Invalid

If you encounter authentication errors, you may need to refresh your token:

1. Delete the existing token file: `rm ~/.credentials/calendar_token.json`
2. Run the setup script again: `python setup_calendar_auth.py`

### Calendar API Errors

If you see errors related to the Calendar API:

1. Check that the API is enabled in your Google Cloud project
2. Verify that your OAuth credentials have the correct scopes
3. Ensure the environment variables are correctly set

### Permission Denied

If you see "Permission denied" errors:

1. Make sure you've granted the necessary permissions during the OAuth flow
2. Check that you're using the correct calendar ID in the environment variable
3. Verify that your Google account has access to the calendar you're trying to use
