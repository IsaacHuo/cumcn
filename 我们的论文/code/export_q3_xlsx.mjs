import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const templatePath = path.join(root, "data", "raw", "result3_template.xlsx");
const resultPath = path.join(root, "results", "q3_export.json");
const outPath = path.join(root, "results", "result3.xlsx");
const verifyDir = path.join(root, "verification", "q3导出检查");

const finite = (value, label) => {
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`Invalid numeric value for ${label}: ${value}`);
  return value;
};
const requiredText = (value, label) => {
  if (value == null || String(value).trim() === "") throw new Error(`Missing text for ${label}`);
  return String(value);
};
const excelDate = (iso) => {
  const dateText = requiredText(iso, "date");
  const d = new Date(`${dateText}T00:00:00Z`);
  if (Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== dateText) throw new Error(`Invalid date: ${iso}`);
  return d;
};
const intervalLabel = (index) => {
  const start = index * 10;
  const end = start + 10;
  const hhmm = (mins) => `${String(Math.floor(mins / 60)).padStart(2, "0")}:${String(mins % 60).padStart(2, "0")}`;
  return `${hhmm(start)}-${hhmm(end)}`;
};
const checkVector = (value, day, key) => {
  if (!Array.isArray(value) || value.length !== 144) throw new Error(`${key} must contain 144 entries: ${day}`);
  return value.map((v, i) => finite(v, `${day}.${key}[${i}]`));
};

const raw = JSON.parse(await fs.readFile(resultPath, "utf8"));
if (!Array.isArray(raw.days) || raw.days.length !== 334) throw new Error(`q3_export.json days must contain 334 entries; got ${raw.days?.length}`);
const input = await FileBlob.load(templatePath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheets = workbook.worksheets.items;
if (sheets.length !== 4) throw new Error(`Template must contain 4 sheets; got ${sheets.length}`);
const [plan, adjusted, storage, emergency] = sheets;
const expectedNames = ["计划购电量", "调整购电量", "充放电量", "紧急购电量"];
if (sheets.map((s) => s.name).join("|") !== expectedNames.join("|")) throw new Error(`Unexpected template sheet names: ${sheets.map((s) => s.name).join(", ")}`);

const headers = ["日期\\时间", ...Array.from({ length: 144 }, (_, i) => intervalLabel(i))];
plan.getRange("A1:EQ1").values = [[...headers, "全天计划购电量", "全天总费用（计划）"]];
adjusted.getRange("A1:EQ1").values = [[...headers, "全天调整购电量", "全天总费用（含紧急购电）"]];
const planRows = [];
const adjustedRows = [];
for (const day of raw.days) {
  const date = excelDate(day.date);
  const planValues = checkVector(day.plan_kwh, day.date, "plan_kwh");
  const adjustedValues = checkVector(day.adjusted_kwh, day.date, "adjusted_kwh");
  const planTotal = finite(day.plan_total, `${day.date}.plan_total`);
  const adjustedTotal = finite(day.adjusted_total, `${day.date}.adjusted_total`);
  if (Math.abs(planTotal - planValues.reduce((a, b) => a + b, 0)) > 1e-5) throw new Error(`Plan total mismatch: ${day.date}`);
  if (Math.abs(adjustedTotal - adjustedValues.reduce((a, b) => a + b, 0)) > 1e-5) throw new Error(`Adjusted total mismatch: ${day.date}`);
  planRows.push([date, ...planValues, planTotal, finite(day.plan_cost, `${day.date}.plan_cost`)]);
  adjustedRows.push([date, ...adjustedValues, adjustedTotal, finite(day.total_cost, `${day.date}.total_cost`)]);
}
for (const sheet of [plan, adjusted]) {
  for (let row = 0; row < 334; row += 1) sheet.getRangeByIndexes(1 + row, 0, 1, 147).copyFrom(sheet.getRange("A2:EQ2"), "all");
  sheet.getRange("A2:A335").setNumberFormat("yyyy-mm-dd");
  sheet.getRange("B2:EP335").setNumberFormat("0.00");
  sheet.getRange("EQ2:EQ335").setNumberFormat("0.00");
  sheet.freezePanes.freezeRows(1);
}
plan.getRange("A2:EQ335").values = planRows;
adjusted.getRange("A2:EQ335").values = adjustedRows;

const storageRows = [];
for (const day of raw.days) {
  if (!Array.isArray(day.blocks) || day.blocks.length !== 6) throw new Error(`blocks must contain 6 entries: ${day.date}`);
  for (let i = 0; i < 6; i += 1) {
    const block = day.blocks[i];
    storageRows.push([i === 0 ? excelDate(day.date) : null, requiredText(block?.interval, `${day.date}.blocks[${i}].interval`), finite(block?.charge_kwh, `${day.date}.blocks[${i}].charge_kwh`), finite(block?.discharge_kwh, `${day.date}.blocks[${i}].discharge_kwh`), i === 0 ? "0:00" : i === 1 ? "24:00" : null, i === 0 ? finite(day.soc_start, `${day.date}.soc_start`) : i === 1 ? finite(day.soc_end, `${day.date}.soc_end`) : null]);
  }
}
for (let dayIndex = 0; dayIndex < 334; dayIndex += 1) storage.getRangeByIndexes(1 + dayIndex * 6, 0, 6, 6).copyFrom(storage.getRange("A2:F7"), "all");
storage.getRange("A2:F2005").values = storageRows;
storage.getRange("A2:A2005").setNumberFormat("yyyy-mm-dd");
storage.getRange("C2:D2005").setNumberFormat("0.00");
storage.getRange("F2:F2005").setNumberFormat("0.00");
storage.freezePanes.freezeRows(1);

const emergencyRows = [];
for (const day of raw.days) {
  if (!Array.isArray(day.emergency_intervals)) throw new Error(`emergency_intervals must be an array: ${day.date}`);
  if (day.emergency_intervals.length === 0) { emergencyRows.push([excelDate(day.date), "无", 0]); continue; }
  day.emergency_intervals.forEach((event, index) => emergencyRows.push([index === 0 ? excelDate(day.date) : null, requiredText(event?.interval, `${day.date}.emergency_intervals[${index}].interval`), finite(event?.kwh, `${day.date}.emergency_intervals[${index}].kwh`)]));
}
for (let row = 0; row < emergencyRows.length; row += 1) emergency.getRangeByIndexes(1 + row, 0, 1, 3).copyFrom(emergency.getRange("A2:C2"), "all");
const emergencyEnd = emergencyRows.length + 1;
emergency.getRange(`A2:C${emergencyEnd}`).values = emergencyRows;
emergency.getRange(`A2:A${emergencyEnd}`).setNumberFormat("yyyy-mm-dd");
emergency.getRange(`C2:C${emergencyEnd}`).setNumberFormat("0.00");
emergency.freezePanes.freezeRows(1);

await fs.mkdir(verifyDir, { recursive: true });
const inspectResults = [];
for (const [sheet, range, rows, cols] of [[plan, "A1:H8", 8, 8], [adjusted, "A1:H8", 8, 8], [storage, "A1:F8", 8, 6], [emergency, "A1:C8", 8, 3]]) inspectResults.push(await workbook.inspect({ kind: "table", range: `${sheet.name}!${range}`, include: "values,formulas", tableMaxRows: rows, tableMaxCols: cols, maxChars: 8000 }));
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 300 }, summary: "q3 final formula error scan" });
await fs.writeFile(path.join(verifyDir, "q3_xlsx_inspect.ndjson"), `${inspectResults.map((x) => x.ndjson).join("\n")}\n${errors.ndjson}\n`);
for (const [sheet, range, name] of [[plan, "A1:H8", "计划购电量.png"], [adjusted, "A1:H8", "调整购电量.png"], [storage, "A1:F8", "充放电量.png"], [emergency, "A1:C8", "紧急购电量.png"]]) { const preview = await workbook.render({ sheetName: sheet.name, range, scale: 2, format: "png" }); await fs.writeFile(path.join(verifyDir, name), new Uint8Array(await preview.arrayBuffer())); }
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outPath);
try { await fs.rename(`${outPath}.inspect.ndjson`, path.join(verifyDir, "result3_full_inspect.ndjson")); }
catch (error) { if (error.code !== "ENOENT") throw error; }
await fs.writeFile(path.join(verifyDir, "q3_xlsx_checks.json"), JSON.stringify({ days: raw.days.length, planRows: planRows.length, adjustedRows: adjustedRows.length, planColumns: planRows[0].length, adjustedColumns: adjustedRows[0].length, storageRows: storageRows.length, emergencyRows: emergencyRows.length, planIntervals: 144, errorScan: errors.ndjson }, null, 2));
console.log(`saved ${outPath}`);
