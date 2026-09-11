function ax=bw_pattern_legend(fig,pos,labels,patterns)
% Two-column black-and-white texture legend, using identical rectangle code.
ax=axes(fig,'Position',pos,'XLim',[0 1],'YLim',[0 1],'Visible','off');hold(ax,'on');
drawnow;
for j=1:numel(labels)
    col=mod(j-1,2); row=floor((j-1)/2); x=.005+col*.52; y=.57-row*.48;
    bw_pattern_rect(ax,x,y,.055,.30,patterns{j});
    text(ax,x+.065,y+.15,labels{j},'FontSize',8,'Color','k','VerticalAlignment','middle');
end
end
