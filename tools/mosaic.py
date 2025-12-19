"""
马赛克工具
"""

from PyQt6.QtCore import QPointF, Qt, QRect
from PyQt6.QtGui import QPainter, QImage
from .base import Tool, ToolContext


class MosaicTool(Tool):
    """
    马赛克工具 - 像素化模糊
    """
    
    id = "mosaic"
    
    def __init__(self):
        self.drawing = False
        self.last_pos = None
    
    def on_press(self, pos: QPointF, button, ctx: ToolContext):
        if button == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.last_pos = pos
            self.apply_mosaic(pos, ctx)
            print(f"[MosaicTool] 开始马赛克: {pos}")
    
    def on_move(self, pos: QPointF, ctx: ToolContext):
        if self.drawing:
            self.apply_mosaic(pos, ctx)
            self.last_pos = pos
    
    def on_release(self, pos: QPointF, ctx: ToolContext):
        if self.drawing:
            self.drawing = False
            
            # 保存快照
            ctx.undo.push_snapshot(ctx.overlay.image().copy())
            
            print(f"[MosaicTool] 完成马赛克")
    
    def apply_mosaic(self, pos: QPointF, ctx: ToolContext):
        """
        应用马赛克效果
        """
        img_pos = ctx.overlay.scene_to_image_pos(pos)
        size = ctx.stroke_width * 3
        
        # 获取区域
        rect = QRect(
            int(img_pos.x() - size // 2),
            int(img_pos.y() - size // 2),
            size,
            size
        )
        
        # 缩小再放大（像素化）
        pixmap = ctx.overlay.image()
        img = pixmap.toImage()
        
        # 确保rect在范围内
        rect = rect.intersected(img.rect())
        if rect.isEmpty():
            return
        
        # 提取区域 -> 缩小10倍 -> 放大回来
        region = img.copy(rect)
        small = region.scaled(
            max(1, rect.width() // 10),
            max(1, rect.height() // 10),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation
        )
        mosaic = small.scaled(
            rect.width(),
            rect.height(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation
        )
        
        # 绘制回去
        painter = QPainter(pixmap)
        painter.drawImage(rect, mosaic)
        painter.end()
        
        ctx.overlay.mark_dirty()
