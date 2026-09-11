function verify_bw_figures
% Check source FIG objects, not just rendered colors.
root=fileparts(fileparts(mfilename('fullpath')));out=fullfile(root,'paper','figures');
files=dir(fullfile(out,'*.fig')); count=0;
for k=1:numel(files)
 f=openfig(fullfile(out,files(k).name),'invisible');objs=findall(f);
 for j=1:numel(objs)
  for prop={'Color','FaceColor','EdgeColor','XColor','YColor'}
   if ~isprop(objs(j),prop{1}),continue;end
   v=get(objs(j),prop{1});
   if isnumeric(v) && numel(v)==3
    assert(max(v)-min(v)<1e-10,['Non-monochrome object in ' files(k).name]);
   end
  end
 end
 close(f);count=count+1;
end
% Verify energy-to-power conversion of the new input graphic.
q=jsondecode(fileread(fullfile(root,'results','q1.json')));
f=openfig(fullfile(out,'overview_inputs.fig'),'invisible');lines=findall(f,'Type','Stair');
targets={6*[q.rows.load_kwh],6*[q.rows.pv_kwh],[q.rows.price_yuan_per_kwh]};
for j=1:numel(targets)
 v=[targets{j} targets{j}(end)]; found=false;
 for i=1:numel(lines)
  y=lines(i).YData; if numel(y)==numel(v)&&max(abs(y(:)-v(:)))<1e-7,found=true;end
 end
 assert(found,'Input figure does not match source data');
end
close(f);
for question=2:3
 q=jsondecode(fileread(fullfile(root,'results',sprintf('q%d_report.json',question))));
 for j=1:numel(q.selected)
  s=q.selected(j);token=strrep(s.date,'-','');
  f=openfig(fullfile(out,sprintf('q%d_day_%s.fig',question,token)),'invisible');
  assertSeries(f,s.soc_kwh);
  em=6*s.emergency_kwh(:);assertSeries(f,[em;em(end)]);
  if question==2
   assertSeries(f,6*(s.load_kwh(:)-s.pv_kwh(:)));
   assertSeries(f,6*(s.forecast_load_kwh(:)-s.forecast_pv_kwh(:)));
  else
   assertSeries(f,6*s.pv_kwh(:));
   p=6*s.plan_kwh(:);assertSeries(f,[p;p(end)]);
   p=6*s.adjusted_kwh(:);assertSeries(f,[p;p(end)]);
  end
  close(f);
 end
end
assert(count==15,'Unexpected figure inventory');
fid=fopen(fullfile(root,'verification','paper_revision','matlab_checks.json'),'w');
fprintf(fid,'{"passed":true,"monochrome_figures":%d,"input_units_checked":true,"representative_days_checked":8}',count);fclose(fid);
end
function assertSeries(f,target)
target=target(:);objects=findall(f);found=false;
for i=1:numel(objects)
 if ~isprop(objects(i),'YData'),continue;end
 y=get(objects(i),'YData');
 if isnumeric(y)&&numel(y)==numel(target)&&all(isfinite(y(:)))&&max(abs(y(:)-target))<1e-7,found=true;break;end
end
assert(found,'Representative figure does not match its source series');
end
