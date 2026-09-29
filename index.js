/**
 * @file index.js
 * @description Entry point for the scrapper project.
 *
 * Usage:
 *   node index.js
 *
 * Environment Variables (see .env.example):
 *   TARGET_URL       - The URL to scrape
 *   OUTPUT_DIR       - Directory to save scraped data
 *   REQUEST_DELAY_MS - Delay between requests (ms)
 */

"use strict";

require("dotenv").config();

const { scrape } = require("./src/scraper");
const { saveToFile } = require("./src/utils/fileHelper");
const path = require("path");
const fs = require("fs");

const TARGET_URL = process.env.TARGET_URL || "https://example.com";
const OUTPUT_DIR = process.env.OUTPUT_DIR || "./output";

(async () => {
  console.log(`\n🕷️  Scrapper Starting...`);
  console.log(`📌 Target URL : ${TARGET_URL}\n`);

  // Ensure output directory exists
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  try {
    const data = await scrape(TARGET_URL);
    const outputPath = path.join(OUTPUT_DIR, `result_${Date.now()}.json`);
    saveToFile(outputPath, data);
    console.log(`\n✅ Done! Data saved to: ${outputPath}`);
  } catch (err) {
    console.error(`\n❌ Scraping failed: ${err.message}`);
    process.exit(1);
  }
})();
