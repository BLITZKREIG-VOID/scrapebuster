/**
 * @file fileHelper.js
 * @description Utility to save scraped data to the filesystem.
 */

"use strict";

const fs = require("fs");

/**
 * Saves a JavaScript object as a formatted JSON file.
 * @param {string} filePath - Absolute or relative path for the output file
 * @param {Object} data - Data to serialize and save
 */
function saveToFile(filePath, data) {
  const json = JSON.stringify(data, null, 2);
  fs.writeFileSync(filePath, json, "utf-8");
  console.log(`💾 Saved ${json.length} bytes → ${filePath}`);
}

module.exports = { saveToFile };
