"""
序号标注工具（简化版）
"""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QFont
from .base import Tool, ToolContext


class NumberTool(Tool):
    """
    序号标注工具
    """
    
    id = "number"
    counter = 1  # 全局计数器
    
    def on_press(self, pos: QPointF, button, ctx: ToolContext):
        if button == Qt.MouseButton.LeftButton:
            painter = QPainter(ctx.overlay.image())
            painter.setOpacity(ctx.opacity)
            
            img_pos = ctx.overlay.scene_to_image_pos(pos)
            radius = ctx.stroke_width * 5
            
            # 绘制圆形
            painter.setPen(QPen(ctx.color, ctx.stroke_width))
            painter.setBrush(QBrush(ctx.color))
            painter.drawEllipse(img_pos, radius, radius)
            
            # 绘制数字
            font = QFont("Arial", int(radius * 0.8), QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(
                int(img_pos.x() - radius), 
                int(img_pos.y() - radius),
                int(radius * 2), 
                int(radius * 2),
                Qt.AlignmentFlag.AlignCenter,
                str(self.counter)
            )
            
            painter.end()
            ctx.overlay.mark_dirty()
            
            # 保存快照
            ctx.undo.push_snapshot(ctx.overlay.image().copy())
            
            print(f"[NumberTool] 绘制序号: {self.counter}")
            self.counter += 1
