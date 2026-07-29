import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  FileBlob,
  SpreadsheetFile,
  Workbook,
} from "@oai/artifact-tool";

// Build the three review-only workbooks from the source manifest prepared by
// separate_axis_mapping_split_workbooks_workflow.py. Run from the repository
// root with @oai/artifact-tool available to Node module resolution.

const repoRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const outputRoot = path.join(
  repoRoot,
  "outputs",
  "separate_axis_mapping_split_20260729",
);
const previewRoot = path.join(outputRoot, "previews");
const manifestPath = path.join(
  outputRoot,
  "split_workbook_manifest.json",
);
const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));

const editableWorkbookPath = manifest.editable_axis_workbook_path;
const pairWorkbookPath = manifest.generated_pair_workbook_path;
const generatedMasterPath = manifest.generated_master_workbook_path;
const canonicalMasterPath = manifest.canonical_master_path;

const colors = {
  navy: "#17365D",
  blue: "#1F4E78",
  lightBlue: "#D9EAF7",
  edit: "#FFF2CC",
  editBorder: "#D6B656",
  generated: "#E7E6E6",
  warning: "#FCE4D6",
  warningText: "#9C0006",
  green: "#E2F0D9",
  greenText: "#375623",
  border: "#B4C6D7",
  white: "#FFFFFF",
};

const booleanHeaders = new Set([
  "exists_in_dataset",
  "active_in_final_esto_year",
  "active_after_final_esto_year",
  "eligible_for_compilation",
  "pair_is_subtotal",
  "leap_is_subtotal",
  "esto_pair_is_subtotal",
  "ninth_pair_is_subtotal",
  "duplicate_to_remove",
]);

async function loadCsvMatrix(relativePath, sheetName) {
  const csvText = await fs.readFile(
    path.join(outputRoot, relativePath),
    "utf8",
  );
  const imported = await Workbook.fromCSV(csvText, { sheetName });
  const importedSheet = imported.worksheets.getItem(sheetName);
  const importedRange = importedSheet.getUsedRange(true);
  if (!importedRange) {
    return [];
  }
  const matrix = importedRange.values;
  const headers = matrix[0] ?? [];
  return matrix.map((row, rowIndex) => row.map((value, columnIndex) => {
    if (rowIndex === 0) {
      return value;
    }
    const header = String(headers[columnIndex] ?? "");
    if (!booleanHeaders.has(header) || typeof value !== "string") {
      return value;
    }
    if (value.toLowerCase() === "true") {
      return "TRUE";
    }
    if (value.toLowerCase() === "false") {
      return "FALSE";
    }
    return value;
  }));
}

function styleTitle(sheet, title, bannerText, bannerStyle) {
  sheet.showGridLines = false;
  sheet.mergeCells("A1:H2");
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1:H2").format = {
    fill: colors.navy,
    font: {
      name: "Aptos Display",
      size: 18,
      bold: true,
      color: colors.white,
    },
    verticalAlignment: "center",
    horizontalAlignment: "left",
  };
  sheet.mergeCells("A4:H4");
  sheet.getRange("A4").values = [[bannerText]];
  sheet.getRange("A4:H4").format = {
    fill: bannerStyle.fill,
    font: {
      name: "Aptos",
      size: 11,
      bold: true,
      color: bannerStyle.color,
    },
    verticalAlignment: "center",
    wrapText: true,
  };
  sheet.getRange("A4:H4").format.rowHeight = 36;
}

function styleReadmeTable(sheet, startRow, rows) {
  const endRow = startRow + rows.length - 1;
  sheet.getRange(`A${startRow}:B${endRow}`).values = rows;
  sheet.getRange(`A${startRow}:A${endRow}`).format = {
    fill: colors.lightBlue,
    font: { name: "Aptos", size: 10, bold: true },
    wrapText: true,
    verticalAlignment: "top",
  };
  sheet.getRange(`B${startRow}:B${endRow}`).format = {
    font: { name: "Aptos", size: 10 },
    wrapText: true,
    verticalAlignment: "top",
  };
  sheet.getRange(`A${startRow}:B${endRow}`).format.borders = {
    preset: "all",
    style: "thin",
    color: colors.border,
  };
  sheet.getRange(`A${startRow}:A${endRow}`).format.columnWidth = 35;
  sheet.getRange(`B${startRow}:B${endRow}`).format.columnWidth = 95;
  sheet.getRange(`C${startRow}:H${endRow}`).format.columnWidth = 4;
}

function styleDataSheet(sheet, editable) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const used = sheet.getUsedRange(true);
  if (!used) {
    return;
  }
  const header = used.getRow(0);
  header.format = {
    fill: editable ? colors.blue : colors.navy,
    font: {
      name: "Aptos",
      size: 10,
      bold: true,
      color: colors.white,
    },
    wrapText: true,
    verticalAlignment: "center",
  };
  header.format.rowHeight = 34;
  if (used.rowCount > 1) {
    const body = sheet.getRangeByIndexes(
      1,
      0,
      used.rowCount - 1,
      used.columnCount,
    );
    body.format = {
      fill: editable ? colors.edit : colors.white,
      font: { name: "Aptos", size: 9 },
      verticalAlignment: "top",
    };
    if (editable) {
      body.format.borders = {
        insideHorizontal: {
          style: "hair",
          color: colors.editBorder,
        },
      };
    }
  }
  const headers = header.values?.[0] ?? [];
  for (let column = 0; column < headers.length; column += 1) {
    const label = String(headers[column] ?? "");
    let width = 38;
    if (
      label.includes("scope")
      || label.includes("status")
      || label.includes("eligible")
      || label.includes("active_")
      || label.includes("exists_")
      || label.includes("subtotal")
    ) {
      width = label.includes("status") ? 42 : 23;
    }
    used.getColumn(column).format.columnWidth = width;
    if (label === "esto_dataset_scope" && used.rowCount > 1) {
      sheet.getRangeByIndexes(
        1,
        column,
        used.rowCount - 1,
        1,
      ).dataValidation = {
        allowBlank: false,
        list: {
          inCellDropDown: true,
          source: ["BOTH", "ESTO", "ESTO_EXTENDED"],
        },
      };
    }
  }
}

async function addCsvSheets(workbook, sourceMap, editable) {
  for (const [sheetName, relativePath] of Object.entries(sourceMap)) {
    const matrix = await loadCsvMatrix(relativePath, sheetName);
    const sheet = workbook.worksheets.add(sheetName);
    if (matrix.length > 0) {
      sheet.getRangeByIndexes(
        0,
        0,
        matrix.length,
        matrix[0].length,
      ).values = matrix;
    }
    styleDataSheet(sheet, editable);
  }
}

async function renderWorkbook(workbook, folder, ranges) {
  const target = path.join(previewRoot, folder);
  await fs.mkdir(target, { recursive: true });
  for (const [sheetName, range] of Object.entries(ranges)) {
    const preview = await workbook.render({
      sheetName,
      range,
      scale: 1,
      format: "png",
    });
    const safeName = sheetName.replaceAll(/[^A-Za-z0-9]+/g, "_");
    await fs.writeFile(
      path.join(target, `${safeName}.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }
}

async function scanFormulaErrors(workbook, label) {
  const result = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: `${label} formula error scan`,
  });
  console.log(result.ndjson);
}

async function removeInspectSidecar(workbookPath) {
  await fs.rm(`${workbookPath}.inspect.ndjson`, { force: true });
}

async function buildEditableWorkbook() {
  const workbook = Workbook.create();
  const readme = workbook.worksheets.add("README");
  styleTitle(
    readme,
    "Single-axis mapping contract",
    "EDIT THIS WORKBOOK — the six mapping sheets are the human-maintained source of truth for this prototype.",
    { fill: colors.green, color: colors.greenText },
  );
  styleReadmeTable(readme, 6, [
    [
      "What people edit",
      "Only the sector/flow and fuel/product relationship rows in the six mapping sheets. Yellow cells are editable.",
    ],
    [
      "Why it is smaller",
      "Each relationship sheet has two key columns. Sheets targeting ESTO have one additional dataset-scope column.",
    ],
    [
      "Allowed cardinality",
      "One-to-one, one-to-many, and many-to-one relationships are supported. A many-to-many connected component within one axis is blocking QA and must be reviewed.",
    ],
    [
      "ESTO dataset scope",
      "BOTH means the relationship applies to ESTO and ESTO Extended. ESTO or ESTO_EXTENDED restricts it to one target registry.",
    ],
    [
      "Generated outputs",
      "Key-pair evidence and final pair mappings live in separate generated workbooks. Do not copy generated columns back into this workbook.",
    ],
    [
      "Subtotals and rollups",
      "Canonical rollup rules are applied to raw key pairs before mappings are compiled. The generated master keeps the existing rollup-rule sheets unchanged.",
    ],
    [
      "Current status",
      manifest.prototype_status,
    ],
  ]);
  readme.getRange("A1:H30").format.font.name = "Aptos";
  readme.freezePanes.freezeRows(4);

  await addCsvSheets(workbook, manifest.editable_sources, true);
  await renderWorkbook(workbook, "editable_axis", {
    README: "A1:H22",
    leap_sector_to_esto: "A1:C20",
    leap_fuel_to_esto: "A1:C20",
    leap_sector_to_ninth: "A1:B20",
    leap_fuel_to_ninth: "A1:B20",
    ninth_sector_to_esto: "A1:C20",
    ninth_fuel_to_esto: "A1:C20",
  });
  await scanFormulaErrors(workbook, "editable axis workbook");
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(editableWorkbookPath);
}

async function buildPairWorkbook() {
  const workbook = Workbook.create();
  const readme = workbook.worksheets.add("README");
  styleTitle(
    readme,
    "Generated key-pair registries",
    "GENERATED — DO NOT EDIT. Rebuild this workbook from dataset evidence and the reviewed single-axis contract.",
    { fill: colors.warning, color: colors.warningText },
  );
  styleReadmeTable(readme, 6, [
    [
      "Purpose",
      "Make dataset-specific sector/fuel and flow/product key pairs explicit, auditable, and reusable by the mapping compiler.",
    ],
    [
      "Possible combinations",
      "ESTO, ESTO Extended, and Ninth sheets contain the Cartesian combination of discovered axis keys. exists_in_dataset is TRUE for raw or deterministically rollup-derived pairs; pair_origin distinguishes raw, rollup, and raw_and_rollup.",
    ],
    [
      "Historical rule",
      `ESTO and ESTO Extended pairs are eligible only when non-zero in the final ESTO year (${manifest.historical_boundary_year}).`,
    ],
    [
      "Projection rule",
      `Ninth pairs are eligible only when non-zero in a year after ${manifest.historical_boundary_year}.`,
    ],
    [
      "LEAP authority",
      manifest.leap_registry_authority,
    ],
    [
      "LEAP boundary",
      "This combines exact model-branch pairs, the deterministic balance-report grid, and canonical rollup-derived pairs. Current observed balance exports are verification evidence; they do not define global validity.",
    ],
    [
      "Subtotal labels",
      "pair_is_subtotal is generated from the source registry and is passed into the final compatibility sheets.",
    ],
    [
      "Compilation",
      "eligible_for_compilation is the narrow programmatic gate used by the prototype compiler. The final mapping workbook remains review-only while within-axis many-to-many cases and generated overrides are unresolved.",
    ],
  ]);
  readme.getRange("A1:H30").format.font.name = "Aptos";
  readme.freezePanes.freezeRows(4);

  await addCsvSheets(workbook, manifest.pair_sources, false);
  await renderWorkbook(workbook, "generated_pairs", {
    README: "A1:H22",
    "LEAP key pairs": "A1:G20",
    "ESTO key pairs": "A1:H20",
    "ESTO Extended key pairs": "A1:H20",
    "Ninth key pairs": "A1:H20",
  });
  await scanFormulaErrors(workbook, "generated pair workbook");
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(pairWorkbookPath);
  await removeInspectSidecar(pairWorkbookPath);
}

async function verifyPairWorkbook() {
  const input = await FileBlob.load(pairWorkbookPath);
  const workbook = await SpreadsheetFile.importXlsx(input);
  const preview = await workbook.render({
    sheetName: "ESTO Extended key pairs",
    range: "A1:H20",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(
    path.join(
      previewRoot,
      "generated_pairs",
      "ESTO_Extended_key_pairs_retry.png",
    ),
    new Uint8Array(await preview.arrayBuffer()),
  );
  const inspection = await workbook.inspect({
    kind: "table",
    range: "ESTO Extended key pairs!A1:H6",
    include: "values,formulas",
    tableMaxRows: 6,
    tableMaxCols: 8,
    maxChars: 5000,
  });
  console.log(inspection.ndjson);
  await removeInspectSidecar(pairWorkbookPath);
}

async function buildGeneratedMaster() {
  const input = await FileBlob.load(canonicalMasterPath);
  const workbook = await SpreadsheetFile.importXlsx(input);
  const replacementSummary = {};

  for (const [sheetName, relativePath] of Object.entries(
    manifest.compiled_sources,
  )) {
    const matrix = await loadCsvMatrix(relativePath, sheetName);
    let sheet = workbook.worksheets.getItem(sheetName);
    const used = sheet.getUsedRange(true);
    if (!used) {
      throw new Error(`Canonical sheet ${sheetName} is empty.`);
    }
    const canonicalHeaders = used.getRow(0).values?.[0] ?? [];
    const generatedHeaders = matrix[0] ?? [];
    if (JSON.stringify(canonicalHeaders.slice(0, generatedHeaders.length))
      !== JSON.stringify(generatedHeaders)) {
      throw new Error(
        `Header mismatch for ${sheetName}: `
        + `${JSON.stringify(canonicalHeaders)} vs `
        + `${JSON.stringify(generatedHeaders)}`,
      );
    }
    const generatedDataRows = matrix.length - 1;
    const canonicalCapacity = used.rowCount - 1;
    const originalIndex = sheet.index;
    sheet.delete();
    sheet = workbook.worksheets.add(sheetName);
    sheet.index = originalIndex;
    sheet.getRangeByIndexes(
      0,
      0,
      matrix.length,
      generatedHeaders.length,
    ).values = matrix;
    const regeneratedUsed = sheet.getUsedRange(true);
    if (
      regeneratedUsed
      && regeneratedUsed.columnCount > generatedHeaders.length
    ) {
      sheet.getRangeByIndexes(
        0,
        generatedHeaders.length,
        regeneratedUsed.rowCount,
        regeneratedUsed.columnCount - generatedHeaders.length,
      ).clear({ applyTo: "contents" });
    }
    styleDataSheet(sheet, false);
    replacementSummary[sheetName] = {
      canonicalCapacity,
      generatedDataRows,
      columns: generatedHeaders,
      presentation: (
        "Recreated at the canonical sheet index so every generated row is "
        + "visible and only contract columns are present."
      ),
    };
  }

  await scanFormulaErrors(workbook, "generated master");
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(generatedMasterPath);

  const reopenedInput = await FileBlob.load(generatedMasterPath);
  const reopened = await SpreadsheetFile.importXlsx(reopenedInput);
  await renderWorkbook(reopened, "generated_master", {
    leap_combined_esto: "A1:H18",
    leap_combined_ninth: "A1:G18",
    ninth_pairs_to_esto_pairs: "A1:H18",
  });
  await scanFormulaErrors(reopened, "reopened generated master");
  await removeInspectSidecar(generatedMasterPath);

  const inspection = {};
  for (const sheetName of Object.keys(manifest.compiled_sources)) {
    const result = await reopened.inspect({
      kind: "table",
      range: `${sheetName}!A1:H6`,
      include: "values,formulas",
      tableMaxRows: 6,
      tableMaxCols: 8,
      maxChars: 5000,
    });
    inspection[sheetName] = result.ndjson;
    console.log(result.ndjson);
  }
  await fs.writeFile(
    path.join(outputRoot, "generated_master_replacement_summary.json"),
    JSON.stringify({ replacementSummary, inspection }, null, 2),
    "utf8",
  );
}

const runtimeEnvironment = globalThis.process?.env ?? {};
const buildEditable = globalThis.BUILD_EDITABLE
  ?? runtimeEnvironment.BUILD_EDITABLE !== "false";
const buildPairs = globalThis.BUILD_PAIRS
  ?? runtimeEnvironment.BUILD_PAIRS !== "false";
const buildMaster = globalThis.BUILD_MASTER
  ?? runtimeEnvironment.BUILD_MASTER !== "false";
const verifyPairs = globalThis.VERIFY_PAIRS
  ?? runtimeEnvironment.VERIFY_PAIRS === "true";

if (buildEditable) {
  await buildEditableWorkbook();
}
if (buildPairs) {
  await buildPairWorkbook();
}
if (buildMaster) {
  await buildGeneratedMaster();
}
if (verifyPairs) {
  await verifyPairWorkbook();
}

console.log(JSON.stringify({
  editableWorkbookPath,
  pairWorkbookPath,
  generatedMasterPath,
}, null, 2));
