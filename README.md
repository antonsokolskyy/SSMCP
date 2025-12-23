# SSMCP - Super Simple MCP Server

Model Context Protocol (MCP) server providing web search with content extraction.

## Why Use SSMCP?

Many AI models, especially local models or certain cloud-based models, don't have built-in web browsing capabilities. SSMCP bridges that gap by providing a simple, self-hosted solution that gives your AI assistant the ability to:

- **Search and Read the Web**: Let your AI search for current information, read articles, documentation, or any web content
- **Extract Clean Content**: Automatically converts messy web pages into clean Markdown format that AI models can easily understand
- **Access YouTube Transcripts**: Extract subtitles from videos with timestamps for analysis or summarization
- **Privacy-Focused**: Self-hosted solution - your searches and browsing stay on your infrastructure
- **Works with Any Model**: Compatible with local models (like Qwen, Llama) and cloud APIs (DeepSeek, Claude, GPT) that support MCP

**Example Use Cases:**
- Research recent news or developments on a topic
- Read and summarize technical documentation
- Analyze current market trends or product reviews
- Extract information from YouTube tutorials or presentations
- Get up-to-date answers that aren't in the model's training data

## Features

- **Web Search**: Search the web and get results with extracted content in Markdown
- **Web Fetch**: Fetch and extract content from any URL as clean Markdown
- **YouTube Subtitles**: Extract subtitles and timestamps from YouTube videos
- **Powered by**: [SearXNG](https://github.com/searxng/searxng) for search, [Crawl4AI](https://github.com/unclecode/crawl4ai) for content extraction, [yt-dlp](https://github.com/yt-dlp/yt-dlp) for subtitles
- **Simple API**: Easy-to-use interface designed for compatibility with both small local models(like Qwen3 30b) and cloud models lacking web capabilities (e.g., DeepSeek 3.2)
- **Container Support**: Full containerized deployment with Docker Compose

## Quick Start

### Prerequisites

- Docker
- Docker Compose

### 1. Clone this repository

```sh
git clone git@github.com:antonsokolskyy/SSMCP.git
```

### 2. Create .env file

```sh
cd ssmcp/
cp .env.example .env
```

### 3. Set Up SearXNG

Start and stop the `searxng` container to generate `settings.yml`:

```sh
docker compose up searxng
```

Wait until you see:
```
"/etc/searxng/settings.yml" does not exist, creating from template...
```

Then press **Ctrl+C** to stop it.

Edit `deploy/docker/searxng_data/settings.yml` and add `json` to the `formats` list:

```yaml
# remove format to deny access, use lower case.
# formats: [html, csv, json, rss]
formats:
  - html
  - json
```

### 4. Build the SSMCP image

```sh
docker compose --build
```

### 5. Run the Full Stack
```sh
docker compose up -d
```

### YouTube Cookies (Optional)

To access age-restricted or private YouTube videos, and to reduce the chances of hitting captchas or IP blocking, you can provide cookies from your browser.

**Note:** The cookies file must be in Netscape cookie format.

#### Generating cookies.txt

**Option 1: Using Browser Extension**

Install an extension (like "Get cookies.txt LOCALLY") for your browser and export cookies for youtube.com in Netscape format.

**Option 2: Using yt-dlp Binary**

```sh
yt-dlp --cookies-from-browser chrome --cookies cookies.txt https://www.youtube.com/watch?v=VIDEO_ID
```

Replace `chrome` with your browser (`firefox`, `edge`, `safari`, etc.). This automatically exports in Netscape format.

#### Using cookies.txt

Place the generated `cookies.txt` file in:
```
deploy/docker/ssmcp/cookies.txt
```

**Security Warning:** The cookies file contains authentication tokens and sensitive data. Set appropriate file permissions to prevent unauthorized access:

```sh
chmod 600 deploy/docker/ssmcp/cookies.txt
```

The file will be automatically detected and used by Docker container.

### MCP URL

The server uses **Streamable HTTP** transport. Connect to the MCP server at:
```
http://{HOST}:{PORT}/mcp
```

Example:
```
http://localhost:8000/mcp
```

## Tools

### web_search

Performs a web search and returns relevant results with extracted content.

**Parameters:**
- `query` (str): Search query or keywords to find relevant web content

**Returns:**
- List of results, each containing:
  - `url` (str): The webpage URL
  - `content` (str): Page content in Markdown format

### web_fetch

Fetches content from a specified URL and converts it to Markdown.

**Parameters:**
- `url` (str): The URL to fetch content from

**Returns:**
- String containing the page content in Markdown format

### youtube_get_subtitles

Gets subtitles/captions from a YouTube video and returns the text content.

**Parameters:**
- `url` (str): YouTube video URL to get subtitles from

**Returns:**
- String containing the subtitles with timestamps in format: [HH:MM:SS.mmm] text

## How Search Works

SSMCP uses a pipeline to deliver clean content from web searches:

### 1. Search (SearXNG)
- Queries are sent to a local [SearXNG](https://github.com/searxng/searxng) instance
- SearXNG aggregates results from multiple search engines
- Returns a list of URLs with titles and snippets

### 2. Content Extraction (Crawl4AI)
- Each URL is fetched using headless Chromium browser
- Pages are fully rendered (JavaScript executed, dynamic content loaded)
- Filtered content is extracted
- All URLs are processed concurrently

### 3. CSS Selector Matching
- Applies a priority list of CSS selectors to find main content
- Default selectors (in order): `article`, `main`, `[role="main"]`, `.article`, `.article-content`, etc.
- For each selector:
  1. Checks if the element exists in the page
  2. Counts words in the element
  3. Returns the first match with ≥ 50 words (configurable)
- If a match is found, the filtered HTML is re-processed through Crawl4AI
- **Fallback**: If no selector matched, uses HTML from step 2

### 4. Markdown Conversion
- The selected HTML is converted to clean Markdown format
- Removes images and external links for cleaner output

### Configuration
All extraction and filtering parameters are configurable via environment variables. See `.env.example`

## Development

All development tasks are performed inside the Docker container. Nothing needs to be installed on the host machine except Docker and Docker Compose.

### Available Make Commands

Run `make help` to see all available commands:

### Development Workflow

0. **Enable Development mode:**  
   Open `.env` and uncomment the line
   ```
   COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml
   ```

1. **Start the services:**
   ```sh
   make build
   ```

2. **Open a shell in the container:**
   ```sh
   make shell
   ```
   
   Inside the shell, you can run any command:
   ```sh
   uv run python -m ssmcp.server
   uv run pytest -v
   ```

3. **Edit code on your host machine** - Changes are automatically reflected in the container via volume mounts

4. **Run tests:**
   ```sh
   make test
   ```

5. **Check code quality (lint + type-check):**
   ```sh
   make check
   ```

6. **Restart or rebuild if needed:**
   ```sh
   make restart
   make rebuild
   ```

7. **Stop services:**
   ```sh
   make down
   ```

## Configuration

All configuration is managed through environment variables. See `.env.example` for available options

## License

Apache License 2.0 - see [LICENSE](LICENSE) file for details.
