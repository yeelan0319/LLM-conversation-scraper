# LLM Conversation Scraper

Scrapes AI conversations from Gemini, ChatGPT, Claude, and other LLM platforms. Formats them as clean User/Model dialogue.

## Features

- 🤖 **Multi-platform support** - Gemini, ChatGPT, Claude
- 🎯 **Template system** - Predefined extraction rules for major platforms
- 📦 **Batch processing** - Scrape thousands of URLs automatically
- 🔐 **Authentication** - Save and reuse browser sessions
- 🔧 **Custom selectors** - For platforms not covered by templates

## Supported Platforms

| Platform | Template | Automated Scraping | Authentication |
|----------|----------|-------------------|----------------|
| **Gemini** | `gemini` | ✅ Yes | Required (use `--login --use-chrome`) |
| **ChatGPT** | `chatgpt` | ✅ Yes | Not required for public shares |
| **Claude** | `claude` | ❌ No (Cloudflare) | Manual HTML download required |

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

## Quick Start

### List Available Templates

```bash
python gemini_scraper.py --list-templates
```

### Gemini: Batch Scraping (Requires Authentication)

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
python gemini_scraper.py --batch urls.txt --template gemini --output-dir ./conversations
```

This will:
- Scrape each URL automatically using your saved session
- Add random delays (2-5 seconds) between requests to avoid rate limiting
- Save each conversation to a separate file
- Track progress and resume if interrupted
- Show statistics when complete

### ChatGPT: Public Shares (No Authentication)

For publicly shared ChatGPT conversations:

```bash
# Create urls.txt with ChatGPT share URLs
echo "https://chatgpt.com/share/def456" > chatgpt_urls.txt

# Batch scrape (no authentication needed for public shares)
python gemini_scraper.py --batch chatgpt_urls.txt --template chatgpt --output-dir ./conversations
```

### Claude: Manual HTML Download (Cloudflare Protection)

Claude.ai uses Cloudflare protection that blocks automated scraping. Workaround:

```bash
# 1. Manually open the Claude conversation URL in your browser
# 2. Complete any Cloudflare challenges ("Verify you are human")
# 3. Save the page as HTML (Ctrl+S / Cmd+S)
# 4. Parse the saved file
python gemini_scraper.py --file claude_conversation.html --template claude
```

### Batch Options

```bash
# Run with visible browser (for debugging)
python gemini_scraper.py --batch urls.txt --template gemini --no-headless

# Custom delays between requests
python gemini_scraper.py --batch urls.txt --template chatgpt --delay-min 3 --delay-max 8

# Output as JSON instead of text
python gemini_scraper.py --batch urls.txt --template gemini --json

# Start fresh (don't skip already-scraped URLs)
python gemini_scraper.py --batch urls.txt --template chatgpt --no-resume
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
| `--list-templates` | List all available templates and exit |
| `--template, -t` | Use predefined template (gemini, chatgpt, claude) |
| `--login` | Open browser to login and save session |
| `--use-chrome` | Use existing Chrome profile (avoids login issues) |
| `--batch FILE` | Batch scrape URLs from file |
| `--file, -f` | Path to local HTML file |
| `--url, -u` | Single share URL (with --browser) |
| `--browser, -b` | Use Playwright browser |
| `--output-dir, -d` | Output directory for batch mode |
| `--delay-min` | Min delay between requests (default: 2.0s) |
| `--delay-max` | Max delay between requests (default: 5.0s) |
| `--no-headless` | Show browser window |
| `--no-resume` | Don't skip already-scraped URLs |
| `--analyze, -a` | Analyze HTML structure |
| `--container, -c` | CSS selector for message containers (custom) |
| `--user-selector` | CSS selector for user messages (custom) |
| `--model-selector` | CSS selector for model messages (custom) |
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
python gemini_scraper.py --batch urls.txt --template gemini --delay-min 5 --delay-max 10
```

### Cloudflare Challenge ("Verify you are human")

Some platforms (like Claude) use Cloudflare protection that blocks automation.

**Error message:** `"Cloudflare challenge detected - this site blocks automated scraping"`

**Solution:** Manual HTML download:
1. Open the URL in your browser
2. Complete the Cloudflare challenge
3. Save the page as HTML (File → Save Page As, or Ctrl+S / Cmd+S)
4. Parse the saved file:
   ```bash
   python gemini_scraper.py --file saved.html --template claude
   ```

## Creating Custom Templates

For platforms not covered by built-in templates, you can:

1. **Analyze the HTML structure:**
   ```bash
   python gemini_scraper.py --file conversation.html --analyze
   ```

2. **Use custom selectors:**
   ```bash
   python gemini_scraper.py --batch urls.txt \
     --container ".message-wrapper" \
     --user-selector ".human-message" \
     --model-selector ".ai-message"
   ```

3. **Or add to `TEMPLATES` in `gemini_scraper.py`:**
   ```python
   "myplatform": {
       "name": "My Platform",
       "structure": "attribute-based",
       "container": "article.message",
       "role_attribute": "data-role",
       "role_mapping": {
           "user": "User",
           "assistant": "Model",
       },
       "description": "For My Platform conversations"
   }
   ```

## License

MIT
