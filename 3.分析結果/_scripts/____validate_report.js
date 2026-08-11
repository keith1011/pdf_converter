#!/usr/bin/env node

const usage = `Usage: node ____validate_report.js --input <report> [--output <report>]

This is a safe template. Add the project's report schema before use.
`;

if (process.argv.includes("--help")) {
  process.stdout.write(usage);
  process.exit(0);
}

process.stderr.write(
  "Report validation template only: define the report schema and coverage rules first.\n",
);
process.exitCode = 2;
