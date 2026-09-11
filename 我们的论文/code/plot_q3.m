function plot_q3
% Reproducible publication figures for Question 3.
% Input: results/q3_report.json.  Output: paper/figures.
root = fileparts(fileparts(mfilename('fullpath')));
inputFile = fullfile(root,'results','q3_report.json');
if ~isfile(inputFile)
    error('未找到结果文件：%s',inputFile);
end
data = jsondecode(fileread(inputFile));
out = fullfile(root,'paper','figures');
if ~isfolder(out), mkdir(out); end

set(groot,'defaultAxesFontName','Microsoft YaHei', ...
    'defaultTextFontName','Microsoft YaHei');
black = [0.05 0.05 0.05]; dark = [0.22 0.22 0.22];
mid = [0.48 0.48 0.48]; light = [0.72 0.72 0.72];

% Figure 1: labeled horizontal bars, one neutral fill for every strategy.
comparison=structArray(data,'comparison');
fig=figure('Visible','off','Color','w','Units','centimeters','Position',[2 2 19 17]);
tl=tiledlayout(fig,2,1,'Padding','loose','TileSpacing','compact');
names=textVector(comparison,'name'); fields={'total_cost','emergency_total'};
units={'总费用 / 万元','紧急购电量 / 万kWh'};
for j=1:2
 ax=nexttile(tl);val=fieldVector(comparison,fields{j})/1e4;
 barh(ax,1:numel(val),val,.65,'FaceColor',[.92 .92 .92],'EdgeColor','k','LineWidth',.6);
 set(ax,'YTick',1:numel(val),'YTickLabel',names,'YDir','reverse','FontSize',8,'Box','off');
 xlim(ax,[0 max(val)*1.13]);xlabel(ax,units{j});ax.XGrid='on';ax.GridAlpha=.1;
 for k=1:numel(val), text(ax,val(k)+max(val)*.01,k,sprintf('%.2f',val(k)),'FontSize',8);end
end
exportFigure(fig,out,'q3_compare');

% Figure 2: monthly cost composition for the primary daily records.
daily = structArray(data,'daily');
if ~isempty(daily)
    d = parseDates({daily.date});
    monthKey = year(d)*100 + month(d);
    [months,~,ix] = unique(monthKey,'stable');
    netPlan = accumarray(ix,fieldVector(daily,'plan_cost') - fieldVector(daily,'refund'),[],@sum,0);
    penalty = accumarray(ix,fieldVector(daily,'penalty'),[],@sum,0);
    extra = accumarray(ix,fieldVector(daily,'extra_cost'),[],@sum,0);
    emergency = accumarray(ix,fieldVector(daily,'emergency_cost'),[],@sum,0);
    labels = arrayfun(@(q) sprintf('%d-%02d',floor(q/100),mod(q,100)), ...
        months,'UniformOutput',false);
    fig=figure('Visible','off','Color','w','Units','centimeters','Position',[2 2 19 12]);
    ax=axes(fig,'Position',[.09 .14 .88 .65]);hold(ax,'on');
    values=[netPlan penalty extra emergency]/1e4;
    xlim(ax,[.5 numel(months)+.5]);ylim(ax,[0 max(sum(values,2))*1.06]);
    set(ax,'XTick',1:numel(months),'XTickLabel',2:12,'Box','off','FontSize',9);
    xlabel(ax,'月份');ylabel(ax,'费用 / 万元');
    drawnow; patterns={'empty','diag','back','dot'};
    for i=1:size(values,1)
        base=0;
        for j=1:4
            bw_pattern_rect(ax,i-.36,base,.72,values(i,j),patterns{j});base=base+values(i,j);
        end
    end
    bw_pattern_legend(fig,[.11 .83 .84 .15],{'净基础费用（原计划减退款）','违约费用','新增费用','紧急购电费用'},patterns);
    exportFigure(fig,out,'q3_year');
end

% Selected days: five aligned panels plus a separate unused-supply panel.
selected=structArray(data,'selected');
for k=1:numel(selected)
 s=selected(k);n=numel(s.plan_kwh);h=(0:n-1)/6;edge=0:1/6:24;
 fig=figure('Visible','off','Color','w','Units','centimeters','Position',[2 2 19 25]);
 tl=tiledlayout(fig,6,1,'TileSpacing','compact','Padding','loose');
 ax=nexttile(tl);hold(ax,'on'); actual=rowVector(s.pv_kwh)*6;
 plot(ax,h,actual,'k-','LineWidth',1.2,'DisplayName','实测');
 F=matrixRows(s.forecast_pv_versions,n);styles={'--',':','-.','--'};marks={'none','o','s','^'};
 for j=1:4
  v=F(j,:)*6;v(h<(j-1)*6)=nan;
  plot(ax,h,v,'Color','k','LineStyle',styles{j},'Marker',marks{j},'MarkerIndices',1:12:n, ...
    'MarkerSize',3,'MarkerFaceColor','w','LineWidth',.75,'DisplayName',sprintf('%d点预报',(j-1)*6));
 end
 ylabel(ax,'光伏 / kW');legend(ax,'Location','northoutside','Orientation','horizontal','NumColumns',5,'FontSize',8,'Box','off');styleHours(ax);
 ax=nexttile(tl);hold(ax,'on');
 stairs(ax,edge,[rowVector(s.plan_kwh) s.plan_kwh(end)]*6,'k:','LineWidth',1,'DisplayName','原计划');
 stairs(ax,edge,[rowVector(s.adjusted_kwh) s.adjusted_kwh(end)]*6,'k-','LineWidth',1.1,'DisplayName','最终交付');
 V=matrixRows(s.plan_versions,n);
 for j=2:4
  v=V(j,:)*6;v(h<(j-1)*6)=nan;
  plot(ax,h,v,'Color','k','LineStyle',styles{j},'Marker',marks{j},'MarkerIndices',1:12:n, ...
    'MarkerSize',3,'MarkerFaceColor','w','LineWidth',.7,'DisplayName',sprintf('%d点版本',(j-1)*6));
 end
 ylabel(ax,'购电 / kW');legend(ax,'Location','northoutside','Orientation','horizontal','NumColumns',5,'FontSize',8,'Box','off');styleHours(ax);
 ax=nexttile(tl);plot(ax,edge,rowVector(s.soc_kwh),'k-','LineWidth',1.1);hold(ax,'on');
 yline(ax,1200,':k');yline(ax,10800,':k');ylabel(ax,'储电量 / kWh');ylim(ax,[0 12000]);styleHours(ax);
 ax=nexttile(tl);em=rowVector(s.emergency_kwh)*6;
 stairs(ax,edge,[em em(end)],'k-','LineWidth',.9);ylabel(ax,{'紧急购电','功率 / kW'});ylim(ax,[0 max(1,max(em)*1.2)]);styleHours(ax);
 ax=nexttile(tl);hold(ax,'on');c=rowVector(s.charge_kwh)*6;d=rowVector(s.discharge_kwh)*6;
 bar(ax,h+1/12,c,1,'FaceColor','w','EdgeColor','k','LineWidth',.35);
 bar(ax,h+1/12,-d,1,'FaceColor',[.75 .75 .75],'EdgeColor','k','LineWidth',.35);
 yline(ax,0,'k-');ylabel(ax,{'充正 / 放负','功率 / kW'});ylim(ax,[-5500 5500]);styleHours(ax);
 ax=nexttile(tl);u=rowVector(s.unused_kwh)*6;
 stairs(ax,edge,[u u(end)],'k-','LineWidth',.9);ylabel(ax,{'未利用供给','功率 / kW'});xlabel(ax,'时刻 / h');styleHours(ax);
 exportFigure(fig,out,['q3_day_' dateToken(s.date)]);
end
end

function a = structArray(s,name)
if ~isfield(s,name) || isempty(s.(name)), a = struct([]); return; end
a = s.(name);
end
function v = fieldVector(a,name)
v=zeros(numel(a),1);
for i=1:numel(a)
    item=a(i); if iscell(a), item=a{i}; end
    if isstruct(item) && isfield(item,name) && ~isempty(item.(name)), v(i)=double(item.(name)); end
end
end
function v = rowVector(x), v=double(x(:).'); end
function m = matrixRows(x,n)
if isempty(x), m=nan(0,n); return; end
m=double(x); if isvector(m), m=m(:).'; end
if size(m,2)~=n && size(m,1)==n, m=m.'; end
if size(m,2)<n, m(:,end+1:n)=nan; elseif size(m,2)>n, m=m(:,1:n); end
end
function v = textVector(a,name)
v=strings(1,numel(a));
for i=1:numel(a)
    item=a(i); if iscell(a), item=a{i}; end
    if isstruct(item) && isfield(item,name) && ~isempty(item.(name)), v(i)=string(item.(name)); end
end
end
function d = parseDates(x)
try
    d=datetime(string(x),'InputFormat','yyyy-MM-dd');
catch
    d=datetime(string(x));
end
end
function t = dateToken(x), t=char(string(x)); t=strrep(t,'-',''); end
function style(ax,xlimv)
set(ax,'Box','off','FontSize',9,'TickDir','out','LineWidth',0.7,'XLim',xlimv, ...
    'YGrid','on','XGrid','off','GridAlpha',0.12);
setAxisExponents(ax,0);
end
function styleHours(ax)
xlim(ax,[0 24]); set(ax,'XTick',0:4:24,'FontSize',9,'Box','off','TickDir','out', ...
    'LineWidth',0.7,'YGrid','on','GridAlpha',0.12); setAxisExponents(ax,0);
end
function styleHorizontal(ax,ylimv)
set(ax,'Box','off','TickDir','out','LineWidth',0.7,'YLim',ylimv, ...
    'XGrid','on','YGrid','off','GridAlpha',0.12); ax.XAxis.Exponent=0;
end
function setAxisExponents(ax,value)
for i=1:numel(ax.YAxis)
    ax.YAxis(i).Exponent=value;
end
end
function exportFigure(fig,out,name)
exportgraphics(fig,fullfile(out,[name '.pdf']),'ContentType','vector','BackgroundColor','white');
exportgraphics(fig,fullfile(out,[name '.png']),'Resolution',300,'BackgroundColor','white');
savefig(fig,fullfile(out,[name '.fig'])); close(fig);
end
