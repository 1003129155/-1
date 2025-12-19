"""
矩形工具
"""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPainter, QPen
from .base import Tool, ToolContext


class RectTool(Tool):
    """
    矩形工具
    """
    
    id = "rect"
    
    def __init__(self):
        self.drawing = False
        self.start_pos = None
        self.temp_pixmap = None
    
    def on_press(self, pos: QPointF, button, ctx: ToolContext):
        if button == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.start_pos = pos
            self.temp_pixmap = ctx.overlay.image().copy()
            print(f"[RectTool] 开始绘制: {pos}")
    
    def on_move(self, pos: QPointF, ctx: ToolContext):
        if self.drawing:
            # 恢复原图
            ctx.overlay.image().swap(self.temp_pixmap.copy())
            
            # 绘制矩形
            rect = QRectF(self.start_pos, pos).normalized()
            
            painter = QPainter(ctx.overlay.image())
            pen = QPen(ctx.color, ctx.stroke_width)
            painter.setPen(pen)
            painter.setOpacity(ctx.opacity)
            
            # 转换到图像坐标
            img_rect = QRectF(
                ctx.overlay.scene_to_image_pos(rect.topLeft()),
                ctx.overlay.scene_to_image_pos(rect.bottomRight())
            )
            
            painter.drawRect(img_rect)
            painter.end()
            ctx.overlay.mark_dirty()
    
    def on_release(self, pos: QPointF, ctx: ToolContext):
        if self.drawing:
            self.drawing = False
            
            # 保存快照
            ctx.undo.push_snapshot(ctx.overlay.image().copy())
            
            print(f"[RectTool] 完成绘制")
            self.temp_pixmap = None
