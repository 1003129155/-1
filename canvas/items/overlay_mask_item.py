"""
遮罩层 - 挖洞显示选区
半透明遮罩 + 挖洞
"""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QPainterPath, QColor, QBrush, QPen
from PyQt6.QtWidgets import QGraphicsPathItem
from canvas.model import SelectionModel


class OverlayMaskItem(QGraphicsPathItem):
    """
    遮罩层 - 半透明遮罩 + 挖洞显示选区
    Z-order: 10
    """
    
    def __init__(self, full_rect: QRectF, model: SelectionModel):
        super().__init__()
        self.setZValue(10)
        
        self._full = QRectF(full_rect)
        self._model = model
        
        # 连接选区变化信号
        self._model.rectChanged.connect(self.rebuild)
        
        # 初始构建
        self.rebuild()
        
        # 确保可见
        self.setVisible(True)
        self.setEnabled(True)
        
        print(f"✅ [遮罩层] 创建: {full_rect}, Z-order: {self.zValue()}, 可见: {self.isVisible()}")
    
    def rebuild(self, *_):
        """重建遮罩路径（挖洞）"""
        # 全屏路径
        all_path = QPainterPath()
        all_path.addRect(self._full)
        
        # 选区路径（洞）
        hole_path = QPainterPath()
        if not self._model.is_empty():
            selection_rect = self._model.rect()
            hole_path.addRect(selection_rect)
        
        # 挖洞: 全屏 - 选区
        final_path = all_path.subtracted(hole_path)
        self.setPath(final_path)
        
        # 设置样式
        self.setBrush(QBrush(QColor(0, 0, 0, 180)))  # 半透明黑色
        self.setPen(QPen(Qt.PenStyle.NoPen))  # 无边框
