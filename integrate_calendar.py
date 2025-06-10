#!/usr/bin/env python3
"""
Gemini Calendar Integration for ADK Voice Agent

This script integrates Gemini-powered calendar functionality with the existing
ADK Voice Agent server. It runs as a middleware that intercepts WebSocket
messages, processes calendar-related queries, and forwards other messages to
the original server.

Usage:
    python integrate_calendar.py

Requirements:
    - The original ADK Voice Agent server must be running
    - GOOGLE_API_KEY environment variable must be set
    - GOOGLE_APPLICATION_CREDENTIALS environment variable must point to valid credentials
"""

import os
import json
import asyncio
import websockets
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Union
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('calendar-integration')

# Import the Gemini calendar manager
try:
    from app.gemini_calendar import calendar_manager
    HAS_CALENDAR = True
    logger.info("Calendar functionality imported successfully.")
    logger.info(f"Calendar API initialized: {calendar_manager.initialized}")
except ImportError as e:
    logger.error(f"Error importing calendar functionality: {e}")
    HAS_CALENDAR = False

# WebSocket settings
DEFAULT_WS_HOST = "localhost"
DEFAULT_WS_PORT = 8081
DEFAULT_MIDDLEWARE_PORT = 8082

class CalendarMiddleware:
    """
    Middleware that sits between the client and the original server,
    intercepting calendar-related queries and handling them with the
    Gemini-powered calendar manager.
    """
    
    def __init__(self, server_host: str, server_port: int, middleware_port: int):
        """Initialize the calendar middleware"""
        self.server_host = server_host
        self.server_port = server_port
        self.middleware_port = middleware_port
        self.server_url = f"ws://{server_host}:{server_port}/ws"
        self.active_connections = {}
        
    def is_calendar_related(self, text: str) -> bool:
        """Check if the message is related to calendar operations"""
        calendar_keywords = [
            "calendar", "schedule", "event", "meeting", "appointment", 
            "reminder", "book", "reserve", "plan", "arrange"
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in calendar_keywords)
    
    async def handle_client(self, websocket, path):
        """Handle client WebSocket connection"""
        session_id = path.strip("/").split("/")[1] if "/" in path else "unknown"
        client_id = id(websocket)
        logger.info(f"Client connected: {client_id} (Session: {session_id})")
        
        # Connect to the original server
        try:
            original_server = await websockets.connect(f"{self.server_url}/{session_id}{path[path.find('?'):] if '?' in path else ''}")
            self.active_connections[client_id] = {
                "client": websocket,
                "server": original_server,
                "session_id": session_id
            }
            
            # Create tasks for handling messages in both directions
            client_to_server = asyncio.create_task(
                self.handle_client_to_server(client_id, websocket, original_server)
            )
            server_to_client = asyncio.create_task(
                self.handle_server_to_client(client_id, original_server, websocket)
            )
            
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [client_to_server, server_to_client],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel the pending task
            for task in pending:
                task.cancel()
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection to original server failed for client {client_id}")
        except Exception as e:
            logger.error(f"Error in handle_client: {str(e)}")
        finally:
            # Clean up connection
            if client_id in self.active_connections:
                conn = self.active_connections[client_id]
                if "server" in conn and conn["server"]:
                    await conn["server"].close()
                del self.active_connections[client_id]
            logger.info(f"Client disconnected: {client_id}")
    
    async def handle_client_to_server(self, client_id: int, client_ws, server_ws):
        """Handle messages from client to server"""
        try:
            async for message in client_ws:
                try:
                    # Parse the message
                    data = json.loads(message)
                    text = data.get("text", "")
                    
                    # Check if this is a calendar-related query and we have calendar functionality
                    if text and self.is_calendar_related(text) and HAS_CALENDAR:
                        logger.info(f"Calendar query from client {client_id}: {text}")
                        
                        # Process with calendar manager
                        response = calendar_manager.handle_calendar_query(text)
                        logger.info(f"Calendar response: {response}")
                        
                        # Send response to client
                        await client_ws.send(json.dumps({
                            "type": "message",
                            "content": response
                        }))
                        
                        # Send turn complete message
                        await client_ws.send(json.dumps({"type": "turnComplete"}))
                    else:
                        # Forward the message to the original server
                        await server_ws.send(message)
                except json.JSONDecodeError:
                    # Not a JSON message, forward as-is
                    await server_ws.send(message)
                except Exception as e:
                    logger.error(f"Error processing client message: {str(e)}")
                    # Try to send an error message to the client
                    try:
                        await client_ws.send(json.dumps({
                            "type": "message",
                            "content": f"I encountered an error processing your request: {str(e)}"
                        }))
                    except:
                        pass
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"Error in handle_client_to_server: {str(e)}")
    
    async def handle_server_to_client(self, client_id: int, server_ws, client_ws):
        """Handle messages from server to client"""
        try:
            async for message in server_ws:
                # Forward the message to the client
                await client_ws.send(message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Server disconnected from client {client_id}")
        except Exception as e:
            logger.error(f"Error in handle_server_to_client: {str(e)}")
    
    async def start_server(self):
        """Start the middleware WebSocket server"""
        server = await websockets.serve(
            self.handle_client,
            "0.0.0.0",
            self.middleware_port
        )
        
        logger.info(f"Calendar middleware running on ws://0.0.0.0:{self.middleware_port}")
        logger.info(f"Forwarding to original server at {self.server_url}")
        logger.info(f"Calendar functionality is {'ACTIVE' if HAS_CALENDAR and calendar_manager.initialized else 'INACTIVE'}")
        
        return server

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Calendar integration middleware for ADK Voice Agent")
    parser.add_argument("--server-host", default=DEFAULT_WS_HOST, help=f"Original server host (default: {DEFAULT_WS_HOST})")
    parser.add_argument("--server-port", type=int, default=DEFAULT_WS_PORT, help=f"Original server port (default: {DEFAULT_WS_PORT})")
    parser.add_argument("--middleware-port", type=int, default=DEFAULT_MIDDLEWARE_PORT, help=f"Middleware port (default: {DEFAULT_MIDDLEWARE_PORT})")
    
    return parser.parse_args()

async def main():
    """Main entry point"""
    args = parse_arguments()
    
    middleware = CalendarMiddleware(
        server_host=args.server_host,
        server_port=args.server_port,
        middleware_port=args.middleware_port
    )
    
    server = await middleware.start_server()
    
    # Keep the server running
    await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Calendar middleware stopped by user")
    except Exception as e:
        logger.error(f"Error running middleware: {str(e)}")
