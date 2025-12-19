"""
高亮笔工具
"""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPainter, QPen, QColor
from .base import Tool, ToolContext


class HighlighterTool(Tool):
    """
    高亮笔工具 - 类似画笔但半透明
    """
    
    id = "highlighter"
    
    def __init__(self):
        self.drawing = False
        self.points = []
    
    def on_press(self, pos: QPointF, button, ctx: ToolContext):
        if button == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.points = [pos]
            print(f"[HighlighterTool] 开始高亮: {pos}")
    
    def on_move(self, pos: QPointF, ctx: ToolContext):
        if self.drawing:
            self.points.append(pos)
            
            painter = QPainter(ctx.overlay.image())
            
            # 高亮笔：半透明+粗线条
            color = QColor(ctx.color)
            color.setAlpha(100)  # 固定半透明
            
            pen = QPen(color, ctx.stroke_width * 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            
            # 绘制最后一段
            if len(self.points) >= 2:
                p1 = ctx.overlay.scene_to_image_pos(self.points[-2])
                p2 = ctx.overlay.scene_to_image_pos(self.points[-1])
                painter.drawLine(p1, p2)
            
            painter.end()
            ctx.overlay.mark_dirty()
    
    def on_release(self, pos: QPointF, ctx: ToolContext):
        if self.drawing:
            self.drawing = False
            
            # 保存快照
            ctx.undo.push_snapshot(ctx.overlay.image().copy())
            
            print(f"[HighlighterTool] 完成高亮")
            self.points = []
