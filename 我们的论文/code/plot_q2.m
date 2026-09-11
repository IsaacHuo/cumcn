function plot_q2
% Reproducible publication figures for Question 2.
% Input: results/q2_report.json.  Output: paper/figures.
root = fileparts(fileparts(mfilename('fullpath')));
inputFile = fullfile(root,'results','q2_report.json');
if ~isfile(inputFile)
    error('未找到结果文件：%s',inputFile);
end
data = jsondecode(fileread(inputFile));
out = fullfile(root,'paper','figures');
if ~isfolder(out), mkdir(out); end

set(groot,'defaultAxesFontName','Microsoft YaHei', ...
    'defaultTextFontName','Microsoft YaHei');
blue = [0.05 0.05 0.05]; green = [0.32 0.32 0.32];
orange = [0.55 0.55 0.55]; red = [0.22 0.22 0.22];

% Figure 1: monthly cost summary and daily emergency electricity.
daily = structArray(data,'daily');
if ~isempty(daily)
    d = parseDates({daily.date});
    monthKey = year(d)*100 + month(d);
    [months,~,ix] = unique(monthKey,'stable');
    plan = accumarray(ix,fieldVector(daily,'plan_cost'),[],@sum,0);
    emergencyCost = accumarray(ix,fieldVector(daily,'emergency_cost'),[],@sum,0);
    monthLabels = arrayfun(@(q) sprintf('%d-%02d',floor(q/100),mod(q,100)), ...
        months,'UniformOutput',false);
    fig=figure('Visible','off','Color','w','Units','centimeters','Position',[2 2 18 14]);
    ax=axes(fig,'Position',[.10 .56 .86 .29]);hold(ax,'on');
    xlim(ax,[.5 numel(months)+.5]);ylim(ax,[0 max(plan/1e4)*1.10]);
    set(ax,'XTick',1:numel(months),'XTickLabel',2:12,'Box','off','FontSize',9);
    ylabel(ax,'费用 / 万元');xlabel(ax,'月份');drawnow;
    for j=1:numel(months)
      bw_pattern_rect(ax,j-.36,0,.32,plan(j)/1e4,'empty');
      bw_pattern_rect(ax,j+.04,0,.32,emergencyCost(j)/1e4,'diag');
    end
    bw_pattern_legend(fig,[.13 .87 .8 .12],{'计划购电费用','紧急购电费用'},{'empty','diag'});
    ax=axes(fig,'Position',[.10 .12 .86 .28]);hold(ax,'on');
    emergencyEnergy=fieldVector(daily,'emergency_total');
    bar(ax,d,emergencyEnergy,.9,'FaceColor',[.3 .3 .3],'EdgeColor','none');
    ylabel(ax,'紧急购电 / kWh');xlabel(ax,'日期');styleDate(ax,d);ax.Box='off';ax.YAxis.Exponent=0;
    exportFigure(fig,out,'q2_year');
end

% Figure 2: each selected day is exported independently for easy inclusion in text.
selected = structArray(data,'selected');
for k = 1:numel(selected)
    s = selected(k);
    n = numel(s.load_kwh);
    h = (0:n-1)/6;
    fig = figure('Visible','off','Color','w','Units','centimeters', ...
        'Position',[2 2 18 17]);
    tl = tiledlayout(fig,3,1,'TileSpacing','compact','Padding','loose');
    ax = nexttile(tl,1); hold(ax,'on');
    loadActual = rowVector(s.load_kwh); pvActual = rowVector(s.pv_kwh);
    loadForecast = rowVector(s.forecast_load_kwh); pvForecast = rowVector(s.forecast_pv_kwh);
    plot(ax,h,(loadActual-pvActual)*6,'Color',blue,'LineWidth',1.25,'DisplayName','实测净负荷');
    plot(ax,h,(loadForecast-pvForecast)*6,'--','Color',orange,'LineWidth',1.1,'Marker','o','MarkerIndices',1:12:n,'MarkerSize',3,'MarkerFaceColor','w','DisplayName','预测净负荷');
    ylabel(ax,'净负荷 / kW'); xlabel(ax,'时段 / h');
    title(ax,'净负荷预测与实测','FontWeight','normal'); legend(ax,'Location','best','Box','off');
    styleHours(ax);
    ax = nexttile(tl,2); hold(ax,'on');
    soc = rowVector(s.soc_kwh);
    hSoc = plot(ax,(0:n)/6,soc,'Color',green,'LineWidth',1.35,'DisplayName','储电量');
    ylabel(ax,'储电量 / kWh');
    xlabel(ax,'时段 / h'); title(ax,'储电量','FontWeight','normal');
    styleHours(ax); ylim(ax,[0 12000]); yline(ax,1200,':k','HandleVisibility','off'); yline(ax,10800,':k','HandleVisibility','off');
    xlim(ax,[0 24]); set(ax,'XTick',0:4:24); grid(ax,'on'); box(ax,'off');
    ax = nexttile(tl,3); hold(ax,'on'); emergency = rowVector(s.emergency_kwh);
    hEmergency = stairs(ax,[h h(end)+1/6],[emergency emergency(end)]*6,'Color',red,'LineWidth',1.15,'DisplayName','紧急购电');
    ylabel(ax,'紧急购电 / kW'); xlabel(ax,'时段 / h'); title(ax,'紧急购电','FontWeight','normal');
    styleHours(ax); ylim(ax,[0 max(1,max(emergency*6)*1.15)]);
    xlim(ax,[0 24]); set(ax,'XTick',0:4:24); grid(ax,'on'); box(ax,'off');
    exportFigure(fig,out,['q2_day_' dateToken(s.date)]);
end

% Figure 3: common-style horizontal bars; categories are explicitly labeled.
comparison = structArray(data,'comparison');
names = textVector(comparison,'name');
fig=figure('Visible','off','Color','w','Units','centimeters','Position',[2 2 19 14]);
tl=tiledlayout(fig,2,1,'TileSpacing','compact','Padding','loose');
fields={'total_cost','emergency_total'}; labels={'总费用 / 万元','紧急购电量 / 万kWh'};
for j=1:2
 ax=nexttile(tl); val=fieldVector(comparison,fields{j})/1e4;
 barh(ax,1:numel(val),val,.6,'FaceColor',[.9 .9 .9],'EdgeColor','k');
 set(ax,'YTick',1:numel(val),'YTickLabel',names,'YDir','reverse','Box','off','FontSize',9,'XGrid','on','GridAlpha',.1);
 xlabel(ax,labels{j});xlim(ax,[0 max(val)*1.16]);
 for k=1:numel(val), text(ax,val(k)+max(val)*.015,k,sprintf('%.2f',val(k)),'FontSize',8);end
end
exportFigure(fig,out,'q2_compare');

end

function a = structArray(s,name)
if ~isfield(s,name) || isempty(s.(name)), a = struct([]); return; end
a = s.(name);
end
function v = fieldVector(a,name)
if isempty(a), v = []; return; end
v = zeros(numel(a),1);
for i=1:numel(a)
    item = a(i); if iscell(a), item = a{i}; end
    if isstruct(item) && isfield(item,name) && ~isempty(item.(name)), v(i)=double(item.(name)); end
end
end
function v = rowVector(x), v = double(x(:).'); end
function v = textVector(a,name)
v = strings(1,numel(a));
for i=1:numel(a)
    item = a(i); if iscell(a), item = a{i}; end
    if isstruct(item) && isfield(item,name) && ~isempty(item.(name)), v(i)=string(item.(name)); end
end
end
function d = parseDates(x)
try
    d = datetime(string(x),'InputFormat','yyyy-MM-dd');
catch
    d = datetime(string(x));
end
end
function t = dateToken(x), t = char(string(x)); t = strrep(t,'-',''); end
function style(ax,xlimv)
set(ax,'Box','off','FontSize',9,'TickDir','out','LineWidth',0.7,'XLim',xlimv,'YGrid','on','XGrid','off','GridAlpha',0.12);
end
function styleDate(ax,d)
ax.XLim = [min(d)-days(1) max(d)+days(1)]; ax.XTick=datetime(2025,2:12,1); ax.XTickLabel=compose('%d月',2:12); ax.XGrid='off'; ax.YGrid='on'; ax.FontSize=9;
end
function styleHours(ax)
xlim(ax,[0 24]); set(ax,'XTick',0:4:24,'FontSize',9,'Box','off','TickDir','out','LineWidth',0.7,'YGrid','on','GridAlpha',0.12);
end
function exportFigure(fig,out,name)
exportgraphics(fig,fullfile(out,[name '.pdf']),'ContentType','vector','BackgroundColor','white');
exportgraphics(fig,fullfile(out,[name '.png']),'Resolution',300,'BackgroundColor','white');
savefig(fig,fullfile(out,[name '.fig'])); close(fig);
end
