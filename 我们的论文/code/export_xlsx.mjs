import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const templatePath = path.join(root, "data", "raw", "result1_template.xlsx");
const resultPath = path.join(root, "results", "q1.json");
const outPath = path.join(root, "results", "result1.xlsx");
const verifyDir = path.join(root, "verification");

const input = await FileBlob.load(templatePath);
const workbook = await SpreadsheetFile.importXlsx(input);
const summary = await workbook.inspect({kind: "workbook,sheet,table", maxChars: 12000, tableMaxRows: 10, tableMaxCols: 8});
console.log(summary.ndjson);

if (process.argv.includes("--template")) {
  await fs.mkdir(verifyDir, {recursive: true});
  for (const sheet of workbook.worksheets.items) {
    const preview = await workbook.render({sheetName: sheet.name, autoCrop: "all", scale: 1, format: "png"});
    await fs.writeFile(path.join(verifyDir, `template_${sheet.name}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
  process.exit(0);
}

const raw = JSON.parse(await fs.readFile(resultPath, "utf8"));
if (!Array.isArray(raw.rows) || raw.rows.length !== 144) throw new Error(`q1.json rows must contain 144 entries; got ${raw.rows?.length}`);
const plan = workbook.worksheets.getItemAt(0);
const storage = workbook.worksheets.getItemAt(1);

// Preserve the template's two-sheet structure and formatting; replace only requested values.
plan.getRange("A2:B145").values = raw.rows.map(r => {
  if (!r.interval || !Number.isFinite(r.grid_kwh)) throw new Error('Invalid interval or grid energy');
  return [r.interval, r.grid_kwh];
});
const blocks = Array.isArray(raw.blocks) ? raw.blocks : [];
if (blocks.length !== 6) throw new Error('Expected six storage blocks');
storage.getRange("B2:C7").values = Array.from({length: 6}, (_, i) => {
  const r = blocks[i];
  if (!Number.isFinite(r.charge_kwh) || !Number.isFinite(r.discharge_kwh)) throw new Error('Invalid storage block');
  return [r.charge_kwh, r.discharge_kwh];
});
const s = raw.summary || {};
if (!Number.isFinite(s.initial_kwh) || !Number.isFinite(s.final_kwh)) throw new Error('Missing SOC boundary');
storage.getRange("E2:E3").values = [[s.initial_kwh], [s.final_kwh]];

await fs.mkdir(verifyDir, {recursive: true});
const check1 = await workbook.inspect({kind: "table", range: `${plan.name}!A1:B145`, include: "values,formulas", tableMaxRows: 4, tableMaxCols: 4, maxChars: 5000});
const check2 = await workbook.inspect({kind: "table", range: `${storage.name}!A1:E7`, include: "values,formulas", tableMaxRows: 10, tableMaxCols: 8, maxChars: 5000});
const errors = await workbook.inspect({kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: {useRegex: true, maxResults: 300}, summary: "final formula error scan"});
console.log(check1.ndjson); console.log(check2.ndjson); console.log(errors.ndjson);
for (const sheet of workbook.worksheets.items) {
  const preview = await workbook.render({sheetName: sheet.name, autoCrop: "all", scale: 1, format: "png"});
  await fs.writeFile(path.join(verifyDir, `xlsx_${sheet.name}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outPath);
const inspection = `${outPath}.inspect.ndjson`;
try { await fs.rename(inspection, path.join(verifyDir, 'xlsx_inspect.ndjson')); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
console.log(`saved ${outPath}`);
