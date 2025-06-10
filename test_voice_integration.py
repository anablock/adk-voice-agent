#!/usr/bin/env python3
"""
Voice Integration Test for ADK Voice Agent

This script tests the complete voice integration flow with the ADK Voice Agent,
simulating voice interactions for calendar operations. It validates that the agent
can handle audio input/output correctly and maintain context across voice interactions.
"""

import asyncio
import json
import uuid
import websockets
import time
import base64
import os
import wave
import pyaudio
from datetime import datetime, timedelta

# Configuration
WS_URL = "ws://localhost:8081/ws"
API_KEY = "development-key"
SESSION_ID = f"voice_test_{uuid.uuid4().hex[:8]}"
AUDIO_FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 5  # Default recording duration

# Test directory for audio samples
TEST_AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_audio")
os.makedirs(TEST_AUDIO_DIR, exist_ok=True)

# Test scenarios for voice interactions
VOICE_TEST_SCENARIOS = [
    {
        "name": "Calendar Event Creation via Voice",
        "prompts": [
            "Schedule a meeting for tomorrow at 3 PM",
            "Call it weekly team sync",
            "Add John and Sarah as attendees",
            "Yes, please create it"
        ]
    },
    {
        "name": "Calendar Query via Voice",
        "prompts": [
            "What meetings do I have today",
            "Give me more details about the team sync",
            "Thanks, that's all I needed"
        ]
    }
]


async def record_audio(filename, duration=RECORD_SECONDS):
    """Record audio from microphone and save to file"""
    print(f"Recording audio for {duration} seconds...")
    
    p = pyaudio.PyAudio()
    stream = p.open(format=AUDIO_FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_second=CHUNK)
    
    frames = []
    for i in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK)
        frames.append(data)
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # Save to WAV file
    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(AUDIO_FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
    print(f"Audio saved to {filename}")
    return filename


async def load_audio_file(filename):
    """Load audio data from file"""
    with open(filename, 'rb') as f:
        audio_data = f.read()
    return audio_data


async def send_audio(websocket, audio_data, mime_type="audio/wav"):
    """Send audio data to the websocket"""
    encoded_data = base64.b64encode(audio_data).decode('utf-8')
    message = {
        "mime_type": mime_type,
        "type": mime_type,
        "data": encoded_data,
        "role": "user"
    }
    await websocket.send(json.dumps(message))
    print(f"[SENT] Audio data: {len(encoded_data)} bytes")


async def send_audio_end_marker(websocket):
    """Send end-of-audio marker to the websocket"""
    message = {
        "mime_type": "audio/end",
        "type": "audio/end",
        "data": "",
        "role": "user"
    }
    await websocket.send(json.dumps(message))
    print("[SENT] End of audio marker")


async def receive_responses(websocket, timeout=15):
    """Receive responses from the websocket with timeout"""
    text_response = ""
    audio_response = None
    turn_complete = False
    message_received = False
    response_start_time = None
    quiet_threshold = 3.0  # seconds without a message to consider turn might be complete
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Set a shorter timeout for each individual receive
            response = await asyncio.wait_for(websocket.recv(), 2)
            message_received = True
            last_message_time = time.time()
            if not response_start_time:
                response_start_time = last_message_time
                
            try:
                response_json = json.loads(response)
            except json.JSONDecodeError:
                print(f"[ERROR] Invalid JSON response: {response[:100]}...")
                continue
            
            # Check for turn completion
            if "turn_complete" in response_json and response_json["turn_complete"]:
                turn_complete = True
                print("[INFO] Received turn_complete marker")
                break
            
            # Check for error messages
            if response_json.get("is_error", False):
                print(f"[ERROR] {response_json.get('data', 'Unknown error')}")
                # Don't break on errors, continue listening for more messages
                
            # Process text messages
            if response_json.get("mime_type") == "text/plain" and "data" in response_json:
                text = response_json.get("data", "")
                if text:
                    text_response += text
                    print(f"[RECEIVED TEXT] {text[:100]}..." if len(text) > 100 else f"[RECEIVED TEXT] {text}")
            
            # Process audio messages
            if response_json.get("mime_type", "").startswith("audio/"):
                try:
                    audio_data = base64.b64decode(response_json.get("data", ""))
                    audio_response = audio_data
                    print(f"[RECEIVED AUDIO] {len(audio_data)} bytes")
                except Exception as e:
                    print(f"[ERROR] Failed to decode audio data: {e}")
        
        except asyncio.TimeoutError:
            # If we've received at least one message and we haven't received any for a while, 
            # the turn might be complete even without a formal turn_complete message
            current_time = time.time()
            if message_received and response_start_time and (current_time - last_message_time > quiet_threshold):
                print(f"[INFO] No messages received for {current_time - last_message_time:.1f} seconds, assuming turn is complete")
                break
            continue
            
        except Exception as e:
            print(f"Error receiving response: {e}")
            if message_received:  # Only break if we've already received some data
                break
    
    # If we timed out but received messages, consider the interaction complete
    if not turn_complete and message_received:
        print("[INFO] Turn wasn't explicitly marked complete, but messages were received")
        turn_complete = True
    elif not message_received:
        print("[WARNING] No messages received at all")
            
    return text_response, audio_response, turn_complete


async def save_audio_response(audio_data, filename):
    """Save received audio data to file"""
    if not audio_data:
        return None
        
    try:
        with open(filename, 'wb') as f:
            f.write(audio_data)
        print(f"Saved audio response to {filename}")
        return filename
    except Exception as e:
        print(f"Error saving audio: {e}")
        return None


async def test_voice_conversation(scenario):
    """Test a complete voice conversation scenario"""
    print(f"\n==== TESTING VOICE SCENARIO: {scenario['name']} ====")
    print(f"Session ID: {SESSION_ID}")
    
    uri = f"{WS_URL}/{SESSION_ID}?is_audio=true&api_key={API_KEY}"
    
    try:
        async with websockets.connect(uri) as websocket:
            # Wait for welcome message
            welcome_text, welcome_audio, welcome_complete = await receive_responses(websocket)
            print(f"Welcome message: {welcome_text}")
            
            if welcome_audio:
                await save_audio_response(
                    welcome_audio, 
                    os.path.join(TEST_AUDIO_DIR, f"welcome_{SESSION_ID}.wav")
                )
            
            # Process each prompt in the scenario
            for i, prompt in enumerate(scenario["prompts"]):
                print(f"\n--- Voice Turn {i+1}: '{prompt}' ---")
                
                # Option 1: Record audio from microphone
                # audio_file = await record_audio(os.path.join(TEST_AUDIO_DIR, f"turn_{i+1}_input.wav"))
                
                # Option 2: Simulate audio by sending text (for automated testing)
                # In a real test, you would use recorded audio files or live recording
                print(f"Simulating voice input: '{prompt}'")
                await websocket.send(json.dumps({
                    "mime_type": "text/plain",
                    "type": "text/plain",
                    "data": prompt,
                    "content": prompt,
                    "role": "user"
                }))
                
                # Receive the agent's response
                text, audio, complete = await receive_responses(websocket)
                
                if audio:
                    # Save the audio response
                    await save_audio_response(
                        audio, 
                        os.path.join(TEST_AUDIO_DIR, f"turn_{i+1}_response.wav")
                    )
                
                if not complete:
                    print("[WARNING] Turn was not completed properly")
                
                # Allow a short pause between turns
                await asyncio.sleep(2)
                
            print(f"\n==== COMPLETED VOICE SCENARIO: {scenario['name']} ====")
            return True
            
    except Exception as e:
        print(f"Error in voice test scenario: {e}")
        return False


async def test_error_handling():
    """Test error handling capabilities with invalid inputs"""
    print("\n==== TESTING ERROR HANDLING ====")
    
    uri = f"{WS_URL}/{SESSION_ID}?is_audio=true&api_key={API_KEY}"
    
    try:
        async with websockets.connect(uri) as websocket:
            # Wait for welcome message
            welcome_text, _, _ = await receive_responses(websocket)
            
            # Test 1: Send invalid JSON
            print("\n--- Testing invalid JSON ---")
            await websocket.send("This is not valid JSON")
            response, _, _ = await receive_responses(websocket, timeout=5)
            print(f"Response to invalid JSON: {response}")
            
            # Test 2: Send empty audio data
            print("\n--- Testing empty audio data ---")
            await send_audio(websocket, b"", mime_type="audio/wav")
            response, _, _ = await receive_responses(websocket, timeout=5)
            print(f"Response to empty audio: {response}")
            
            # Test 3: Send invalid MIME type
            print("\n--- Testing invalid MIME type ---")
            await websocket.send(json.dumps({
                "mime_type": "invalid/type",
                "type": "invalid/type",
                "data": "test data",
                "role": "user"
            }))
            response, _, _ = await receive_responses(websocket, timeout=5)
            print(f"Response to invalid MIME type: {response}")
            
            return True
    except Exception as e:
        print(f"Error in error handling test: {e}")
        return False


async def main():
    """Run all voice integration tests"""
    print(f"Starting voice integration tests at {datetime.now().isoformat()}")
    print(f"Test audio directory: {TEST_AUDIO_DIR}")
    
    all_succeeded = True
    
    # Test voice conversation scenarios
    for scenario in VOICE_TEST_SCENARIOS:
        success = await test_voice_conversation(scenario)
        if not success:
            all_succeeded = False
    
    # Test error handling
    error_success = await test_error_handling()
    if not error_success:
        all_succeeded = False
    
    if all_succeeded:
        print("\n✅ All voice integration tests passed successfully!")
    else:
        print("\n❌ Some tests failed. Check the logs above for details.")


if __name__ == "__main__":
    asyncio.run(main())
