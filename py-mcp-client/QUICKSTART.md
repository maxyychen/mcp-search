# Quick Start Guide

## Step 1: Start the MCP Server

Open a terminal and start the MCP SQLite server:

```bash
# From the project root
cd /home/maxchen/docker/mcp-sqlite
uvicorn src.server:app --reload --port 8080
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
INFO:     Started reloader process
```

## Step 2: Verify Ollama is Running

Check if Ollama is running and the model is available:

```bash
# Check Ollama service
curl http://localhost:11434/api/tags

# If model is not available, pull it
ollama pull gpt-oss:20b
```

## Step 3: Run the Chatbot

Open a new terminal and run the chatbot:

```bash
cd /home/maxchen/docker/mcp-sqlite/py-mcp-client
python3 chatbot.py
```

## Step 4: Test the Chatbot

Try these example commands:

### List Available Tools
```
You: tools
```

### Create a Table
```
You: Create a table called products with columns: id (integer), name (text), price (real). Make id the primary key.
```

### Insert Data
```
You: Insert a product with id 1, name "Laptop", and price 999.99
```

### Query Data
```
You: Show me all products
```

### Update Data
```
You: Update the price of product with id 1 to 899.99
```

### Delete Data
```
You: Delete the product with id 1
```

## Troubleshooting

### MCP Server Not Running
```
Error: Failed to connect to MCP server!
```
**Solution**: Make sure the MCP server is running on port 8080

### Ollama Model Not Found
```
Model gpt-oss:20b not found
```
**Solution**: Pull the model with `ollama pull gpt-oss:20b`

### Database File Error
The MCP server creates the database file automatically in the `./data` directory. Make sure the server has write permissions.

## Configuration

Edit `config.yaml` to customize:
- MCP server URL
- Ollama model
- Temperature and other LLM parameters
- System prompt
- Chat history size

## Tips

1. Use the `clear` command to reset conversation history
2. Use the `tools` command to see all available MCP tools
3. Tool calls are shown in cyan panels (can be disabled in config)
4. Conversation history is saved in `~/.mcp_chatbot_history`
