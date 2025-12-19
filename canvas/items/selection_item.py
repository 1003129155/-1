"""
选区框 - 边框和控制点
"""

from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import QPen, QColor, QBrush, QPainter
from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from canvas.model import SelectionModel


class SelectionItem(QGraphicsItem):
    """
    选区框 - 显示边框和8个控制点
    Z-order: 15
    """
    
    HANDLE_SIZE = 10  # 控制点大小
    
    def __init__(self, model: SelectionModel):
        super().__init__()
        self.setZValue(15)
        
        self._model = model
        self._model.rectChanged.connect(self.update_bounds)
        
        # 可交互（用于拖拽调整选区）
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        
        print(f"✅ [选区框] 创建")
    
    def boundingRect(self) -> QRectF:
        """边界矩形"""
        if self._model.is_empty():
            return QRectF()
        
        rect = self._model.rect()
        # 扩展一点以包含边框和控制点
        return rect.adjusted(-20, -20, 20, 20)
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        """绘制选区边框和控制点"""
        if self._model.is_empty():
            return
        
        rect = self._model.rect()
        
        # 绘制边框
        pen = QPen(QColor(64, 224, 208), 4, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        
        # 绘制8个控制点
        handles = self._get_handle_positions(rect)
        for pos in handles:
            # 外圈（白色）
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(QColor(48, 200, 192))
            painter.drawEllipse(pos, self.HANDLE_SIZE // 2 + 1, self.HANDLE_SIZE // 2 + 1)
            
            # 内圈（青色）
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(48, 200, 192))
            painter.drawEllipse(pos, self.HANDLE_SIZE // 2, self.HANDLE_SIZE // 2)
    
    def _get_handle_positions(self, rect: QRectF) -> list[QPointF]:
        """获取8个控制点的位置"""
        left = rect.left()
        right = rect.right()
        top = rect.top()
        bottom = rect.bottom()
        cx = rect.center().x()
        cy = rect.center().y()
        
        return [
            QPointF(left, cy),      # 左中
            QPointF(cx, top),       # 上中
            QPointF(right, cy),     # 右中
            QPointF(cx, bottom),    # 下中
            QPointF(left, top),     # 左上
            QPointF(left, bottom),  # 左下
            QPointF(right, top),    # 右上
            QPointF(right, bottom), # 右下
        ]
    
    def update_bounds(self, *_):
        """更新边界"""
        self.prepareGeometryChange()
        self.update()
