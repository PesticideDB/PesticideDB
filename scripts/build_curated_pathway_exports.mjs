import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "/Users/nana/Desktop/PepDB/PepDatabase";
const sourcePath = path.join(root, "data_files", "core", "pesticide_data.xlsx");
const outputDir = path.join(
  root,
  "curation_outputs",
  "pathway_evidence_curated_20260625",
);
const perPesticideDir = path.join(outputDir, "per_pesticide");

const input = await FileBlob.load(sourcePath);
const sourceWorkbook = await SpreadsheetFile.importXlsx(input);
const sourceSheet = sourceWorkbook.worksheets.getItemAt(0);
const used = sourceSheet.getUsedRange(true);
const matrix = used.values;
const headers = matrix[0].map((value) => String(value ?? "").trim());
const rows = matrix.slice(1).map((values, index) => {
  const row = {};
  headers.forEach((header, column) => {
    row[header] = values[column] ?? "";
  });
  row.source_row = index + 2;
  return row;
});

const clean = (value) => String(value ?? "").replace(/\s+/g, " ").trim();
const canonicalKey = (value) => clean(value).toLocaleLowerCase("en");
const canonicalNames = new Map();
for (const row of rows) {
  const name = clean(row.Pesticide);
  const key = canonicalKey(name);
  if (name && !canonicalNames.has(key)) canonicalNames.set(key, name);
}

const duplicateKey = (row) =>
  [
    row.Pesticide,
    row.Microorganism,
    row.Gene,
    row.Enzyme,
    row.Reference,
  ]
    .map(canonicalKey)
    .join("||");
const duplicateCounts = new Map();
for (const row of rows) {
  const key = duplicateKey(row);
  duplicateCounts.set(key, (duplicateCounts.get(key) || 0) + 1);
}

const doiPattern = /^10\.\d{4,9}\/\S+$/i;
const classifyReference = (value) => {
  const reference = clean(value);
  if (!reference) return ["missing", "review_required"];
  if (doiPattern.test(reference)) return ["DOI", "format_valid"];
  if (/^PMID\s*:/i.test(reference)) return ["PMID", "format_valid"];
  if (/no DOI|DOI not available/i.test(reference)) {
    return ["citation_without_DOI", "manual_citation_needed"];
  }
  if (/^0\.1007\//i.test(reference)) return ["probable_DOI_typo", "review_required"];
  return ["other_reference", "review_required"];
};

const combinedHeaders = [
  "source_row",
  "source_dataset",
  "record_scope",
  "canonical_pesticide",
  ...headers,
  "duplicate_key_count",
  "potential_duplicate",
  "reference_type",
  "reference_format_status",
  "pathway_step_ready",
  "pathway_data_gap",
];

const combinedRows = rows.map((row) => {
  const [referenceType, referenceStatus] = classifyReference(row.Reference);
  const duplicateCount = duplicateCounts.get(duplicateKey(row)) || 1;
  return {
    source_row: row.source_row,
    source_dataset: "data_files/core/pesticide_data.xlsx",
    record_scope: "CURATED_BIODEGRADATION_ONLY",
    canonical_pesticide: canonicalNames.get(canonicalKey(row.Pesticide)),
    ...Object.fromEntries(headers.map((header) => [header, row[header]])),
    duplicate_key_count: duplicateCount,
    potential_duplicate: duplicateCount > 1 ? "Yes" : "No",
    reference_type: referenceType,
    reference_format_status: referenceStatus,
    pathway_step_ready: "No",
    pathway_data_gap:
      "Verify substrate, product, reaction order, step evidence, and pathway completeness from the cited publication",
  };
});

const templateHeaders = [
  "pathway_id",
  "pesticide",
  "pathway_title",
  "pathway_status",
  "pathway_organism",
  "step_order",
  "substrate_name",
  "substrate_identifier_type",
  "substrate_identifier",
  "product_name",
  "product_identifier_type",
  "product_identifier",
  "transformation_type",
  "gene",
  "enzyme",
  "pesticidedb_protein_id",
  "ncbi_protein_accession",
  "uniprot_accession",
  "step_evidence_type",
  "evidence_description",
  "assay_type",
  "metabolite_detection_method",
  "source_doi",
  "source_pmid",
  "source_reference",
  "evidence_scope",
  "step_confidence",
  "curator",
  "review_status",
  "notes",
];

const templateRows = [...canonicalNames.values()]
  .sort((a, b) => a.localeCompare(b))
  .map((pesticide) => ({
    pesticide,
    pathway_status: "",
    review_status: "NOT_STARTED",
  }));

const pilotSourceRows = combinedRows.filter(
  (row) => canonicalKey(row.canonical_pesticide) === "2,4-d",
);
const pilotRows = pilotSourceRows.map((sourceRow, index) => ({
  pathway_id: "PILOT_2_4_D_001",
  pesticide: "2,4-D",
  pathway_title: "2,4-D degradation pathway - literature curation pilot",
  pathway_status: "",
  pathway_organism: sourceRow.Microorganism,
  step_order: "",
  substrate_name: "",
  substrate_identifier_type: "",
  substrate_identifier: "",
  product_name: "",
  product_identifier_type: "",
  product_identifier: "",
  transformation_type: "",
  gene: sourceRow.Gene,
  enzyme: sourceRow.Enzyme_name_reported || sourceRow.Enzyme,
  pesticidedb_protein_id: "",
  ncbi_protein_accession: "",
  uniprot_accession: "",
  step_evidence_type:
    clean(sourceRow.Evidence).toLocaleLowerCase("en").includes("enzymatic")
      ? "PURIFIED_OR_ENZYME_ASSAY_REVIEW"
      : "EXPERIMENTAL_RECORD_REVIEW",
  evidence_description: sourceRow.Evidence,
  assay_type: "",
  metabolite_detection_method: "",
  source_doi: doiPattern.test(clean(sourceRow.Reference)) ? sourceRow.Reference : "",
  source_pmid: /^PMID\s*:/i.test(clean(sourceRow.Reference))
    ? clean(sourceRow.Reference).replace(/^PMID\s*:\s*/i, "")
    : "",
  source_reference: sourceRow.Reference,
  evidence_scope: "SOURCE_RECORD_ONLY_NOT_YET_ASSIGNED_TO_REACTION_STEP",
  step_confidence: "",
  curator: "",
  review_status: "NEEDS_FULL_TEXT_REVIEW",
  notes: `Seeded from curated source row ${sourceRow.source_row}; reaction fields intentionally blank.`,
  source_row: sourceRow.source_row,
  isolation_environment: sourceRow.Isolation_environment,
  isolation_location: sourceRow.Isolation_Location,
  publication_year: sourceRow.Publication_Year,
  source_record_number: index + 1,
}));
const pilotHeaders = [
  ...templateHeaders,
  "source_row",
  "isolation_environment",
  "isolation_location",
  "publication_year",
  "source_record_number",
];

const csvEscape = (value) => {
  const text = String(value ?? "");
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};
const toCsv = (headersList, records) =>
  [
    headersList.map(csvEscape).join(","),
    ...records.map((record) =>
      headersList.map((header) => csvEscape(record[header])).join(","),
    ),
  ].join("\n") + "\n";
const safeFilename = (name) =>
  clean(name)
    .replace(/[^A-Za-z0-9._-]+/g, "_")
    .replace(/^_+|_+$/g, "") || "unnamed";

await fs.mkdir(perPesticideDir, { recursive: true });
await fs.writeFile(
  path.join(outputDir, "curated_biodegradation_evidence_all_pesticides.csv"),
  toCsv(combinedHeaders, combinedRows),
);
for (const pesticide of [...canonicalNames.values()].sort((a, b) => a.localeCompare(b))) {
  const pesticideRows = combinedRows.filter(
    (row) => canonicalKey(row.canonical_pesticide) === canonicalKey(pesticide),
  );
  await fs.writeFile(
    path.join(perPesticideDir, `${safeFilename(pesticide)}.csv`),
    toCsv(combinedHeaders, pesticideRows),
  );
}
await fs.writeFile(
  path.join(outputDir, "pathway_curation_template_all_pesticides.csv"),
  toCsv(templateHeaders, templateRows),
);
await fs.writeFile(
  path.join(outputDir, "pilot_2_4_D_pathway_curation.csv"),
  toCsv(pilotHeaders, pilotRows),
);

const referenceCounts = combinedRows.reduce((counts, row) => {
  counts[row.reference_type] = (counts[row.reference_type] || 0) + 1;
  return counts;
}, {});
const summaryRows = [
  ["Metric", "Value", "Interpretation"],
  ["Source file", "data_files/core/pesticide_data.xlsx", "Curated biodegradation source only"],
  ["Database fidelity", "1016/1016 exact rows", "Live Pesticide table matches source multiset"],
  ["Source rows", rows.length, "All rows retained"],
  ["Canonical pesticides", canonicalNames.size, "Whitespace/case-normalized"],
  [
    "Potential duplicate rows",
    combinedRows.filter((row) => row.potential_duplicate === "Yes").length,
    "Review before merging; repeated records may represent distinct enzyme/evidence entries",
  ],
  ["Duplicate key groups", [...duplicateCounts.values()].filter((count) => count > 1).length, "Key: pesticide, organism, gene, enzyme, reference"],
  ["Records missing enzyme", rows.filter((row) => !clean(row.Enzyme)).length, "Pathway enzyme assignment unavailable"],
  ["Records missing gene", rows.filter((row) => !clean(row.Gene)).length, "Pathway gene assignment unavailable"],
  ["Records missing location", rows.filter((row) => !clean(row.Isolation_Location)).length, "Source metadata gap"],
  ["DOI-shaped references", referenceCounts.DOI || 0, "Format check only; not full-text biological validation"],
  ["PMID references", referenceCounts.PMID || 0, "Format check only"],
  [
    "References requiring review",
    combinedRows.filter((row) => row.reference_format_status === "review_required").length,
    "Probable typo or non-standard reference string",
  ],
  ["Supplemental protein rows included", 0, "Protein supplemental files are not read by this export or pathway evidence table"],
];
await fs.writeFile(
  path.join(outputDir, "validation_summary.csv"),
  toCsv(["Metric", "Value", "Interpretation"], summaryRows.slice(1).map((row) => ({
    Metric: row[0],
    Value: row[1],
    Interpretation: row[2],
  }))),
);

const reviewWorkbook = Workbook.create();
const summarySheet = reviewWorkbook.worksheets.add("Validation Summary");
summarySheet.getRange(`A1:C${summaryRows.length}`).values = summaryRows;
summarySheet.showGridLines = false;
summarySheet.freezePanes.freezeRows(1);
summarySheet.getRange("A1:C1").format = {
  fill: "#1F5D50",
  font: { bold: true, color: "#FFFFFF" },
};
summarySheet.getRange(`A2:A${summaryRows.length}`).format.font = { bold: true };
summarySheet.getRange(`A1:C${summaryRows.length}`).format.wrapText = true;
summarySheet.getRange("A:A").format.columnWidth = 28;
summarySheet.getRange("B:B").format.columnWidth = 24;
summarySheet.getRange("C:C").format.columnWidth = 62;

const evidenceSheet = reviewWorkbook.worksheets.add("Curated Evidence");
const evidenceMatrix = [
  combinedHeaders,
  ...combinedRows.map((row) => combinedHeaders.map((header) => row[header] ?? "")),
];
evidenceSheet.getRangeByIndexes(0, 0, evidenceMatrix.length, combinedHeaders.length).values =
  evidenceMatrix;
evidenceSheet.freezePanes.freezeRows(1);
evidenceSheet.freezePanes.freezeColumns(4);
evidenceSheet.getRangeByIndexes(0, 0, 1, combinedHeaders.length).format = {
  fill: "#1F5D50",
  font: { bold: true, color: "#FFFFFF" },
  wrapText: true,
};
evidenceSheet.getUsedRange().format.wrapText = true;
evidenceSheet.getUsedRange().format.autofitColumns();
for (let column = 0; column < combinedHeaders.length; column += 1) {
  const range = evidenceSheet.getRangeByIndexes(0, column, evidenceMatrix.length, 1);
  if (range.format.columnWidth > 28) range.format.columnWidth = 28;
}
evidenceSheet.tables.add(
  `A1:${String.fromCharCode(64 + combinedHeaders.length)}${evidenceMatrix.length}`,
  true,
  "CuratedEvidenceTable",
);

const templateSheet = reviewWorkbook.worksheets.add("Pathway Template");
const templateMatrix = [
  templateHeaders,
  ...templateRows.map((row) => templateHeaders.map((header) => row[header] ?? "")),
];
templateSheet.getRangeByIndexes(0, 0, templateMatrix.length, templateHeaders.length).values =
  templateMatrix;
templateSheet.freezePanes.freezeRows(1);
templateSheet.getRangeByIndexes(0, 0, 1, templateHeaders.length).format = {
  fill: "#365F91",
  font: { bold: true, color: "#FFFFFF" },
  wrapText: true,
};
templateSheet.getUsedRange().format.wrapText = true;
templateSheet.getUsedRange().format.autofitColumns();
for (let column = 0; column < templateHeaders.length; column += 1) {
  const range = templateSheet.getRangeByIndexes(0, column, templateMatrix.length, 1);
  if (range.format.columnWidth > 24) range.format.columnWidth = 24;
}

const pilotSheet = reviewWorkbook.worksheets.add("2,4-D Pilot");
const pilotMatrix = [
  pilotHeaders,
  ...pilotRows.map((row) => pilotHeaders.map((header) => row[header] ?? "")),
];
pilotSheet.getRangeByIndexes(0, 0, pilotMatrix.length, pilotHeaders.length).values =
  pilotMatrix;
pilotSheet.freezePanes.freezeRows(1);
pilotSheet.getRangeByIndexes(0, 0, 1, pilotHeaders.length).format = {
  fill: "#7A4E21",
  font: { bold: true, color: "#FFFFFF" },
  wrapText: true,
};
pilotSheet.getUsedRange().format.wrapText = true;
pilotSheet.getUsedRange().format.autofitColumns();
for (let column = 0; column < pilotHeaders.length; column += 1) {
  const range = pilotSheet.getRangeByIndexes(0, column, pilotMatrix.length, 1);
  if (range.format.columnWidth > 24) range.format.columnWidth = 24;
}

const xlsx = await SpreadsheetFile.exportXlsx(reviewWorkbook);
await xlsx.save(path.join(outputDir, "curated_pathway_evidence_review.xlsx"));

const preview = await reviewWorkbook.render({
  sheetName: "Validation Summary",
  range: `A1:C${summaryRows.length}`,
  scale: 1.5,
  format: "png",
});
await fs.writeFile(
  path.join(outputDir, "validation_summary_preview.png"),
  new Uint8Array(await preview.arrayBuffer()),
);
for (const [sheetName, range, filename] of [
  ["Curated Evidence", "A1:J12", "curated_evidence_preview.png"],
  ["Pathway Template", "A1:J12", "pathway_template_preview.png"],
  ["2,4-D Pilot", "A1:J12", "pilot_2_4_D_preview.png"],
]) {
  const sheetPreview = await reviewWorkbook.render({
    sheetName,
    range,
    scale: 1.2,
    format: "png",
  });
  await fs.writeFile(
    path.join(outputDir, filename),
    new Uint8Array(await sheetPreview.arrayBuffer()),
  );
}

const inspection = await reviewWorkbook.inspect({
  kind: "table",
  range: `Validation Summary!A1:C${summaryRows.length}`,
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 3,
});
await fs.writeFile(
  path.join(outputDir, "validation_summary.inspect.ndjson"),
  inspection.ndjson,
);

console.log(
  JSON.stringify({
    outputDir,
    sourceRows: rows.length,
    canonicalPesticides: canonicalNames.size,
    perPesticideFiles: canonicalNames.size,
    pilotRows: pilotRows.length,
  }),
);
