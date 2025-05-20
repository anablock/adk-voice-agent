#!/usr/bin/env python
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Print environment variables (redacting sensitive values)
print("Environment Variables Check:")
print("-" * 40)

# Check API_KEY
api_key = os.getenv("API_KEY")
print(f"API_KEY: {'✅ Set' if api_key else '❌ Not set'}")

# Check GOOGLE_API_KEY
google_api_key = os.getenv("GOOGLE_API_KEY")
print(f"GOOGLE_API_KEY: {'✅ Set' if google_api_key else '❌ Not set'}")

# Check ALLOWED_ORIGINS
allowed_origins = os.getenv("ALLOWED_ORIGINS")
print(f"ALLOWED_ORIGINS: {allowed_origins}")

# Check Gemini configuration
print("\nGoogle ADK Configuration:")
print("-" * 40)

genai_api_key = os.getenv("GOOGLE_API_KEY")
if genai_api_key:
    print("Gemini API Key: ✅ Found")
    
    # Import and check Gemini configuration
    try:
        import google.generativeai as genai
        genai.configure(api_key=genai_api_key)
        
        # List models to verify API key works
        try:
            models = genai.list_models()
            print(f"Available Gemini models: ✅ API key works")
            gemini_models = [m.name for m in models if "gemini" in m.name]
            print(f"Gemini models: {', '.join(gemini_models)}")
        except Exception as e:
            print(f"Error listing models: ❌ {str(e)}")
    except ImportError:
        print("Google Generative AI package not installed properly")
else:
    print("Gemini API Key: ❌ Not configured")

# Check additional environment variables that might be needed
print("\nCalendar Related Configuration:")
print("-" * 40)
calendar_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
print(f"GOOGLE_APPLICATION_CREDENTIALS: {'✅ Set to ' + calendar_credentials if calendar_credentials else '❌ Not set'}")
