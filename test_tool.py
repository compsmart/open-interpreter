#!/usr/bin/env python3
"""
Test script for the new TestTool in Open Interpreter.
This script demonstrates how to use the new TestTool.
"""

from development.interpreter.tools.collection import ToolCollection
from development.interpreter.tools.test import TestTool
from development.interpreter.interpreter import Interpreter
import sys
import os
import asyncio
from pathlib import Path

# Add the development directory to the path so we can import the interpreter module
sys.path.append(str(Path(__file__).parent.parent.parent))


async def main():
    # Create a tool collection with just our TestTool
    test_tool = TestTool()
    tool_collection = ToolCollection(test_tool)

    print(f"Testing {test_tool.name} tool...")

    # Execute the tool and get the result
    result = await tool_collection.run(name="test", tool_input={})

    print(f"Tool output: {result.output}")

    # You can also manually create an Interpreter instance and add the test tool
    print("\nTesting via Interpreter class...")
    interpreter = Interpreter()
    # Add 'test' to the allowed tools
    interpreter.tools.append("test")

    print("TestTool was successfully installed!")
    print("To use it in the Open Interpreter, run:")
    print("    interpreter = Interpreter()")
    print("    interpreter.tools.append('test')")
    print("    interpreter.chat()")
    print("\nThen you can ask the AI to use the test tool to see 'hello world'.")

if __name__ == "__main__":
    asyncio.run(main())
