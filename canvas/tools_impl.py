"""
具体工具实现 - 基于新架构
"""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QInputDialog

from .tools_v2 import Tool, ToolContext
from .document import (
    StrokeLayer, RectLayer, EllipseLayer, ArrowLayer,
    TextLayer, NumberLayer, HighlighterLayer, MosaicLayer,
    LayerStyle
)


# ============================================================================
#  画笔工具
# ============================================================================

class PenTool(Tool):
    """画笔工具 - 自由绘制"""
    
    def __init__(self):
        super().__init__("pen", "画笔")
        self.drawing = False
    
    def on_press(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """开始绘制"""
        self.drawing = True
        
        # 创建画笔图层
        style = LayerStyle(
            color=ctx.style.color,
            stroke_width=ctx.style.stroke_width,
            opacity=ctx.style.opacity
        )
        layer = StrokeLayer(style)
        layer.add_point(pos)
        
        self.set_preview(layer, ctx)
        print(f"[PenTool] 开始绘制: {pos}")
    
    def on_move(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """添加点"""
        if self.drawing and self.preview_layer:
            self.preview_layer.add_point(pos)
            ctx.canvas.update()
    
    def on_release(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """完成绘制"""
        if self.drawing and self.preview_layer:
            # 至少需要2个点
            if len(self.preview_layer.points) >= 2:
                self.push_layer(self.preview_layer, ctx)
                print(f"[PenTool] 完成绘制, 点数: {len(self.preview_layer.points)}")
            else:
                print(f"[PenTool] 点数不足, 取消")
            
            self.clear_preview(ctx)
            self.drawing = False


# ============================================================================
#  矩形工具
# ============================================================================

class RectTool(Tool):
    """矩形工具"""
    
    def __init__(self):
        super().__init__("rect", "矩形")
        self.start_pos = None
    
    def on_press(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """开始拖拽"""
        self.start_pos = pos
        
        # 创建矩形图层
        style = LayerStyle(
            color=ctx.style.color,
            stroke_width=ctx.style.stroke_width,
            opacity=ctx.style.opacity
        )
        layer = RectLayer(style, QRectF(pos, pos))
        
        self.set_preview(layer, ctx)
        print(f"[RectTool] 开始拖拽: {pos}")
    
    def on_move(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """更新矩形"""
        if self.start_pos and self.preview_layer:
            # 是否按住Shift(保持比例)
            keep_ratio = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            
            if keep_ratio:
                # 保持1:1
                dx = pos.x() - self.start_pos.x()
                dy = pos.y() - self.start_pos.y()
                side = min(abs(dx), abs(dy))
                
                end_x = self.start_pos.x() + (side if dx >= 0 else -side)
                end_y = self.start_pos.y() + (side if dy >= 0 else -side)
                pos = QPointF(end_x, end_y)
            
            self.preview_layer.rect = QRectF(self.start_pos, pos).normalized()
            ctx.canvas.update()
    
    def on_release(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """完成矩形"""
        if self.preview_layer and not self.preview_layer.rect.isEmpty():
            self.push_layer(self.preview_layer, ctx)
            print(f"[RectTool] 完成矩形: {self.preview_layer.rect}")
        
        self.clear_preview(ctx)
        self.start_pos = None


# ============================================================================
#  椭圆工具
# ============================================================================

class EllipseTool(Tool):
    """椭圆工具"""
    
    def __init__(self):
        super().__init__("ellipse", "椭圆")
        self.start_pos = None
    
    def on_press(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """开始拖拽"""
        self.start_pos = pos
        
        style = LayerStyle(
            color=ctx.style.color,
            stroke_width=ctx.style.stroke_width,
            opacity=ctx.style.opacity
        )
        layer = EllipseLayer(style, QRectF(pos, pos))
        
        self.set_preview(layer, ctx)
    
    def on_move(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """更新椭圆"""
        if self.start_pos and self.preview_layer:
            # Shift保持圆形
            keep_ratio = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            
            if keep_ratio:
                dx = pos.x() - self.start_pos.x()
                dy = pos.y() - self.start_pos.y()
                side = min(abs(dx), abs(dy))
                
                end_x = self.start_pos.x() + (side if dx >= 0 else -side)
                end_y = self.start_pos.y() + (side if dy >= 0 else -side)
                pos = QPointF(end_x, end_y)
            
            self.preview_layer.rect = QRectF(self.start_pos, pos).normalized()
            ctx.canvas.update()
    
    def on_release(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """完成椭圆"""
        if self.preview_layer and not self.preview_layer.rect.isEmpty():
            self.push_layer(self.preview_layer, ctx)
        
        self.clear_preview(ctx)
        self.start_pos = None


# ============================================================================
#  箭头工具
# ============================================================================

class ArrowTool(Tool):
    """箭头工具"""
    
    def __init__(self):
        super().__init__("arrow", "箭头")
        self.start_pos = None
    
    def on_press(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """开始拖拽"""
        self.start_pos = pos
        
        style = LayerStyle(
            color=ctx.style.color,
            stroke_width=ctx.style.stroke_width,
            opacity=ctx.style.opacity
        )
        layer = ArrowLayer(style, pos, pos)
        
        self.set_preview(layer, ctx)
    
    def on_move(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """更新箭头终点"""
        if self.start_pos and self.preview_layer:
            self.preview_layer.end = pos
            ctx.canvas.update()
    
    def on_release(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """完成箭头"""
        if self.preview_layer:
            # 检查长度
            dx = self.preview_layer.end.x() - self.preview_layer.start.x()
            dy = self.preview_layer.end.y() - self.preview_layer.start.y()
            length = (dx**2 + dy**2) ** 0.5
            
            if length > 10:  # 最小长度
                self.push_layer(self.preview_layer, ctx)
        
        self.clear_preview(ctx)
        self.start_pos = None


# ============================================================================
#  文字工具
# ============================================================================

class TextTool(Tool):
    """文字工具"""
    
    def __init__(self):
        super().__init__("text", "文字")
    
    def on_press(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """点击位置输入文字"""
        # 弹出输入对话框
        text, ok = QInputDialog.getText(
            ctx.canvas,
            "输入文字",
            "请输入文字内容:",
        )
        
        if ok and text:
            style = LayerStyle(
                color=ctx.style.color,
                stroke_width=ctx.style.stroke_width,
                opacity=ctx.style.opacity
            )
            layer = TextLayer(style, pos, text)
            
            # 直接推入(不需要预览)
            self.push_layer(layer, ctx)
    
    def on_move(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """文字工具不需要拖拽"""
        pass
    
    def on_release(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """文字工具不需要松开"""
        pass


# ============================================================================
#  序号工具
# ============================================================================

class NumberTool(Tool):
    """序号工具 - 自动递增序号"""
    
    _counter = 1  # 全局计数器
    
    def __init__(self):
        super().__init__("number", "序号")
    
    def on_press(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """点击位置添加序号"""
        style = LayerStyle(
            color=ctx.style.color,
            stroke_width=ctx.style.stroke_width,
            opacity=ctx.style.opacity
        )
        layer = NumberLayer(style, pos, NumberTool._counter)
        NumberTool._counter += 1
        
        self.push_layer(layer, ctx)
    
    def on_move(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        pass
    
    def on_release(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        pass
    
    @classmethod
    def reset_counter(cls):
        """重置计数器"""
        cls._counter = 1


# ============================================================================
#  荧光笔工具
# ============================================================================

class HighlighterTool(Tool):
    """荧光笔工具 - 半透明画笔"""
    
    def __init__(self):
        super().__init__("highlighter", "荧光笔")
        self.drawing = False
    
    def on_press(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """开始绘制"""
        self.drawing = True
        
        style = LayerStyle(
            color=ctx.style.color,
            stroke_width=max(ctx.style.stroke_width * 3, 15),  # 更粗
            opacity=0.3  # 半透明
        )
        layer = HighlighterLayer(style)
        layer.add_point(pos)
        
        self.set_preview(layer, ctx)
    
    def on_move(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """添加点"""
        if self.drawing and self.preview_layer:
            self.preview_layer.add_point(pos)
            ctx.canvas.update()
    
    def on_release(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """完成绘制"""
        if self.drawing and self.preview_layer:
            if len(self.preview_layer.points) >= 2:
                self.push_layer(self.preview_layer, ctx)
            
            self.clear_preview(ctx)
            self.drawing = False


# ============================================================================
#  马赛克工具
# ============================================================================

class MosaicTool(Tool):
    """马赛克工具"""
    
    def __init__(self):
        super().__init__("mosaic", "马赛克")
        self.start_pos = None
    
    def on_press(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """开始拖拽"""
        self.start_pos = pos
        
        style = LayerStyle(
            color=ctx.style.color,
            stroke_width=ctx.style.stroke_width,
            opacity=ctx.style.opacity
        )
        layer = MosaicLayer(style, QRectF(pos, pos))
        
        self.set_preview(layer, ctx)
    
    def on_move(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """更新区域"""
        if self.start_pos and self.preview_layer:
            self.preview_layer.rect = QRectF(self.start_pos, pos).normalized()
            ctx.canvas.update()
    
    def on_release(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """完成马赛克"""
        if self.preview_layer and not self.preview_layer.rect.isEmpty():
            self.push_layer(self.preview_layer, ctx)
        
        self.clear_preview(ctx)
        self.start_pos = None
