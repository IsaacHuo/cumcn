function plot_q1
% Reproducible publication figures; all values come from the verified solver.
root = fileparts(fileparts(mfilename('fullpath')));
data = jsondecode(fileread(fullfile(root,'results','q1.json')));
r = data.rows;
edges = (0:144)'/6;
blue = [0.05 0.05 0.05]; green = [0.32 0.32 0.32];
orange = [0.55 0.55 0.55]; gray = [0.72 0.72 0.72];
set(groot,'defaultAxesFontName','Microsoft YaHei','defaultTextFontName','Microsoft YaHei');
fig = figure('Visible','off','Color','w','Units','centimeters','Position',[2 2 18 22]);
layout = tiledlayout(fig,4,1,'TileSpacing','compact','Padding','loose');
ax = nexttile(layout);
hold(ax,'on');
step(ax,edges,[r.load_kwh]'*6,gray,'负载');
step(ax,edges,[r.pv_kwh]'*6,orange,'光伏');
step(ax,edges,[r.grid_kwh]'*6,blue,'购电');
ylabel(ax,'功率 / kW');
ylim(ax,[0 11500]);
title(ax,'(a) 负载、光伏与购电','FontWeight','normal','HorizontalAlignment','left');
legend(ax,'Location','northeast','Orientation','horizontal','Box','off');
style(ax);
ax = nexttile(layout); hold(ax,'on');
bar(ax,edges(1:end-1)+1/12,[r.charge_kwh]'*6,1,'FaceColor','w','EdgeColor','k','DisplayName','充电');
bar(ax,edges(1:end-1)+1/12,-[r.discharge_kwh]'*6,1,'FaceColor',[.75 .75 .75],'EdgeColor','k','DisplayName','放电（负向显示）');
yline(ax,0,'Color',gray,'HandleVisibility','off');
ylabel(ax,'功率 / kW');ylim(ax,[-6000 6800]);
title(ax,'(b) 储能充放电','FontWeight','normal');
legend(ax,'Location','northoutside','Orientation','horizontal','Box','off');style(ax);
ax = nexttile(layout);hold(ax,'on');
plot(ax,edges,[r(1).soc_start_kwh;[r.soc_end_kwh]'],'Color',blue,'LineWidth',1.5);
yline(ax,1200,'--','Color',gray);
yline(ax,10800,'--','Color',gray);
text(ax,0.3,1500,'下限 1200','FontName','Microsoft YaHei','FontSize',8,'Color',gray,'VerticalAlignment','bottom');
text(ax,0.3,11100,'上限 10800','FontName','Microsoft YaHei','FontSize',8,'Color',gray,'VerticalAlignment','bottom');
ylabel(ax,'储电量 / kWh');ylim(ax,[0 12500]);
title(ax,'(c) 储电量轨迹','FontWeight','normal');style(ax);
ax = nexttile(layout);step(ax,edges,[r.price_yuan_per_kwh]',orange,'电价');
ylabel(ax,'电价 / (元/kWh)');xlabel(ax,'时刻 / h');
title(ax,'(d) 分时电价','FontWeight','normal');style(ax);
out=fullfile(root,'paper','figures');
exportgraphics(fig,fullfile(out,'q1_dispatch.pdf'),'ContentType','vector','BackgroundColor','white');
exportgraphics(fig,fullfile(out,'q1_dispatch.png'),'Resolution',300,'BackgroundColor','white');
savefig(fig,fullfile(out,'q1_dispatch.fig'));close(fig);
end

function step(ax,edges,values,color,label)
styles={'--','-.','-'}; labels={'负载','光伏','购电'}; j=find(strcmp(label,labels),1); if isempty(j), j=3; end
stairs(ax,edges,[values;values(end)],'Color','k','LineStyle',styles{j},'LineWidth',1.1,'DisplayName',label);
end

function style(ax)
set(ax,'Box','off','FontSize',9,'TickDir','out','LineWidth',0.7,'XLim',[0 24],'XTick',0:4:24,'YGrid','on','XGrid','off','GridAlpha',0.12);
end
