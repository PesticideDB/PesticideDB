import fs from "node:fs/promises";
import path from "node:path";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const root = "/Users/nana/Desktop/PepDB/PepDatabase";
const outDir = path.join(root, "curation_outputs", "missing_stepwise_pathway_information_20260707");
const jsonPath = path.join(outDir, "missing_stepwise_pathway_information.json");
const outputPath = path.join(outDir, "PesticideDB_Missing_Stepwise_Pathway_Information.xlsx");

const payload = JSON.parse(await fs.readFile(jsonPath, "utf8"));
const remaining = payload.remaining;
const allRows = payload.all;

const headers = [
  "pesticide",
  "current_pathway_status",
  "stepwise_arrow_count",
  "folder_found",
  "real_pdf_count",
  "html_placeholder_count",
  "top_candidate_papers",
  "doi_candidates_from_queue",
  "automated_evidence_signal",
  "needed_information_for_kegg_like_arrow",
  "recommended_next_action",
  "sample_files_from_usb_folder",
];

function matrix(rows) {
  return [
    headers,
    ...rows.map((row) => headers.map((header) => row[header] ?? "")),
  ];
}

function styleTable(sheet, rowCount, colCount) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const header = sheet.getRangeByIndexes(0, 0, 1, colCount);
  header.format.fill.color = "#143d59";
  header.format.font.color = "#ffffff";
  header.format.font.bold = true;
  header.format.wrapText = true;
  const used = sheet.getRangeByIndexes(0, 0, rowCount, colCount);
  used.format.borders = { preset: "inside", style: "thin", color: "#d9e1e8" };
  used.format.wrapText = true;
  const widths = [24, 36, 14, 13, 13, 17, 52, 42, 28, 58, 58, 58];
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, rowCount, 1).format.columnWidth = width;
  });
  sheet.getRangeByIndexes(1, 2, Math.max(rowCount - 1, 1), 4).format.horizontalAlignment = "center";
}

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
summary.showGridLines = false;
summary.getRange("A1:F1").merge();
summary.getRange("A1").values = [["PesticideDB Stepwise Pathway Curation Status"]];
summary.getRange("A1").format.font.bold = true;
summary.getRange("A1").format.font.size = 16;
summary.getRange("A1").format.fill.color = "#eaf3f8";
summary.getRange("A3:B8").values = [
  ["Evidence-positive pesticides audited", allRows.length],
  ["Pesticides with integrated stepwise arrows", allRows.filter((row) => Number(row.stepwise_arrow_count) > 0).length],
  ["Pesticides still needing stepwise pathway information", remaining.length],
  ["Total integrated stepwise arrows", allRows.reduce((sum, row) => sum + Number(row.stepwise_arrow_count || 0), 0)],
  ["File purpose", "Track which evidence-positive pesticides still need substrate/product/intermediate curation before KEGG-like pathway arrows are added."],
  ["Important rule", "Do not create pathway arrows from disappearance-only evidence unless products/intermediates or reactions are reported."],
];
summary.getRange("A3:A8").format.font.bold = true;
summary.getRange("A3:B8").format.wrapText = true;
summary.getRange("A3:B8").format.borders = { preset: "all", style: "thin", color: "#d9e1e8" };
summary.getRange("A3:B8").format.fill.color = "#ffffff";
summary.getRange("A:A").format.columnWidth = 42;
summary.getRange("B:B").format.columnWidth = 82;

const remainingSheet = workbook.worksheets.add("Remaining Needs");
remainingSheet.getRangeByIndexes(0, 0, remaining.length + 1, headers.length).values = matrix(remaining);
styleTable(remainingSheet, remaining.length + 1, headers.length);

const auditSheet = workbook.worksheets.add("All Evidence-Positive Audit");
auditSheet.getRangeByIndexes(0, 0, allRows.length + 1, headers.length).values = matrix(allRows);
styleTable(auditSheet, allRows.length + 1, headers.length);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "formula error scan",
});
console.log(errors.ndjson);

const preview = await workbook.render({ sheetName: "Summary", autoCrop: "all", scale: 1, format: "png" });
await fs.writeFile(path.join(outDir, "PesticideDB_Missing_Stepwise_Pathway_Information_summary_preview.png"), new Uint8Array(await preview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
