# Gemini Conversation Scraper

Scrapes exported Google Gemini conversations and formats them as clean User/Model dialogue.

## Output Format

```
User: something user said
Model: something model said
User: something user said
Model: something model said
```

## Installation

```bash
pip install -r requirements.txt

# For browser automation mode (optional)
playwright install chromium
```

## Usage

### Method 1: Save HTML Locally (Recommended)

Since Gemini shared conversations require authentication, the easiest approach is to save the HTML from your browser:

1. Open the Gemini share URL in your browser (e.g., `https://gemini.google.com/share/9184c7fceea1`)
2. Log in to your Google account if prompted
3. Wait for the conversation to fully load
4. Save the page: **Ctrl+S** (or **Cmd+S** on Mac) → Save as "Webpage, Complete" or "Webpage, HTML Only"
5. Run the scraper:

```bash
python gemini_scraper.py --file conversation.html
```

### Method 2: Browser Automation

Use Playwright to open a browser, manually log in, and capture the content:

```bash
python gemini_scraper.py --url "https://gemini.google.com/share/9184c7fceea1" --browser
```

This will:
1. Open a Chromium browser window
2. Navigate to the URL
3. Wait for you to log in and confirm the page is loaded
4. Capture the HTML and extract the conversation

### Analyzing HTML Structure

If auto-detection doesn't work, use analyze mode to inspect the HTML:

```bash
python gemini_scraper.py --file conversation.html --analyze
```

This shows potential message containers, CSS classes, and data attributes to help identify the correct selectors.

### Custom Selectors

Once you identify the correct selectors, use them explicitly:

```bash
python gemini_scraper.py --file conversation.html \
  --container ".message-container" \
  --user-selector ".user-query" \
  --model-selector ".model-response" \
  --content-selector ".message-text"
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `--file, -f` | Path to local HTML file |
| `--url, -u` | Gemini share URL (requires --browser) |
| `--browser, -b` | Use Playwright browser automation |
| `--analyze, -a` | Analyze HTML structure for selectors |
| `--container, -c` | CSS selector for message containers |
| `--user-selector` | CSS selector to identify user messages |
| `--model-selector` | CSS selector to identify model messages |
| `--content-selector` | CSS selector for message content |
| `--output, -o` | Output file path (default: stdout) |
| `--json` | Output as JSON instead of text |

## Examples

```bash
# Basic usage with local file
python gemini_scraper.py -f saved_conversation.html

# Save output to file
python gemini_scraper.py -f saved_conversation.html -o conversation.txt

# Output as JSON
python gemini_scraper.py -f saved_conversation.html --json -o conversation.json

# Analyze structure first
python gemini_scraper.py -f saved_conversation.html --analyze

# Browser mode with URL
python gemini_scraper.py -u "https://gemini.google.com/share/abc123" -b
```

## Troubleshooting

### "No conversations found"

1. Run with `--analyze` to see the HTML structure
2. Use browser DevTools (F12) to inspect message elements
3. Provide custom selectors based on what you find

### Authentication Issues

Gemini shared conversations require a Google account login. Use either:
- Method 1: Save HTML while logged in
- Method 2: Browser automation with manual login

### Missing Content

If some messages are missing:
- Make sure the page fully loads before saving
- Scroll through the entire conversation to load all messages
- Check for lazy-loaded content

## License

MIT
