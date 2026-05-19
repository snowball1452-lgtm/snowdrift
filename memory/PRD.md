# SnowDrift - Product Requirements Document

## Overview
SnowDrift is a mobile AI assistant app (Expo/React Native) with an agentic backend (FastAPI) that can execute commands, discover tools, learn skills, and control phone actions.

## Architecture
- **Frontend**: Expo (React Native) with expo-router file-based routing
- **Backend**: FastAPI with ReAct agent loop, MongoDB for persistence
- **AI**: Multi-provider LLM support (OpenAI, Anthropic, Gemini) via Emergent Universal Key + LiteLLM

## Features Implemented
1. ✅ Chat with AI agent (ReAct loop: think → act → observe)
2. ✅ Multi-provider LLM switching (OpenAI/Anthropic/Gemini)
3. ✅ Tool discovery and shell command execution
4. ✅ Skill learning system
5. ✅ Device action routing (alarms, SMS, calls, clipboard)
6. ✅ Safety controls with action approval modal
7. ✅ Conversation management (create, list, delete, messages)
8. ✅ Voice input (Web Speech API on web, expo-av on native)
9. ✅ Text-to-speech output (expo-speech)
10. ✅ Markdown rendering in chat messages
11. ✅ Execution step visualization (collapsible reasoning steps)
12. ✅ Copy message content
13. ✅ Polished dark theme UI across all screens

## Screens
- `/` - Main chat screen with sidebar
- `/settings` - Provider, model, and safety settings
- `/tools` - Tools & skills dashboard

## API Endpoints
- POST /api/chat - Send message to agent
- GET/POST /api/conversations - Manage conversations
- GET /api/tools - List available tools
- POST /api/tools/discover - Discover new tools
- GET /api/skills - List learned skills
- GET/PUT /api/settings - Agent settings
- GET /api/providers - Available LLM providers
- GET /api/pending-actions - Actions awaiting approval
- POST /api/pending-actions/{id}/approve - Approve/reject action
- GET /api/device-actions/pending - Phone actions to execute
- POST /api/transcribe - Audio transcription
- POST /api/tts - Text-to-speech
