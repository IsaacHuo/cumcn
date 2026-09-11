function bw_pattern_rect(ax,x,y,w,h,pattern)
% White rectangle and physically scaled, strictly clipped vector texture.
% Call after fixing axis limits and layout. No texture extends past its box.
if w<=0 || h<=0, return; end
rectangle(ax,'Position',[x y w h],'FaceColor','w','EdgeColor','k', ...
    'LineWidth',.55,'HandleVisibility','off');
if strcmp(pattern,'empty'), return; end
pos=getpixelposition(ax,true); sx=pos(3)/diff(ax.XLim); sy=pos(4)/diff(ax.YLim);
W=w*sx; H=h*sy; gap=10;
if strcmp(pattern,'dot')
    xx=gap/2:gap:W; yy=gap/2:gap:H;
    if isempty(xx), xx=W/2; end
    if isempty(yy), yy=H/2; end
    [X,Y]=meshgrid(xx,yy);
    line(ax,x+X(:)/sx,y+Y(:)/sy,'LineStyle','none','Marker','.', ...
        'MarkerSize',2.5,'Color','k','HandleVisibility','off');
    return
end
directions=1;
if strcmp(pattern,'back'), directions=-1; end
if strcmp(pattern,'cross'), directions=[1 -1]; end
for direction=directions
    for b=-W:gap*sqrt(2):H
        P=[0 b; W W+b; -b 0; H-b H];
        P=P(P(:,1)>=-1e-9 & P(:,1)<=W+1e-9 & P(:,2)>=-1e-9 & P(:,2)<=H+1e-9,:);
        P=unique(P,'rows','stable');
        if size(P,1)<2, continue; end
        P=P([1 end],:);
        if direction<0, P(:,2)=H-P(:,2); end
        line(ax,x+P(:,1)/sx,y+P(:,2)/sy,'Color','k','LineWidth',.35,'HandleVisibility','off');
    end
end
end
