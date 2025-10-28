# MCP SQLite Chatbot

A Python chatbot that integrates with the MCP SQLite Server using local Ollama API. This chatbot can interact with SQLite databases through natural language using the Model Context Protocol (MCP).

## Features

- 🤖 **Local LLM**: Uses Ollama with gpt-oss:20b model (configurable)
- 🔧 **MCP Integration**: Full access to 8 SQLite CRUD tools via MCP protocol
- 💬 **Interactive Chat**: Rich terminal interface with history
- 🛠️ **Tool Calling**: Automatic tool detection and execution
- 📝 **Smart Context**: Maintains conversation history with context management
- 🎨 **Rich UI**: Beautiful terminal UI with syntax highlighting

## Architecture

```
┌─────────────┐      ┌─────────────┐      ┌──────────────────┐
│   Chatbot   │─────▶│   Ollama    │      │   MCP Server     │
│  (Python)   │      │    API      │      │  (SQLite CRUD)   │
│             │◀─────│  gpt-oss    │      │                  │
└─────────────┘      └─────────────┘      └──────────────────┘
       │                                            ▲
       │                                            │
       └────────────── Tool Calls ─────────────────┘
```

For a detailed data flow diagram, see [dataflow.md](dataflow.md).

## How It Works: Key Flow Highlights

**1. User Input → Chatbot**
   - User asks a question in natural language

**2. Chatbot → Ollama Client**
   - Sends conversation history + available tools array via API
   - Tools are passed as structured data, not in prompt text

**3. Ollama Client → LLM Model**
   - Forwards the request to the LLM (e.g., Llama 3.1)
   - Model is trained to recognize tools from API structure

**4. LLM Analysis**
   - Model analyzes user intent
   - Decides if it needs to call tools to answer the question
   - Generates response with `tool_calls` field if tools needed

**5. Ollama Parsing**
   - Ollama automatically parses LLM output into structured JSON
   - Extracts tool calls into `message.tool_calls` field

**6. Chatbot → MCP Client**
   - Chatbot extracts tool name and arguments from `tool_calls`
   - Sends to MCP Client for execution

**7. MCP Client → MCP Server**
   - HTTP POST to `/mcp/v1/tools/call`
   - Sends tool name and arguments as JSON

**8. MCP Server Execution**
   - Executes actual business logic (SQL queries, file operations, etc.)
   - Interacts with SQLite database
   - Returns structured result

**9. Result Back to Chatbot**
   - MCP Client returns formatted result
   - Chatbot appends to conversation history with `role: "tool"`

**10. Loop Back to LLM**
   - Sends updated history (now includes tool result) back to Ollama
   - LLM sees the tool result in context
   - Generates natural language response for the user

**11. Final Response to User**
   - No more tool calls needed
   - Displays formatted answer to user

### Multi-Step Tool Calling

The chatbot supports **iterative tool calling** (up to 5 iterations), enabling:
- Chain multiple tool calls sequentially
- Use results from one tool to inform the next call
- Build complex multi-step solutions automatically
- Handle follow-up queries that require additional data

## Prerequisites

1. **MCP SQLite Server** running on `http://localhost:8080`
   - See parent directory README for setup instructions
   - Start server: `uvicorn src.server:app --reload --port 8080`

2. **Ollama** installed and running
   ```bash
   # Install Ollama (see https://ollama.ai)
   curl https://ollama.ai/install.sh | sh

   # Pull the model
   ollama pull gpt-oss:20b
   ```

3. **Python 3.10+**

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy environment file (optional):
   ```bash
   cp .env.example .env
   ```

3. Review and customize `config.yaml` if needed

## Configuration

### config.yaml

The main configuration file controls all aspects of the chatbot:

```yaml
mcp_server:
  url: "http://localhost:8080"  # MCP server URL
  timeout: 30

ollama:
  base_url: "http://localhost:11434"  # Ollama API URL
  model: "gpt-oss:20b"                # Model to use
  temperature: 0.7
  num_ctx: 4096

chatbot:
  name: "MCP Assistant"
  max_history: 10                     # Number of message pairs to keep
  show_tool_calls: true               # Display tool executions
```

## Usage

### Quick Start

```bash
# Terminal 1: Start MCP Server
cd ..
uvicorn src.server:app --reload --port 8080

# Terminal 2: Start Chatbot
cd py-mcp-client
python chatbot.py
```

### Chat Commands

- **General chat**: Just type your message
- **quit/exit**: Exit the chatbot
- **clear**: Clear conversation history
- **tools**: List all available MCP tools

### Example Conversations

#### Example 1: Creating a Table

```
You: Create a table called users with id, name, and email columns


