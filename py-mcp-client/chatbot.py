"""MCP-enabled chatbot using Ollama."""
import json
import logging
import yaml
import re
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from mcp_client import MCPClient
from ollama_client import OllamaClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

console = Console()


class MCPChatbot:
    """Chatbot with MCP tool integration."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize chatbot.

        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        self.console = Console()

        # Initialize clients
        self.mcp_client = MCPClient(
            base_url=self.config['mcp_server']['url'],
            timeout=self.config['mcp_server']['timeout']
        )

        self.ollama_client = OllamaClient(
            base_url=self.config['ollama']['base_url'],
            model=self.config['ollama']['model'],
            temperature=self.config['ollama']['temperature'],
            num_ctx=self.config['ollama']['num_ctx'],
            timeout=self.config['ollama']['timeout']
        )

        # Chat history
        self.messages: List[Dict[str, str]] = []
        self.max_history = self.config['chatbot']['max_history']
        self.system_prompt = self.config['chatbot']['system_prompt']
        self.show_tool_calls = self.config['chatbot']['show_tool_calls']

        # Tools for native function calling
        self.ollama_tools: List[Dict[str, Any]] = []

        # Setup prompt session with history
        history_file = Path.home() / ".mcp_chatbot_history"
        self.session = PromptSession(history=FileHistory(str(history_file)))

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file.

        Args:
            config_path: Path to config file

        Returns:
            Configuration dictionary
        """
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def initialize(self) -> bool:
        """Initialize the chatbot and check connections.

        Returns:
            True if initialization successful
        """
        self.console.print("[bold blue]Initializing MCP Chatbot...[/bold blue]")

        # Check MCP server
        self.console.print("Checking MCP server connection...")
        if not self.mcp_client.health_check():
            self.console.print("[bold red]Failed to connect to MCP server![/bold red]")
            return False
        self.console.print("[green]✓ MCP server connected[/green]")

        # Load tools
        self.console.print("Loading MCP tools...")
        try:
            tools = self.mcp_client.list_tools()
            self.console.print(f"[green]✓ Loaded {len(tools)} tools[/green]")
        except Exception as e:
            self.console.print(f"[bold red]Failed to load tools: {e}[/bold red]")
            return False

        # Check Ollama model
        self.console.print(f"Checking Ollama model: {self.ollama_client.model}...")
        if not self.ollama_client.check_model_exists():
            self.console.print(f"[yellow]Model {self.ollama_client.model} not found[/yellow]")
            self.console.print("Would you like to pull it? (y/n): ", end="")
            if input().lower() == 'y':
                if not self.ollama_client.pull_model():
                    self.console.print("[bold red]Failed to pull model[/bold red]")
                    return False
            else:
                return False
        self.console.print("[green]✓ Ollama model ready[/green]")

        # Load tools in Ollama's native format
        self.ollama_tools = self.mcp_client.format_tools_for_ollama()
        self.console.print(f"[green]✓ Formatted {len(self.ollama_tools)} tools for native function calling[/green]")

        # Initialize system message (simplified for native function calling)
        self.messages = [{"role": "system", "content": self.system_prompt}]

        return True

    def _extract_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract tool call from LLM response.

        Args:
            text: LLM response text

        Returns:
            Tool call dictionary or None
        """
        # Look for JSON tool call
        json_pattern = r'\{[^{}]*"tool"[^{}]*"arguments"[^{}]*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)

        for match in matches:
            try:
                tool_call = json.loads(match)
                if "tool" in tool_call and "arguments" in tool_call:
                    return tool_call
            except json.JSONDecodeError:
                continue

        return None

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool and return the result.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Tool execution result as string
        """
        if self.show_tool_calls:
            self.console.print(Panel(
                f"[bold cyan]Tool:[/bold cyan] {tool_name}\n"
                f"[bold cyan]Arguments:[/bold cyan]\n{json.dumps(arguments, indent=2)}",
                title="🔧 Tool Call",
                border_style="cyan"
            ))

        # Execute tool and track timing
        start_time = time.time()
        result = self.mcp_client.call_tool(tool_name, arguments)
        execution_time = time.time() - start_time

        # Display result if showing tool calls
        if self.show_tool_calls:
            if result["success"]:
                result_content = result['result']
                # Truncate long results for display
                display_result = result_content
                if len(str(result_content)) > 500:
                    display_result = str(result_content)[:500] + "\n...(truncated)"

                self.console.print(Panel(
                    f"{display_result}\n\n"
                    f"[dim]Execution time: {execution_time:.2f}s[/dim]",
                    title="✅ Tool Result",
                    border_style="green"
                ))
            else:
                error_msg = result.get('error', 'Unknown error')
                self.console.print(Panel(
                    f"[bold red]{error_msg}[/bold red]\n\n"
                    f"[dim]Execution time: {execution_time:.2f}s[/dim]",
                    title="❌ Tool Error",
                    border_style="red"
                ))

        if result["success"]:
            return f"Tool execution successful. Result:\n{result['result']}"
        else:
            return f"Tool execution failed. Error: {result.get('error', 'Unknown error')}"

    def _chat(self, user_message: str) -> str:
        """Process a chat message.

        Args:
            user_message: User's message

        Returns:
            Assistant's response
        """
        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})

        # Limit history size
        if len(self.messages) > self.max_history * 2 + 1:  # +1 for system message
            self.messages = [self.messages[0]] + self.messages[-(self.max_history * 2):]

        max_iterations = 5
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Get response from LLM with tools
            try:
                response = self.ollama_client.chat(self.messages, tools=self.ollama_tools)
                message = response["message"]
            except Exception as e:
                logger.error(f"Ollama chat failed: {e}")
                return f"Error: Failed to get response from LLM - {str(e)}"

            # Check for native tool calls
            tool_calls = message.get("tool_calls")

            if tool_calls:
                # Add assistant message with tool calls to history
                self.messages.append(message)

                # Execute each tool call
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    tool_name = function.get("name")
                    tool_args = function.get("arguments", {})

                    # Execute tool
                    tool_result = self._execute_tool(tool_name, tool_args)

                    # Add tool result to history
                    self.messages.append({
                        "role": "tool",
                        "content": tool_result
                    })

                # Continue loop to get next response
                continue
            else:
                # No tool calls, check if there's a text response
                assistant_message = message.get("content", "")

                # Fallback: check for JSON-based tool calls in text
                if assistant_message:
                    text_tool_call = self._extract_tool_call(assistant_message)
                    if text_tool_call:
                        # Execute tool
                        tool_result = self._execute_tool(
                            text_tool_call["tool"],
                            text_tool_call["arguments"]
                        )

                        # Add assistant message and tool result to history
                        self.messages.append({"role": "assistant", "content": assistant_message})
                        self.messages.append({
                            "role": "user",
                            "content": f"Tool execution result:\n{tool_result}\n\nPlease continue the conversation based on this result."
                        })

                        # Continue loop to get next response
                        continue

                # No tool calls, this is the final response
                self.messages.append({"role": "assistant", "content": assistant_message})
                return assistant_message

        return "Maximum tool iterations reached. Please try rephrasing your request."

    def run(self):
        """Run the chatbot REPL."""
        if not self.initialize():
            self.console.print("[bold red]Failed to initialize chatbot[/bold red]")
            return

        self.console.print("\n" + "="*70)
        self.console.print(Panel.fit(
            f"[bold green]{self.config['chatbot']['name']}[/bold green]\n"
            f"Model: {self.ollama_client.model}\n"
            f"MCP Server: {self.mcp_client.base_url}\n\n"
            "[dim]Type 'quit', 'exit', or press Ctrl+C to exit\n"
            "Type 'clear' to clear conversation history\n"
            "Type 'tools' to list available tools[/dim]",
            title="🤖 MCP Chatbot Ready",
            border_style="green"
        ))
        self.console.print("="*70 + "\n")

        try:
            while True:
                # Get user input
                try:
                    user_input = self.session.prompt("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    self.console.print("\n[yellow]Goodbye![/yellow]")
                    break

                if not user_input:
                    continue

                # Handle special commands
                if user_input.lower() in ['quit', 'exit']:
                    self.console.print("[yellow]Goodbye![/yellow]")
                    break
                elif user_input.lower() == 'clear':
                    self.messages = [{"role": "system", "content": self.system_prompt}]
                    self.console.print("[green]Conversation history cleared[/green]")
                    continue
                elif user_input.lower() == 'tools':
                    tools = self.mcp_client.get_tool_descriptions()
                    tools_text = "Available Tools:\n\n"
                    for tool in tools:
                        tools_text += f"**{tool['name']}**\n"
                        tools_text += f"{tool['description']}\n"
                        tools_text += f"Parameters:\n{tool['parameters']}\n\n"
                    self.console.print(Panel(Markdown(tools_text), title="🔧 MCP Tools", border_style="cyan"))
                    continue

                # Process message
                self.console.print("\n[bold blue]Assistant:[/bold blue]", end=" ")
                response = self._chat(user_input)

                # Display response
                self.console.print(Markdown(response))
                self.console.print()

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Goodbye![/yellow]")
        finally:
            self.mcp_client.close()
            self.ollama_client.close()


def main():
    """Main entry point."""
    import sys

    config_path = "config.yaml"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    chatbot = MCPChatbot(config_path)
    chatbot.run()


if __name__ == "__main__":
    main()
