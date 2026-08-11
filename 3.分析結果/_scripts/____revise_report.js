#!/usr/bin/env node

const usage = `Usage: node ____revise_report.js --input <report> --output <report>

This is a safe template. Revisions must be written to a new output file.
`;

if (process.argv.includes("--help")) {
  process.stdout.write(usage);
  process.exit(0);
}

process.stderr.write(
  "Report revision template only: provide an explicit new output path first.\n",
);
process.exitCode = 2;
