# MCP Search Service - Developer Guide

## Table of Contents
- [Overview](#overview)
- [What is MCP?](#what-is-mcp)
- [Getting Started](#getting-started)
- [Service Architecture](#service-architecture)
- [API Reference](#api-reference)
- [Integration Examples](#integration-examples)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

## Overview

The MCP Search Service is a privacy-respecting web search solution that combines **SearXNG** (a metasearch engine) with the **Model Context Protocol (MCP)**, enabling AI applications and LLMs to perform web searches through a standardized interface.

### Key Features

- **Privacy-Focused**: No tracking, respects user privacy
- **MCP-Compliant**: Standard protocol for AI tool integration
- **Easy Integration**: RESTful HTTP API with JSON-RPC 2.0
- **Flexible Search**: Support for multiple search parameters and filters
- **Production-Ready**: Includes health checks, rate limiting, CORS, and authentication
- **Caching**: Built-in 5-minute cache for improved performance
- **Retry Logic**: Automatic retry with exponential backoff

---

## What is MCP?

**Model Context Protocol (MCP)** is an open protocol that standardizes how AI applications provide context to Large Language Models (LLMs). It allows LLMs to:

- Access external tools and services
- Execute operations in a standardized way
- Receive structured responses

Think of it as a "REST API for AI agents" - instead of humans calling APIs, LLMs can discover and use tools automatically.

### Why Use MCP?

1. **Standardization**: One protocol for all tools
2. **Discoverability**: LLMs can list and understand available tools
3. **Safety**: Structured input/output reduces errors
4. **Flexibility**: Works with any MCP-compatible AI application

---

## Getting Started

### Prerequisites

- **Docker** and **Docker Compose** installed
- **Port 8888** (SearXNG UI) available
- **Port 8081** (MCP API) available

### Quick Start

1. **Clone and Start Services**
   ```bash
   cd /home/maxchen/docker/mcp-search
   docker-compose up -d
   ```

2. **Verify Services**
   ```bash
   # Check service status
   docker-compose ps

   # Check MCP health
   curl http://localhost:8081/healthz
   ```

   Expected response:
   ```json
   {
     "status": "ok",
     "version": "0.10.0"
   }
   ```

3. **Test Search**
   ```bash
   curl -X POST http://localhost:8081/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "initialize",
       "params": {
         "protocolVersion": "2024-11-05",
         "capabilities": {},
         "clientInfo": {
           "name": "test-client",
           "version": "1.0.0"
         }
       }
     }'
   ```

---

## Service Architecture

```
┌─────────────────────┐
│   Your Application  │
│   (Python, JS, etc) │
└──────────┬──────────┘
           │ HTTP Requests
           │ (JSON-RPC 2.0)
           ▼
    Port 8081 (MCP API)
┌─────────────────────┐
│  MCP Bridge Server  │
│  - Rate Limiting    │
│  - CORS Support     │
│  - Authentication   │
│  - Caching          │
└──────────┬──────────┘
           │ Internal Network
           │ (searxng:8080)
           ▼
┌─────────────────────┐
│      SearXNG        │
│   Metasearch Engine │
└─────────────────────┘
           │
           ▼
    ┌──────────────────┐
    │  Search Engines  │
    │ (Google, Bing,   │
    │  DuckDuckGo...)  │
    └──────────────────┘
```

### Components

1. **SearXNG**: Aggregates results from multiple search engines
2. **MCP Bridge**: Translates HTTP requests to MCP protocol
3. **Your Application**: Integrates with the MCP API

---

## API Reference

### Base URL
```
http://localhost:8081/mcp
```

### Authentication (Optional)

If `MCP_HTTP_BEARER` is set in [docker-compose.yml](docker-compose.yml):
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8081/mcp
```

### Endpoints

#### 1. Initialize Session

**Required first call** to establish an MCP session.

```bash
POST /mcp
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "your-client-name",
      "version": "1.0.0"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "resources": {},
      "tools": {}
    },
    "serverInfo": {
      "name": "searxng-bridge",
      "version": "0.10.0"
    }
  }
}
```

**Note**: Save the `mcp-session-id` header from the response for subsequent requests.

---

#### 2. List Available Tools

Discover what tools the MCP server provides.

```bash
POST /mcp
Content-Type: application/json
mcp-session-id: <session-id-from-initialize>

{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "search",
        "description": "Perform a search using the configured SearxNG instance",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "The search query string"
            },
            "language": {
              "type": "string",
              "description": "Language code (e.g., 'en-US', 'fr', 'de')"
            },
            "categories": {
              "type": "array",
              "items": {"type": "string"},
              "description": "Categories to search (e.g., ['general', 'images', 'news'])"
            },
            "time_range": {
              "type": "string",
              "description": "Time range: 'day', 'week', 'month', 'year'"
            },
            "safesearch": {
              "type": "number",
              "description": "Safe search level: 0 (off), 1 (moderate), 2 (strict)"
            },
            "max_results": {
              "type": "number",
              "description": "Maximum number of results to return"
            }
          },
          "required": ["query"]
        }
      },
      {
        "name": "health_check",
        "description": "Check the health and connectivity status of the SearxNG bridge",
        "inputSchema": {
          "type": "object",
          "properties": {},
          "required": []
        }
      }
    ]
  }
}
```

---

#### 3. Perform Search

Execute a web search with optional parameters.

```bash
POST /mcp
Content-Type: application/json
mcp-session-id: <session-id>

{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "search",
    "arguments": {
      "query": "docker containerization best practices",
      "language": "en-US",
      "categories": ["general"],
      "max_results": 5,
      "safesearch": 0
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"query\": \"docker containerization best practices\",\n  \"number_of_results\": 5,\n  \"results\": [\n    {\n      \"url\": \"https://example.com/docker-guide\",\n      \"title\": \"Docker Best Practices Guide\",\n      \"content\": \"Complete guide to Docker containerization...\",\n      \"engine\": \"google\"\n    }\n  ]\n}"
      }
    ],
    "isError": false
  }
}
```

---

#### 4. Health Check

Monitor service health and connectivity.

```bash
POST /mcp
Content-Type: application/json
mcp-session-id: <session-id>

{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "health_check",
    "arguments": {}
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"status\": \"healthy\",\n  \"searxng_instance\": \"http://searxng:8080\",\n  \"searxng_status\": \"healthy\",\n  \"response_time_ms\": 145,\n  \"cache_size\": 3,\n  \"debug_mode\": false,\n  \"version\": \"0.10.0\",\n  \"timestamp\": \"2025-11-04T10:30:00.000Z\"\n}"
      }
    ],
    "isError": false
  }
}
```

---

## Integration Examples

### Python Client

See [py-mcp-client/mcp_client.py](py-mcp-client/mcp_client.py) for a full implementation.

**Quick Example:**
```python
from mcp_client import MCPClient

# Initialize client
with MCPClient(base_url="http://localhost:8081/mcp", timeout=30) as mcp:
    # Check health
    if mcp.health_check():
        print("MCP server is healthy")

    # List available tools
    tools = mcp.list_tools()
    for tool in tools:
        print(f"- {tool.name}: {tool.description}")

    # Perform search
    result = mcp.call_tool("search", {
        "query": "python best practices",
        "max_results": 5
    })

    if result["success"]:
        print(result["result"])
    else:
        print(f"Error: {result['error']}")
```

**Installation:**
```bash
cd py-mcp-client
pip install -r requirements.txt
python example.py
```

---

### JavaScript/TypeScript Client

```javascript
class MCPClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
    this.sessionId = null;
  }

  async initialize() {
    const response = await fetch(this.baseUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'initialize',
        params: {
          protocolVersion: '2024-11-05',
          capabilities: {},
          clientInfo: { name: 'js-client', version: '1.0.0' }
        }
      })
    });

    this.sessionId = response.headers.get('mcp-session-id');
    return response.json();
  }

  async search(query, options = {}) {
    const response = await fetch(this.baseUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'mcp-session-id': this.sessionId
      },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 2,
        method: 'tools/call',
        params: {
          name: 'search',
          arguments: { query, ...options }
        }
      })
    });

    return response.json();
  }
}

// Usage
const client = new MCPClient('http://localhost:8081/mcp');
await client.initialize();
const results = await client.search('docker containers', { max_results: 5 });
console.log(results.result.content[0].text);
```

---

### cURL Examples

**Basic Search:**
```bash
# Step 1: Initialize
SESSION_ID=$(curl -si -X POST http://localhost:8081/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"1.0.0"}}}' \
  | grep -i "mcp-session-id" | cut -d' ' -f2 | tr -d '\r')

# Step 2: Search
curl -X POST http://localhost:8081/mcp \
  -H "Content-Type: application/json" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search",
      "arguments": {
        "query": "kubernetes orchestration",
        "max_results": 3
      }
    }
  }' | jq .
```

---

### AI/LLM Integration

The service is designed for AI agents. Here's how an LLM can use it:

**Python with Ollama/vLLM:**
```python
from mcp_client import MCPClient
from ollama_client import OllamaClient

# Setup
mcp = MCPClient(base_url="http://localhost:8081/mcp")
ollama = OllamaClient(base_url="http://localhost:8000", model="gpt-oss:20b")

# Load tools for the LLM
tools = mcp.format_tools_for_ollama()

# Chat with tool access
messages = [
    {"role": "system", "content": "You are a helpful assistant with web search."},
    {"role": "user", "content": "What are the latest Docker security updates?"}
]

response = ollama.chat(messages, tools=tools)

# If LLM wants to use search tool
if response.get("message", {}).get("tool_calls"):
    for tool_call in response["message"]["tool_calls"]:
        result = mcp.call_tool(
            tool_call["function"]["name"],
            tool_call["function"]["arguments"]
        )
        # Add result to conversation and continue...
```

See [py-mcp-client/chatbot.py](py-mcp-client/chatbot.py) for a complete chatbot implementation.

---

## Configuration

### Environment Variables

Edit [docker-compose.yml](docker-compose.yml) to configure the MCP Bridge:

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSPORT` | `http` | Transport mode: `http` or `stdio` |
| `PORT` | `8081` | HTTP server port |
| `HOST` | `0.0.0.0` | Bind address |
| `SEARXNG_INSTANCE_URL` | `http://searxng:8080` | SearXNG backend URL |
| `NODE_ENV` | `production` | Environment mode |
| `CORS_ORIGIN` | `*` (production) | Allowed CORS origins (comma-separated) |
| `MCP_HTTP_BEARER` | *(unset)* | Bearer token for authentication |
| `SEARXNG_BRIDGE_DEBUG` | `false` | Enable debug logging |

**Example with Authentication:**
```yaml
environment:
  - MCP_HTTP_BEARER=your-secret-token-here
```

Then clients must include:
```bash
curl -H "Authorization: Bearer your-secret-token-here" http://localhost:8081/mcp
```

---

### SearXNG Configuration

Customize search behavior by editing [searxng/config/settings.yml](searxng/config/settings.yml):

- **Search engines**: Enable/disable specific engines
- **Privacy settings**: Configure tracking protection
- **Rate limiting**: Adjust request limits
- **UI preferences**: Change appearance

After changes, restart services:
```bash
docker-compose restart
```

---

### Rate Limiting

The MCP Bridge includes built-in rate limiting:
- **1000 requests per minute per IP** (default)
- Configurable in [searxng-mcp-bridge/src/index.ts:461](searxng-mcp-bridge/src/index.ts#L461)

Response when rate limit exceeded:
```json
{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded. Please try again later."
}
```

---

### Caching

- **TTL**: 5 minutes (configurable in [searxng-mcp-bridge/src/index.ts:87](searxng-mcp-bridge/src/index.ts#L87))
- **Automatic cleanup**: Runs every 60 seconds
- **Cache key**: Based on query + all parameters

To clear cache, restart the service:
```bash
docker-compose restart searxng-mcp-bridge
```

---

## Troubleshooting

### Service Won't Start

**Check logs:**
```bash
docker-compose logs -f
```

**Common issues:**
- Port conflicts (8888 or 8081 already in use)
- Docker not running
- Insufficient permissions

**Solution:**
```bash
# Change ports in docker-compose.yml
ports:
  - "9999:8080"  # For SearXNG
  - "9081:8081"  # For MCP Bridge
```

---

### Connection Refused

**Symptom:**
```
Failed to connect to SearXNG instance at http://searxng:8080
```

**Solution:**
```bash
# Check if SearXNG is running
docker ps | grep searxng

# Verify internal connectivity
docker exec searxng-mcp-bridge wget -qO- http://searxng:8080
```

---

### Empty Search Results

**Possible causes:**
1. SearXNG search engines not configured
2. Network connectivity issues
3. Rate limiting by search engines

**Solution:**
```bash
# Check SearXNG web UI
open http://localhost:8888

# Test direct SearXNG search
curl "http://localhost:8888/search?q=test&format=json"
```

---

### CORS Errors

**Symptom:**
```
Access to fetch at 'http://localhost:8081/mcp' from origin 'http://localhost:3000'
has been blocked by CORS policy
```

**Solution:**
Edit [docker-compose.yml](docker-compose.yml):
```yaml
environment:
  - CORS_ORIGIN=http://localhost:3000,http://localhost:3001
```

---

### High Memory Usage

**Check resource usage:**
```bash
docker stats searxng searxng-mcp-bridge
```

**Reduce cache size** in [searxng-mcp-bridge/src/index.ts:87](searxng-mcp-bridge/src/index.ts#L87):
```typescript
private readonly CACHE_TTL = 1 * 60 * 1000; // 1 minute instead of 5
```

---

## Best Practices

### For Developers

1. **Always Initialize**: Call `initialize` before any other MCP operations
2. **Store Session ID**: Reuse the same session for multiple requests
3. **Handle Errors**: Check `isError` field in responses
4. **Respect Rate Limits**: Implement client-side throttling
5. **Cache Results**: Cache search results in your application to reduce API calls
6. **Use Health Checks**: Monitor service health before critical operations

### For Production

1. **Enable Authentication**: Set `MCP_HTTP_BEARER` environment variable
2. **Configure CORS**: Whitelist specific origins instead of using `*`
3. **Monitor Logs**: Set up log aggregation for troubleshooting
4. **Use HTTPS**: Put service behind a reverse proxy with SSL
5. **Backup Configuration**: Keep [searxng/config/settings.yml](searxng/config/settings.yml) in version control
6. **Resource Limits**: Set Docker memory/CPU limits for containers

**Example Production docker-compose.yml:**
```yaml
services:
  searxng-mcp-bridge:
    environment:
      - TRANSPORT=http
      - PORT=8081
      - HOST=0.0.0.0
      - SEARXNG_INSTANCE_URL=http://searxng:8080
      - NODE_ENV=production
      - CORS_ORIGIN=https://yourdomain.com
      - MCP_HTTP_BEARER=${MCP_SECRET_TOKEN}  # From .env file
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
```

### For AI/LLM Applications

1. **Tool Discovery**: Always call `tools/list` to get current schema
2. **Structured Arguments**: Use the `inputSchema` to validate arguments
3. **Iterative Calls**: Use tool results to inform follow-up queries
4. **Error Handling**: Gracefully handle search failures
5. **Result Formatting**: Parse JSON from `content[0].text` field

---

## Additional Resources

- **SearXNG Documentation**: https://docs.searxng.org/
- **Model Context Protocol**: https://modelcontextprotocol.io/
- **MCP Bridge GitHub**: https://github.com/nitish-raj/searxng-mcp-bridge
- **Python Client Example**: [py-mcp-client/README.md](py-mcp-client/README.md)
- **Chatbot Example**: [py-mcp-client/chatbot.py](py-mcp-client/chatbot.py)

---

## Support

For issues and questions:

1. **Service Issues**: Check [README.md](README.md) for infrastructure setup
2. **API Issues**: Review this guide's [Troubleshooting](#troubleshooting) section
3. **Python Client**: See [py-mcp-client/README.md](py-mcp-client/README.md)
4. **MCP Bridge**: Visit https://github.com/nitish-raj/searxng-mcp-bridge/issues

---

## License

- **SearXNG**: AGPLv3
- **SearXNG MCP Bridge**: MIT
- **This Documentation**: Same as parent project

---

**Last Updated**: 2025-11-04
**MCP Bridge Version**: 0.10.0
**SearXNG Version**: latest
