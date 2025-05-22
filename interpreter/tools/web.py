import asyncio
import random
import json
from typing import ClassVar, Literal, Optional, List, Dict, Any
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool, ToolResult


class WebTool(BaseAnthropicTool):
    """
    A web scraping tool that uses Playwright to read web pages in a human-like manner.
    Handles JavaScript-rendered content and anti-bot protection including Cloudflare Turnstile.
    """

    name: ClassVar[Literal["web"]] = "web"
    api_type: ClassVar[Literal["function"]] = "function"

    def __init__(self):
        super().__init__()
        self.browser: Optional[Browser] = None
        self.playwright = None

    async def __call__(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        wait_time: int = 3,
        scroll: bool = True,
        extract_links: bool = False,
        extract_images: bool = False,
        max_retries: int = 3,
        **kwargs
    ):
        """
        Scrape a web page with human-like behavior.

        Args:
            url: The URL to scrape
            wait_for_selector: CSS selector to wait for before extracting content
            wait_time: Additional time to wait after page load (seconds)
            scroll: Whether to scroll through the page to trigger lazy loading
            extract_links: Whether to extract all links from the page
            extract_images: Whether to extract all images from the page
            max_retries: Maximum number of retry attempts
        """
        print(f"Web scraper called for URL: {url}")

        for attempt in range(max_retries):
            try:
                result = await self._scrape_page(
                    url=url,
                    wait_for_selector=wait_for_selector,
                    wait_time=wait_time,
                    scroll=scroll,
                    extract_links=extract_links,
                    extract_images=extract_images
                )

                # Format result as JSON string for easier handling
                output = json.dumps(result, indent=2, ensure_ascii=False)
                return ToolResult(output=output)

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    await self._cleanup()
                    # Longer delay between retries
                    await asyncio.sleep(random.uniform(5, 15))
                    continue
                else:
                    error_result = {
                        'url': url,
                        'status': 'error',
                        'error': str(e),
                        'text_content': '',
                        'html_content': '',
                        'title': ''
                    }
                    output = json.dumps(error_result, indent=2)
                    return ToolResult(output=output)

        await self._cleanup()

    async def _ensure_browser(self):
        """Initialize browser if not already started"""
        if not self.browser:
            self.playwright = await async_playwright().start()

            # Enhanced browser launch with additional stealth options
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--disable-gpu',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-default-apps',
                    '--disable-features=TranslateUI,VizDisplayCompositor',
                    '--disable-ipc-flooding-protection',
                    '--disable-renderer-backgrounding',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-field-trial-config',
                    '--disable-back-forward-cache',
                    '--disable-hang-monitor',
                    '--disable-prompt-on-repost',
                    '--disable-sync',
                    '--metrics-recording-only',
                    '--no-report-upload',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
            )

            # Create context with realistic fingerprint
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York',
                geolocation={'latitude': 40.7128, 'longitude': -74.0060},
                permissions=['geolocation'],
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': '"Windows"',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1'
                }
            )

    async def _cleanup(self):
        """Clean up browser resources"""
        if hasattr(self, 'context') and self.context:
            await self.context.close()
            self.context = None
        if hasattr(self, 'browser') and self.browser:
            await self.browser.close()
            self.browser = None
        if hasattr(self, 'playwright') and self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def _human_like_delays(self):
        """Add random delays to simulate human behavior"""
        await asyncio.sleep(random.uniform(1.0, 3.0))

    async def _simulate_realistic_behavior(self, page: Page):
        """Enhanced human-like behavior simulation"""
        try:
            # Random mouse movements with more realistic patterns
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, 1200)
                y = random.randint(100, 800)
                await page.mouse.move(x, y, steps=random.randint(3, 8))
                await asyncio.sleep(random.uniform(0.1, 0.4))

            # Simulate reading behavior with pauses
            await asyncio.sleep(random.uniform(1.5, 4.0))

            # Random scrolling patterns
            if random.random() < 0.7:
                for _ in range(random.randint(1, 3)):
                    scroll_amount = random.randint(150, 500)
                    await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                    await asyncio.sleep(random.uniform(0.8, 2.0))

                    # Sometimes scroll back
                    if random.random() < 0.3:
                        await page.evaluate(f"window.scrollBy(0, -{scroll_amount//2})")
                        await asyncio.sleep(random.uniform(0.5, 1.0))

            # Simulate keyboard activity occasionally
            if random.random() < 0.2:
                await page.keyboard.press('Tab')
                await asyncio.sleep(random.uniform(0.1, 0.3))

        except Exception as e:
            print(f"Warning: Behavior simulation failed: {e}")

    async def _setup_enhanced_stealth(self, page: Page) -> None:
        """Enhanced stealth configuration to bypass Turnstile"""

        # Comprehensive stealth script
        await page.add_init_script("""
            // Remove webdriver indicators
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            delete navigator.__proto__.webdriver;
            
            // Mock chrome runtime and app
            window.chrome = {
                runtime: {
                    onConnect: undefined,
                    onMessage: undefined
                },
                app: {
                    isInstalled: false
                }
            };
            
            // Enhanced plugin mocking
            Object.defineProperty(navigator, 'plugins', {
                get: () => ({
                    length: 5,
                    0: { 
                        name: 'Chrome PDF Plugin',
                        filename: 'internal-pdf-viewer',
                        description: 'Portable Document Format'
                    },
                    1: { 
                        name: 'Chrome PDF Viewer',
                        filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                        description: ''
                    },
                    2: { 
                        name: 'Native Client',
                        filename: 'internal-nacl-plugin',
                        description: ''
                    },
                    3: { 
                        name: 'WebKit built-in PDF',
                        filename: 'webkit-pdf-plugin',
                        description: 'Portable Document Format'
                    },
                    4: { 
                        name: 'Microsoft Edge PDF Viewer',
                        filename: 'edge-pdf-viewer',
                        description: 'Portable Document Format'
                    }
                }),
            });
            
            // Enhanced language support
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            // Mock realistic permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => {
                return parameters.name === 'notifications' ?
                    Promise.resolve({ state: 'default' }) :
                    originalQuery(parameters);
            };
            
            // Enhanced connection info
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: Math.floor(Math.random() * 50) + 30,
                    downlink: Math.random() * 5 + 8,
                    saveData: false
                }),
            });
            
            // Mock realistic hardware
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => [4, 8, 16][Math.floor(Math.random() * 3)],
            });
            
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => [4, 8, 16][Math.floor(Math.random() * 3)],
            });
            
            // Enhanced screen properties
            Object.defineProperty(screen, 'colorDepth', {
                get: () => 24,
            });
            
            Object.defineProperty(screen, 'pixelDepth', {
                get: () => 24,
            });
            
            // Mock battery API
            Object.defineProperty(navigator, 'getBattery', {
                get: () => () => Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: Math.random() * 0.3 + 0.7
                }),
            });
            
            // Override getParameter to return realistic WebGL info
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel(R) Iris(TM) Graphics 6100';
                }
                return getParameter.apply(this, arguments);
            };
            
            // Mock media devices
            Object.defineProperty(navigator, 'mediaDevices', {
                get: () => ({
                    enumerateDevices: () => Promise.resolve([
                        { kind: 'audioinput', deviceId: 'default', label: 'Default - Microphone' },
                        { kind: 'audiooutput', deviceId: 'default', label: 'Default - Speaker' },
                        { kind: 'videoinput', deviceId: 'default', label: 'Default - Camera' }
                    ])
                }),
            });
            
            // Enhanced timezone handling
            const originalDateTimeFormat = Intl.DateTimeFormat;
            Intl.DateTimeFormat = function(...args) {
                const instance = new originalDateTimeFormat(...args);
                const originalResolvedOptions = instance.resolvedOptions;
                instance.resolvedOptions = function() {
                    const options = originalResolvedOptions.call(this);
                    options.timeZone = 'America/New_York';
                    return options;
                };
                return instance;
            };
            
            // Mock clipboard API
            Object.defineProperty(navigator, 'clipboard', {
                get: () => ({
                    writeText: () => Promise.resolve(),
                    readText: () => Promise.resolve('')
                }),
            });
            
            // Enhanced toString override
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === navigator.webdriver ||
                    this === navigator.plugins ||
                    this === navigator.languages ||
                    this === navigator.permissions.query ||
                    this === navigator.connection ||
                    this === navigator.hardwareConcurrency ||
                    this === navigator.deviceMemory) {
                    return 'function () { [native code] }';
                }
                return originalToString.apply(this, arguments);
            };
            
            // Mock performance timing
            Object.defineProperty(performance, 'timing', {
                get: () => ({
                    navigationStart: Date.now() - Math.floor(Math.random() * 1000),
                    loadEventEnd: Date.now() - Math.floor(Math.random() * 500)
                }),
            });
            
            // Add realistic event listeners
            window.addEventListener('beforeunload', () => {});
            window.addEventListener('unload', () => {});
            
            // Mock realistic canvas fingerprint variance
            const originalGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type, ...args) {
                const context = originalGetContext.apply(this, [type, ...args]);
                if (type === '2d' && context) {
                    const originalFillText = context.fillText;
                    context.fillText = function(text, x, y, maxWidth) {
                        // Add slight variance to prevent fingerprinting
                        const variance = (Math.random() - 0.5) * 0.0001;
                        return originalFillText.call(this, text, x + variance, y + variance, maxWidth);
                    };
                }
                return context;
            };
            
            // Mock service worker
            if ('serviceWorker' in navigator) {
                Object.defineProperty(navigator.serviceWorker, 'controller', {
                    get: () => null,
                });
            }
        """)

    async def _handle_turnstile_challenge(self, page: Page, max_wait: int = 60) -> bool:
        """Enhanced Cloudflare Turnstile challenge handler"""
        try:
            # Extended list of Turnstile/Cloudflare indicators
            turnstile_selectors = [
                'iframe[src*="challenges.cloudflare.com"]',
                'div[class*="cf-turnstile"]',
                'div[id*="cf-turnstile"]',
                '.cf-turnstile',
                '#cf-turnstile',
                'div[class*="cf-"]',
                '#cf-wrapper',
                '.cf-browser-verification',
                'div:has-text("Checking your browser")',
                'div:has-text("Just a moment")',
                'div:has-text("Please wait")',
                'div:has-text("DDoS protection")',
                'div:has-text("Verify you are human")',
                'div:has-text("Please complete the security check")',
                '[data-sitekey]'
            ]

            is_challenge = False
            challenge_type = None

            # Check for various challenge indicators
            for selector in turnstile_selectors:
                try:
                    if await page.locator(selector).count() > 0:
                        is_challenge = True
                        if 'turnstile' in selector:
                            challenge_type = 'turnstile'
                        else:
                            challenge_type = 'cloudflare'
                        print(
                            f"Detected {challenge_type} challenge: {selector}")
                        break
                except:
                    continue

            # Also check page content for challenge text
            if not is_challenge:
                try:
                    page_content = await page.content()
                    challenge_indicators = [
                        'checking your browser',
                        'just a moment',
                        'verify you are human',
                        'security check',
                        'ddos protection',
                        'turnstile',
                        'cloudflare'
                    ]

                    content_lower = page_content.lower()
                    for indicator in challenge_indicators:
                        if indicator in content_lower:
                            is_challenge = True
                            challenge_type = 'generic'
                            print(
                                f"Detected challenge by content: {indicator}")
                            break
                except:
                    pass

            if not is_challenge:
                return True

            print(
                f"Handling {challenge_type or 'unknown'} challenge, waiting up to {max_wait}s...")

            # Enhanced challenge solving approach
            start_time = asyncio.get_event_loop().time()
            check_interval = 2.0
            last_check = 0

            while (asyncio.get_event_loop().time() - start_time) < max_wait:
                current_time = asyncio.get_event_loop().time()

                # Perform realistic human actions during wait
                await self._simulate_realistic_behavior(page)

                # Check if challenge is complete (less frequently to avoid detection)
                if current_time - last_check >= check_interval:
                    try:
                        # Multiple ways to check if challenge is complete
                        page_content = await page.content()
                        current_url = page.url

                        # Look for signs that challenge is complete
                        challenge_complete = True
                        content_lower = page_content.lower()

                        for indicator in ['checking your browser', 'just a moment',
                                          'please wait', 'verify you are human',
                                          'security check', 'ddos protection']:
                            if indicator in content_lower:
                                challenge_complete = False
                                break

                        # Additional checks for Turnstile specifically
                        if challenge_type == 'turnstile':
                            turnstile_present = False
                            for selector in ['iframe[src*="challenges.cloudflare.com"]',
                                             'div[class*="cf-turnstile"]', '.cf-turnstile']:
                                try:
                                    if await page.locator(selector).count() > 0:
                                        turnstile_present = True
                                        break
                                except:
                                    continue

                            if turnstile_present:
                                challenge_complete = False

                        if challenge_complete:
                            print("Challenge appears to be resolved")
                            # Wait a bit more to ensure page is fully loaded
                            await asyncio.sleep(random.uniform(2, 4))
                            return True

                        last_check = current_time

                    except Exception as e:
                        print(f"Error checking challenge status: {e}")

                # Variable wait time to appear more human
                await asyncio.sleep(random.uniform(1.5, 3.5))

            print(f"Challenge timeout after {max_wait}s")
            return False

        except Exception as e:
            print(f"Error handling challenge: {e}")
            return False

    async def _scroll_page(self, page: Page):
        """Enhanced natural scrolling with realistic patterns"""
        try:
            # Get page dimensions
            page_height = await page.evaluate("document.body.scrollHeight")
            viewport_height = await page.evaluate("window.innerHeight")

            if page_height <= viewport_height:
                return  # No need to scroll

            # More realistic scrolling pattern
            current_position = 0
            total_scrolled = 0

            while total_scrolled < page_height * 0.8:  # Don't always scroll to bottom
                # Variable scroll amounts
                scroll_amount = random.randint(
                    viewport_height // 4, viewport_height // 2)
                current_position += scroll_amount
                total_scrolled += scroll_amount

                await page.evaluate(f"window.scrollTo(0, {current_position})")

                # Realistic pause times
                await asyncio.sleep(random.uniform(0.8, 2.5))

                # Sometimes pause longer (reading)
                if random.random() < 0.3:
                    await asyncio.sleep(random.uniform(2, 5))

                # Sometimes scroll back up a bit
                if random.random() < 0.2:
                    back_scroll = random.randint(50, 150)
                    current_position = max(0, current_position - back_scroll)
                    await page.evaluate(f"window.scrollTo(0, {current_position})")
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                # Update page height in case new content loaded
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height > page_height:
                    page_height = new_height

            # Sometimes scroll back to top, sometimes stay at bottom
            if random.random() < 0.6:
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"Warning: Error during scrolling: {e}")

    async def _scrape_page(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        wait_time: int = 3,
        scroll: bool = True,
        extract_links: bool = False,
        extract_images: bool = False
    ) -> Dict[str, Any]:
        """
        Internal method to scrape a web page with enhanced Turnstile handling.
        """
        await self._ensure_browser()

        page = await self.context.new_page()

        try:
            await self._setup_enhanced_stealth(page)

            # Initial delay to appear more human
            await asyncio.sleep(random.uniform(1, 3))

            # Navigate to the page with extended timeout
            print(f"Navigating to: {url}")

            # Use goto with networkidle for better challenge detection
            response = await page.goto(
                url,
                wait_until='networkidle',
                timeout=60000
            )

            # Check response status
            if response and response.status >= 400:
                print(f"Warning: HTTP {response.status} response")

            # Enhanced challenge handling with longer timeout
            if not await self._handle_turnstile_challenge(page, max_wait=90):
                raise Exception("Failed to bypass protection challenges")

            # Post-challenge human behavior simulation
            await self._simulate_realistic_behavior(page)

            # Wait for specific selector if provided
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=20000)
                except PlaywrightTimeoutError:
                    print(
                        f"Warning: Selector '{wait_for_selector}' not found within timeout")

            # Extended wait for JavaScript execution
            try:
                await page.wait_for_load_state('networkidle', timeout=30000)
            except PlaywrightTimeoutError:
                print("Warning: Network idle timeout, proceeding anyway")

            # Additional wait time with human variation
            actual_wait = wait_time + random.uniform(1, 3)
            await asyncio.sleep(actual_wait)

            # Enhanced scrolling if requested
            if scroll:
                await self._scroll_page(page)
                await asyncio.sleep(random.uniform(1, 2))

            # Final behavior simulation
            await self._simulate_realistic_behavior(page)

            # Get page content
            html_content = await page.content()

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract comprehensive information
            result = {
                'url': page.url,  # Use actual URL in case of redirects
                'title': soup.title.string.strip() if soup.title and soup.title.string else '',
                'text_content': soup.get_text(separator=' ', strip=True),
                'html_content': html_content,
                'meta_description': '',
                'headings': {},
                'status': 'success',
                'final_url': page.url,
                'response_status': response.status if response else None
            }

            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if not meta_desc:
                meta_desc = soup.find(
                    'meta', attrs={'property': 'og:description'})
            if meta_desc:
                result['meta_description'] = meta_desc.get(
                    'content', '').strip()

            # Extract headings
            for i in range(1, 7):
                headings = soup.find_all(f'h{i}')
                if headings:
                    result['headings'][f'h{i}'] = [h.get_text(strip=True)
                                                   for h in headings if h.get_text(strip=True)]

            # Extract links if requested
            if extract_links:
                links = soup.find_all('a', href=True)
                result['links'] = []
                for link in links:
                    link_text = link.get_text(strip=True)
                    if link_text:
                        result['links'].append({
                            'text': link_text,
                            'href': link['href'],
                            'title': link.get('title', '').strip()
                        })

            # Extract images if requested
            if extract_images:
                images = soup.find_all('img', src=True)
                result['images'] = []
                for img in images:
                    result['images'].append({
                        'src': img['src'],
                        'alt': img.get('alt', '').strip(),
                        'title': img.get('title', '').strip()
                    })

            return result

        finally:
            await page.close()

    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
            "function": {
                "name": self.name,
                "description": "Advanced web scraper with enhanced anti-bot protection bypass including Cloudflare Turnstile. Uses realistic human behavior simulation and stealth techniques for legitimate web scraping purposes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to scrape"
                        },
                        "wait_for_selector": {
                            "type": "string",
                            "description": "Optional CSS selector to wait for before extracting content"
                        },
                        "wait_time": {
                            "type": "integer",
                            "description": "Additional time to wait after page load in seconds (default: 3)",
                            "default": 3
                        },
                        "scroll": {
                            "type": "boolean",
                            "description": "Whether to scroll through the page to trigger lazy loading (default: true)",
                            "default": True
                        },
                        "extract_links": {
                            "type": "boolean",
                            "description": "Whether to extract all links from the page (default: false)",
                            "default": False
                        },
                        "extract_images": {
                            "type": "boolean",
                            "description": "Whether to extract all images from the page (default: false)",
                            "default": False
                        },
                        "max_retries": {
                            "type": "integer",
                            "description": "Maximum number of retry attempts (default: 3)",
                            "default": 3
                        }
                    },
                    "required": ["url"],
                },
            },
        }


# Example usage and testing
async def test_enhanced_scraper():
    """Test the enhanced web scraping tool"""
    tool = WebTool()

    # Test with a site that might have Turnstile protection
    result = await tool(
        url="https://example.com",
        extract_links=True,
        max_retries=2
    )

    print("=== Enhanced Web Scraper Test Result ===")
    print(result.output)

    # Clean up
    await tool._cleanup()

if __name__ == "__main__":
    asyncio.run(test_enhanced_scraper())
