# 🕷️ ScrapeBuster

A Node.js web scraper built with **axios** + **cheerio** for fast, lightweight HTML parsing.

## 🚀 Quick Start

```bash
# 1. Clone & install
npm install

# 2. Configure environment
cp .env.example .env
# Edit .env with your target URL

# 3. Run
npm start
```

## 📁 Project Structure

```
scrapper/
├── src/
│   ├── scraper.js          # Core scraping logic (axios + cheerio)
│   └── utils/
│       └── fileHelper.js   # Save results to JSON files
├── output/                 # Scraped data saved here (gitignored)
├── index.js                # Entry point
├── .env.example            # Environment variable template
└── package.json
```

## ⚙️ Configuration (`.env`)

| Variable           | Default               | Description                     |
|--------------------|-----------------------|---------------------------------|
| `TARGET_URL`       | `https://example.com` | The URL to scrape               |
| `OUTPUT_DIR`       | `./output`            | Directory for output JSON files |
| `REQUEST_DELAY_MS` | `1000`                | Delay between requests (ms)     |

## 🛠️ Tech Stack

- [axios](https://axios-http.com/) — HTTP client
- [cheerio](https://cheerio.js.org/) — Server-side HTML parsing (jQuery-like)
- [dotenv](https://github.com/motdotla/dotenv) — Environment variable management
- [puppeteer-core](https://pptr.dev/) — Available for JS-heavy sites (opt-in)
