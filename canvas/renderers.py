"""
向量图层渲染器 - 将Layer渲染到QPainter
专业截图软件的向量绘制实现
"""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QLinearGradient, QImage
import math

from .document import (
    Layer, StrokeLayer, RectLayer, EllipseLayer, ArrowLayer,
    TextLayer, NumberLayer, HighlighterLayer, MosaicLayer
)


class LayerRenderer:
    """
    图层渲染器 - 负责将向量图层渲染到QPainter
    
    每个图层类型有对应的渲染方法
    """
    
    def __init__(self, background: QImage = None):
        """
        Args:
            background: 背景图像(用于马赛克)
        """
        self.background = background
    
    def render(self, painter: QPainter, layer: Layer):
        """
        渲染图层(主入口)
        
        Args:
            painter: QPainter
            layer: 图层对象
        """
        if not layer.visible:
            return
        
        # 根据图层类型分发
        if isinstance(layer, StrokeLayer):
            self._render_stroke(painter, layer)
        elif isinstance(layer, RectLayer):
            self._render_rect(painter, layer)
        elif isinstance(layer, EllipseLayer):
            self._render_ellipse(painter, layer)
        elif isinstance(layer, ArrowLayer):
            self._render_arrow(painter, layer)
        elif isinstance(layer, TextLayer):
            self._render_text(painter, layer)
        elif isinstance(layer, NumberLayer):
            self._render_number(painter, layer)
        elif isinstance(layer, HighlighterLayer):
            self._render_highlighter(painter, layer)
        elif isinstance(layer, MosaicLayer):
            self._render_mosaic(painter, layer)
    
    # ========================================================================
    #  各图层类型的渲染实现
    # ========================================================================
    
    def _render_stroke(self, painter: QPainter, layer: StrokeLayer):
        """渲染画笔图层"""
        if len(layer.points) < 2:
            return
        
        pen = self._create_pen(layer.style)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # 绘制连续线段
        for i in range(1, len(layer.points)):
            painter.drawLine(layer.points[i-1], layer.points[i])
    
    def _render_rect(self, painter: QPainter, layer: RectLayer):
        """渲染矩形图层"""
        pen = self._create_pen(layer.style)
        painter.setPen(pen)
        
        if layer.filled:
            brush = QBrush(layer.style.color)
            painter.setBrush(brush)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        
        painter.drawRect(layer.rect)
    
    def _render_ellipse(self, painter: QPainter, layer: EllipseLayer):
        """渲染椭圆图层"""
        pen = self._create_pen(layer.style)
        painter.setPen(pen)
        
        if layer.filled:
            brush = QBrush(layer.style.color)
            painter.setBrush(brush)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        
        painter.drawEllipse(layer.rect)
    
    def _render_arrow(self, painter: QPainter, layer: ArrowLayer):
        """渲染箭头图层"""
        pen = self._create_pen(layer.style)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # 1. 绘制主线
        painter.drawLine(layer.start, layer.end)
        
        # 2. 绘制箭头
        arrow_size = layer.arrow_size
        
        # 计算箭头角度
        dx = layer.end.x() - layer.start.x()
        dy = layer.end.y() - layer.start.y()
        angle = math.atan2(dy, dx)
        
        # 箭头两侧的点
        arrow_angle = math.pi / 6  # 30度
        left_angle = angle + math.pi - arrow_angle
        right_angle = angle + math.pi + arrow_angle
        
        left_pt = QPointF(
            layer.end.x() + arrow_size * math.cos(left_angle),
            layer.end.y() + arrow_size * math.sin(left_angle)
        )
        right_pt = QPointF(
            layer.end.x() + arrow_size * math.cos(right_angle),
            layer.end.y() + arrow_size * math.sin(right_angle)
        )
        
        # 绘制箭头两边
        painter.drawLine(layer.end, left_pt)
        painter.drawLine(layer.end, right_pt)
    
    def _render_text(self, painter: QPainter, layer: TextLayer):
        """渲染文字图层"""
        painter.setPen(layer.style.color)
        
        font = QFont()
        font.setPixelSize(layer.font_size)
        painter.setFont(font)
        
        painter.drawText(layer.pos, layer.text)
    
    def _render_number(self, painter: QPainter, layer: NumberLayer):
        """渲染序号图层(圆圈+数字)"""
        # 1. 绘制圆圈
        pen = QPen(layer.style.color, layer.style.stroke_width)
        painter.setPen(pen)
        
        brush = QBrush(layer.style.color)
        painter.setBrush(brush)
        
        painter.drawEllipse(
            layer.pos.x() - layer.radius,
            layer.pos.y() - layer.radius,
            layer.radius * 2,
            layer.radius * 2
        )
        
        # 2. 绘制数字(白色)
        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPixelSize(int(layer.radius * 1.2))
        font.setBold(True)
        painter.setFont(font)
        
        # 居中对齐
        text = str(layer.number)
        rect = QRectF(
            layer.pos.x() - layer.radius,
            layer.pos.y() - layer.radius,
            layer.radius * 2,
            layer.radius * 2
        )
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    
    def _render_highlighter(self, painter: QPainter, layer: HighlighterLayer):
        """渲染荧光笔图层(半透明粗线)"""
        if len(layer.points) < 2:
            return
        
        # 设置半透明
        color = QColor(layer.style.color)
        color.setAlphaF(layer.style.opacity)
        
        pen = QPen(color, layer.style.stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # 设置混合模式(荧光笔效果)
        old_mode = painter.compositionMode()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        
        # 绘制连续线段
        for i in range(1, len(layer.points)):
            painter.drawLine(layer.points[i-1], layer.points[i])
        
        painter.setCompositionMode(old_mode)
    
    def _render_mosaic(self, painter: QPainter, layer: MosaicLayer):
        """渲染马赛克图层"""
        if not self.background or layer.rect.isEmpty():
            return
        
        # 马赛克算法:将区域分成小块,每块填充平均色
        block_size = layer.block_size
        rect = layer.rect.toRect()
        
        for y in range(rect.top(), rect.bottom(), block_size):
            for x in range(rect.left(), rect.right(), block_size):
                # 计算当前块的范围
                block_rect = QRectF(x, y, block_size, block_size)
                block_rect = block_rect.intersected(layer.rect)
                
                if block_rect.isEmpty():
                    continue
                
                # 采样块中心点的颜色
                center_x = int(block_rect.center().x())
                center_y = int(block_rect.center().y())
                
                # 确保坐标在图像范围内
                if (0 <= center_x < self.background.width() and 
                    0 <= center_y < self.background.height()):
                    color = self.background.pixelColor(center_x, center_y)
                    
                    # 填充整个块
                    painter.fillRect(block_rect, color)
    
    # ========================================================================
    #  辅助方法
    # ========================================================================
    
    def _create_pen(self, style) -> QPen:
        """根据样式创建画笔"""
        color = QColor(style.color)
        color.setAlphaF(style.opacity)
        
        pen = QPen(color, style.stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        return pen


class SelectionRenderer:
    """
    选区渲染器 - 绘制蒙层、选区框、吸附引导线、信息条
    """
    
    def __init__(self):
        self.mask_color = QColor(0, 0, 0, 120)  # 半透明黑色
        self.border_color = QColor(0, 120, 215)  # 蓝色边框
        self.handle_color = QColor(255, 255, 255)  # 白色控制点
        
        # 吸附引导线渲染
        self.enable_snap_guides = True
        
        # 信息条渲染
        self.enable_info_bar = True
    
    def render_mask(self, painter: QPainter, canvas_rect: QRectF, selection: QRectF):
        """
        渲染蒙层(四周暗,选区透明)
        
        Args:
            painter: QPainter
            canvas_rect: 画布范围
            selection: 选区
        """
        if not selection or selection.isEmpty():
            return
        
        # 使用裁剪实现:先填充整个画布,再挖掉选区
        painter.save()
        
        # 填充整个画布
        painter.fillRect(canvas_rect, self.mask_color)
        
        # 挖掉选区(使用清除模式)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(selection, Qt.GlobalColor.transparent)
        
        painter.restore()
    
    def render_border(self, painter: QPainter, selection: QRectF):
        """
        渲染选区边框
        
        Args:
            painter: QPainter
            selection: 选区
        """
        if not selection or selection.isEmpty():
            return
        
        pen = QPen(self.border_color, 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(selection)
    
    def render_handles(self, painter: QPainter, selection: QRectF, handle_size: int = 8):
        """
        渲染8个控制点
        
        Args:
            painter: QPainter
            selection: 选区
            handle_size: 控制点大小
        """
        if not selection or selection.isEmpty():
            return
        
        half = handle_size / 2
        
        # 8个控制点位置
        handles = [
            QPointF(selection.left(), selection.top()),           # 左上
            QPointF(selection.center().x(), selection.top()),     # 上
            QPointF(selection.right(), selection.top()),          # 右上
            QPointF(selection.right(), selection.center().y()),   # 右
            QPointF(selection.right(), selection.bottom()),       # 右下
            QPointF(selection.center().x(), selection.bottom()),  # 下
            QPointF(selection.left(), selection.bottom()),        # 左下
            QPointF(selection.left(), selection.center().y()),    # 左
        ]
        
        # 绘制控制点
        pen = QPen(self.border_color, 1)
        brush = QBrush(self.handle_color)
        painter.setPen(pen)
        painter.setBrush(brush)
        
        for pt in handles:
            rect = QRectF(pt.x() - half, pt.y() - half, handle_size, handle_size)
            painter.drawRect(rect)
    
    def render_snap_guides(self, painter: QPainter, snap_system):
        """
        渲染吸附引导线
        
        Args:
            painter: QPainter
            snap_system: SnapSystem 实例
        """
        if not self.enable_snap_guides or not snap_system:
            return
        
        try:
            snap_system.render_guides(painter)
        except Exception as e:
            print(f"⚠️ [SelectionRenderer] 渲染吸附引导线失败: {e}")
    
    def render_info_bar(self, painter: QPainter, selection: QRectF, canvas_rect: QRectF, info_bar_renderer):
        """
        渲染选区信息条
        
        Args:
            painter: QPainter
            selection: 选区
            canvas_rect: 画布矩形
            info_bar_renderer: SelectionInfoBarRenderer 实例
        """
        if not self.enable_info_bar or not info_bar_renderer or not selection or selection.isEmpty():
            return
        
        try:
            info_bar_renderer.render(painter, selection, canvas_rect)
        except Exception as e:
            print(f"⚠️ [SelectionRenderer] 渲染信息条失败: {e}")


class ActiveLayerRenderer:
    """
    选中图层渲染器 - 绘制选中图层的包围框和控制点
    """
    
    def __init__(self):
        self.border_color = QColor(0, 120, 215)
        self.handle_color = QColor(255, 255, 255)
    
    def render(self, painter: QPainter, layer: Layer, handle_size: int = 6):
        """
        渲染选中图层的高亮
        
        Args:
            painter: QPainter
            layer: 选中的图层
            handle_size: 控制点大小
        """
        if not layer:
            return
        
        bounds = layer.bounds()
        if bounds.isEmpty():
            return
        
        # 1. 绘制包围框(虚线)
        pen = QPen(self.border_color, 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(bounds)
        
        # 2. 绘制4个角的控制点
        half = handle_size / 2
        corners = [
            bounds.topLeft(),
            bounds.topRight(),
            bounds.bottomRight(),
            bounds.bottomLeft(),
        ]
        
        pen = QPen(self.border_color, 1)
        brush = QBrush(self.handle_color)
        painter.setPen(pen)
        painter.setBrush(brush)
        
        for pt in corners:
            rect = QRectF(pt.x() - half, pt.y() - half, handle_size, handle_size)
            painter.drawRect(rect)
