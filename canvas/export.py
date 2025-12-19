"""
导出服务
统一的图像导出接口
"""

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication


class ExportService:
    """
    导出服务 - 统一处理图像导出
    """
    
    def __init__(self, scene):
        """
        Args:
            scene: CanvasScene 实例
        """
        self.scene = scene
    
    def export(self, selection_rect: QRectF) -> QImage:
        """
        导出选区图像（背景 + overlay）
        
        Args:
            selection_rect: 选区矩形（场景坐标）
            
        Returns:
            导出的图像
        """
        if selection_rect.isNull() or selection_rect.isEmpty():
            print("⚠️ [导出] 选区为空")
            return QImage()
        
        print(f"🔍 [导出] 接收到选区: {selection_rect}")
        print(f"🔍 [导出] 场景范围: {self.scene.scene_rect}")
        
        # 输出图像大小按选区逻辑像素
        w = max(1, int(selection_rect.width()))
        h = max(1, int(selection_rect.height()))
        
        print(f"🔍 [导出] 目标图像大小: {w}x{h}")
        
        out = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(0)  # 透明背景
        
        painter = QPainter(out)
        
        # 1. 先绘制背景的选区部分
        bg_pixmap = self.scene.background.pixmap()
        print(f"🔍 [导出] 背景pixmap大小: {bg_pixmap.width()}x{bg_pixmap.height()}")
        
        # 计算背景的源区域（图像坐标）
        src_rect = selection_rect.translated(-self.scene.scene_rect.topLeft())
        print(f"🔍 [导出] 背景源区域: {src_rect}")
        
        painter.drawPixmap(0, 0, bg_pixmap, 
                          int(src_rect.x()), int(src_rect.y()),
                          w, h)
        
        # 2. 再绘制overlay的选区部分
        overlay_img = self.scene.overlay_pixmap.image()
        print(f"🔍 [导出] overlay图像大小: {overlay_img.width()}x{overlay_img.height()}")
        
        # overlay也是从scene_rect.topLeft()开始的
        painter.drawImage(0, 0, overlay_img,
                         int(src_rect.x()), int(src_rect.y()),
                         w, h)
        
        painter.end()
        
        print(f"📤 [导出] 完成！最终图像: {out.width()}x{out.height()}")
        return out
    
    def export_full(self) -> QImage:
        """
        导出整个场景
        
        Returns:
            完整场景图像
        """
        rect = self.scene.sceneRect()
        return self.export(rect)
    
    def copy_to_clipboard(self, img: QImage):
        """
        复制图像到剪贴板
        
        Args:
            img: 要复制的图像
        """
        QApplication.clipboard().setImage(img)
        print(f"📋 [导出] 已复制到剪贴板")
    
    def save_to_file(self, img: QImage, path: str, quality: int = 100) -> bool:
        """
        保存图像到文件
        
        Args:
            img: 要保存的图像
            path: 文件路径
            quality: 质量（0-100）
            
        Returns:
            是否成功
        """
        success = img.save(path, quality=quality)
        if success:
            print(f"💾 [导出] 保存成功: {path}")
        else:
            print(f"❌ [导出] 保存失败: {path}")
        return success
    
    def export_and_copy(self, selection_rect: QRectF):
        """
        导出选区并复制到剪贴板（快捷操作）
        
        Args:
            selection_rect: 选区矩形
        """
        if selection_rect.isNull() or selection_rect.isEmpty():
            print("⚠️ [导出] 选区为空")
            return
        
        img = self.export(selection_rect)
        self.copy_to_clipboard(img)
