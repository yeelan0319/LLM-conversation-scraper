#!/usr/bin/env python3
"""
Gemini Conversation Scraper

Scrapes exported Gemini conversations and formats them as:
User: <message>
Model: <message>
...

Usage:
    1. Local HTML file: python gemini_scraper.py --file conversation.html
    2. Browser mode: python gemini_scraper.py --url <gemini_share_url> --browser
    3. Analyze mode: python gemini_scraper.py --file conversation.html --analyze
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, Tag


def load_html_from_file(file_path: str) -> str:
    """Load HTML content from a local file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return path.read_text(encoding="utf-8")


def load_html_with_playwright(url: str, wait_time: int = 5) -> str:
    """
    Load HTML using Playwright browser automation.
    Opens a browser for manual login, then captures the page content.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install")
        sys.exit(1)

    print(f"Opening browser for URL: {url}")
    print("Please log in to your Google account if prompted.")
    print(f"The page will be captured after {wait_time} seconds of loading...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto(url)

        # Wait for user to log in and page to load
        print("\nWaiting for page to load...")
        print("Press Enter when the conversation is fully visible...")
        input()

        # Get the full page HTML
        html_content = page.content()

        # Optionally save for debugging
        debug_path = Path("debug_gemini_page.html")
        debug_path.write_text(html_content, encoding="utf-8")
        print(f"Page HTML saved to: {debug_path}")

        browser.close()

    return html_content


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

    # Strategy 1: Look for elements with turn/message-related classes
    # Common patterns in Google's chat interfaces
    turn_patterns = [
        # Pattern: message-content with user/model distinction
        {"container": "[class*='turn']", "user_marker": "[class*='user']", "model_marker": "[class*='model']"},
        {"container": "[class*='message']", "user_marker": "[class*='query']", "model_marker": "[class*='response']"},
        {"container": "[class*='conversation']", "user_marker": "[class*='human']", "model_marker": "[class*='assistant']"},
    ]

    # Strategy 2: Look for alternating message blocks
    # Find all text blocks that look like messages
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
        # Determine role
        role = "Model"  # Default
        if user_selector and container.select_one(user_selector):
            role = "User"
        elif model_selector and container.select_one(model_selector):
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


def format_conversation(conversations: list[tuple[str, str]]) -> str:
    """Format conversations as User/Model dialogue."""
    output = []
    for role, message in conversations:
        # Clean up the message
        message = re.sub(r'\n{3,}', '\n\n', message)  # Remove excessive newlines
        message = message.strip()
        output.append(f"{role}: {message}")
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Gemini conversations and format as User/Model dialogue"
    )
    parser.add_argument(
        "--file", "-f",
        help="Path to local HTML file (save the page from your browser while logged in)"
    )
    parser.add_argument(
        "--url", "-u",
        help="Gemini share URL (requires --browser flag)"
    )
    parser.add_argument(
        "--browser", "-b",
        action="store_true",
        help="Use Playwright browser automation (requires manual login)"
    )
    parser.add_argument(
        "--analyze", "-a",
        action="store_true",
        help="Analyze HTML structure to help identify selectors"
    )
    parser.add_argument(
        "--container", "-c",
        help="CSS selector for message containers"
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
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of formatted text"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.file and not args.url:
        parser.error("Either --file or --url must be specified")
    if args.url and not args.browser:
        parser.error("--url requires --browser flag (Gemini requires authentication)")

    # Load HTML
    if args.file:
        print(f"Loading HTML from file: {args.file}")
        html_content = load_html_from_file(args.file)
    else:
        html_content = load_html_with_playwright(args.url)

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
    if args.container:
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
            indent=2
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
