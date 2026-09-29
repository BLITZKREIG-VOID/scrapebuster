/**
 * @file scraper.js
 * @description Core scraping logic using axios + cheerio for static pages.
 */

"use strict";

const axios = require("axios");
const cheerio = require("cheerio");

const DELAY_MS = parseInt(process.env.REQUEST_DELAY_MS || "1000", 10);

/**
 * Pauses execution for a given number of milliseconds.
 * @param {number} ms - Milliseconds to wait
 * @returns {Promise<void>}
 */
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Scrapes a target URL and extracts basic page data.
 * @param {string} url - The URL to scrape
 * @returns {Promise<Object>} Scraped data
 */
async function scrape(url) {
  console.log(`⏳ Fetching: ${url}`);
  await sleep(DELAY_MS);

  const response = await axios.get(url, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    },
    timeout: 15000,
  });

  const $ = cheerio.load(response.data);

  // --- Extract data (customize this section for your target site) ---
  const title = $("title").text().trim();
  const headings = [];
  $("h1, h2, h3").each((_, el) => {
    headings.push($(el).text().trim());
  });

  const links = [];
  $("a[href]").each((_, el) => {
    const href = $(el).attr("href");
    const text = $(el).text().trim();
    if (href && text) links.push({ text, href });
  });

  return {
    url,
    scrapedAt: new Date().toISOString(),
    title,
    headings,
    links: links.slice(0, 50), // Limit to 50 links
  };
}

module.exports = { scrape };
