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

# Install browser for Playwright
python -m playwright install chromium
```

## Quick Start: Batch Scraping (Recommended for Many URLs)

For scraping thousands of conversations automatically:

### Step 1: Login Once

To avoid Google's "browser not secure" block, use `--use-chrome` which connects to your regular Chrome:

**Step 1a:** Close all Chrome windows, then start Chrome with remote debugging:

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222

# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

**Step 1b:** In that Chrome window:
1. Go to https://gemini.google.com/
2. Log in to your Google account
3. Open any shared conversation to verify it works

**Step 1c:** Run the login command:
```bash
python gemini_scraper.py --login --use-chrome
```

This extracts cookies from your authenticated Chrome session for batch scraping.

### Step 2: Create URL List

Create a text file with your Gemini share URLs (one per line):

```
# urls.txt
https://gemini.google.com/share/abc123
https://gemini.google.com/share/def456
https://gemini.google.com/share/ghi789
# Lines starting with # are ignored
```

### Step 3: Run Batch Scraping

```bash
python gemini_scraper.py --batch urls.txt --output-dir ./conversations
```

This will:
- Scrape each URL automatically using your saved session
- Add random delays (2-5 seconds) between requests to avoid rate limiting
- Save each conversation to a separate file
- Track progress and resume if interrupted
- Show statistics when complete

### Batch Options

```bash
# Run with visible browser (for debugging)
python gemini_scraper.py --batch urls.txt --output-dir ./out --no-headless

# Custom delays between requests
python gemini_scraper.py --batch urls.txt --delay-min 3 --delay-max 8

# Output as JSON instead of text
python gemini_scraper.py --batch urls.txt --json

# Start fresh (don't skip already-scraped URLs)
python gemini_scraper.py --batch urls.txt --no-resume
```

## Other Usage Methods

### Single URL with Browser

```bash
python gemini_scraper.py --url "https://gemini.google.com/share/abc123" --browser
```

### Local HTML File

If you've saved an HTML file from your browser:

```bash
python gemini_scraper.py --file conversation.html
```

### Analyze HTML Structure

If auto-detection doesn't work, analyze the HTML to find the right selectors:

```bash
python gemini_scraper.py --file conversation.html --analyze
```

### Custom CSS Selectors

```bash
python gemini_scraper.py --batch urls.txt \
  --container ".message-container" \
  --user-selector ".user-query" \
  --model-selector ".model-response"
```

## Command Line Reference

| Option | Description |
|--------|-------------|
| `--login` | Open browser to login and save session |
| `--use-chrome` | Use existing Chrome profile (avoids login issues) |
| `--batch FILE` | Batch scrape URLs from file |
| `--file, -f` | Path to local HTML file |
| `--url, -u` | Single Gemini share URL (with --browser) |
| `--browser, -b` | Use Playwright browser |
| `--output-dir, -d` | Output directory for batch mode |
| `--delay-min` | Min delay between requests (default: 2.0s) |
| `--delay-max` | Max delay between requests (default: 5.0s) |
| `--no-headless` | Show browser window |
| `--no-resume` | Don't skip already-scraped URLs |
| `--analyze, -a` | Analyze HTML structure |
| `--container, -c` | CSS selector for message containers |
| `--user-selector` | CSS selector for user messages |
| `--model-selector` | CSS selector for model messages |
| `--output, -o` | Output file (single URL/file mode) |
| `--json` | Output as JSON |

## Output Structure

For batch scraping, files are saved as:
```
./conversations/
  abc123.txt          # Conversation from share/abc123
  def456.txt          # Conversation from share/def456
  .progress.json      # Resume tracking
  scraping_stats.json # Final statistics
```

## Troubleshooting

### "This browser or app may not be secure"

Google blocks login from automated browsers. Use `--use-chrome` to connect to your regular Chrome:

1. Start Chrome with: `google-chrome --remote-debugging-port=9222`
2. Log in to Google in that browser
3. Run: `python gemini_scraper.py --login --use-chrome`

See "Step 1" above for detailed instructions.

### "No saved session found"

Run `--login` first to authenticate:
```bash
python gemini_scraper.py --login --use-chrome
```

### "No messages found"

1. Run with `--no-headless` to see what's happening
2. Use `--analyze` on a saved HTML to find correct selectors
3. Provide custom selectors with `--container`

### Session Expired

Re-run `--login` to refresh your session.

### Rate Limiting

Increase delays between requests:
```bash
python gemini_scraper.py --batch urls.txt --delay-min 5 --delay-max 10
```

## License

MIT
