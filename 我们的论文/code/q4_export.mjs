import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const outdir=path.join(root,'verification','q4','workbooks');await fs.mkdir(outdir,{recursive:true});
const date=x=>new Date(`${x}T00:00:00Z`);
const clock=m=>`${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;
const labels=Array.from({length:144},(_,i)=>`${clock(i*10)}-${clock((i+1)*10)}`);
for(const [variant,name] of [['q2','result4-2'],['main','result4-3']]){
 const data=JSON.parse(await fs.readFile(path.join(root,'results','q4',`${variant}_export.json`),'utf8'));
 if(data.days.length!==334)throw Error('Expected 334 days');
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root,'data','raw',`${name}_template.xlsx`)));
 const sheets=wb.worksheets.items;const [plan]=sheets;const adjusted=variant==='main'?sheets[1]:null;
 const storage=sheets.at(-2),emergency=sheets.at(-1);
 for(const [s,field,total,cost] of [[plan,'plan_kwh','plan_total',variant==='q2'?'total_cost':'plan_cost'],...(adjusted?[[adjusted,'adjusted_kwh','adjusted_total','total_cost']]:[])]){
  s.getRange('A1:EQ1').values=[['日期\\时间',...labels,field==='plan_kwh'?'全天计划购电量':'全天调整购电量',cost==='plan_cost'?'原计划金额（元）':'最终总费用（元）']];
  for(let i=0;i<334;i++)s.getRangeByIndexes(i+1,0,1,147).copyFrom(s.getRange('A2:EQ2'),'all');
  const rows=data.days.map(d=>{
   if(d[field].length!==144||d[field].some(x=>!Number.isFinite(x)))throw Error(`Invalid ${d.date}`);
   if(Math.abs(d[field].reduce((a,b)=>a+b,0)-d[total])>1e-5)throw Error('Total mismatch');
   return [date(d.date),...d[field],d[total],d[cost]];
  });
  s.getRange('A2:EQ335').values=rows;
  s.getRange('A2:A335').setNumberFormat('yyyy-mm-dd');s.getRange('B2:EQ335').setNumberFormat('0.0000');
  // The delivered quantity total remains auditable from its 144 entries.
  s.getRange('EP2:EP335').formulas=rows.map((_,i)=>[`=SUM(B${i+2}:EO${i+2})`]);
  s.freezePanes.freezeRows(1);
 }
 const storageRows=[];
 for(let k=0;k<334;k++){
  const d=data.days[k];storage.getRangeByIndexes(1+6*k,0,6,6).copyFrom(storage.getRange('A2:F7'),'all');
  d.blocks.forEach((b,i)=>storageRows.push([i===0?date(d.date):null,b.interval,b.charge_kwh,b.discharge_kwh,i===0?'0:00':i===1?'24:00':null,i===0?d.soc_start:i===1?d.soc_end:null]));
 }
 storage.getRange('A2:F2005').values=storageRows;storage.getRange('A2:A2005').setNumberFormat('yyyy-mm-dd');
 storage.getRange('C2:D2005').setNumberFormat('0.0000');storage.getRange('F2:F2005').setNumberFormat('0.0000');storage.freezePanes.freezeRows(1);
 const erows=[];
 for(const d of data.days){
  const events=d.emergency_intervals.length?d.emergency_intervals:[{interval:'无',kwh:0}];
  if(Math.abs(events.reduce((a,b)=>a+b.kwh,0)-d.emergency_total)>0.0015)throw Error('Emergency total mismatch');
  events.forEach((e,i)=>erows.push([i===0?date(d.date):null,e.interval,e.kwh]));
 }
 for(let i=0;i<erows.length;i++)emergency.getRangeByIndexes(i+1,0,1,3).copyFrom(emergency.getRange('A2:C2'),'all');
 emergency.getRange(`A2:C${erows.length+1}`).values=erows;emergency.getRange(`A2:A${erows.length+1}`).setNumberFormat('yyyy-mm-dd');
 emergency.getRange(`C2:C${erows.length+1}`).setNumberFormat('0.0000');emergency.freezePanes.freezeRows(1);
 const inspections=[];
 for(const s of sheets){
  const range=s===storage?'A1:F8':s===emergency?'A1:C8':'A1:H6';
  inspections.push((await wb.inspect({kind:'table',range:`${s.name}!${range}`,include:'values,formulas',tableMaxRows:8,tableMaxCols:8,maxChars:2500})).ndjson);
  const preview=await wb.render({sheetName:s.name,range,scale:1.5,format:'png'});
  await fs.writeFile(path.join(outdir,`${name}_${s.name}.png`),new Uint8Array(await preview.arrayBuffer()));
 }
 inspections.push((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20}})).ndjson);
 await fs.writeFile(path.join(outdir,`${name}_inspect.ndjson`),inspections.join('\n'));
 await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(root,'results',`${name}.xlsx`));
 console.log(`${name}: ${data.days.length} days, ${erows.length} emergency rows`);
}
