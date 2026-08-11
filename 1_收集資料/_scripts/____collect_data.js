#!/usr/bin/env node

const usage = `Usage: node ____collect_data.js --input <path> --output <path> [--dry-run]

This is a safe template. Implement a project-specific collector before use.
`;

if (process.argv.includes("--help")) {
  process.stdout.write(usage);
  process.exit(0);
}

process.stderr.write(
  "Collection template only: define the source schema and explicit output path first.\n",
);
process.exitCode = 2;
