import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import {
  FileBlob,
  SpreadsheetFile,
  Workbook,
} from "@oai/artifact-tool";

// Build the three review-only workbooks from the source manifest prepared by
// separate_axis_mapping_split_workbooks_workflow.py. Run from the repository
// root with @oai/artifact-tool available to Node module resolution.

const runtimeEnvironment = globalThis.process?.env ?? {};
const repoRoot = runtimeEnvironment.SEPARATE_AXIS_REPO_ROOT
  ? path.resolve(runtimeEnvironment.SEPARATE_AXIS_REPO_ROOT)
  : path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "..",
  );
const outputRoot = path.join(
  repoRoot,
  "outputs",
  "separate_axis_mapping_refresh",
  "workbooks",
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
const generationManifestPath = path.join(
  repoRoot,
  "config",
  "outlook_mappings_generation_manifest.json",
);
const compilerManifestPath = path.join(
  repoRoot,
  "outputs",
  "separate_axis_mapping_refresh",
  "compiler",
  "workbook_manifest.json",
);

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
      return true;
    }
    if (value.toLowerCase() === "false") {
      return false;
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

async function sha256(filePath) {
  const content = await fs.readFile(filePath);
  return crypto.createHash("sha256").update(content).digest("hex");
}

function validateLiteralBooleans(workbook, sheetNames) {
  const problems = [];
  const checkedColumns = [];
  for (const sheetName of sheetNames) {
    const sheet = workbook.worksheets.getItem(sheetName);
    const used = sheet.getUsedRange(true);
    if (!used || used.rowCount < 1) {
      problems.push(`${sheetName}: empty sheet`);
      continue;
    }
    const matrix = used.values;
    const headers = matrix[0] ?? [];
    for (let column = 0; column < headers.length; column += 1) {
      const header = String(headers[column] ?? "");
      if (!booleanHeaders.has(header)) {
        continue;
      }
      checkedColumns.push(`${sheetName}.${header}`);
      for (let row = 1; row < matrix.length; row += 1) {
        const value = matrix[row]?.[column];
        if (
          value !== null
          && value !== undefined
          && value !== true
          && value !== false
        ) {
          problems.push(
            `${sheetName}!R${row + 1}C${column + 1} `
            + `(${header}) is ${JSON.stringify(value)}, not a Boolean`,
          );
          if (problems.length >= 30) {
            break;
          }
        }
      }
    }
  }
  if (problems.length > 0) {
    throw new Error(
      "Workbook Boolean validation failed:\n- " + problems.join("\n- "),
    );
  }
  return checkedColumns;
}

function validateMasterContract(workbook, expectedSheetNames) {
  const actualSheetNames = workbook.worksheets.items.map((sheet) => sheet.name);
  if (JSON.stringify(actualSheetNames) !== JSON.stringify(expectedSheetNames)) {
    throw new Error(
      "Generated master sheet order changed: "
      + `${JSON.stringify(actualSheetNames)} vs `
      + `${JSON.stringify(expectedSheetNames)}`,
    );
  }
  for (const [sheetName, expectedHeaders] of Object.entries(
    manifest.compiled_columns,
  )) {
    const sheet = workbook.worksheets.getItem(sheetName);
    const used = sheet.getUsedRange(true);
    const actualHeaders = used?.getRow(0).values?.[0] ?? [];
    if (JSON.stringify(actualHeaders) !== JSON.stringify(expectedHeaders)) {
      throw new Error(
        `Generated master header mismatch for ${sheetName}: `
        + `${JSON.stringify(actualHeaders)} vs `
        + `${JSON.stringify(expectedHeaders)}`,
      );
    }
  }
  return {
    sheetCount: actualSheetNames.length,
    sheetNames: actualSheetNames,
    booleanColumns: validateLiteralBooleans(
      workbook,
      Object.keys(manifest.compiled_sources),
    ),
  };
}

async function buildEditableWorkbook() {
  const workbook = Workbook.create();
  const readme = workbook.worksheets.add("README");
  styleTitle(
    readme,
    "Single-axis mapping contract",
    "EDIT THIS WORKBOOK - axis mappings and accepted extra key pairs are the human-maintained source of truth.",
    { fill: colors.green, color: colors.greenText },
  );
  styleReadmeTable(readme, 6, [
    [
      "What people edit",
      "The six single-axis mapping sheets and four extra-key-pair sheets. Yellow cells are editable.",
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
      "Extra key pairs",
      "Each row accepts one exact dataset pair that would otherwise be excluded. Presence means accepted; delete the row to withdraw that authority. No checkbox column is used.",
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
    extra_leap_key_pairs: "A1:B20",
    extra_esto_key_pairs: "A1:B20",
    extra_esto_extended_pairs: "A1:B20",
    extra_ninth_key_pairs: "A1:B20",
  });
  await scanFormulaErrors(workbook, "editable axis workbook");
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(editableWorkbookPath);
  await removeInspectSidecar(editableWorkbookPath);
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
      "ESTO, ESTO Extended, and Ninth sheets contain the Cartesian combination of discovered axis keys. pair_origin also identifies human-accepted reviewed_extra pairs.",
    ],
    [
      "Historical rule",
      `ESTO and ESTO Extended pairs are eligible when non-zero in the final ESTO year (${manifest.historical_boundary_year}) or accepted in the editable extra-pair sheets.`,
    ],
    [
      "Projection rule",
      `Ninth pairs are eligible when non-zero after ${manifest.historical_boundary_year} or accepted in the editable extra-pair sheet.`,
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
      "eligible_for_compilation is TRUE for boundary-active or reviewed-extra pairs. Within-axis many-to-many components remain explicit semantic review debt.",
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
  const reopenedInput = await FileBlob.load(pairWorkbookPath);
  const reopened = await SpreadsheetFile.importXlsx(reopenedInput);
  validateLiteralBooleans(
    reopened,
    Object.keys(manifest.pair_sources),
  );
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
  const expectedSheetNames = workbook.worksheets.items.map(
    (sheet) => sheet.name,
  );
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
  const contractValidation = validateMasterContract(
    reopened,
    expectedSheetNames,
  );
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
    JSON.stringify(
      { replacementSummary, contractValidation, inspection },
      null,
      2,
    ),
    "utf8",
  );

  return { replacementSummary, contractValidation };
}

const buildEditable = globalThis.BUILD_EDITABLE
  ?? runtimeEnvironment.BUILD_EDITABLE === "true";
const buildPairs = globalThis.BUILD_PAIRS
  ?? runtimeEnvironment.BUILD_PAIRS !== "false";
const buildMaster = globalThis.BUILD_MASTER
  ?? runtimeEnvironment.BUILD_MASTER !== "false";
const verifyPairs = globalThis.VERIFY_PAIRS
  ?? runtimeEnvironment.VERIFY_PAIRS === "true";
const promoteMaster = globalThis.PROMOTE_MASTER
  ?? runtimeEnvironment.PROMOTE_MASTER === "true";

if (buildEditable) {
  await buildEditableWorkbook();
}
if (buildPairs) {
  await buildPairWorkbook();
}
let masterBuildResult = null;
if (buildMaster) {
  masterBuildResult = await buildGeneratedMaster();
}
if (verifyPairs) {
  await verifyPairWorkbook();
}

if (promoteMaster) {
  if (!buildMaster || !masterBuildResult) {
    throw new Error("PROMOTE_MASTER requires BUILD_MASTER.");
  }
  const compilerManifest = JSON.parse(
    await fs.readFile(compilerManifestPath, "utf8"),
  );
  const priorCanonicalHash = await sha256(canonicalMasterPath);
  const candidateHash = await sha256(generatedMasterPath);
  let existingGenerationManifest = null;
  try {
    existingGenerationManifest = JSON.parse(
      await fs.readFile(generationManifestPath, "utf8"),
    );
  } catch {
    existingGenerationManifest = null;
  }
  const originalCanonicalHash = (
    existingGenerationManifest?.hashes?.original_canonical_master_sha256
    ?? runtimeEnvironment.ORIGINAL_CANONICAL_MASTER_SHA256
    ?? existingGenerationManifest?.hashes?.prior_canonical_master_sha256
    ?? priorCanonicalHash
  );
  const backupPath = path.join(
    outputRoot,
    `prior_canonical_master_${priorCanonicalHash.slice(0, 12)}.xlsx`,
  );
  await fs.copyFile(canonicalMasterPath, backupPath);
  let originalCanonicalBackupPath = (
    existingGenerationManifest?.original_canonical_backup_path
    ?? null
  );
  if (!originalCanonicalBackupPath) {
    const expectedBackup = path.join(
      outputRoot,
      `prior_canonical_master_${originalCanonicalHash.slice(0, 12)}.xlsx`,
    );
    try {
      await fs.access(expectedBackup);
      originalCanonicalBackupPath = expectedBackup;
    } catch {
      originalCanonicalBackupPath = null;
    }
  }

  const promotionTempPath = `${canonicalMasterPath}.separate_axis_refresh.tmp`;
  await fs.copyFile(generatedMasterPath, promotionTempPath);
  await fs.rename(promotionTempPath, canonicalMasterPath);

  const promotedInput = await FileBlob.load(canonicalMasterPath);
  const promotedWorkbook = await SpreadsheetFile.importXlsx(promotedInput);
  const promotedValidation = validateMasterContract(
    promotedWorkbook,
    masterBuildResult.contractValidation.sheetNames,
  );
  const promotedHash = await sha256(canonicalMasterPath);
  if (promotedHash !== candidateHash) {
    throw new Error(
      `Promoted workbook hash ${promotedHash} does not match `
      + `candidate hash ${candidateHash}.`,
    );
  }
  await removeInspectSidecar(canonicalMasterPath);

  const generationManifest = {
    status: "promoted_and_reopened",
    generated_at_utc: new Date().toISOString(),
    contract_version: "separate_axis_mapping_contract_v1",
    historical_boundary_year: manifest.historical_boundary_year,
    editable_axis_workbook_path: editableWorkbookPath,
    generated_pair_workbook_path: pairWorkbookPath,
    canonical_master_path: canonicalMasterPath,
    candidate_path: generatedMasterPath,
    prior_canonical_backup_path: backupPath,
    original_canonical_backup_path: originalCanonicalBackupPath,
    hashes: {
      original_canonical_master_sha256: originalCanonicalHash,
      prior_canonical_master_sha256: priorCanonicalHash,
      promoted_master_sha256: promotedHash,
      generated_pair_workbook_sha256: await sha256(pairWorkbookPath),
      editable_axis_workbook_sha256: await sha256(editableWorkbookPath),
      compiler_manifest_sha256: await sha256(compilerManifestPath),
      split_manifest_sha256: await sha256(manifestPath),
    },
    compiled_counts: manifest.compiled_counts,
    pair_counts: manifest.pair_counts,
    compiler_summary: compilerManifest.summary,
    leap_pair_registry_manifest: compilerManifest.leap_pair_registry_manifest,
    provisional_relationship_policy: "provisionally_accepted",
    semantic_review_debt: {
      within_axis_many_to_many_components:
        compilerManifest.summary
          .blocking_within_axis_many_to_many_components,
      additional_compiled_relationships:
        compilerManifest.summary.generated_relationship_governance_rows,
    },
    validation: promotedValidation,
    boolean_storage: "literal_boolean_no_checkbox_controls",
    rollup_boundary:
      "Manual rollups remain workbook rules; graph-generated Common rows "
      + "are not written back as manual rollups.",
    rollback:
      "Restore config/outlook_mappings_master.xlsx from Git, then rerun "
      + "the separate-axis refresh when ready.",
  };
  await fs.writeFile(
    generationManifestPath,
    JSON.stringify(generationManifest, null, 2),
    "utf8",
  );
}

console.log(JSON.stringify({
  editableWorkbookPath,
  pairWorkbookPath,
  generatedMasterPath,
  generationManifestPath,
  promoted: promoteMaster,
}, null, 2));
