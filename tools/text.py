"""
文字工具（简化版）
"""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPainter, QFont
from .base import Tool, ToolContext


class TextTool(Tool):
    """
    文字工具 - 简化版（完整版需要输入框）
    """
    
    id = "text"
    
    def on_press(self, pos: QPointF, button, ctx: ToolContext):
        if button == Qt.MouseButton.LeftButton:
            # TODO: 显示输入框
            # 这里简化为绘制"Text"
            painter = QPainter(ctx.overlay.image())
            painter.setOpacity(ctx.opacity)
            
            font = QFont("Arial", ctx.stroke_width * 4)
            painter.setFont(font)
            painter.setPen(ctx.color)
            
            img_pos = ctx.overlay.scene_to_image_pos(pos)
            painter.drawText(img_pos, "Text")
            
            painter.end()
            ctx.overlay.mark_dirty()
            
            # 保存快照
            ctx.undo.push_snapshot(ctx.overlay.image().copy())
            
            print(f"[TextTool] 绘制文字: {pos}")
