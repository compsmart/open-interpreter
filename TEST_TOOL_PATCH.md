# Open Interpreter TestTool Patch
# This patch adds a new "test" tool to Open Interpreter with three different functions

# Step 1: Create test.py in the tools directory
# File: development/interpreter/tools/test.py
```python
from typing import ClassVar, Literal

from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool, ToolResult


class TestTool(BaseAnthropicTool):
    """A test tool with three different functions."""

    name: ClassVar[Literal["test"]] = "test"
    api_type: ClassVar[Literal["function"]] = "function"

    async def __call__(self, function_name="test1", user_name=None, **kwargs):
        """Execute the selected test function and return its output.
        
        Args:
            function_name: Which function to run (test1, test2, or test3)
            user_name: Optional username for test2 function
        """
        print(f"Test tool called with function: {function_name}, args: {kwargs}")
        
        if function_name == "test1":
            return ToolResult(output="hello world")
        elif function_name == "test2":
            name = user_name if user_name else "user"
            return ToolResult(output=f"hello {name}")
        elif function_name == "test3":
            return ToolResult(output="goodbye")
        else:
            return ToolResult(output=f"Unknown function: {function_name}")

    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
            "function": {
                "name": self.name,
                "description": "A test tool with three different functions: test1 outputs 'hello world', test2 outputs a personalized greeting, and test3 outputs 'goodbye'",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "enum": ["test1", "test2", "test3"],
                            "description": "The test function to execute"
                        },
                        "user_name": {
                            "type": "string",
                            "description": "Optional user name for test2 function"
                        }
                    },
                    "required": ["function_name"],
                },
            },
        }
```

# Step 2: Update __init__.py to expose the TestTool
# File: development/interpreter/tools/__init__.py
# Add the import:
```python
from .test import TestTool
```

# Add TestTool to __ALL__:
```python
__ALL__ = [
    BashTool,
    CLIResult,
    ComputerTool,
    EditTool,
    TestTool,  # Add this line
    ToolCollection,
    ToolResult,
]
```

# Step 3: Update interpreter.py to import and use TestTool
# File: development/interpreter/interpreter.py
# Add TestTool to the import:
```python
from .tools import BashTool, ComputerTool, EditTool, TestTool, ToolCollection, ToolResult
```

# Add TestTool to the tools list in async_respond:
```python
tools = []
if "interpreter" in self.tools:
    tools.append(BashTool())
if "editor" in self.tools:
    tools.append(EditTool())
if "gui" in self.tools:
    tools.append(ComputerTool())
if "test" in self.tools:
    tools.append(TestTool())
```

# Add the test tool definition for non-Anthropic models:
```python
if "test" in self.tools:
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "test",
                "description": "A test tool with three different functions: test1 outputs 'hello world', test2 outputs a personalized greeting, and test3 outputs 'goodbye'",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "enum": ["test1", "test2", "test3"],
                            "description": "The test function to execute"
                        },
                        "user_name": {
                            "type": "string",
                            "description": "Optional user name for test2 function"
                        }
                    },
                    "required": ["function_name"],
                },
            },
        }
    )
```
