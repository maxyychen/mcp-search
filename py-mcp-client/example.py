"""Simple example of using MCP client and Ollama together."""
import yaml
from mcp_client import MCPClient
from ollama_client import OllamaClient


def main():
    """Run a simple example."""
    # Load config
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    print("=== MCP Client Example ===\n")

    # Initialize MCP client
    print("1. Connecting to MCP server...")
    with MCPClient(
        base_url=config['mcp_server']['url'],
        timeout=config['mcp_server']['timeout']
    ) as mcp:
        # Check health
        if mcp.health_check():
            print("   ✓ MCP server is healthy\n")
        else:
            print("   ✗ MCP server is not responding")
            return

        # List tools
        print("2. Loading available tools...")
        tools = mcp.list_tools()
        print(f"   ✓ Found {len(tools)} tools:")
        for tool in tools:
            print(f"     - {tool.name}: {tool.description}")

        # Example: Create a table
        print("\n3. Example: Creating a table...")
        result = mcp.call_tool("create_table", {
            "table_name": "example_users",
            "schema": {
                "id": "INTEGER",
                "name": "TEXT",
                "email": "TEXT"
            },
            "primary_key": "id"
        })

        if result["success"]:
            print(f"   ✓ {result['result']}")
        else:
            print(f"   ✗ Error: {result.get('error')}")

        # Example: Insert record
        print("\n4. Example: Inserting a record...")
        result = mcp.call_tool("insert_record", {
            "table_name": "example_users",
            "data": {
                "id": 1,
                "name": "Alice",
                "email": "alice@example.com"
            }
        })

        if result["success"]:
            print(f"   ✓ {result['result']}")
        else:
            print(f"   ✗ Error: {result.get('error')}")

        # Example: Query records
        print("\n5. Example: Querying records...")
        result = mcp.call_tool("query_records", {
            "table_name": "example_users",
            "limit": 10
        })

        if result["success"]:
            print(f"   ✓ {result['result']}")
        else:
            print(f"   ✗ Error: {result.get('error')}")

    print("\n=== Ollama Client Example ===\n")

    # Initialize Ollama client
    print("1. Connecting to Ollama...")
    with OllamaClient(
        base_url=config['ollama']['base_url'],
        model=config['ollama']['model'],
        temperature=config['ollama']['temperature']
    ) as ollama:
        # Check model
        print(f"   Checking model: {ollama.model}")
        if ollama.check_model_exists():
            print("   ✓ Model is available\n")
        else:
            print(f"   ✗ Model {ollama.model} not found")
            print("   Run: ollama pull gpt-oss:20b")
            return

        # Example chat
        print("2. Example: Simple chat...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in one sentence."}
        ]

        response = ollama.chat(messages)
        assistant_reply = response["message"]["content"]
        print(f"   Assistant: {assistant_reply}")

    print("\n=== Example Complete ===")


if __name__ == "__main__":
    main()
