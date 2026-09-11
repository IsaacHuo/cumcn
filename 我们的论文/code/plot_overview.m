function plot_overview
% All plotted powers equal six times ten-minute energy.
root=fileparts(fileparts(mfilename('fullpath'))); out=fullfile(root,'paper','figures');
set(groot,'defaultAxesFontName','Microsoft YaHei','defaultTextFontName','Microsoft YaHei');
q=jsondecode(fileread(fullfile(root,'results','q1.json'))); r=q.rows; h=(0:144)/6;
p=[r.price_yuan_per_kwh]; ell=6*[r.load_kwh]; pv=6*[r.pv_kwh]; net=ell-pv;
f=figure('Visible','off','Color','w','Units','centimeters','Position',[2 2 18 15]);
tl=tiledlayout(f,3,1,'Padding','loose','TileSpacing','compact');
a=nexttile(tl);stairs(a,h,[p p(end)],'k-','LineWidth',1.1);
ylabel(a,'电价 / (元/kWh)');title(a,'(a) 分时电价','FontWeight','normal');style(a);
a=nexttile(tl);hold(a,'on');stairs(a,h,[ell ell(end)],'k-','LineWidth',1.1);stairs(a,h,[pv pv(end)],'k--','LineWidth',1.1);
ylabel(a,'功率 / kW');title(a,'(b) 负载与光伏','FontWeight','normal');
legend(a,{'负载','光伏'},'Location','northoutside','Orientation','horizontal','Box','off');style(a);
a=nexttile(tl);stairs(a,h,[net net(end)],'k-','LineWidth',1.1);yline(a,0,':k');
ylabel(a,'净负荷 / kW');xlabel(a,'时刻 / h');title(a,'(c) 净负荷','FontWeight','normal');style(a);
saveplot(f,out,'overview_inputs');
% Rectangles and arrows use the same axes coordinates.
f=figure('Visible','off','Color','w','Units','centimeters','Position',[2 2 18 10]);
a=axes(f,'Position',[.02 .02 .96 .96]);hold(a,'on');axis(a,[0 100 0 60]);axis(a,'off');
boxtext(a,[3 42 27 14],{'负载、光伏及电价信息','构造预测及误差情景'});
boxtext(a,[37 42 27 14],{'0:00日前优化','锁定当天原计划'});
boxtext(a,[71 42 27 14],{'6/12/18点更新','问题三/四修订计划'});
boxtext(a,[37 18 27 14],{'每十分钟储能优化','固定当前购电版本'});
boxtext(a,[71 18 27 14],{'执行当前充放电','必要时紧急补电'});
boxtext(a,[3 18 27 14],{'当前负载、光伏与价格','实际储电量'});
arr(a,[30 49],[37 49]);arr(a,[64 49],[71 49]);arr(a,[50.5 42],[50.5 32]);
plot(a,[84.5 84.5 60],[42 37 37],'k-');arr(a,[60 37],[60 32]);
arr(a,[30 25],[37 25]);arr(a,[64 25],[71 25]);
plot(a,[84.5 84.5 16.5],[18 7 7],'k-','LineWidth',.8);arr(a,[16.5 7],[16.5 18]);
text(a,50,3,'更新实际状态，进入下一个十分钟区间','HorizontalAlignment','center','FontSize',9);
saveplot(f,out,'overview_flow');
end
function boxtext(a,b,t)
rectangle(a,'Position',b,'FaceColor','w','EdgeColor','k','LineWidth',.8);
text(a,b(1)+b(3)/2,b(2)+b(4)/2,t,'HorizontalAlignment','center','VerticalAlignment','middle','FontSize',9);
end
function arr(a,p,q)
quiver(a,p(1),p(2),q(1)-p(1),q(2)-p(2),0,'Color','k','LineWidth',.8,'MaxHeadSize',.6,'AutoScale','off');
end
function style(a)
set(a,'Box','off','FontSize',9,'TickDir','out','XLim',[0 24],'XTick',0:4:24,'YGrid','on','GridAlpha',.12);a.YAxis.Exponent=0;
end
function saveplot(f,out,n)
exportgraphics(f,fullfile(out,[n '.pdf']),'ContentType','vector','BackgroundColor','white');
exportgraphics(f,fullfile(out,[n '.png']),'Resolution',300,'BackgroundColor','white');
savefig(f,fullfile(out,[n '.fig']));close(f);
end
