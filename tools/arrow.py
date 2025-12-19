"""
箭头工具
"""

from PyQt6.QtCore import QPointF, QLineF, Qt
from PyQt6.QtGui import QPainter, QPen, QPolygonF
import math
from .base import Tool, ToolContext


class ArrowTool(Tool):
    """
    箭头工具
    """
    
    id = "arrow"
    
    def __init__(self):
        self.drawing = False
        self.start_pos = None
        self.temp_pixmap = None
    
    def on_press(self, pos: QPointF, button, ctx: ToolContext):
        if button == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.start_pos = pos
            self.temp_pixmap = ctx.overlay.image().copy()
            print(f"[ArrowTool] 开始绘制: {pos}")
    
    def on_move(self, pos: QPointF, ctx: ToolContext):
        if self.drawing:
            # 恢复原图
            ctx.overlay.image().swap(self.temp_pixmap.copy())
            
            painter = QPainter(ctx.overlay.image())
            pen = QPen(ctx.color, ctx.stroke_width)
            painter.setPen(pen)
            painter.setBrush(ctx.color)
            painter.setOpacity(ctx.opacity)
            
            # 转换到图像坐标
            p1 = ctx.overlay.scene_to_image_pos(self.start_pos)
            p2 = ctx.overlay.scene_to_image_pos(pos)
            
            # 绘制线段
            painter.drawLine(p1, p2)
            
            # 绘制箭头
            line = QLineF(p1, p2)
            angle = math.atan2(-line.dy(), line.dx())
            arrow_size = ctx.stroke_width * 3
            
            arrow_p1 = p2 - QPointF(
                math.sin(angle - math.pi / 3) * arrow_size,
                math.cos(angle - math.pi / 3) * arrow_size
            )
            arrow_p2 = p2 - QPointF(
                math.sin(angle + math.pi / 3) * arrow_size,
                math.cos(angle + math.pi / 3) * arrow_size
            )
            
            arrow_head = QPolygonF([p2, arrow_p1, arrow_p2])
            painter.drawPolygon(arrow_head)
            
            painter.end()
            ctx.overlay.mark_dirty()
    
    def on_release(self, pos: QPointF, ctx: ToolContext):
        if self.drawing:
            self.drawing = False
            
            # 保存快照
            ctx.undo.push_snapshot(ctx.overlay.image().copy())
            
            print(f"[ArrowTool] 完成绘制")
            self.temp_pixmap = None
