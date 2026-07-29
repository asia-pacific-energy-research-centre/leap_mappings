// Build the review-only temporal gap and subtotal workbook.

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  SpreadsheetFile,
  Workbook,
} from "@oai/artifact-tool";

const scriptPath = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(scriptPath), "..");
const outputRoot = path.join(
  repoRoot,
  "outputs",
  "separate_axis_mapping_gap_review_20260729",
);
const dataRoot = path.join(outputRoot, "data");
const previewRoot = path.join(outputRoot, "previews");
const outputPath = path.join(
  outputRoot,
  "separate_axis_mapping_gap_and_subtotal_review.xlsx",
);

const COLORS = {
  navy: "#1F4E78",
  blue: "#D9EAF7",
  paleBlue: "#EAF3F8",
  orange: "#FCE4D6",
  yellow: "#FFF2CC",
  green: "#E2F0D9",
  red: "#F4CCCC",
  grey: "#E7E6E6",
  darkGrey: "#595959",
  white: "#FFFFFF",
};

async function readCsvRows(filename) {
  const csvText = await fs.readFile(path.join(dataRoot, filename), "utf8");
  const csvWorkbook = await Workbook.fromCSV(csvText, { sheetName: "Data" });
  const used = csvWorkbook.worksheets.getItem("Data").getUsedRange();
  if (!used) return [];
  return used.values.map((row, rowIndex) => row.map((value) => {
    if (rowIndex === 0 || typeof value !== "string") return value;
    if (value.toLowerCase() === "true") return "TRUE";
    if (value.toLowerCase() === "false") return "FALSE";
    return value;
  }));
}

function addTitle(sheet, title, subtitle, columnCount) {
  const lastColumn = columnName(Math.max(columnCount, 3));
  sheet.mergeCells(`A1:${lastColumn}1`);
  sheet.getRange("A1").values = [[title]];
  sheet.mergeCells(`A2:${lastColumn}2`);
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A1:${lastColumn}1`).format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white, size: 16 },
    verticalAlignment: "center",
  };
  sheet.getRange(`A2:${lastColumn}2`).format = {
    fill: COLORS.paleBlue,
    font: { color: COLORS.darkGrey, italic: true },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("1:1").format.rowHeight = 28;
  sheet.getRange("2:2").format.rowHeight = 34;
}

function columnName(columnCount) {
  let value = columnCount;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function styleDataSheet(sheet, rows, tableName) {
  if (!rows.length) return;
  const columnCount = rows[0].length;
  const rowCount = rows.length;
  const lastColumn = columnName(columnCount);
  sheet.getRangeByIndexes(0, 0, rowCount, columnCount).values = rows;
  sheet.getRange(`A1:${lastColumn}1`).format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("1:1").format.rowHeight = 42;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(Math.min(4, columnCount));
  sheet.showGridLines = false;
  sheet.tables.add(`A1:${lastColumn}${rowCount}`, true, tableName);
  sheet.getRange(`A1:${lastColumn}${Math.min(rowCount, 300)}`).format
    .autofitColumns();
  for (let index = 0; index < columnCount; index += 1) {
    const header = String(rows[0][index] ?? "");
    let width = 18;
    if (header.includes("diagnostic") || header.includes("reason")) {
      width = 55;
    } else if (header.includes("review_queue")) {
      width = 36;
    } else if (
      header.includes("flow")
      || header.includes("product")
    ) {
      width = 31;
    } else if (header.includes("status")) {
      width = 28;
    } else if (header.includes("note")) {
      width = 48;
    } else if (header.includes("workbook_row")) {
      width = 14;
    } else if (
      header.includes("count")
      || header.includes("year")
      || header.includes("subtotal")
      || header.includes("active")
    ) {
      width = 16;
    }
    sheet.getRangeByIndexes(0, index, rowCount, 1).format.columnWidth = width;
  }
}

async function buildWorkbook() {
  await fs.mkdir(previewRoot, { recursive: true });
  const [
    summaryRows,
    missingRows,
    exactSubtotalRows,
    masterSubtotalRows,
    incompleteRows,
  ] = await Promise.all([
    readCsvRows("summary.csv"),
    readCsvRows("missing_mappings.csv"),
    readCsvRows("exact_subtotal_differences.csv"),
    readCsvRows("master_subtotal_review.csv"),
    readCsvRows("incomplete_current_rows.csv"),
  ]);

  const workbook = Workbook.create();
  const readme = workbook.worksheets.add("README");
  addTitle(
    readme,
    "Separate-axis gap and subtotal review",
    "Review-only evidence. The canonical mapping workbook has not been edited.",
    8,
  );
  readme.getRange("A4:B13").values = [
    ["Purpose", "Inspect every maintained relationship omitted by the temporal compiler and review subtotal inconsistencies."],
    ["Missing rows", "The Missing mappings sheet contains all 4,373 current relationships not generated."],
    ["ESTO any-year", "Direct exact-pair evidence from base ESTO across every available year."],
    ["ESTO Extended any-year", "Direct exact-pair evidence from ESTO Extended across every available year."],
    ["Ninth any-year", "Direct exact-pair evidence from Ninth across every available year and scenario in the selected registry."],
    ["Cross-dataset caution", "ESTO codes are not looked up as Ninth codes, or vice versa. Non-applicable evidence cells are blank."],
    ["Absent status caution", "The compiler label absent can also mean that the source pair was not generated. Use primary_diagnostic instead."],
    ["Subtotal review", "Generated structural flags are evidence, not automatically authoritative. Mixed master flags are direct internal inconsistencies."],
    ["Recommended use", "Filter review_queue and primary_diagnostic first; then inspect the original workbook row number."],
    ["Safety", "Do not paste these rows into the maintained master automatically."],
  ];
  readme.getRange("A4:A13").format = {
    fill: COLORS.blue,
    font: { bold: true },
    verticalAlignment: "top",
  };
  readme.getRange("B4:B13").format = {
    wrapText: true,
    verticalAlignment: "top",
  };
  readme.getRange("A4:B13").format.borders = {
    preset: "inside",
    style: "thin",
    color: "#B4C6E7",
  };
  readme.getRange("A:A").format.columnWidth = 27;
  readme.getRange("B:B").format.columnWidth = 95;
  readme.getRange("4:13").format.rowHeight = 34;
  readme.showGridLines = false;

  const summary = workbook.worksheets.add("Summary");
  addTitle(
    summary,
    "What the missing mappings actually represent",
    "Counts separate boundary-policy questions from likely source-authority, structural-pair, and subtotal issues.",
    3,
  );
  summary.getRange("A4:C6").values = [
    ["Headline", "Count", "Interpretation"],
    ["Only boundary-window evidence issue", 811, "These pairs have non-zero evidence in another year but fail the selected final-year/future-window rule."],
    ["Stronger mapping or authority review", 3562, "These involve an absent source pair, missing structural target pair, or zero values across all available years."],
  ];
  summary.getRange("A4:C4").format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white },
  };
  summary.getRange("A5:C5").format.fill = COLORS.yellow;
  summary.getRange("A6:C6").format.fill = COLORS.orange;
  summary.getRange("A8:C8").values = [["Section", "Metric", "Value"]];
  if (summaryRows.length > 1) {
    summary.getRangeByIndexes(8, 0, summaryRows.length - 1, 3).values =
      summaryRows.slice(1);
  }
  const summaryLastRow = 8 + Math.max(summaryRows.length - 1, 1);
  summary.getRange("A8:C8").format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white },
  };
  summary.getRange(`C9:C${summaryLastRow}`).format.numberFormat = "#,##0";
  summary.getRange("A:A").format.columnWidth = 26;
  summary.getRange("B:B").format.columnWidth = 54;
  summary.getRange("C:C").format.columnWidth = 70;
  summary.getRange("A4:C6").format.wrapText = true;
  summary.getRange("5:6").format.rowHeight = 54;
  summary.freezePanes.freezeRows(8);
  summary.showGridLines = false;

  const missing = workbook.worksheets.add("Missing mappings");
  styleDataSheet(missing, missingRows, "MissingMappingsTable");
  if (missingRows.length > 1) {
    const queueRange = missing.getRange(`A2:A${missingRows.length}`);
    queueRange.conditionalFormats.add("containsText", {
      text: "boundary_policy_review",
      format: { fill: COLORS.yellow },
    });
    queueRange.conditionalFormats.add("containsText", {
      text: "strong_mapping_review",
      format: { fill: COLORS.red },
    });
    queueRange.conditionalFormats.add("containsText", {
      text: "source_authority_or_mapping_review",
      format: { fill: COLORS.orange },
    });
  }

  const exactSubtotal = workbook.worksheets.add("Exact subtotal differences");
  styleDataSheet(
    exactSubtotal,
    exactSubtotalRows,
    "ExactSubtotalDifferencesTable",
  );

  const masterSubtotal = workbook.worksheets.add("Master subtotal review");
  styleDataSheet(
    masterSubtotal,
    masterSubtotalRows,
    "MasterSubtotalReviewTable",
  );

  const incomplete = workbook.worksheets.add("Incomplete current rows");
  styleDataSheet(
    incomplete,
    incompleteRows,
    "IncompleteCurrentRowsTable",
  );

  const errorScan = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 100 },
    summary: "gap review formula error scan",
  });
  console.log(errorScan.ndjson);

  for (const [sheetName, range, filename] of [
    ["README", "A1:B13", "readme.png"],
    ["Summary", "A1:C25", "summary.png"],
    ["Missing mappings", "A1:N18", "missing_mappings.png"],
    ["Exact subtotal differences", "A1:N18", "exact_subtotal_differences.png"],
    ["Master subtotal review", "A1:N18", "master_subtotal_review.png"],
    ["Incomplete current rows", "A1:N18", "incomplete_current_rows.png"],
  ]) {
    const preview = await workbook.render({
      sheetName,
      range,
      scale: 1.4,
      format: "png",
    });
    await fs.writeFile(
      path.join(previewRoot, filename),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);
  return outputPath;
}

const builtPath = await buildWorkbook();
console.log(JSON.stringify({ outputPath: builtPath }, null, 2));
