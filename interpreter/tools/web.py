from typing import ClassVar, Literal, Optional
import asyncio
import re
import time
import os
from pathlib import Path
import tempfile

from playwright.async_api import async_playwright
from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool, ToolResult, ToolError


class WebTool(BaseAnthropicTool):
    """Tool for accessing web content using Playwright for full JavaScript rendering."""

    name: ClassVar[Literal["web"]] = "web"
    api_type: ClassVar[Literal["function"]] = "function"
    
    async def __call__(
        self, 
        url: str, 
        selector: Optional[str] = None, 
        wait_for_load: bool = True, 
        wait_time: int = 5,
        javascript: Optional[str] = None,
        **kwargs
    ):
        """
        Fetch and extract content from a web page using Playwright.
        
        Args:
            url: The URL to visit
            selector: Optional CSS selector to extract specific content (default: extracts body content)
            wait_for_load: Whether to wait for the page to fully load (default: True)
            wait_time: Seconds to wait after navigation before extracting content (default: 5)
            javascript: Optional JavaScript code to execute before extracting content
        """
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            
        try:
            # Launch playwright and browser asynchronously
            content = await self._get_page_content(url, selector, wait_for_load, wait_time, javascript)
            return ToolResult(output=content)
        except Exception as e:
            error_message = f"Error accessing {url}: {str(e)}"
            return ToolResult(error=error_message)
    
    async def _get_page_content(self, url, selector, wait_for_load, wait_time, javascript):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            )
            
            # Enable JavaScript
            page = await context.new_page()
            
            try:
                # Navigate to the URL with a timeout
                response = await page.goto(url, wait_until="domcontentloaded" if wait_for_load else "commit", timeout=30000)
                
                if not response:
                    raise ToolError(f"Failed to load page: {url}")
                    
                if response.status >= 400:
                    raise ToolError(f"HTTP error {response.status} when accessing {url}")
                
                # Wait for additional time if specified
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                
                # Execute custom JavaScript if provided
                if javascript:
                    await page.evaluate(javascript)
                
                # Extract content based on selector or default to body
                if selector:
                    element = await page.query_selector(selector)
                    if not element:
                        raise ToolError(f"Selector '{selector}' not found on page")
                    content = await element.inner_text()
                else:
                    # Get the text content of the entire page, cleaning it
                    content = await page.content()
                    # Simple HTML to text conversion as fallback
                    content = await page.evaluate("""() => {
                        return document.body.innerText;
                    }""")
                
                # Clean up the content
                content = self._clean_content(content)
                
                await browser.close()
                return content
                
            except Exception as e:
                await browser.close()
                raise e
    
    def _clean_content(self, content):
        """Clean up webpage content by removing excessive whitespace."""
        # Replace multiple newlines with a single one
        content = re.sub(r'\n\s*\n', '\n\n', content)
        # Trim leading/trailing whitespace
        content = content.strip()
        return content
    
    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
            "function": {
                "name": self.name,
                "description": "Access web content with full JavaScript rendering support. Can extract specific elements using CSS selectors.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to visit (e.g., 'https://example.com' or just 'example.com')"
                        },
                        "selector": {
                            "type": "string",
                            "description": "Optional CSS selector to extract specific content (e.g., 'div.main-content')"
                        },
                        "wait_for_load": {
                            "type": "boolean",
                            "description": "Whether to wait for the page to fully load (default: true)"
                        },
                        "wait_time": {
                            "type": "integer",
                            "description": "Additional seconds to wait after navigation (default: 5)"
                        },
                        "javascript": {
                            "type": "string",
                            "description": "Optional JavaScript code to execute before extracting content"
                        }
                    },
                    "required": ["url"],
                },
            },
        }
