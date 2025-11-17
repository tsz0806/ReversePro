# Grok Mirror API - Multi-turn Conversation Support

## Overview
This is a FastAPI-based backend application that provides a Grok API mirror service with multi-turn conversation support. The API allows users to interact with the Grok AI model in both single-turn and multi-turn conversation modes.

## Project Architecture

### Tech Stack
- **Framework**: FastAPI 0.104.1
- **Server**: Uvicorn 0.24.0
- **Language**: Python 3.11
- **Key Dependencies**: 
  - requests (for API calls)
  - pydantic (for data validation)
  - python-multipart (for file uploads)

### Project Structure
```
.
├── main.py           # Main application file with FastAPI endpoints
├── requirements.txt  # Python dependencies
├── Dockerfile       # Docker configuration (for reference)
├── .gitignore       # Git ignore patterns
└── replit.md        # This documentation file
```

## Key Features
1. **Single-turn conversations**: Start a new conversation without context
2. **Multi-turn conversations**: Continue conversations with context using conversation_id and parent_response_id
3. **CORS enabled**: Allows cross-origin requests from any origin
4. **Streaming response parsing**: Handles Grok's streaming API responses

## API Endpoints

### GET /
- Returns API information and features
- No authentication required

### GET /health
- Health check endpoint
- Returns: `{"status": "healthy"}`

### POST /api/chat
- Main chat endpoint
- Request body:
  ```json
  {
    "message": "Your question here",
    "model": "grok-3",  // optional
    "conversation_id": "...",  // optional, for continuing conversation
    "parent_response_id": "..."  // optional, for continuing conversation
  }
  ```
- Response:
  ```json
  {
    "success": true,
    "data": {
      "response": "AI response text",
      "conversation_id": "...",
      "response_id": "...",
      "is_new_conversation": true/false
    }
  }
  ```

## Configuration

### Port and Host
- **Port**: 5000 (configured for Replit environment)
- **Host**: 0.0.0.0 (accepts connections from all interfaces)

### Environment
- Runs on Replit with Python 3.11
- Dependencies managed via pip and requirements.txt

## Recent Changes
- **2024-11-17**: Initial import and setup for Replit environment
  - Changed port from 7860 to 5000 for Replit compatibility
  - Added .gitignore for Python projects
  - Created replit.md documentation
  - Installed Python 3.11 and all required dependencies

## Development Notes
- The application uses a hardcoded cookie for authentication with the upstream Grok service
- CORS is configured to allow all origins for maximum compatibility
- Streaming responses are parsed to extract the final response text
- Conversation state is managed via conversation_id and parent_response_id parameters

## User Preferences
- None specified yet

## Deployment
- Configured for Replit autoscale deployment
- Suitable for stateless API requests
- No database required (stateless design)

