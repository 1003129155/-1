"""
画笔工具
"""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPainter, QPen
from .base import Tool, ToolContext


class PenTool(Tool):
    """
    画笔工具 - 自由绘制
    """
    
    id = "pen"
    
    def __init__(self):
        self.drawing = False
        self.points = []
    
    def on_press(self, pos: QPointF, button, ctx: ToolContext):
        if button == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.points = [pos]
    
    def on_move(self, pos: QPointF, ctx: ToolContext):
        if self.drawing:
            self.points.append(pos)
            
            # 在overlay的image上绘制
            painter = QPainter(ctx.overlay.image())
            pen = QPen(ctx.color, ctx.stroke_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setOpacity(ctx.opacity)
            
            # 绘制最后一段
            if len(self.points) >= 2:
                p1 = ctx.overlay.scene_to_image_pos(self.points[-2])
                p2 = ctx.overlay.scene_to_image_pos(self.points[-1])
                painter.drawLine(p1, p2)
            
            painter.end()
            
            # 标记需要更新
            ctx.overlay.mark_dirty()
    
    def on_release(self, pos: QPointF, ctx: ToolContext):
        if self.drawing:
            self.drawing = False
            
            # 保存快照
            ctx.undo.push_snapshot(ctx.overlay.image().copy())
            
            self.points = []
