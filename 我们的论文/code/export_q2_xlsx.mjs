import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const templatePath = path.join(root, "data", "raw", "result2_template.xlsx");
const resultPath = path.join(root, "results", "q2_export.json");
const outPath = path.join(root, "results", "result2.xlsx");
const verifyDir = path.join(root, "verification");

const finite = (value) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`Invalid numeric value: ${value}`);
  return value;
};
const text = (value, fallback = "") => value == null ? fallback : String(value);
const excelDate = (iso) => {
  const d = new Date(`${text(iso)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) throw new Error(`Invalid date: ${iso}`);
  return d;
};
const intervalLabel = (index) => {
  const start = index * 10;
  const end = start + 10;
  const hhmm = (mins) => `${String(Math.floor(mins / 60)).padStart(2, "0")}:${String(mins % 60).padStart(2, "0")}`;
  return `${hhmm(start)}-${hhmm(end)}`;
};

const input = await FileBlob.load(templatePath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheets = workbook.worksheets.items;
if (sheets.length !== 3) throw new Error(`Template must contain 3 sheets; got ${sheets.length}`);
const [plan, storage, emergency] = sheets;
const raw = JSON.parse(await fs.readFile(resultPath, "utf8"));
if (!Array.isArray(raw.days) || raw.days.length !== 334) throw new Error(`q2_export.json days must contain 334 entries; got ${raw.days?.length}`);

// Plan table: one row per day, with 144 ten-minute columns and two summaries.
plan.getRange("A1:EQ1").values = [["日期\\时间", ...Array.from({ length: 144 }, (_, i) => intervalLabel(i)), "全天计划购电量", "全天总费用（计划+紧急）"]];
const planRows = raw.days.map((day) => {
  const values = Array.isArray(day.plan_kwh) ? day.plan_kwh : [];
  if (values.length !== 144) throw new Error(`Expected 144 intervals: ${day.date}`);
  const energy = Array.from({ length: 144 }, (_, i) => finite(values[i]));
  const planTotal = finite(day.plan_total);
  if (Math.abs(planTotal - energy.reduce((a, b) => a + b, 0)) > 1e-5) throw new Error('Plan total mismatch');
  return [excelDate(day.date), ...energy, planTotal, finite(day.total_cost)];
});
plan.getRange("A2:EQ335").values = planRows;
plan.getRange("A2:A335").setNumberFormat("yyyy-mm-dd");
plan.getRange("B2:EP335").setNumberFormat("0.00");
plan.getRange("EQ2:EQ335").setNumberFormat("0.00");
plan.freezePanes.freezeRows(1);

// Storage table: six four-hour records per day. The first two rows carry the
// 0:00/start and 24:00/end boundary values, as requested by the template.
const storageRows = [];
for (const day of raw.days) {
  const blocks = Array.isArray(day.blocks) ? day.blocks : [];
  if (blocks.length !== 6) throw new Error(`Expected six storage blocks: ${day.date}`);
  for (let i = 0; i < 6; i += 1) {
    const block = blocks[i];
    storageRows.push([
      i === 0 ? excelDate(day.date) : null,
      text(block.interval),
      finite(block.charge_kwh),
      finite(block.discharge_kwh),
      i === 0 ? "0:00" : i === 1 ? "24:00" : null,
      i === 0 ? finite(day.soc_start) : i === 1 ? finite(day.soc_end) : null,
    ]);
  }
}
// Copy the template's six-row formatting pattern before replacing its values.
const storageBody = storage.getRange("A2:F2005");
for (let dayIndex = 0; dayIndex < 334; dayIndex += 1) {
  storage.getRangeByIndexes(1 + dayIndex * 6, 0, 6, 6).copyFrom(storage.getRange("A2:F7"), "all");
}
storageBody.values = storageRows;
storage.getRange("A2:A2005").setNumberFormat("yyyy-mm-dd");
storage.getRange("C2:D2005").setNumberFormat("0.00");
storage.getRange("F2:F2005").setNumberFormat("0.00");
storage.freezePanes.freezeRows(1);

// Emergency table: retain every day, even when no emergency purchase occurs.
const emergencyRows = [];
for (const day of raw.days) {
  const events = Array.isArray(day.emergency_intervals) ? day.emergency_intervals : [];
  if (events.length === 0) {
    emergencyRows.push([excelDate(day.date), "无", 0]);
    continue;
  }
  events.forEach((event, index) => emergencyRows.push([
    index === 0 ? excelDate(day.date) : null,
    text(event.interval, "无"),
    finite(event.kwh),
  ]));
}
const emergencyEnd = emergencyRows.length + 1;
const emergencyBody = emergency.getRange(`A2:C${emergencyEnd}`);
for (let rowIndex = 0; rowIndex < emergencyRows.length; rowIndex += 1) {
  emergency.getRangeByIndexes(1 + rowIndex, 0, 1, 3).copyFrom(emergency.getRange("A2:C2"), "all");
}
emergencyBody.values = emergencyRows;
emergency.getRange(`A2:A${emergencyEnd}`).setNumberFormat("yyyy-mm-dd");
emergency.getRange(`C2:C${emergencyEnd}`).setNumberFormat("0.00");
emergency.freezePanes.freezeRows(1);

await fs.mkdir(verifyDir, { recursive: true });
const inspectPlan = await workbook.inspect({ kind: "table", range: `${plan.name}!A1:H8`, include: "values,formulas", tableMaxRows: 8, tableMaxCols: 8, maxChars: 8000 });
const inspectStorage = await workbook.inspect({ kind: "table", range: `${storage.name}!A1:F8`, include: "values,formulas", tableMaxRows: 8, tableMaxCols: 6, maxChars: 8000 });
const inspectEmergency = await workbook.inspect({ kind: "table", range: `${emergency.name}!A1:C8`, include: "values,formulas", tableMaxRows: 8, tableMaxCols: 3, maxChars: 8000 });
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 300 }, summary: "q2 final formula error scan" });
console.log(inspectPlan.ndjson); console.log(inspectStorage.ndjson); console.log(inspectEmergency.ndjson); console.log(errors.ndjson);
await fs.writeFile(path.join(verifyDir, "q2_xlsx_inspect.ndjson"), `${inspectPlan.ndjson}\n${inspectStorage.ndjson}\n${inspectEmergency.ndjson}\n${errors.ndjson}\n`);
for (const [sheet, range, name] of [[plan, "A1:H8", "q2_xlsx_plan.png"], [storage, "A1:F8", "q2_xlsx_storage.png"], [emergency, "A1:C8", "q2_xlsx_emergency.png"]]) {
  const preview = await workbook.render({ sheetName: sheet.name, range, scale: 2, format: "png" });
  await fs.writeFile(path.join(verifyDir, name), new Uint8Array(await preview.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outPath);
const checks = {
  days: raw.days.length,
  planRows: planRows.length,
  planColumns: planRows[0].length,
  storageRows: storageRows.length,
  emergencyRows: emergencyRows.length,
  planIntervals: 144,
  errorScan: errors.ndjson,
};
await fs.writeFile(path.join(verifyDir, "q2_xlsx_checks.json"), JSON.stringify(checks, null, 2));
console.log(`saved ${outPath}`);
