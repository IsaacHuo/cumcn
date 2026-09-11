function q4_figures
% All figures read the same verified report used for the paper and workbook.
root=fileparts(fileparts(mfilename('fullpath')));out=fullfile(root,'paper','figures');
d=jsondecode(fileread(fullfile(root,'results','q4_report.json')));
set(groot,'defaultAxesFontName','Microsoft YaHei','defaultTextFontName','Microsoft YaHei');
names=string({d.comparison.name});vars=string({d.comparison.variant});
f=newfig(19,18);tl=tiledlayout(f,2,1,'TileSpacing','compact','Padding','loose');
fields={'total_cost','emergency_total'};units={'实际总费用 / 万元','紧急购电量 / 万kWh'};
for j=1:2
 ax=nexttile(tl);v=[d.comparison.(fields{j})]/1e4;
 hold(ax,'on');
 for k=1:numel(v)
  shade=.87;if vars(k)=="q2"||vars(k)=="main",shade=.45;end
  barh(ax,k,v(k),.63,'FaceColor',shade*ones(1,3),'EdgeColor','k','LineWidth',.6);
 end
 set(ax,'YTick',1:numel(v),'YTickLabel',names,'YDir','reverse','FontSize',8,'Box','off');
 xlim(ax,[0 max(v)*1.16]);xlabel(ax,units{j});ax.XGrid='on';ax.GridAlpha=.12;
 for k=1:numel(v),text(ax,v(k)+max(v)*.012,k,sprintf('%.2f',v(k)),'FontSize',8);end
end
saveall(f,out,'q4_compare');

f=newfig(19,12);tl=tiledlayout(f,2,1,'TileSpacing','compact','Padding','compact');
ax=nexttile(tl);monthly=zeros(11,4);
for k=1:numel(d.daily)
 r=d.daily(k);m=str2double(r.date(6:7))-1;
 monthly(m,:)=monthly(m,:)+[r.plan_cost-r.refund,r.penalty,r.extra_cost,r.emergency_cost]/1e4;
end
b=bar(ax,2:12,monthly,'stacked','BarWidth',.7,'EdgeColor','k','LineWidth',.5);
gray=[.96 .72 .48 .20];for j=1:4,b(j).FaceColor=gray(j)*ones(1,3);end
legend(ax,{'净基础费用','违约费','增购费','紧急费'},'Location','northoutside','Orientation','horizontal','Box','off');
xlabel(ax,'月份');ylabel(ax,'费用 / 万元');xticks(ax,2:12);ax.Box='off';
ax=nexttile(tl);t=datetime(string({d.daily.date}),'InputFormat','yyyy-MM-dd');
stem(ax,t,[d.daily.emergency_total],'Marker','none','Color',[.25 .25 .25],'LineWidth',.7);
ylabel(ax,'紧急购电量 / kWh');xlabel(ax,'日期');ax.Box='off';ax.XLim=[t(1) t(end)];xtickformat(ax,'MM-dd');
saveall(f,out,'q4_year');

for k=1:numel(d.selected)
 s=d.selected(k);q=d.selected_q2(k);x=(0:143)'/6;xe=(0:144)'/6;
 f=newfig(19,22);tl=tiledlayout(f,5,1,'TileSpacing','compact','Padding','compact');
 ax=nexttile(tl);hold(ax,'on');
 fill(ax,[x;flipud(x)],[s.price_actual(:);flipud(s.forecast_price(:))],[.88 .88 .88],'EdgeColor','none','HandleVisibility','off');
 plot(ax,x,s.price_actual,'k-','LineWidth',.8);plot(ax,x,s.forecast_price,'k--','LineWidth',1.0);
 ylabel(ax,'电价 / (元/kWh)');legend(ax,{'实际价格','日前预测'},'Location','northwest','Orientation','horizontal','Box','off');
 ax=nexttile(tl);stairs(ax,xe,[s.plan_kwh(:);s.plan_kwh(end)],'k--','LineWidth',.85);hold(ax,'on');
 stairs(ax,xe,[s.adjusted_kwh(:);s.adjusted_kwh(end)],'k-','LineWidth',.85);
 ylabel(ax,'普通购电量 / kWh');legend(ax,{'0点原计划','最终有效量'},'Location','northwest','Orientation','horizontal','Box','off');
 ax=nexttile(tl);plot(ax,xe,s.soc_kwh,'k-','LineWidth',1);hold(ax,'on');
 plot(ax,xe,q.soc_kwh,'k--','LineWidth',.8,'Marker','o','MarkerIndices',1:18:145,'MarkerSize',3,'MarkerFaceColor','w');
 yline(ax,1200,':','Color',[.55 .55 .55],'HandleVisibility','off');yline(ax,10800,':','Color',[.55 .55 .55],'HandleVisibility','off');
 ylim(ax,[0 12000]);ylabel(ax,'储电量 / kWh');legend(ax,{'允许购电调整','不允许购电调整'},'Location','northwest','Orientation','horizontal','Box','off');
 ax=nexttile(tl);hold(ax,'on');bar(ax,x,s.charge_kwh,1,'FaceColor',[.96 .96 .96],'EdgeColor',[.25 .25 .25],'LineWidth',.3);
 bar(ax,x,-s.discharge_kwh,1,'FaceColor',[.45 .45 .45],'EdgeColor',[.25 .25 .25],'LineWidth',.3);
 ylabel(ax,'充放电量 / kWh');legend(ax,{'充电','放电（负向）'},'Location','northwest','Orientation','horizontal','Box','off');
 ax=nexttile(tl);area(ax,x,s.emergency_kwh,'FaceColor',[.7 .7 .7],'EdgeColor','k','LineWidth',.65);hold(ax,'on');
 stairs(ax,x,q.emergency_kwh,'k--','LineWidth',.75);ylabel(ax,'紧急购电量 / kWh');xlabel(ax,'时刻 / h');
 legend(ax,{'允许购电调整','不允许购电调整'},'Location','northwest','Orientation','horizontal','Box','off');
 axesList=findall(f,'Type','axes');for a=axesList',xlim(a,[0 24]);xticks(a,0:4:24);a.Box='off';a.FontSize=8;end
 saveall(f,out,['q4_day_' strrep(s.date,'-','')]);
end

e=jsondecode(fileread(fullfile(root,'results','forecast_diagnostics.json')));
f=newfig(19,12);tl=tiledlayout(f,1,2,'TileSpacing','compact','Padding','loose');
ax=nexttile(tl);hours={'0','6','12','18'};v=zeros(4,4);
for i=1:4,for j=1:4,v(i,j)=e.q3_lead.(['x' hours{i}]).(['x' num2str(j-1)]).mae;end,end
styles={'-o','--s','-.^',':d'};hold(ax,'on');
for i=1:4,plot(ax,1:4,v(i,:),['k' styles{i}],'LineWidth',1,'MarkerSize',4,'MarkerFaceColor','w');end
xticks(ax,1:4);xticklabels(ax,{'1–6','7–12','13–18','19–24'});xlabel(ax,'预测提前量 / h');ylabel(ax,'MAE / kWh');
legend(ax,{'0点','6点','12点','18点'},'Location','northwest','Box','off');ax.Box='off';
ax=nexttile(tl);v=zeros(3,2);hours={'6','12','18'};
for i=1:3,v(i,:)=[e.q3_overlap.(['x' hours{i}]).old.mae,e.q3_overlap.(['x' hours{i}]).new.mae];end
b=bar(ax,v,'grouped','EdgeColor','k');b(1).FaceColor=[.95 .95 .95];b(2).FaceColor=[.48 .48 .48];
xticks(ax,1:3);xticklabels(ax,{'6点','12点','18点'});xlabel(ax,'更新时刻');ylabel(ax,'共同目标区间 MAE / kWh');
legend(ax,{'0点预报','更新预报'},'Location','northoutside','Box','off');ax.Box='off';
saveall(f,out,'forecast_errors');
end

function f=newfig(w,h)
f=figure('Visible','off','Color','w','Units','centimeters','Position',[2 2 w h]);
end
function saveall(f,out,name)
drawnow;savefig(f,fullfile(out,[name '.fig']));exportgraphics(f,fullfile(out,[name '.pdf']),'ContentType','vector');
exportgraphics(f,fullfile(out,[name '.png']),'Resolution',180);close(f);
end
