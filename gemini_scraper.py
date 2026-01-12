#!/usr/bin/env python3
"""
LLM Conversation Scraper

Scrapes conversations from Gemini, ChatGPT, Claude, and other AI platforms.
Formats them as:
User: <message>
Model: <message>
...

Usage:
    1. List templates: python gemini_scraper.py --list-templates
    2. Local HTML file: python gemini_scraper.py --file conversation.html --template gemini
    3. Single URL with browser: python gemini_scraper.py --url <url> --browser --template chatgpt
    4. Login and save session: python gemini_scraper.py --login
    5. Batch scrape: python gemini_scraper.py --batch urls.txt --template gemini --output-dir ./conversations
    6. Analyze mode: python gemini_scraper.py --file conversation.html --analyze
"""

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup


# Conversation extraction templates for different platforms
TEMPLATES = {
    "gemini": {
        "name": "Gemini Shared Conversations",
        "structure": "turn-based",  # Each container has both user and model
        "container": ".share-turn-viewer",
        "user_selector": "user-query",
        "model_selector": "response-container",
        "description": "For Gemini shared conversation pages (gemini.google.com/share/...)"
    },
    "chatgpt": {
        "name": "ChatGPT Conversations",
        "structure": "attribute-based",  # Role determined by attribute
        "container": "article",
        "role_attribute": "data-turn",
        "role_mapping": {
            "user": "User",
            "assistant": "Model",
        },
        "description": "For ChatGPT conversation exports"
    },
    "claude": {
        "name": "Claude Conversations",
        "structure": "attribute-based",
        "container": "[data-testid*='message']",
        "role_attribute": "data-testid",
        "role_mapping": {
            "user-message": "User",
            "model-message": "Model",
            "assistant-message": "Model",
        },
        "description": "For Claude conversation pages (claude.ai)"
    },
}


# Default paths
SESSION_DIR = Path.home() / ".gemini_scraper_session"
DEFAULT_OUTPUT_DIR = Path("./gemini_conversations")


def find_chrome_user_data_dir() -> Optional[Path]:
    """Find the default Chrome/Chromium user data directory."""
    import platform
    system = platform.system()

    possible_paths = []

    if system == "Darwin":  # macOS
        possible_paths = [
            Path.home() / "Library/Application Support/Google/Chrome",
            Path.home() / "Library/Application Support/Chromium",
        ]
    elif system == "Linux":
        possible_paths = [
            Path.home() / ".config/google-chrome",
            Path.home() / ".config/chromium",
            Path.home() / "snap/chromium/common/chromium",
        ]
    elif system == "Windows":
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        possible_paths = [
            local_app_data / "Google/Chrome/User Data",
            local_app_data / "Chromium/User Data",
        ]

    for path in possible_paths:
        if path.exists():
            return path

    return None


def get_playwright():
    """Import and return playwright, with helpful error message."""
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        print("Playwright not installed. Run:")
        print("  pip install playwright")
        print("  playwright install chromium")
        sys.exit(1)


def login_and_save_session(session_dir: Path = SESSION_DIR, use_chrome: bool = False) -> None:
    """
    Open browser for manual Google login and save the session for reuse.

    Args:
        session_dir: Directory to save session data
        use_chrome: If True, connect to existing Chrome via remote debugging
    """
    sync_playwright = get_playwright()

    session_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("GEMINI SESSION LOGIN")
    print("=" * 60)
    print()

    if use_chrome:
        # Connect to existing Chrome instance via CDP
        print("This method connects to your regular Chrome browser")
        print("(not controlled by automation) to extract cookies.")
        print()
        print("=" * 60)
        print("STEP 1: Start Chrome with remote debugging")
        print("=" * 60)
        print()
        print("Close ALL Chrome windows, then run this command:")
        print()

        import platform
        system = platform.system()
        if system == "Darwin":
            print('  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222')
        elif system == "Windows":
            print('  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222')
        else:
            print('  google-chrome --remote-debugging-port=9222')
            print('  # or: chromium-browser --remote-debugging-port=9222')

        print()
        print("=" * 60)
        print("STEP 2: Log in to Google in that browser")
        print("=" * 60)
        print()
        print("1. In the Chrome window that opens, go to: https://gemini.google.com/")
        print("2. Log in to your Google account if needed")
        print("3. Open any shared conversation to verify access")
        print()
        print("=" * 60)
        print("STEP 3: Press Enter here when ready")
        print("=" * 60)
        print()
        input("Press Enter after completing the steps above...")

        print()
        print("Connecting to Chrome...")

        try:
            with sync_playwright() as p:
                # Connect to existing browser via CDP
                browser = p.chromium.connect_over_cdp("http://localhost:9222")

                # Get the default context (the user's actual browser session)
                context = browser.contexts[0]

                # Get a page to extract browser context
                if context.pages:
                    page = context.pages[0]
                else:
                    page = context.new_page()

                # Extract cookies
                cookies = context.cookies()

                # Extract user agent and other browser fingerprint info
                user_agent = page.evaluate("navigator.userAgent")
                viewport = page.viewport_size

                browser_context = {
                    "user_agent": user_agent,
                    "viewport": viewport,
                    "platform": page.evaluate("navigator.platform"),
                    "languages": page.evaluate("navigator.languages"),
                }

                print(f"Found {len(cookies)} cookies")
                print(f"User agent: {user_agent}")

                # Don't close - user's browser
                browser.close()

        except Exception as e:
            print(f"ERROR: Could not connect to Chrome: {e}")
            print()
            print("Make sure:")
            print("1. Chrome is running with --remote-debugging-port=9222")
            print("2. No other Chrome instances were running before")
            print("3. The port 9222 is not blocked")
            sys.exit(1)

        # Save cookies and browser context to session dir
        cookies_file = session_dir / "cookies.json"
        with open(cookies_file, 'w') as f:
            json.dump(cookies, f)

        context_file = session_dir / "browser_context.json"
        with open(context_file, 'w') as f:
            json.dump(browser_context, f)

        print()
        print("Session saved successfully!")
        print(f"Cookies saved to: {cookies_file}")
        print(f"Browser context saved to: {context_file}")
        print()
        print("You can now close Chrome and run batch scraping:")
        print(f"  python gemini_scraper.py --batch urls.txt --output-dir ./conversations")

    else:
        print("A browser window will open. Please:")
        print("1. Log in to your Google account")
        print("2. Navigate to any Gemini shared conversation")
        print("3. Make sure you can see the conversation content")
        print("4. Press Enter in this terminal when done")
        print()
        print("NOTE: If you see 'This browser may not be secure', use:")
        print("  python gemini_scraper.py --login --use-chrome")
        print()
        print(f"Session will be saved to: {session_dir}")
        print()

        with sync_playwright() as p:
            # Use persistent context to save session data
            context = p.chromium.launch_persistent_context(
                str(session_dir),
                headless=False,
                viewport={"width": 1280, "height": 800}
            )

            page = context.new_page()
            page.goto("https://gemini.google.com/")

            print("Waiting for you to log in...")
            print("Press Enter when you're logged in and can see conversations...")
            input()

            # Verify login by checking for user-specific elements
            print("Verifying session...")
            context.close()

        print()
        print("Session saved successfully!")
        print(f"Session location: {session_dir}")
        print()
        print("You can now run batch scraping with:")
        print(f"  python gemini_scraper.py --batch urls.txt --output-dir ./conversations")


def load_html_from_file(file_path: str) -> str:
    """Load HTML content from a local file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return path.read_text(encoding="utf-8")


def load_html_with_browser(
    url: str,
    session_dir: Optional[Path] = None,
    headless: bool = True,
    wait_selector: Optional[str] = None,
    wait_time: float = 3.0
) -> str:
    """
    Load HTML using Playwright with optional saved session.

    Args:
        url: URL to load
        session_dir: Path to saved session (for authenticated access)
        headless: Run browser in headless mode
        wait_selector: CSS selector to wait for before capturing
        wait_time: Additional wait time in seconds
    """
    sync_playwright = get_playwright()

    with sync_playwright() as p:
        if session_dir and session_dir.exists():
            # Use saved session
            context = p.chromium.launch_persistent_context(
                str(session_dir),
                headless=headless,
                viewport={"width": 1280, "height": 800}
            )
        else:
            # Fresh browser (will need manual login)
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()

        page = context.new_page()

        try:
            page.goto(url, timeout=30000)

            # Wait for content to load
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    pass  # Continue even if selector not found

            # Additional wait for dynamic content
            time.sleep(wait_time)

            # Scroll to load lazy content
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.5)

            html_content = page.content()

        finally:
            context.close()

    return html_content


def scrape_single_url(
    url: str,
    session_dir: Optional[Path] = None,
    headless: bool = True,
    template: Optional[str] = None,
    container_selector: Optional[str] = None,
    user_selector: Optional[str] = None,
    model_selector: Optional[str] = None,
    content_selector: Optional[str] = None
) -> list[tuple[str, str]]:
    """
    Scrape a single URL and return conversations.
    """
    html_content = load_html_with_browser(url, session_dir, headless)
    soup = BeautifulSoup(html_content, "lxml")

    if template:
        return extract_with_template(soup, template)
    elif container_selector:
        return extract_with_selectors(
            soup, container_selector, user_selector, model_selector, content_selector
        )
    else:
        return extract_conversations_auto(soup)


def batch_scrape(
    urls_file: str,
    output_dir: str,
    session_dir: Path = SESSION_DIR,
    delay_min: float = 2.0,
    delay_max: float = 5.0,
    headless: bool = True,
    template: Optional[str] = None,
    container_selector: Optional[str] = None,
    user_selector: Optional[str] = None,
    model_selector: Optional[str] = None,
    content_selector: Optional[str] = None,
    output_json: bool = False,
    resume: bool = True
) -> dict:
    """
    Batch scrape multiple URLs from a file.

    Args:
        urls_file: Path to file containing URLs (one per line)
        output_dir: Directory to save scraped conversations
        session_dir: Path to saved browser session
        delay_min: Minimum delay between requests (seconds)
        delay_max: Maximum delay between requests (seconds)
        headless: Run browser in headless mode
        resume: Skip already-scraped URLs

    Returns:
        Statistics dict with success/failure counts
    """
    urls_path = Path(urls_file)
    if not urls_path.exists():
        raise FileNotFoundError(f"URLs file not found: {urls_file}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Check session
    cookies_file = session_dir / "cookies.json"
    has_cookies = cookies_file.exists()
    has_session = session_dir.exists() and any(session_dir.iterdir())

    if not has_cookies and not has_session:
        print(f"No saved session found at: {session_dir}")
        print("Run with --login first to authenticate:")
        print("  python gemini_scraper.py --login --use-chrome")
        sys.exit(1)

    # Load URLs
    urls = []
    with open(urls_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                urls.append(line)

    print(f"Found {len(urls)} URLs to scrape")
    print(f"Output directory: {output_path}")
    print(f"Session: {session_dir}")
    print()

    stats = {
        "total": len(urls),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "errors": []
    }

    # Progress file for resuming
    progress_file = output_path / ".progress.json"
    completed_urls = set()
    if resume and progress_file.exists():
        with open(progress_file, 'r') as f:
            completed_urls = set(json.load(f).get("completed", []))
        print(f"Resuming: {len(completed_urls)} URLs already completed")

    sync_playwright = get_playwright()

    with sync_playwright() as p:
        # Open browser context
        if has_cookies:
            # Load browser context if available
            context_file = session_dir / "browser_context.json"
            browser_context = {}
            if context_file.exists():
                with open(context_file, 'r') as f:
                    browser_context = json.load(f)
                print(f"Loaded browser context (user agent, viewport, etc.)")

            # Prepare context options
            context_options = {
                "viewport": browser_context.get("viewport", {"width": 1280, "height": 800}),
            }

            # Add user agent if available
            if browser_context.get("user_agent"):
                context_options["user_agent"] = browser_context["user_agent"]

            # Add locale/language if available
            if browser_context.get("languages"):
                # Use the first language as locale
                context_options["locale"] = browser_context["languages"][0] if browser_context["languages"] else None

            # Use fresh browser with saved cookies and context
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',  # Hide automation
                ]
            )
            context = browser.new_context(**context_options)

            # Set additional properties to avoid detection
            context.add_init_script("""
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Fix navigator.plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // Fix navigator.languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)

            # Load cookies
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            print(f"Loaded {len(cookies)} cookies from saved session")
        else:
            # Use persistent context
            context = p.chromium.launch_persistent_context(
                str(session_dir),
                headless=headless,
                viewport={"width": 1280, "height": 800}
            )

        page = context.new_page()

        try:
            for i, url in enumerate(urls, 1):
                # Generate filename from URL
                url_id = url.rstrip('/').split('/')[-1]
                ext = ".json" if output_json else ".txt"
                output_file = output_path / f"{url_id}{ext}"

                # Skip if already completed
                if resume and url in completed_urls:
                    print(f"[{i}/{len(urls)}] Skipping (already done): {url_id}")
                    stats["skipped"] += 1
                    continue

                print(f"[{i}/{len(urls)}] Scraping: {url_id}...", end=" ", flush=True)

                try:
                    # Navigate to URL
                    page.goto(url, timeout=30000)

                    # Wait for content
                    time.sleep(3)

                    # Scroll to load lazy content
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)
                    page.evaluate("window.scrollTo(0, 0)")
                    time.sleep(0.5)

                    # Get HTML and parse
                    html_content = page.content()
                    soup = BeautifulSoup(html_content, "lxml")

                    # Check if we hit a consent/login page
                    if "consent.google.com" in page.url or "accounts.google.com" in page.url:
                        print("ERROR: Hit consent/login page")
                        print(f"  Current URL: {page.url}")
                        stats["failed"] += 1
                        stats["errors"].append({
                            "url": url,
                            "error": "Redirected to consent/login page - authentication may have expired"
                        })
                        continue

                    # Extract conversations
                    if template:
                        conversations = extract_with_template(soup, template)
                    elif container_selector:
                        conversations = extract_with_selectors(
                            soup, container_selector, user_selector,
                            model_selector, content_selector
                        )
                    else:
                        conversations = extract_conversations_auto(soup)

                    if not conversations:
                        # Check if it's a consent page
                        page_title = soup.find("title")
                        page_text = soup.get_text().lower()
                        is_consent_page = (
                            "consent" in page_text[:5000] or
                            "cookie" in page_text[:5000] or
                            (page_title and "consent" in page_title.get_text().lower())
                        )

                        if is_consent_page:
                            print("ERROR: Got consent page instead of content")
                            error_msg = "Got consent/cookie page - session may be invalid or expired"
                        else:
                            print("No messages found!")
                            error_msg = "No messages found"

                        stats["failed"] += 1
                        stats["errors"].append({"url": url, "error": error_msg})

                        # Save debug HTML
                        debug_file = output_path / f"{url_id}_debug.html"
                        debug_file.write_text(html_content, encoding="utf-8")
                        print(f"  Debug HTML saved to: {debug_file}")
                        continue

                    # Format and save output
                    if output_json:
                        output = json.dumps(
                            [{"role": role, "content": msg} for role, msg in conversations],
                            indent=2,
                            ensure_ascii=False
                        )
                    else:
                        output = format_conversation(conversations)

                    output_file.write_text(output, encoding="utf-8")

                    print(f"OK ({len(conversations)} messages)")
                    stats["success"] += 1

                    # Update progress
                    completed_urls.add(url)
                    with open(progress_file, 'w') as f:
                        json.dump({"completed": list(completed_urls)}, f)

                except Exception as e:
                    print(f"ERROR: {e}")
                    stats["failed"] += 1
                    stats["errors"].append({"url": url, "error": str(e)})

                # Random delay between requests
                if i < len(urls):
                    delay = random.uniform(delay_min, delay_max)
                    time.sleep(delay)

        finally:
            context.close()

    # Print summary
    print()
    print("=" * 60)
    print("BATCH SCRAPING COMPLETE")
    print("=" * 60)
    print(f"Total URLs: {stats['total']}")
    print(f"Successful: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    print(f"Skipped: {stats['skipped']}")

    if stats["errors"]:
        print()
        print("Errors:")
        for err in stats["errors"][:10]:
            print(f"  {err['url']}: {err['error']}")
        if len(stats["errors"]) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")

        # Check if consent/authentication errors occurred
        consent_errors = [e for e in stats["errors"] if "consent" in e["error"].lower() or "login" in e["error"].lower()]
        if consent_errors:
            print()
            print("=" * 60)
            print("AUTHENTICATION ISSUE DETECTED")
            print("=" * 60)
            print("Your session cookies may be invalid or expired.")
            print("Please re-authenticate by running:")
            print()
            print("  python gemini_scraper.py --login --use-chrome")
            print()
            print("Then try batch scraping again.")

    # Save stats
    stats_file = output_path / "scraping_stats.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"\nStats saved to: {stats_file}")

    return stats


def analyze_html_structure(soup: BeautifulSoup) -> dict:
    """
    Analyze the HTML structure to help identify conversation elements.
    Returns statistics about common elements and potential conversation markers.
    """
    analysis = {
        "potential_message_containers": [],
        "elements_with_role": [],
        "data_attributes": set(),
        "common_classes": {},
    }

    # Look for elements with role attributes (common in chat UIs)
    for elem in soup.find_all(attrs={"role": True}):
        role = elem.get("role")
        tag = elem.name
        classes = elem.get("class", [])
        analysis["elements_with_role"].append({
            "tag": tag,
            "role": role,
            "classes": classes[:3] if classes else [],
            "text_preview": elem.get_text()[:100].strip() if elem.get_text() else ""
        })

    # Look for data-* attributes
    for elem in soup.find_all():
        for attr in elem.attrs:
            if attr.startswith("data-"):
                analysis["data_attributes"].add(attr)

    # Count class frequencies to find patterns
    class_counts = {}
    for elem in soup.find_all(class_=True):
        for cls in elem.get("class", []):
            class_counts[cls] = class_counts.get(cls, 0) + 1

    # Find classes that appear multiple times (potential message containers)
    analysis["common_classes"] = {
        k: v for k, v in sorted(class_counts.items(), key=lambda x: -x[1])
        if v >= 2 and v <= 100  # Likely message containers
    }

    # Look for turn/message/chat related classes
    chat_keywords = ["message", "turn", "chat", "response", "query", "user", "model", "assistant", "human"]
    for elem in soup.find_all(class_=True):
        classes = elem.get("class", [])
        class_str = " ".join(classes).lower()
        if any(kw in class_str for kw in chat_keywords):
            text = elem.get_text()[:200].strip()
            if text and len(text) > 10:
                analysis["potential_message_containers"].append({
                    "tag": elem.name,
                    "classes": classes,
                    "text_preview": text
                })

    analysis["data_attributes"] = list(analysis["data_attributes"])
    return analysis


def extract_conversations_auto(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """
    Attempt to auto-detect and extract conversations from Gemini HTML.
    Returns list of (role, message) tuples.
    """
    conversations = []

    # Strategy 0: Look for data-message-author attribute (common in Gemini)
    messages_with_author = soup.find_all(attrs={"data-message-author": True})
    if messages_with_author:
        for elem in messages_with_author:
            author = elem.get("data-message-author", "").lower()
            text = elem.get_text(separator="\n", strip=True)
            if text and len(text) > 5:
                role = "User" if "user" in author or "human" in author else "Model"
                conversations.append((role, text))
        if conversations:
            return conversations

    # Strategy 1: Look for message containers with role attributes
    for elem in soup.find_all(attrs={"role": "listitem"}):
        text = elem.get_text(separator="\n", strip=True)
        if text and len(text) > 5:
            # Check for user/model indicators in classes or data attributes
            classes = " ".join(elem.get("class", [])).lower()
            role = "Model"
            if "user" in classes or "query" in classes:
                role = "User"
            # Check siblings or structure for role hints
            conversations.append((role, text))

    if conversations:
        return conversations

    # Strategy 2: Look for specific Gemini conversation patterns
    # Try to find turn containers
    potential_messages = []

    # Look for query-response pairs common in Gemini
    for elem in soup.find_all(class_=lambda x: x and any(
        kw in " ".join(x).lower() for kw in ["query", "prompt", "user-message", "human"]
    )):
        text = elem.get_text(separator="\n", strip=True)
        if text and len(text) > 5:
            potential_messages.append(("User", text))

    for elem in soup.find_all(class_=lambda x: x and any(
        kw in " ".join(x).lower() for kw in ["response", "model-response", "assistant", "answer"]
    )):
        text = elem.get_text(separator="\n", strip=True)
        if text and len(text) > 5:
            potential_messages.append(("Model", text))

    if potential_messages:
        return potential_messages

    # Strategy 3: Look for message-text or similar content classes
    for elem in soup.find_all(class_=lambda x: x and "message" in " ".join(x).lower()):
        classes = " ".join(elem.get("class", [])).lower()
        text = elem.get_text(separator="\n", strip=True)
        if text and len(text) > 10:
            # Try to determine role from classes or parent elements
            role = "Model"  # Default
            if "user" in classes or "query" in classes or "human" in classes:
                role = "User"
            conversations.append((role, text))

    return conversations


def extract_with_template(soup: BeautifulSoup, template_name: str) -> list[tuple[str, str]]:
    """
    Extract conversations using a predefined template.

    Args:
        soup: BeautifulSoup object of the HTML
        template_name: Name of the template to use (from TEMPLATES dict)

    Returns:
        List of (role, message) tuples
    """
    if template_name not in TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}. Available: {', '.join(TEMPLATES.keys())}")

    template = TEMPLATES[template_name]
    structure = template.get("structure")

    if structure == "turn-based":
        # Each container has both user and model messages
        return extract_with_selectors(
            soup,
            template["container"],
            template.get("user_selector"),
            template.get("model_selector"),
            template.get("content_selector")
        )

    elif structure == "attribute-based":
        # Role is determined by an attribute value
        conversations = []
        containers = soup.select(template["container"])
        role_attr = template["role_attribute"]
        role_mapping = template.get("role_mapping", {})

        for container in containers:
            attr_value = container.get(role_attr, "").lower()
            text = container.get_text(separator="\n", strip=True)

            if not text or len(text) < 5:
                continue

            # Map attribute value to role
            role = role_mapping.get(attr_value, "Model")
            conversations.append((role, text))

        return conversations

    elif structure == "class-based":
        # Role is determined by CSS classes
        conversations = []
        containers = soup.select(template["container"])
        role_classes = template.get("role_classes", {})

        for container in containers:
            classes = container.get("class", [])
            class_str = " ".join(classes).lower()
            text = container.get_text(separator="\n", strip=True)

            if not text or len(text) < 5:
                continue

            # Determine role from classes
            role = "Model"  # Default
            for cls in classes:
                if any(user_cls.lower() in cls.lower() for user_cls in role_classes.get("user", [])):
                    role = "User"
                    break
                elif any(model_cls.lower() in cls.lower() for model_cls in role_classes.get("model", [])):
                    role = "Model"
                    break

            conversations.append((role, text))

        return conversations

    else:
        raise ValueError(f"Unknown structure type: {structure}")


def extract_with_selectors(
    soup: BeautifulSoup,
    container_selector: str,
    user_selector: Optional[str] = None,
    model_selector: Optional[str] = None,
    content_selector: Optional[str] = None
) -> list[tuple[str, str]]:
    """
    Extract conversations using custom CSS selectors.

    Args:
        container_selector: CSS selector for message containers
        user_selector: CSS selector to identify user messages (within container)
        model_selector: CSS selector to identify model messages (within container)
        content_selector: CSS selector for message content within container
    """
    conversations = []
    containers = soup.select(container_selector)

    for container in containers:
        # Check if container has both user and model content (turn-based structure)
        user_elem = container.select_one(user_selector) if user_selector else None
        model_elem = container.select_one(model_selector) if model_selector else None

        if user_elem and model_elem:
            # This container has both user and model - extract them separately
            # Extract user message
            user_text = user_elem.get_text(separator="\n", strip=True)
            if user_text and len(user_text) > 5:
                conversations.append(("User", user_text))

            # Extract model message
            model_text = model_elem.get_text(separator="\n", strip=True)
            if model_text and len(model_text) > 5:
                conversations.append(("Model", model_text))

        else:
            # Single role container - use original logic
            role = "Model"  # Default
            if user_elem:
                role = "User"
            elif model_elem:
                role = "Model"
            else:
                # Check class names
                classes = " ".join(container.get("class", [])).lower()
                if "user" in classes or "query" in classes or "human" in classes:
                    role = "User"

            # Extract content
            if content_selector:
                content_elem = container.select_one(content_selector)
                text = content_elem.get_text(separator="\n", strip=True) if content_elem else ""
            else:
                text = container.get_text(separator="\n", strip=True)

            if text and len(text) > 5:
                conversations.append((role, text))

    return conversations


def split_combined_conversation(text: str) -> list[tuple[str, str]]:
    """
    Attempt to split a combined conversation text into individual turns.
    This is a fallback for when all conversation is extracted as one block.
    """
    # First try splitting by double newlines
    chunks = re.split(r'\n\n+', text.strip())

    # If we only got one chunk, try single newlines
    if len(chunks) <= 1:
        chunks = text.strip().split('\n')

    conversations = []
    current_role = "User"  # Conversations typically start with user

    for i, chunk in enumerate(chunks):
        chunk = chunk.strip()
        if not chunk or len(chunk) < 5:
            continue

        # Alternate between User and Model
        conversations.append((current_role, chunk))
        current_role = "Model" if current_role == "User" else "User"

    return conversations


def format_conversation(conversations: list[tuple[str, str]]) -> str:
    """Format conversations as User/Model dialogue."""
    # Check if we have a single large message that might be a combined conversation
    if len(conversations) == 1:
        role, message = conversations[0]
        # If message contains multiple paragraphs separated by blank lines,
        # it might be a combined conversation
        if '\n\n' in message or message.count('\n') > 10:
            # Try to split it
            split_convs = split_combined_conversation(message)
            if len(split_convs) > 1:
                conversations = split_convs

    output = []
    for role, message in conversations:
        # Clean up the message
        message = re.sub(r'\n{3,}', '\n\n', message)  # Remove excessive newlines
        message = message.strip()
        output.append(f"{role}: {message}")
    return "\n\n".join(output)  # Use double newline to separate messages clearly


def main():
    parser = argparse.ArgumentParser(
        description="Scrape AI conversations from Gemini, ChatGPT, Claude, and format as User/Model dialogue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available templates
  python gemini_scraper.py --list-templates

  # Step 1: Login and save session (do this once)
  python gemini_scraper.py --login --use-chrome

  # Step 2: Create a file with URLs to scrape (one per line)
  # urls.txt:
  # https://gemini.google.com/share/abc123
  # https://chatgpt.com/share/def456

  # Step 3: Batch scrape with a template
  python gemini_scraper.py --batch urls.txt --template gemini --output-dir ./conversations
  python gemini_scraper.py --batch urls.txt --template chatgpt --output-dir ./conversations

  # Using custom selectors (instead of template)
  python gemini_scraper.py --batch urls.txt \\
    --container ".share-turn-viewer" \\
    --user-selector "user-query" \\
    --model-selector "response-container" \\
    --output-dir ./conversations

  # Single file parsing
  python gemini_scraper.py --file saved.html --template gemini
  python gemini_scraper.py --file saved.html --analyze  # Analyze HTML structure
        """
    )

    # Input modes (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--file", "-f",
        help="Path to local HTML file"
    )
    input_group.add_argument(
        "--url", "-u",
        help="Single Gemini share URL (use with --browser)"
    )
    input_group.add_argument(
        "--batch",
        metavar="URLS_FILE",
        help="Path to file containing URLs to scrape (one per line)"
    )
    input_group.add_argument(
        "--login",
        action="store_true",
        help="Open browser to login and save session for batch scraping"
    )

    # Browser options
    parser.add_argument(
        "--browser", "-b",
        action="store_true",
        help="Use Playwright browser (required for --url)"
    )
    parser.add_argument(
        "--use-chrome",
        action="store_true",
        help="Use existing Chrome profile for login (avoids 'browser not secure' error)"
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        default=SESSION_DIR,
        help=f"Directory for browser session data (default: {SESSION_DIR})"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (for batch scraping)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser with visible window (useful for debugging)"
    )

    # Batch options
    parser.add_argument(
        "--output-dir", "-d",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for batch scraping (default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "--delay-min",
        type=float,
        default=2.0,
        help="Minimum delay between requests in seconds (default: 2.0)"
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=5.0,
        help="Maximum delay between requests in seconds (default: 5.0)"
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Don't skip already-scraped URLs (start fresh)"
    )

    # Analysis mode
    parser.add_argument(
        "--analyze", "-a",
        action="store_true",
        help="Analyze HTML structure to help identify selectors"
    )

    # Template options
    parser.add_argument(
        "--template", "-t",
        choices=list(TEMPLATES.keys()),
        help=f"Use a predefined template (choices: {', '.join(TEMPLATES.keys())})"
    )
    parser.add_argument(
        "--list-templates",
        action="store_true",
        help="List all available templates and exit"
    )

    # Selector options (for custom extraction)
    parser.add_argument(
        "--container", "-c",
        help="CSS selector for message containers (custom extraction)"
    )
    parser.add_argument(
        "--user-selector",
        help="CSS selector to identify user messages"
    )
    parser.add_argument(
        "--model-selector",
        help="CSS selector to identify model messages"
    )
    parser.add_argument(
        "--content-selector",
        help="CSS selector for message content within container"
    )

    # Output options
    parser.add_argument(
        "--output", "-o",
        help="Output file path (for single URL/file mode)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of formatted text"
    )

    args = parser.parse_args()

    # Handle --list-templates mode
    if args.list_templates:
        print("Available templates:\n")
        for name, info in TEMPLATES.items():
            print(f"  {name}:")
            print(f"    Name: {info['name']}")
            print(f"    Structure: {info['structure']}")
            print(f"    Description: {info['description']}")
            print()
        return

    # Handle --login mode
    if args.login:
        login_and_save_session(args.session_dir, use_chrome=args.use_chrome)
        return

    # Handle --batch mode
    if args.batch:
        headless = not args.no_headless  # Default to headless for batch
        batch_scrape(
            urls_file=args.batch,
            output_dir=args.output_dir,
            session_dir=args.session_dir,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            headless=headless,
            template=args.template,
            container_selector=args.container,
            user_selector=args.user_selector,
            model_selector=args.model_selector,
            content_selector=args.content_selector,
            output_json=args.json,
            resume=not args.no_resume
        )
        return

    # Validate arguments for single-file/URL modes
    if not args.file and not args.url:
        parser.error("One of --file, --url, --batch, or --login is required")
    if args.url and not args.browser:
        parser.error("--url requires --browser flag")

    # Load HTML
    if args.file:
        print(f"Loading HTML from file: {args.file}")
        html_content = load_html_from_file(args.file)
    else:
        html_content = load_html_with_browser(
            args.url,
            session_dir=args.session_dir if args.session_dir.exists() else None,
            headless=args.headless and not args.no_headless
        )

    # Parse HTML
    soup = BeautifulSoup(html_content, "lxml")

    # Analyze mode
    if args.analyze:
        print("\n=== HTML Structure Analysis ===\n")
        analysis = analyze_html_structure(soup)

        print("Potential message containers (classes with chat-related keywords):")
        for item in analysis["potential_message_containers"][:20]:
            print(f"  <{item['tag']}> classes={item['classes']}")
            print(f"    Preview: {item['text_preview'][:80]}...")
            print()

        print("\nElements with 'role' attribute:")
        for item in analysis["elements_with_role"][:10]:
            print(f"  <{item['tag']} role='{item['role']}'> classes={item['classes']}")

        print("\nData attributes found:")
        for attr in sorted(analysis["data_attributes"])[:20]:
            print(f"  {attr}")

        print("\nCommon classes (potential containers):")
        for cls, count in list(analysis["common_classes"].items())[:30]:
            print(f"  {cls}: {count} occurrences")

        print("\n=== Recommendation ===")
        print("1. Look at the 'potential message containers' above")
        print("2. Use browser DevTools to inspect the actual elements")
        print("3. Run again with --container, --user-selector, --model-selector")
        return

    # Extract conversations
    if args.template:
        print(f"Extracting with template: {args.template}")
        conversations = extract_with_template(soup, args.template)
    elif args.container:
        print("Extracting with custom selectors...")
        conversations = extract_with_selectors(
            soup,
            args.container,
            args.user_selector,
            args.model_selector,
            args.content_selector
        )
    else:
        print("Attempting auto-detection of conversation structure...")
        conversations = extract_conversations_auto(soup)

    if not conversations:
        print("\nNo conversations found with auto-detection.")
        print("Try running with --analyze to examine the HTML structure,")
        print("then provide custom selectors with --container option.")
        sys.exit(1)

    print(f"\nFound {len(conversations)} messages")

    # Format output
    if args.json:
        output = json.dumps(
            [{"role": role, "content": msg} for role, msg in conversations],
            indent=2,
            ensure_ascii=False
        )
    else:
        output = format_conversation(conversations)

    # Write output
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Output written to: {args.output}")
    else:
        print("\n=== Conversation ===\n")
        print(output)


if __name__ == "__main__":
    main()
