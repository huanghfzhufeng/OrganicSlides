#!/usr/bin/env node
/**
 * CLI runner for html2pptx.js
 *
 * Usage:
 *   node html2pptx_runner.js <html_file> <output_pptx>
 *
 * Outputs JSON to stdout:
 *   { "success": true, "output_path": "...", "placeholders": [...] }
 *   { "success": false, "error": "..." }
 */

const path = require('path');
const html2pptx = require('./html2pptx');

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    const msg = { success: false, error: 'Usage: html2pptx_runner.js <html_file> <output_pptx>' };
    process.stdout.write(JSON.stringify(msg) + '\n');
    process.exit(1);
  }

  const htmlFile = args[0];
  const outputPptx = args[1];

  try {
    // pptxgenjs must be available in node_modules
    const pptxgen = require('pptxgenjs');
    const prs = new pptxgen();
    prs.layout = 'LAYOUT_16x9';

    const { slide, placeholders } = await html2pptx(htmlFile, prs);

    await prs.writeFile({ fileName: outputPptx });

    const result = {
      success: true,
      output_path: path.resolve(outputPptx),
      placeholders: placeholders || [],
    };
    process.stdout.write(JSON.stringify(result) + '\n');
  } catch (err) {
    const result = { success: false, error: String(err.message || err) };
    process.stdout.write(JSON.stringify(result) + '\n');
    process.exit(1);
  }
}

main();
