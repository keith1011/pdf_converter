#!/usr/bin/env node

const usage = `Usage: node ____clean_data.js --input <path> --output <path> [--dry-run]

This is a safe template. It must clean a copy, never the original source.
`;

if (process.argv.includes("--help")) {
  process.stdout.write(usage);
  process.exit(0);
}

process.stderr.write(
  "Cleaning template only: define reversible rules and an output copy first.\n",
);
process.exitCode = 2;
