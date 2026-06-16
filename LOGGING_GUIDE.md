# Logging Configuration Guide

## Overview

Comprehensive logging has been added to the entire session flow and chat flow using Python's built-in `logging` library. Logs are written to both console and rotating file handlers to help with debugging, monitoring, and auditing the application.

## Logging Setup

### Logger Configuration (`app/logger.py`)

A centralized logging configuration module has been created with the following features:

- **Console Handler**: INFO level logs displayed in terminal
- **File Handler**: DEBUG level logs saved to `logs/research_app.log` (rotating, max 10MB)
- **Session Logger**: Dedicated logger for session-related events in `logs/sessions.log`
- **Chat Logger**: Dedicated logger for chat interactions in `logs/chat.log`

All logs include:
- Timestamp (YYYY-MM-DD HH:MM:SS format)
- Logger name
- Log level (DEBUG, INFO, WARNING, ERROR)
- File name and line number
- Message content

### Log Files Location

```
backend/
└── logs/
    ├── research_app.log     # Main application logs
    ├── sessions.log         # Session-specific logs
    └── chat.log             # Chat interaction logs
```

Each file uses rotating handlers that create backups when they reach 10MB (5 backup files retained).

## Logged Components

### 1. **Main API Endpoints** (`app/main.py`)

- **Health Check** (`/health`): Debug level
- **Session Creation** (`POST /sessions`): 
  - Company name, website, objective, auto-run status
  - Session ID generation and creation confirmation
  
- **List Sessions** (`GET /sessions`): 
  - Number of sessions retrieved
  
- **Get Session Detail** (`GET /sessions/{session_id}`):
  - Session status and company name
  
- **Session Events** (`GET /sessions/{session_id}/events`):
  - Client subscription/unsubscription
  - Event streaming status
  - Event types being transmitted
  
- **Run Session** (`POST /sessions/{session_id}/run`):
  - Session status checks
  - Workflow scheduling
  
- **Chat Endpoint** (`POST /sessions/{session_id}/chat`):
  - User message (truncated to first 100 chars)
  - Generated answer
  - Chat history updates

### 2. **Workflow Graph** (`app/workflow/graph.py`)

#### Planner Node
```
[session_id] Planner node started
[session_id] Company: X, Objective: Y
[session_id] Research plan created with N tasks
[session_id] Planner node completed
```

#### Research Node
```
[session_id] Research node started
[session_id] Fetching website: URL
[session_id] HTTP response status: 200
[session_id] Website text extracted: N characters
[session_id] Research context collected/Proceeding with limited context
[session_id] Research node completed
```

#### Analysis Node
```
[session_id] Analysis node started
[session_id] Website text length: N characters
[session_id] Using fallback summary as base analysis
[session_id] Gemini API key found, attempting advanced analysis
[session_id] Calling Gemini API (model: gemini-model)
[session_id] Gemini response received, parsing JSON
[session_id] Successfully parsed Gemini response / Gemini returned invalid JSON
[session_id] Analysis node completed
```

#### Quality Check Node
```
[session_id] Quality check node started
[session_id] Quality score: X% (N/M sections present)
[session_id] Current retries: X
[session_id] Quality check node completed
```

#### Routing Logic
```
[session_id] Quality threshold met (X%), routing to report_generation
[session_id] Quality threshold not met (X%), retrying research (retry N/2)
[session_id] Max retries reached, routing to report_generation anyway
```

#### Report Generation Node
```
[session_id] Report generation node started
[session_id] Formatting analysis into report structure
[session_id] Report generated with N sections
[session_id] Report generation node completed
```

#### Workflow Orchestration
```
[session_id] Research workflow started
[session_id] Session loaded - Company: X
[session_id] Website: URL, Objective: Y
[session_id] Updating session status to running
[session_id] Invoking research graph with state
[session_id] Workflow completed successfully, updating session with report
[session_id] Report title: X, Quality score: Y%
[session_id] Session status updated to completed
[session_id] Workflow failed with error: ERROR_MSG
[session_id] Session status updated to failed
```

### 3. **Chat Flow** (`app/workflow/graph.py` - `answer_followup`)

```
[session_id] Answering followup question
[session_id] Question: USER_QUESTION (first 100 chars)
[session_id] Session retrieved
[session_id] No report available for this session
[session_id] Attempting to answer using Gemini API
[session_id] Calling Gemini with followup question
[session_id] Gemini response received
[session_id] Gemini API call failed: ERROR, falling back to keyword-based answer
[session_id] Using keyword-based fallback for answering
[session_id] Identified keyword: risk/challenge / question/discovery / outreach/email
[session_id] No specific keyword match, using generic answer
```

### 4. **Database Operations** (`app/db.py`)

#### Session Management
```
Creating session: session_id
Session created successfully: session_id
Fetching all sessions from database
Retrieved N sessions
Fetching session: session_id
Session retrieved successfully - Status: RUNNING
Session not found: session_id
Failed to get session: ERROR_MSG
```

#### Session Updates
```
Updating session session_id with fields: [field1, field2]
Session session_id updated successfully
Session session_id status updated to: COMPLETED
Session update event broadcasted for session_id
```

#### Progress Tracking
```
[session_id] Appending progress - Node: NODE_NAME, Status: STATUS
[session_id] Progress event created: MESSAGE
[session_id] Progress updated successfully
[session_id] Failed to append progress for node NODE: ERROR_MSG
```

#### Chat History
```
[session_id] Appending chat message - Role: user/assistant
[session_id] Message: MESSAGE_TEXT
[session_id] Chat message added, total messages: N
[session_id] Chat history updated successfully
[session_id] Failed to append chat message from user/assistant: ERROR_MSG
```

### 5. **Event Broadcasting** (`app/events.py`)

```
[session_id] New subscriber added, total subscribers: N
[session_id] Subscriber removed, remaining subscribers: N
[session_id] All subscribers removed, cleaning up session
[session_id] Broadcasting event to N subscribers - Event type: TYPE
[session_id] Event broadcast completed - Delivered: N, Failed: M
```

## Log Levels

- **DEBUG**: Detailed diagnostic information (file/line operations, state details)
- **INFO**: General informational messages (session creation, status changes, workflow progress)
- **WARNING**: Warning messages (missing sessions, API failures, queue issues)
- **ERROR**: Error messages with full exception traces

## Usage Examples

### Reading Session Logs
```bash
# View current session logs
tail -f backend/logs/sessions.log

# View chat interactions
tail -f backend/logs/chat.log

# Search for specific session
grep "session_id" backend/logs/research_app.log
```

### Filtering by Log Level
```bash
# View only errors
grep "ERROR" backend/logs/research_app.log

# View all workflow progress
grep "Planner\|Research\|Analysis\|Quality\|Report" backend/logs/research_app.log
```

### Troubleshooting
```bash
# Find failed sessions
grep "FAILED" backend/logs/research_app.log

# Track a specific company research
grep "Company Name" backend/logs/research_app.log

# Monitor Gemini API calls
grep "Calling Gemini" backend/logs/research_app.log
```

## Log Retention

- Each log file automatically rotates when it reaches 10MB
- Up to 5 backup files are retained per log file
- Older backups are automatically deleted
- This prevents unbounded disk space growth

## Performance Considerations

- Console logging is set to INFO level (minimal overhead)
- File logging is DEBUG level for comprehensive troubleshooting
- Rotating file handlers are efficient for long-running processes
- Queue full events are logged but don't block operations

## Integration with Monitoring

The structured logging format makes it easy to integrate with monitoring systems:
- **ELK Stack**: Parse logs using the consistent timestamp and format
- **Datadog/New Relic**: Extract session_id from logs for distributed tracing
- **Splunk**: Use the log format for creating saved searches and alerts
- **CloudWatch**: Ship logs to AWS CloudWatch for centralized monitoring
