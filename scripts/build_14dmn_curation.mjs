import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "/Users/nana/Desktop/PepDB/PepDatabase";
const outputDir = path.join(
  root,
  "curation_outputs",
  "1_4_dimethylnaphthalene_literature_20260625",
);

const screeningHeaders = [
  "paper_id",
  "pdf_filename",
  "title",
  "year",
  "doi",
  "target_compound_role",
  "evidence_category",
  "include_as_1_4_DMN_degradation_evidence",
  "include_as_pathway_step",
  "biological_system",
  "analytical_method",
  "substrate_information",
  "product_information",
  "gene_information",
  "enzyme_information",
  "curation_summary",
  "exclusion_or_limitation",
  "verification_status",
];

const papers = [
  {
    paper_id: "DMN-P01",
    pdf_filename:
      "1,4-dimethylnaphthalene treatment of seed potatoes affects tuber size distribution..pdf",
    title:
      "1,4-Dimethylnaphthalene Treatment of Seed Potatoes Affects Tuber Size Distribution",
    year: 2005,
    doi: "",
    target_compound_role: "Applied potato sprout inhibitor",
    evidence_category: "Plant/agronomic response",
    include_as_1_4_DMN_degradation_evidence: "No",
    include_as_pathway_step: "No",
    biological_system: "Potato seed tubers",
    analytical_method: "Agronomic and residue measurements",
    substrate_information: "1,4-DMN treatment",
    product_information: "No microbial transformation products reported",
    gene_information: "",
    enzyme_information: "",
    curation_summary:
      "Evaluates sprout inhibition, emergence, yield, and tuber-size distribution.",
    exclusion_or_limitation:
      "No microbial biodegradation experiment and no substrate-to-product transformation.",
    verification_status: "Full PDF screened",
  },
  {
    paper_id: "DMN-P02",
    pdf_filename:
      "Anaerobic biodegradation of benzo(a)pyrene by a novel Cellulosimicrobium cellulans CWS2 isolated from polycyclic aromatic hydrocarbon-contaminated soil..pdf",
    title:
      "Anaerobic biodegradation of benzo(a)pyrene by a novel Cellulosimicrobium cellulans CWS2",
    year: 2017,
    doi: "10.1016/j.bjm.2017.04.014",
    target_compound_role: "Not studied",
    evidence_category: "Other-substrate biodegradation",
    include_as_1_4_DMN_degradation_evidence: "No",
    include_as_pathway_step: "No",
    biological_system: "Cellulosimicrobium cellulans CWS2",
    analytical_method: "GC-MS and benzo(a)pyrene removal assays",
    substrate_information: "Benzo(a)pyrene",
    product_information: "Benzo(a)pyrene-related metabolites",
    gene_information: "",
    enzyme_information: "",
    curation_summary: "Direct biodegradation evidence for benzo(a)pyrene.",
    exclusion_or_limitation: "Does not test 1,4-DMN.",
    verification_status: "Full PDF screened; DOI present in PDF",
  },
  {
    paper_id: "DMN-P03",
    pdf_filename:
      "Biodegradation of Crude Oil by Nitrate-Reducing, Sulfate-Reducing, and Methanogenic Microbial Communities under High-Pressure Conditions..pdf",
    title:
      "Biodegradation of Crude Oil by Nitrate-Reducing, Sulfate-Reducing, and Methanogenic Microbial Communities under High-Pressure Conditions",
    year: 2024,
    doi: "10.3390/microorganisms12081543",
    target_compound_role:
      "One named isomer within a pooled crude-oil C2-naphthalene fraction",
    evidence_category: "Indirect mixture-level biodegradation evidence",
    include_as_1_4_DMN_degradation_evidence: "Yes - indirect",
    include_as_pathway_step: "No",
    biological_system:
      "Sulfate-reducing enrichment from Jilin Oilfield production water; Desulfomicrobium, Desulfovibrio, Desulfotomaculum/Desulfovirgula, and Thermodesulfovibrio reported",
    analytical_method: "GC-MS total-ion chromatograms of crude-oil aromatic fractions",
    substrate_information:
      "Crude-oil C2-naphthalene fraction containing 1,4-DMN and multiple other isomers",
    product_information: "Products not identified for 1,4-DMN",
    gene_information: "No 1,4-DMN-specific gene identified",
    enzyme_information: "No 1,4-DMN-specific enzyme identified",
    curation_summary:
      "C2-naphthalene fraction was largely degraded after 90 days under sulfate-reducing atmospheric- and high-pressure incubations at 60 C.",
    exclusion_or_limitation:
      "1,4-DMN was not quantified separately from the pooled isomer fraction; no reaction products or specific degrader were assigned.",
    verification_status: "Full PDF screened; DOI present in PDF",
  },
  {
    paper_id: "DMN-P04",
    pdf_filename:
      "Changes in gene expression in potato meristems treated with the sprout suppressor 1,4-dimethylnaphthalene are dependent on tuber age and dormancy status..pdf",
    title:
      "Changes in gene expression in potato meristems treated with the sprout suppressor 1,4-dimethylnaphthalene are dependent on tuber age and dormancy status",
    year: 2020,
    doi: "10.1371/journal.pone.0235444",
    target_compound_role: "Potato sprout inhibitor",
    evidence_category: "Plant transcriptomic response",
    include_as_1_4_DMN_degradation_evidence: "No",
    include_as_pathway_step: "No",
    biological_system: "Solanum tuberosum meristems",
    analytical_method: "RNA-seq",
    substrate_information: "1,4-DMN exposure",
    product_information: "No degradation products reported",
    gene_information: "Plant stress, DNA replication, and cell-division responses",
    enzyme_information: "",
    curation_summary: "Characterizes potato gene-expression responses to treatment.",
    exclusion_or_limitation:
      "Response genes are not microbial degradation genes and no chemical transformation was measured.",
    verification_status: "Full PDF screened; DOI present in PDF",
  },
  {
    paper_id: "DMN-P05",
    pdf_filename:
      "Diesel and Crude Oil Biodegradation by Cold-Adapted Microbial Communities in the Labrador Sea..pdf",
    title:
      "Diesel and Crude Oil Biodegradation by Cold-Adapted Microbial Communities in the Labrador Sea",
    year: 2021,
    doi: "10.1128/AEM.00800-21",
    target_compound_role: "Not specifically resolved",
    evidence_category: "Petroleum-mixture biodegradation",
    include_as_1_4_DMN_degradation_evidence: "No",
    include_as_pathway_step: "No",
    biological_system: "Cold marine sediment microbial communities",
    analytical_method: "Hydrocarbon chemistry, amplicon sequencing, and metagenomics",
    substrate_information: "Diesel and crude oil",
    product_information: "No 1,4-DMN-specific products",
    gene_information: "General hydrocarbon-degradation potential",
    enzyme_information: "General alkane/aromatic degradation potential",
    curation_summary: "Demonstrates cold marine petroleum biodegradation.",
    exclusion_or_limitation:
      "Does not provide isomer-specific evidence for 1,4-DMN.",
    verification_status: "Full PDF screened; DOI present in PDF",
  },
  {
    paper_id: "DMN-P06",
    pdf_filename:
      "Exposure of Potato Tuber to Varying Concentrations of 1,4-Dimethylnaphthalene Decrease the Expression of Transcripts for Plastid Proteins.pdf",
    title:
      "Exposure of Potato Tuber to Varying Concentrations of 1,4-Dimethylnaphthalene Decrease the Expression of Transcripts for Plastid Proteins",
    year: 2016,
    doi: "10.1007/s12230-016-9504-x",
    target_compound_role: "Potato sprout inhibitor",
    evidence_category: "Plant transcriptomic response",
    include_as_1_4_DMN_degradation_evidence: "No",
    include_as_pathway_step: "No",
    biological_system: "Potato tubers",
    analytical_method: "Transcript-expression analysis",
    substrate_information: "1,4-DMN exposure",
    product_information: "No degradation products reported",
    gene_information: "Plant plastid-associated transcript responses",
    enzyme_information: "",
    curation_summary: "Measures potato transcriptional responses.",
    exclusion_or_limitation: "No microbial biodegradation or metabolite identification.",
    verification_status: "Full PDF screened; DOI present in PDF",
  },
  {
    paper_id: "DMN-P07",
    pdf_filename:
      "Functionalized derivatives of 1,4-dimethylnaphthalene as precursors for biomedical applications synthesis, structures, spectroscopy and photochemical activation in the presence of dioxygen..pdf",
    title:
      "Functionalized derivatives of 1,4-dimethylnaphthalene as precursors for biomedical applications",
    year: 2012,
    doi: "10.1039/c2ob26236c",
    target_compound_role: "Chemical precursor",
    evidence_category: "Synthetic/photochemical chemistry",
    include_as_1_4_DMN_degradation_evidence: "No",
    include_as_pathway_step: "No",
    biological_system: "No microbial system",
    analytical_method: "Chemical synthesis, spectroscopy, and photochemistry",
    substrate_information: "Functionalized 1,4-DMN derivatives",
    product_information: "Synthetic derivatives and endoperoxides",
    gene_information: "",
    enzyme_information: "",
    curation_summary: "Describes non-biological synthesis and photochemical activation.",
    exclusion_or_limitation: "Chemical products are not microbial degradation products.",
    verification_status: "Full PDF screened; DOI present in PDF",
  },
  {
    paper_id: "DMN-P08",
    pdf_filename:
      "Genome sequence analysis of deep sea Aspergillus sydowii BOBA1 and effect of high pressure on biodegradation of spent engine oil..pdf",
    title:
      "Genome sequence analysis of deep sea Aspergillus sydowii BOBA1 and effect of high pressure on biodegradation of spent engine oil",
    year: 2021,
    doi: "10.1038/s41598-021-88525-9",
    target_compound_role: "Not specifically studied",
    evidence_category: "Other-substrate biodegradation",
    include_as_1_4_DMN_degradation_evidence: "No",
    include_as_pathway_step: "No",
    biological_system: "Aspergillus sydowii BOBA1",
    analytical_method: "Spent-engine-oil degradation and genome analysis",
    substrate_information: "Spent engine oil",
    product_information: "No 1,4-DMN-specific products",
    gene_information: "General hydrocarbon/xenobiotic pathway genes",
    enzyme_information: "General dioxygenase, hydrolase, reductase, and peroxidase annotations",
    curation_summary: "Supports fungal spent-oil degradation.",
    exclusion_or_limitation:
      "Genome annotations do not establish 1,4-DMN degradation.",
    verification_status: "Full PDF screened; DOI present in PDF",
  },
  {
    paper_id: "DMN-P09",
    pdf_filename:
      "Structural phase transition in a charge-transfer compound tropylium hexafluoridoantimonateV-1,4-dimethylnaphthalene ..pdf",
    title:
      "Structural phase transition in a charge-transfer compound: tropylium hexafluoridoantimonate(V)-1,4-dimethylnaphthalene",
    year: 2022,
    doi: "10.1107/S2053229622005320",
    target_compound_role: "Crystal component",
    evidence_category: "Crystallography/materials chemistry",
    include_as_1_4_DMN_degradation_evidence: "No",
    include_as_pathway_step: "No",
    biological_system: "No biological system",
    analytical_method: "X-ray crystallography and dielectric measurements",
    substrate_information: "1,4-DMN charge-transfer crystal",
    product_information: "No biodegradation products",
    gene_information: "",
    enzyme_information: "",
    curation_summary: "Describes crystal structure and phase transition.",
    exclusion_or_limitation: "No biodegradation experiment.",
    verification_status: "Full PDF screened; DOI present in PDF",
  },
  {
    paper_id: "DMN-P10",
    pdf_filename:
      "Substrate interactions during aerobic biodegradation of benzene..pdf",
    title: "Substrate interactions during aerobic biodegradation of benzene",
    year: 1989,
    doi: "10.1128/aem.55.12.3221-3225.1989",
    target_compound_role: "Directly measured mixed-culture substrate",
    evidence_category: "Direct parent-compound disappearance",
    include_as_1_4_DMN_degradation_evidence: "Yes - direct",
    include_as_pathway_step: "No",
    biological_system:
      "Two undefined aerobic mixed bacterial biofilm inocula acclimated in rotating-drum systems",
    analytical_method: "Pentane extraction followed by GC-FID; ATP biomass assay",
    substrate_information:
      "1,4-DMN at approximately 0.20 mg/L, alone or in factorial mixtures of aromatic compounds",
    product_information: "Products and mineralization were not measured",
    gene_information: "No genes identified",
    enzyme_information: "No enzymes identified",
    curation_summary:
      "DMN disappearance ranged with mixture composition; authors report aromatic hydrocarbons including DMN were degraded within 11 days, with many DMN-containing treatments reaching 100% disappearance.",
    exclusion_or_limitation:
      "Undefined consortium, no isolate assignment, no products, no mineralization measurement, and no gene/enzyme evidence.",
    verification_status: "Full PDF screened; DOI verified through Crossref",
  },
  {
    paper_id: "DMN-P11",
    pdf_filename:
      "The sprout inhibitor 1,4-dimethylnaphthalene induces the expression of the cell cycle inhibitors KRP1 and KRP2 in potatoes..pdf",
    title:
      "The sprout inhibitor 1,4-dimethylnaphthalene induces the expression of the cell cycle inhibitors KRP1 and KRP2 in potatoes",
    year: 2012,
    doi: "10.1007/s10142-011-0257-9",
    target_compound_role: "Potato sprout inhibitor",
    evidence_category: "Plant transcriptomic/cell-cycle response",
    include_as_1_4_DMN_degradation_evidence: "No",
    include_as_pathway_step: "No",
    biological_system: "Potato tuber meristems",
    analytical_method: "Microarray, qRT-PCR, and thymidine incorporation",
    substrate_information: "1,4-DMN exposure",
    product_information: "No degradation products reported",
    gene_information: "Plant KRP1 and KRP2 response",
    enzyme_information: "",
    curation_summary: "Studies plant mode of action and cell-cycle regulation.",
    exclusion_or_limitation:
      "Plant response genes are not microbial degradation genes.",
    verification_status: "Full PDF screened; DOI present in PDF",
  },
  {
    paper_id: "DMN-P12",
    pdf_filename:
      "The sprout inhibitors chlorpropham and 1,4-dimethylnaphthalene elicit different transcriptional profiles and do not suppress growth through a prolongation of the dormant state..pdf",
    title:
      "The sprout inhibitors chlorpropham and 1,4-dimethylnaphthalene elicit different transcriptional profiles",
    year: 2010,
    doi: "10.1007/s11103-010-9607-6",
    target_compound_role: "Potato sprout inhibitor",
    evidence_category: "Plant transcriptomic/metabolic response",
    include_as_1_4_DMN_degradation_evidence: "No",
    include_as_pathway_step: "No",
    biological_system: "Potato tuber meristems",
    analytical_method: "Microarray and plant metabolite profiling",
    substrate_information: "1,4-DMN and chlorpropham exposure",
    product_information: "No 1,4-DMN degradation products reported",
    gene_information: "Plant dormancy and oxygen-metabolism responses",
    enzyme_information: "",
    curation_summary: "Compares potato responses to two sprout inhibitors.",
    exclusion_or_limitation:
      "No microbial transformation of 1,4-DMN was measured.",
    verification_status: "Full PDF screened; DOI present in PDF",
  },
];

const evidenceHeaders = [
  "evidence_record_id",
  "pesticide",
  "pathway_status",
  "pathway_step_ready",
  "substrate_name",
  "substrate_identifier",
  "product_name",
  "product_identifier",
  "organism_or_community",
  "culture_type",
  "electron_acceptor",
  "temperature_C",
  "pressure_MPa",
  "incubation_time_days",
  "initial_concentration",
  "degradation_result",
  "analytical_method",
  "gene",
  "enzyme",
  "evidence_type",
  "evidence_directness",
  "confidence",
  "doi",
  "source_pdf",
  "curation_notes",
];

const evidence = [
  {
    evidence_record_id: "DMN-E01",
    pesticide: "1,4-Dimethylnaphthalene",
    pathway_status: "Partial degradation evidence only",
    pathway_step_ready: "No",
    substrate_name: "1,4-Dimethylnaphthalene",
    substrate_identifier: "CAS 571-58-4",
    product_name: "Not identified",
    product_identifier: "",
    organism_or_community:
      "Undefined mixed aerobic bacterial biofilm cultures from rotating-drum systems",
    culture_type: "Mixed acclimated biofilm inocula in batch bottles",
    electron_acceptor: "Oxygen",
    temperature_C: 22,
    pressure_MPa: "",
    incubation_time_days: "5 and 11",
    initial_concentration: "Approximately 0.20 mg/L",
    degradation_result:
      "Variable at day 5; authors state DMN and other tested hydrocarbons were degraded within 11 days, with many DMN-containing treatments showing 100% disappearance",
    analytical_method: "Pentane extraction and GC-FID",
    gene: "Not identified",
    enzyme: "Not identified",
    evidence_type: "Parent-compound disappearance",
    evidence_directness: "Direct",
    confidence: "Moderate",
    doi: "10.1128/aem.55.12.3221-3225.1989",
    source_pdf:
      "Substrate interactions during aerobic biodegradation of benzene..pdf",
    curation_notes:
      "Usable as degradation evidence, but not as a substrate-to-product pathway arrow because products and mineralization were not measured.",
  },
  {
    evidence_record_id: "DMN-E02",
    pesticide: "1,4-Dimethylnaphthalene",
    pathway_status: "Indirect mixture-level evidence",
    pathway_step_ready: "No",
    substrate_name: "Crude-oil C2-naphthalene fraction containing 1,4-DMN",
    substrate_identifier: "",
    product_name: "Not identified",
    product_identifier: "",
    organism_or_community:
      "Sulfate-reducing Jilin Oilfield production-water enrichment; Desulfomicrobium, Desulfovibrio, Desulfotomaculum/Desulfovirgula, and Thermodesulfovibrio reported",
    culture_type: "Anaerobic crude-oil enrichment",
    electron_acceptor: "Sulfate, 10 mM",
    temperature_C: 60,
    pressure_MPa: "0.1 and 12",
    incubation_time_days: 90,
    initial_concentration: "2 g crude oil in 50 mL production water for atmospheric setup",
    degradation_result:
      "Pooled C2-naphthalene chromatographic fraction was largely degraded under sulfate-reducing conditions",
    analytical_method: "GC-MS total-ion chromatograms",
    gene: "No 1,4-DMN-specific gene",
    enzyme: "No 1,4-DMN-specific enzyme",
    evidence_type: "Mixture/fraction disappearance",
    evidence_directness: "Indirect",
    confidence: "Low for the 1,4 isomer specifically",
    doi: "10.3390/microorganisms12081543",
    source_pdf:
      "Biodegradation of Crude Oil by Nitrate-Reducing, Sulfate-Reducing, and Methanogenic Microbial Communities under High-Pressure Conditions..pdf",
    curation_notes:
      "The C2 fraction included several dimethylnaphthalene isomers; 1,4-DMN was not resolved or quantified independently.",
  },
];

const pathwayHeaders = [
  "pathway_id",
  "pesticide",
  "pathway_title",
  "pathway_status",
  "step_order",
  "substrate_name",
  "product_name",
  "gene",
  "enzyme",
  "organism",
  "step_evidence_type",
  "source_doi",
  "step_confidence",
  "review_status",
  "notes",
];
const pathwayRows = [
  {
    pathway_id: "DMN_PATHWAY_UNRESOLVED_001",
    pesticide: "1,4-Dimethylnaphthalene",
    pathway_title: "1,4-Dimethylnaphthalene microbial degradation",
    pathway_status: "INSUFFICIENT_PRODUCT_DATA",
    step_order: "",
    substrate_name: "1,4-Dimethylnaphthalene",
    product_name: "",
    gene: "",
    enzyme: "",
    organism: "",
    step_evidence_type: "PARENT_DISAPPEARANCE_ONLY",
    source_doi: "10.1128/aem.55.12.3221-3225.1989",
    step_confidence: "Not arrow-ready",
    review_status: "NEEDS_PRODUCT_IDENTIFICATION_PAPER",
    notes:
      "Do not draw a pathway arrow until at least one experimentally identified transformation product is supported by a source.",
  },
];

const csvEscape = (value) => {
  const text = String(value ?? "");
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};
const toCsv = (headers, records) =>
  [
    headers.map(csvEscape).join(","),
    ...records.map((record) =>
      headers.map((header) => csvEscape(record[header])).join(","),
    ),
  ].join("\n") + "\n";

await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(
  path.join(outputDir, "1_4_DMN_paper_screening.csv"),
  toCsv(screeningHeaders, papers),
);
await fs.writeFile(
  path.join(outputDir, "1_4_DMN_degradation_evidence.csv"),
  toCsv(evidenceHeaders, evidence),
);
await fs.writeFile(
  path.join(outputDir, "1_4_DMN_pathway_curation.csv"),
  toCsv(pathwayHeaders, pathwayRows),
);

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const summaryRows = [
  ["Metric", "Value", "Interpretation"],
  ["PDFs screened", papers.length, "All supplied PDFs were full-text screened"],
  [
    "Direct 1,4-DMN degradation studies",
    papers.filter((paper) => paper.include_as_1_4_DMN_degradation_evidence === "Yes - direct").length,
    "Parent-compound disappearance measured",
  ],
  [
    "Indirect 1,4-DMN evidence",
    papers.filter((paper) => paper.include_as_1_4_DMN_degradation_evidence === "Yes - indirect").length,
    "1,4-DMN included within a pooled fraction",
  ],
  ["Pathway-ready reaction steps", 0, "No supplied paper identifies a substrate-to-product reaction for 1,4-DMN"],
  ["Identified products", 0, "No 1,4-DMN-specific microbial products found"],
  ["Identified degradation genes", 0, "No 1,4-DMN-specific genes found"],
  ["Identified degradation enzymes", 0, "No 1,4-DMN-specific enzymes found"],
  [
    "Recommended database status",
    "Partial degradation evidence",
    "Display experimental records but do not draw a complete pathway",
  ],
];
summary.getRange(`A1:C${summaryRows.length}`).values = summaryRows;
summary.showGridLines = false;
summary.freezePanes.freezeRows(1);
summary.getRange("A1:C1").format = {
  fill: "#285C4D",
  font: { bold: true, color: "#FFFFFF" },
};
summary.getRange(`A1:C${summaryRows.length}`).format.wrapText = true;
summary.getRange(`A2:A${summaryRows.length}`).format.font = { bold: true };
summary.getRange("A:A").format.columnWidth = 30;
summary.getRange("B:B").format.columnWidth = 30;
summary.getRange("C:C").format.columnWidth = 62;

function addDataSheet(name, headers, records, color, tableName) {
  const sheet = workbook.worksheets.add(name);
  const matrix = [
    headers,
    ...records.map((record) => headers.map((header) => record[header] ?? "")),
  ];
  sheet.getRangeByIndexes(0, 0, matrix.length, headers.length).values = matrix;
  sheet.freezePanes.freezeRows(1);
  sheet.getRangeByIndexes(0, 0, 1, headers.length).format = {
    fill: color,
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  sheet.getUsedRange().format.wrapText = true;
  sheet.getUsedRange().format.autofitColumns();
  for (let column = 0; column < headers.length; column += 1) {
    const range = sheet.getRangeByIndexes(0, column, matrix.length, 1);
    if (range.format.columnWidth > 30) range.format.columnWidth = 30;
  }
  const endColumn = String.fromCharCode(64 + headers.length);
  sheet.tables.add(`A1:${endColumn}${matrix.length}`, true, tableName);
}

addDataSheet("Paper Screening", screeningHeaders, papers, "#365F91", "PaperScreeningTable");
addDataSheet("Degradation Evidence", evidenceHeaders, evidence, "#7A4E21", "DegradationEvidenceTable");
addDataSheet("Pathway Curation", pathwayHeaders, pathwayRows, "#6A4C76", "PathwayCurationTable");

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(path.join(outputDir, "1_4_DMN_literature_curation_review.xlsx"));

for (const [sheetName, range, filename] of [
  ["Summary", `A1:C${summaryRows.length}`, "summary_preview.png"],
  ["Paper Screening", "A1:H13", "paper_screening_preview.png"],
  ["Degradation Evidence", "A1:J3", "degradation_evidence_preview.png"],
  ["Pathway Curation", "A1:O2", "pathway_curation_preview.png"],
]) {
  const preview = await workbook.render({
    sheetName,
    range,
    scale: 1.4,
    format: "png",
  });
  await fs.writeFile(
    path.join(outputDir, filename),
    new Uint8Array(await preview.arrayBuffer()),
  );
}

const inspection = await workbook.inspect({
  kind: "table",
  range: `Summary!A1:C${summaryRows.length}`,
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 3,
});
await fs.writeFile(path.join(outputDir, "summary.inspect.ndjson"), inspection.ndjson);

console.log(JSON.stringify({
  outputDir,
  screened: papers.length,
  evidenceRecords: evidence.length,
  pathwaySteps: 0,
}));
