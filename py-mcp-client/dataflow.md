# MCP Chatbot Data Flow

## Architecture Overview

```
┌─────────────┐
│    User     │
└──────┬──────┘
       │
       │ 1. User Input
       ↓
┌──────────────────────────────────────────────────────────┐
│                    MCPChatbot                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │         Conversation History (messages[])          │  │
│  │  [system, user, assistant, tool, user, ...]        │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
       │
       │ 2. Send: messages + tools[]
       ↓
┌──────────────────────────────────────────────────────────┐
│                   Ollama Client                          │
│                                                          │
│  POST /api/chat                                          │
│  {                                                       │
│    "model": "llama3.1",                                  │
│    "messages": [...],                                    │
│    "tools": [                                            │
│      {                                                   │
│        "type": "function",                               │
│        "function": {                                     │
│          "name": "execute_query",                        │
│          "description": "Execute SQL query",             │
│          "parameters": {...}                             │
│        }                                                 │
│      },                                                  │
│      ...                                                 │
│    ]                                                     │
│  }                                                       │
└──────────────────────────────────────────────────────────┘
       │
       │ 3. Forward to LLM
       ↓
┌──────────────────────────────────────────────────────────┐
│                    LLM Model                             │
│              (e.g., Llama 3.1 8B)                        │
│                                                          │
│  • Analyzes user intent                                  │
│  • Reads available tools from API                        │
│  • Decides if tool call needed                           │
│  • Generates response with tool_calls                    │
└──────────────────────────────────────────────────────────┘
       │
       │ 4. Raw Response
       ↓
┌──────────────────────────────────────────────────────────┐
│              Ollama (Parser)                             │
│                                                          │
│  • Parses LLM output                                     │
│  • Extracts tool calls into structured format            │
│  • Returns JSON response                                 │
└──────────────────────────────────────────────────────────┘
       │
       │ 5. Structured Response
       │    {
       │      "message": {
       │        "role": "assistant",
       │        "content": "",
       │        "tool_calls": [
       │          {
       │            "function": {
       │              "name": "execute_query",
       │              "arguments": {"query": "SELECT * FROM users"}
       │            }
       │          }
       │        ]
       │      }
       │    }
       ↓
┌──────────────────────────────────────────────────────────┐
│                   MCPChatbot                             │
│                                                          │
│  • Extracts tool_calls from response                     │
│  • Loops through each tool call                          │
└──────────────────────────────────────────────────────────┘
       │
       │ 6. Execute Tool: tool_name + arguments
       ↓
┌──────────────────────────────────────────────────────────┐
│                    MCP Client                            │
│                                                          │
│  POST http://localhost:8080/mcp/v1/tools/call            │
│  {                                                       │
│    "name": "execute_query",                              │
│    "arguments": {                                        │
│      "query": "SELECT * FROM users"                      │
│    }                                                     │
│  }                                                       │
└──────────────────────────────────────────────────────────┘
       │
       │ 7. HTTP Request
       ↓
┌──────────────────────────────────────────────────────────┐
│                   MCP Server                             │
│                                                          │
│  • Receives tool call request                            │
│  • Validates tool name and arguments                     │
│  • Executes actual function (SQL query)                  │
│  • Interacts with SQLite database                        │
│  • Returns result                                        │
└──────────────────────────────────────────────────────────┘
       │
       │ 8. Tool Result
       │    {
       │      "success": true,
       │      "result": [
       │        {"id": 1, "name": "Alice"},
       │        {"id": 2, "name": "Bob"}
       │      ]
       │    }
       ↓
┌──────────────────────────────────────────────────────────┐
│                    MCP Client                            │
│                                                          │
│  • Returns formatted result to chatbot                   │
└──────────────────────────────────────────────────────────┘
       │
       │ 9. Formatted Result
       ↓
┌──────────────────────────────────────────────────────────┐
│                   MCPChatbot                             │
│                                                          │
│  • Appends tool result to messages[]                     │
│    messages.append({                                     │
│      "role": "tool",                                     │
│      "content": "Tool execution successful. Result:\n    │
│                  [{'id': 1, 'name': 'Alice'}, ...]"      │
│    })                                                    │
│                                                          │
│  • Loops back to step 2 (send to Ollama again)          │
└──────────────────────────────────────────────────────────┘
       │
       │ 10. messages + tools[] (with tool result)
       ↓
┌──────────────────────────────────────────────────────────┐
│                   Ollama → LLM                           │
│                                                          │
│  • LLM sees tool result in context                       │
│  • Generates natural language response                   │
│  • No more tool calls needed                             │
└──────────────────────────────────────────────────────────┘
       │
       │ 11. Final Response
       │     {
       │       "message": {
       │         "role": "assistant",
       │         "content": "I found 2 users: Alice and Bob.",
       │         "tool_calls": null
       │       }
       │     }
       ↓
┌──────────────────────────────────────────────────────────┐
│                   MCPChatbot                             │
│                                                          │
│  • No tool_calls detected                                │
│  • Appends assistant response to messages[]              │
│  • Returns response to user                              │
└──────────────────────────────────────────────────────────┘
       │
       │ 12. Display Response
       ↓
┌─────────────┐
│    User     │
│  "I found   │
│  2 users:   │
│  Alice and  │
│  Bob."      │
└─────────────┘
```

## Key Components

### 1. MCPChatbot (`chatbot.py`)
- **Role**: Orchestrator
- **Responsibilities**:
  - Manages conversation history
  - Coordinates between Ollama and MCP
  - Handles tool call loop (max 5 iterations)
  - Formats messages for display

### 2. Ollama Client (`ollama_client.py`)
- **Role**: LLM API Gateway
- **Responsibilities**:
  - Sends HTTP requests to Ollama API
  - Passes tools as structured data
  - Returns parsed responses

### 3. Ollama (External Service)
- **Role**: LLM Runtime + Parser
- **Responsibilities**:
  - Runs the LLM model (Llama 3.1, etc.)
  - Parses model output into `tool_calls` field
  - Handles model loading and inference

### 4. LLM Model
- **Role**: Intelligence Layer
- **Responsibilities**:
  - Understands user intent
  - Decides when to use tools
  - Generates tool calls or text responses
  - Processes tool results

### 5. MCP Client (`mcp_client.py`)
- **Role**: Tool Executor
- **Responsibilities**:
  - Fetches available tools from MCP server
  - Formats tools for Ollama API
  - Executes tool calls via HTTP
  - Returns results to chatbot

### 6. MCP Server (External Service)
- **Role**: Tool Provider
- **Responsibilities**:
  - Exposes tools via HTTP API
  - Executes actual business logic (SQL queries, etc.)
  - Manages resources (database connections)
  - Returns structured results

## Message Flow Example

**User:** "Show me all users in the database"

**Step-by-step:**

1. **MCPChatbot** adds to history:
   ```python
   messages = [
     {"role": "system", "content": "You are a helpful AI assistant..."},
     {"role": "user", "content": "Show me all users in the database"}
   ]
   ```

2. **Ollama Client** sends:
   ```json
   POST /api/chat
   {
     "messages": [...],
     "tools": [{"type": "function", "function": {"name": "execute_query", ...}}]
   }
   ```

3. **LLM** thinks: "User wants database data → I should use execute_query tool"

4. **Ollama** parses output and returns:
   ```json
   {
     "message": {
       "tool_calls": [{
         "function": {
           "name": "execute_query",
           "arguments": {"query": "SELECT * FROM users"}
         }
       }]
     }
   }
   ```

5. **MCPChatbot** extracts tool call and sends to **MCP Client**

6. **MCP Client** calls **MCP Server**:
   ```json
   POST /mcp/v1/tools/call
   {"name": "execute_query", "arguments": {"query": "SELECT * FROM users"}}
   ```

7. **MCP Server** executes SQL and returns:
   ```json
   {"success": true, "result": [{"id": 1, "name": "Alice"}, ...]}
   ```

8. **MCPChatbot** appends to history:
   ```python
   messages.append({"role": "tool", "content": "Tool execution successful..."})
   ```

9. **Back to Ollama** with updated messages (now includes tool result)

10. **LLM** sees result and generates: "I found 2 users: Alice and Bob."

11. **MCPChatbot** displays to user

## Tool Call Loop

The chatbot supports **multiple iterations** (max 5):

```
User Query
    ↓
┌─────────────────────────┐
│  Send to Ollama + Tools │ ← ─────┐
└───────────┬─────────────┘        │
            │                      │
            ↓                      │
    ┌───────────────┐              │
    │  Tool Calls?  │              │
    └───┬───────┬───┘              │
        │       │                  │
       Yes      No                 │
        │       │                  │
        │       └─→ Return Response│
        │                          │
        ↓                          │
┌───────────────┐                  │
│ Execute Tools │                  │
└───────┬───────┘                  │
        │                          │
        ↓                          │
┌───────────────────┐              │
│ Append to History │              │
└───────┬───────────┘              │
        │                          │
        └──────────────────────────┘
           (Loop again)
```

This allows for **chain-of-thought** tool calling where the LLM can:
- Call multiple tools sequentially
- Use results from one tool to inform the next
- Build complex multi-step solutions


