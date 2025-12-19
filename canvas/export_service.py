"""
导出服务 V2 - 基于Document的向量渲染导出
"""

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage, QPainter, QColor

from .document import Document
from .renderers import LayerRenderer


class ExportService:
    """
    导出服务 - 将Document渲染并导出为图像
    
    流程:
    1. 创建临时图像
    2. 绘制背景(选区范围)
    3. 渲染所有图层
    4. 返回选区范围的图像
    """
    
    def __init__(self, document: Document):
        self.doc = document
        self.renderer = LayerRenderer(document.background)
    
    def export(self, selection: QRectF = None) -> QImage:
        """
        导出图像
        
        Args:
            selection: 导出的选区范围,None=整个画布
            
        Returns:
            QImage: 导出的图像
        """
        # 确定导出范围
        if selection is None or selection.isEmpty():
            selection = self.doc.rect
        
        # 创建临时图像
        width = int(selection.width())
        height = int(selection.height())
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(0, 0, 0, 0))  # 透明背景
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 平移坐标系,使选区左上角为原点
        painter.translate(-selection.left(), -selection.top())
        
        # 1. 绘制背景(选区范围)
        painter.drawImage(selection.topLeft(), self.doc.background, selection)
        
        # 2. 绘制所有图层
        for layer in self.doc.layers:
            if layer.visible:
                self.renderer.render(painter, layer)
        
        painter.end()
        
        print(f"✅ [导出] 范围: {selection}, 尺寸: {width}x{height}")
        return image
    
    def export_to_file(self, filepath: str, selection: QRectF = None) -> bool:
        """
        导出到文件
        
        Args:
            filepath: 文件路径(.png/.jpg)
            selection: 导出范围
            
        Returns:
            bool: 是否成功
        """
        image = self.export(selection)
        success = image.save(filepath)
        
        if success:
            print(f"✅ [导出] 保存成功: {filepath}")
        else:
            print(f"❌ [导出] 保存失败: {filepath}")
        
        return success
    
    def export_to_clipboard(self, selection: QRectF = None):
        """
        导出到剪贴板
        
        Args:
            selection: 导出范围
        """
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QPixmap
        
        image = self.export(selection)
        pixmap = QPixmap.fromImage(image)
        
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(pixmap)
        
        print(f"✅ [导出] 已复制到剪贴板")
