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

const editableWorkbookPath = runtimeEnvironment.EDITABLE_WORKBOOK_OVERRIDE
  ? path.resolve(runtimeEnvironment.EDITABLE_WORKBOOK_OVERRIDE)
  : manifest.editable_axis_workbook_path;
const pairWorkbookPath = manifest.generated_pair_workbook_path;
const generatedMasterPath = manifest.generated_master_workbook_path;
const canonicalMasterPath = manifest.canonical_master_path;
const generationManifestPath = path.join(
  repoRoot,
  "config",
  "outlook_mappings_generation_manifest.json",
);
const mappingWorkflowDiagramPath = path.join(
  repoRoot,
  "docs",
  "diagrams",
  "mapping_production_workflow.png",
);
const compilerManifestPath = path.join(
  repoRoot,
  "outputs",
  "separate_axis_mapping_refresh",
  "compiler",
  "workbook_manifest.json",
);
const editableDuplicateAuditPath = path.join(
  outputRoot,
  "editable_duplicate_cleanup.json",
);
const exceptionSheetName = "exceptions";
const exceptionHeaders = [
  "exception_type",
  "enabled",
  "mapping_name",
  "comparison_scope",
  "axis_name",
  "source_keys",
  "target_keys",
  "notes",
];
const initialExceptionRow = [
  "allowed_many_to_many_component",
  false,
  "leap_to_esto",
  "BOTH",
  "flow",
  "Demand\\All demand aggregated\\Road|Road|Transport non road/Freight non road/Rail|Transport non road/Nonspecified transport|Transport non road/Passenger non road/Rail",
  "15.02 Road|15.03 Rail|15.06 Non-specified transport",
  "Approved aggregate road and rail hierarchy bridge.",
];
const editableManualSheetNames = [
  "leap_rollup_rules",
  "esto_rollup_rules",
  "ninth_rollup_rules",
  "rollup_label_overrides",
];

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

async function addWorkflowDiagram(sheet, headingRow, imageTopRow) {
  const diagramBytes = await fs.readFile(mappingWorkflowDiagramPath);
  const dataUrl = `data:image/png;base64,${diagramBytes.toString("base64")}`;
  sheet.mergeCells(`A${headingRow}:H${headingRow}`);
  sheet.getRange(`A${headingRow}`).values = [[
    "Production workflow (rendered from docs/diagrams/mapping_production_workflow.mmd)",
  ]];
  sheet.getRange(`A${headingRow}:H${headingRow}`).format = {
    fill: colors.lightBlue,
    font: { name: "Aptos", size: 11, bold: true, color: colors.navy },
    verticalAlignment: "center",
  };
  sheet.getRange(`A${headingRow}:H${headingRow}`).format.rowHeight = 25;
  sheet.getRange(`A${imageTopRow}:H${imageTopRow + 11}`).format.rowHeight = 18;
  sheet.images.add({
    dataUrl,
    anchor: {
      from: { row: imageTopRow - 1, col: 0 },
      extent: { widthPx: 1180, heightPx: 235 },
    },
  });
}

async function refreshMasterGuide(workbook) {
  const existing = workbook.worksheets.getItem("Guide");
  const originalIndex = existing.index;
  existing.delete();
  const guide = workbook.worksheets.add("Guide");
  guide.index = originalIndex;
  styleTitle(
    guide,
    "Generated mapping compatibility workbook",
    "GENERATED COMPATIBILITY INTERFACE — edit outlook_mappings_single_axis.xlsx, not generated pair or rollup sheets here.",
    { fill: colors.warning, color: colors.warningText },
  );
  styleReadmeTable(guide, 6, [
    [
      "Where people edit",
      "config/outlook_mappings_single_axis.xlsx is the human-maintained authority for the six axes, accepted exact pairs, exceptions, and rollups.",
    ],
    [
      "Preliminary production gate",
      "After an editable-contract change, save and close Excel, then run codebase/separate_axis_mapping_refresh_workflow.py before Stage 1. Preliminary means upstream, not optional.",
    ],
    [
      "Generated pair sheets",
      "leap_combined_esto, leap_combined_ninth, and ninth_pairs_to_esto_pairs are compiled compatibility outputs. Do not edit their bodies.",
    ],
    [
      "Generated rollup copies",
      "leap_rollup_rules, esto_rollup_rules, and ninth_rollup_rules are copied from the editable workbook. Change the upstream copies.",
    ],
    [
      "Preserved live sheets",
      "leap_display_names, NINTH unique sectors and fuels, ESTO unique flows and products, and ninth fuel to esto product remain active reference/compatibility inputs.",
    ],
    [
      "Reserved sheet",
      "rollup_label_overrides is loaded for schema compatibility, but preferred-label overrides are not currently applied.",
    ],
    [
      "Deletion candidates",
      "other branches and deleted rows - might regret have no executable consumers in the three repositories. Keep them empty; remove only in a coordinated workbook-contract migration.",
    ],
    [
      "Then run",
      "Run the affected mapping pipeline stages (normally Stages 1–3) and review relationship, cardinality, hierarchy, lineage, and value-preservation QA.",
    ],
    [
      "QA exceptions",
      "Reviewed diagnostic exceptions belong in config/mapping_issue_exception_sets.xlsx. They never create or repair a mapping relationship.",
    ],
    [
      "Detailed documentation",
      "See docs/guide_outlook_mappings_master.md, docs/mappings_system.md, config/README.md, and docs/separate_axis_mapping_pipeline.md.",
    ],
  ]);
  await addWorkflowDiagram(guide, 18, 19);
  guide.getRange("A1:H34").format.font.name = "Aptos";
  guide.freezePanes.freezeRows(4);
}

function normaliseEditableKeyValue(value, header) {
  const cleaned = String(value ?? "").trim();
  if (header === "esto_dataset_scope") {
    return cleaned.toUpperCase();
  }
  return cleaned;
}

function editableMappingColumns(sheetName, headers) {
  const scopedMappingSheets = {
    leap_sector_to_esto: ["leap_sector", "esto_flow"],
    leap_fuel_to_esto: ["leap_fuel", "esto_product"],
    ninth_sector_to_esto: ["ninth_sector", "esto_flow"],
    ninth_fuel_to_esto: ["ninth_fuel", "esto_product"],
  };
  const mappingColumns = scopedMappingSheets[sheetName];
  if (!mappingColumns) {
    return headers.map((header) => String(header ?? "").trim());
  }
  return mappingColumns;
}

function consolidatedScope(scopes) {
  if (scopes.has("BOTH") || (scopes.has("ESTO") && scopes.has("ESTO_EXTENDED"))) {
    return "BOTH";
  }
  return scopes.values().next().value;
}

function ensureExceptionSheet(workbook) {
  const existing = workbook.worksheets.items.find(
    (sheet) => sheet.name === exceptionSheetName,
  );
  if (existing) {
    return false;
  }
  const sheet = workbook.worksheets.add(exceptionSheetName);
  sheet.getRangeByIndexes(0, 0, 2, exceptionHeaders.length).values = [
    exceptionHeaders,
    initialExceptionRow,
  ];
  styleDataSheet(sheet, true);
  return true;
}

function ensureExceptionEnabledColumn(workbook) {
  const sheet = workbook.worksheets.items.find(
    (candidate) => candidate.name === exceptionSheetName,
  );
  const used = sheet.getUsedRange(true);
  const headers = used?.getRow(0).values?.[0] ?? [];
  if (headers.map((header) => String(header ?? "").trim()).includes("enabled")) {
    return false;
  }
  const columnIndex = headers.length;
  sheet.getRangeByIndexes(0, columnIndex, 1, 1).values = [["enabled"]];
  if (used && used.rowCount > 1) {
    sheet.getRangeByIndexes(1, columnIndex, used.rowCount - 1, 1).values = (
      Array.from({ length: used.rowCount - 1 }, () => [false])
    );
  }
  styleDataSheet(sheet, true);
  return true;
}

function copySheetValues(sourceWorkbook, targetWorkbook, sheetName, editable) {
  const sourceSheet = sourceWorkbook.worksheets.getItem(sheetName);
  const sourceRange = sourceSheet.getUsedRange(true);
  if (!sourceRange) {
    throw new Error(`Source sheet ${sheetName} is empty.`);
  }
  const targetSheet = targetWorkbook.worksheets.add(sheetName);
  targetSheet.getRangeByIndexes(
    0,
    0,
    sourceRange.rowCount,
    sourceRange.columnCount,
  ).values = sourceRange.values;
  styleDataSheet(targetSheet, editable);
  return targetSheet;
}

async function ensureEditableManualSheets(workbook) {
  const missingSheetNames = editableManualSheetNames.filter(
    (sheetName) => !workbook.worksheets.items.some((sheet) => sheet.name === sheetName),
  );
  if (missingSheetNames.length === 0) {
    return [];
  }
  const input = await FileBlob.load(canonicalMasterPath);
  const canonicalWorkbook = await SpreadsheetFile.importXlsx(input);
  for (const sheetName of missingSheetNames) {
    copySheetValues(canonicalWorkbook, workbook, sheetName, true);
  }
  return missingSheetNames;
}

function collectEditableDuplicateAudit(workbook) {
  const sheets = {};
  let duplicateRows = 0;
  for (const sheetName of Object.keys(manifest.editable_sources)) {
    const sheet = workbook.worksheets.getItem(sheetName);
    const used = sheet.getUsedRange(true);
    const matrix = used?.values ?? [];
    const headers = matrix[0] ?? [];
    const headerIndexes = new Map(
      headers.map((header, columnIndex) => [String(header ?? "").trim(), columnIndex]),
    );
    const keyHeaders = editableMappingColumns(sheetName, headers);
    const keyColumnIndexes = keyHeaders.map((header) => {
      const columnIndex = headerIndexes.get(header);
      if (columnIndex === undefined) {
        throw new Error(`${sheetName} is missing editable mapping column: ${header}`);
      }
      return columnIndex;
    });
    const scopeColumnIndex = headerIndexes.get("esto_dataset_scope");
    const seen = new Map();
    const duplicates = [];
    const retainedRows = [];
    for (let rowIndex = 1; rowIndex < matrix.length; rowIndex += 1) {
      const row = matrix[rowIndex].slice(0, headers.length);
      const keyValues = keyColumnIndexes.map((columnIndex) => (
        normaliseEditableKeyValue(row[columnIndex], String(headers[columnIndex] ?? ""))
      ));
      if (keyValues.every((value) => value === "")) {
        retainedRows.push(row);
        continue;
      }
      const key = JSON.stringify(keyValues);
      const workbookRowNumber = rowIndex + 1;
      if (seen.has(key)) {
        const retained = seen.get(key);
        if (scopeColumnIndex !== undefined) {
          retained.scopes.add(normaliseEditableKeyValue(row[scopeColumnIndex], "esto_dataset_scope"));
        }
        duplicates.push({
          workbook_row_number: workbookRowNumber,
          retained_workbook_row_number: retained.workbookRowNumber,
          mapping_key: keyValues,
          scope_consolidated_into: scopeColumnIndex === undefined ? null : "pending",
        });
        duplicateRows += 1;
        continue;
      }
      seen.set(key, {
        workbookRowNumber,
        retainedRowIndex: retainedRows.length,
        scopes: new Set(
          scopeColumnIndex === undefined
            ? []
            : [normaliseEditableKeyValue(row[scopeColumnIndex], "esto_dataset_scope")],
        ),
      });
      retainedRows.push(row);
    }
    if (scopeColumnIndex !== undefined) {
      for (const retained of seen.values()) {
        retainedRows[retained.retainedRowIndex][scopeColumnIndex] = consolidatedScope(retained.scopes);
      }
      for (const duplicate of duplicates) {
        const retained = [...seen.values()].find(
          (candidate) => candidate.workbookRowNumber === duplicate.retained_workbook_row_number,
        );
        duplicate.scope_consolidated_into = consolidatedScope(retained.scopes);
      }
    }
    sheets[sheetName] = {
      input_row_count: Math.max(0, matrix.length - 1),
      retained_row_count: retainedRows.length,
      duplicate_rows_removed: duplicates.length,
      duplicates,
      retainedRows,
      usedColumnCount: headers.length,
      usedRowCount: matrix.length,
    };
  }
  return { duplicateRows, sheets };
}

async function cleanEditableWorkbookDuplicates() {
  const input = await FileBlob.load(editableWorkbookPath);
  const workbook = await SpreadsheetFile.importXlsx(input);
  const exceptionSheetAdded = ensureExceptionSheet(workbook);
  const exceptionSheetEnabledColumnAdded = ensureExceptionEnabledColumn(workbook);
  const manualSheetsAdded = await ensureEditableManualSheets(workbook);
  const initial = collectEditableDuplicateAudit(workbook);
  const changedSheets = [];

  for (const [sheetName, sheetAudit] of Object.entries(initial.sheets)) {
    if (sheetAudit.duplicate_rows_removed === 0) {
      continue;
    }
    changedSheets.push(sheetName);
    const sheet = workbook.worksheets.getItem(sheetName);
    if (sheetAudit.usedRowCount > 1 && sheetAudit.usedColumnCount > 0) {
      sheet.getRangeByIndexes(
        1,
        0,
        sheetAudit.usedRowCount - 1,
        sheetAudit.usedColumnCount,
      ).clear({ applyTo: "contents" });
    }
    if (sheetAudit.retainedRows.length > 0) {
      sheet.getRangeByIndexes(
        1,
        0,
        sheetAudit.retainedRows.length,
        sheetAudit.usedColumnCount,
      ).values = sheetAudit.retainedRows;
    }
  }

  const audit = {
    checked_at_utc: new Date().toISOString(),
    workbook_path: editableWorkbookPath,
    checked_sheets: Object.keys(initial.sheets),
    duplicate_rows_removed: initial.duplicateRows,
    workbook_rewritten: changedSheets.length > 0 || exceptionSheetAdded || exceptionSheetEnabledColumnAdded || manualSheetsAdded.length > 0,
    changed_sheets: changedSheets,
    exception_sheet_added: exceptionSheetAdded,
    exception_sheet_enabled_column_added: exceptionSheetEnabledColumnAdded,
    manual_sheets_added: manualSheetsAdded,
    sheets: Object.fromEntries(
      Object.entries(initial.sheets).map(([sheetName, sheetAudit]) => [
        sheetName,
        {
          input_row_count: sheetAudit.input_row_count,
          retained_row_count: sheetAudit.retained_row_count,
          duplicate_rows_removed: sheetAudit.duplicate_rows_removed,
          duplicates: sheetAudit.duplicates,
        },
      ]),
    ),
  };

  if (changedSheets.length > 0 || exceptionSheetAdded || exceptionSheetEnabledColumnAdded || manualSheetsAdded.length > 0) {
    await scanFormulaErrors(workbook, "deduplicated editable workbook");
    const tempPath = `${editableWorkbookPath}.deduplicate.tmp.xlsx`;
    const output = await SpreadsheetFile.exportXlsx(workbook);
    await output.save(tempPath);
    const reopenedInput = await FileBlob.load(tempPath);
    const reopened = await SpreadsheetFile.importXlsx(reopenedInput);
    const remaining = collectEditableDuplicateAudit(reopened);
    if (remaining.duplicateRows !== 0) {
      throw new Error(
        "Editable workbook duplicate cleanup did not converge: "
        + `${remaining.duplicateRows} duplicate row(s) remain.`,
      );
    }
    for (const sheetName of [
      ...changedSheets,
      ...((exceptionSheetAdded || exceptionSheetEnabledColumnAdded) ? [exceptionSheetName] : []),
      ...manualSheetsAdded,
    ]) {
      const preview = await reopened.render({
        sheetName,
        range: "A1:C20",
        scale: 1,
        format: "png",
      });
      const safeName = sheetName.replaceAll(/[^A-Za-z0-9]+/g, "_");
      await fs.mkdir(
        path.join(previewRoot, "editable_duplicate_cleanup"),
        { recursive: true },
      );
      await fs.writeFile(
        path.join(
          previewRoot,
          "editable_duplicate_cleanup",
          `${safeName}.png`,
        ),
        new Uint8Array(await preview.arrayBuffer()),
      );
    }
    await fs.copyFile(tempPath, editableWorkbookPath);
    await fs.unlink(tempPath);
    await removeInspectSidecar(tempPath);
  }

  await fs.writeFile(
    editableDuplicateAuditPath,
    JSON.stringify(audit, null, 2),
    "utf8",
  );
  await removeInspectSidecar(editableWorkbookPath);
  return audit;
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
      "Start here",
      "This is the human-maintained mapping contract. Yellow cells are editable; generated pair sheets live in other workbooks.",
    ],
    [
      "What people edit",
      "Maintain the six single-axis mapping sheets, four accepted-extra-pair sheets, exceptions, and rollup sheets in this workbook.",
    ],
    [
      "Why axes are separate",
      "Sector/flow and fuel/product meanings are maintained once, then combined only for accepted exact source and target pairs.",
    ],
    [
      "ESTO dataset scope",
      "BOTH means the relationship applies to ESTO and ESTO Extended. ESTO or ESTO_EXTENDED restricts it to one target registry.",
    ],
    [
      "Generated outputs",
      "The refresh writes exact-pair evidence and the compatibility master. Do not copy generated columns back here or edit generated pair sheets.",
    ],
    [
      "Extra key pairs",
      "Each row accepts one exact dataset pair that would otherwise be excluded. Presence means accepted; delete the row to withdraw that authority. No checkbox column is used.",
    ],
    [
      "Duplicate rows",
      "Each refresh keeps the first occurrence of an exact mapping key and removes later duplicates from this workbook. Different targets remain valid one-to-many mappings.",
    ],
    [
      "Subtotals and rollups",
      "Maintain rollup rules here. The refresh applies them to pair evidence and copies the rollup sheets into the generated master.",
    ],
    [
      "Run order",
      "Save and close Excel, run separate_axis_mapping_refresh_workflow.py as the preliminary production gate, then run the affected mapping Stages 1–3.",
    ],
    [
      "Review after generation",
      "Inspect missing relations, many-to-many components, sibling coverage, rollup/hierarchy checks, lineage, and value preservation.",
    ],
    [
      "Current status",
      `${String(manifest.prototype_status).replace(/[.\s]+$/, "")}. Presence accepts a row; deletion withdraws it.`,
    ],
  ]);
  await addWorkflowDiagram(readme, 19, 20);
  readme.getRange("A1:H35").format.font.name = "Aptos";
  readme.freezePanes.freezeRows(4);

  await addCsvSheets(workbook, manifest.editable_sources, true);
  ensureExceptionSheet(workbook);
  await ensureEditableManualSheets(workbook);
  const expectedEditableSheets = [
    "README",
    ...Object.keys(manifest.editable_sources),
    exceptionSheetName,
    ...editableManualSheetNames,
  ];
  const actualEditableSheets = workbook.worksheets.items.map((sheet) => sheet.name);
  if (JSON.stringify(actualEditableSheets) !== JSON.stringify(expectedEditableSheets)) {
    throw new Error(
      "Editable workbook sheet contract changed: "
      + `${JSON.stringify(actualEditableSheets)} vs `
      + `${JSON.stringify(expectedEditableSheets)}`,
    );
  }
  await renderWorkbook(workbook, "editable_axis", {
    README: "A1:H35",
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
      `Ordinary ESTO pairs are eligible when non-zero in the final ESTO year (${manifest.historical_boundary_year}) or reviewed. ESTO Extended accepts structurally present pairs because valid detail can currently be zero.`,
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
      "Eligibility follows each dataset's authority rule. Oversized or cross-family product-axis connected components block compilation before mappings are promoted.",
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
  const editableInput = await FileBlob.load(editableWorkbookPath);
  const editableWorkbook = await SpreadsheetFile.importXlsx(editableInput);
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

  for (const sheetName of editableManualSheetNames) {
    const existing = workbook.worksheets.getItem(sheetName);
    const originalIndex = existing.index;
    existing.delete();
    const copiedSheet = copySheetValues(
      editableWorkbook,
      workbook,
      sheetName,
      false,
    );
    copiedSheet.index = originalIndex;
    replacementSummary[sheetName] = {
      presentation: "Copied from the editable single-axis workbook.",
    };
  }

  await refreshMasterGuide(workbook);

  await scanFormulaErrors(workbook, "generated master");
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(generatedMasterPath);

  let validatedWorkbook = workbook;
  let validationLabel = "generated master";
  if (reopenMaster) {
    const reopenedInput = await FileBlob.load(generatedMasterPath);
    validatedWorkbook = await SpreadsheetFile.importXlsx(reopenedInput);
    validationLabel = "reopened generated master";
  }
  const contractValidation = validateMasterContract(
    validatedWorkbook,
    expectedSheetNames,
  );
  await renderWorkbook(validatedWorkbook, "generated_master", {
    Guide: "A1:H34",
    leap_combined_esto: "A1:H18",
    leap_combined_ninth: "A1:G18",
    ninth_pairs_to_esto_pairs: "A1:H18",
  });
  await scanFormulaErrors(validatedWorkbook, validationLabel);
  await removeInspectSidecar(generatedMasterPath);

  const inspection = {};
  for (const sheetName of Object.keys(manifest.compiled_sources)) {
    const result = await validatedWorkbook.inspect({
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
const reopenMaster = globalThis.REOPEN_MASTER
  ?? runtimeEnvironment.REOPEN_MASTER !== "false";
const verifyPairs = globalThis.VERIFY_PAIRS
  ?? runtimeEnvironment.VERIFY_PAIRS === "true";
const promoteMaster = globalThis.PROMOTE_MASTER
  ?? runtimeEnvironment.PROMOTE_MASTER === "true";
const cleanEditableDuplicates = globalThis.CLEAN_EDITABLE_DUPLICATES
  ?? runtimeEnvironment.CLEAN_EDITABLE_DUPLICATES !== "false";

if (buildEditable) {
  await buildEditableWorkbook();
}
let editableDuplicateCleanup = null;
if (cleanEditableDuplicates) {
  editableDuplicateCleanup = await cleanEditableWorkbookDuplicates();
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
  // Node's rename cannot replace an existing destination on Windows (EPERM).
  // A verified backup already exists above, and the hash/reopen checks below
  // protect the promoted copy, so overwrite explicitly and remove the temp.
  await fs.copyFile(promotionTempPath, canonicalMasterPath);
  await fs.unlink(promotionTempPath);

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
    editable_duplicate_cleanup: editableDuplicateCleanup,
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
  editableDuplicateAuditPath,
  editableDuplicateCleanup,
  promoted: promoteMaster,
}, null, 2));
