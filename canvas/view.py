"""
画布视图 - 处理用户交互
"""

from PyQt6.QtWidgets import QGraphicsView
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter


class CanvasView(QGraphicsView):
    """
    画布视图
    """
    
    def __init__(self, scene):
        super().__init__(scene)
        
        self.canvas_scene = scene
        
        # 设置渲染选项
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 禁用滚动条
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 交互状态
        self.is_selecting = False  # 是否在选择区域
        self.is_drawing = False    # 是否在绘制
        
        self.start_pos = QPointF()
    
    def mousePressEvent(self, event):
        """
        鼠标按下
        """
        scene_pos = self.mapToScene(event.pos())
        
        if not self.canvas_scene.selection_model.is_confirmed:
            # 选区模式
            self.is_selecting = True
            self.start_pos = scene_pos
            self.canvas_scene.selection_model.activate()
        else:
            # 绘图模式
            self.is_drawing = True
            self.canvas_scene.tool_controller.on_press(scene_pos, event.button())
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """
        鼠标移动
        """
        scene_pos = self.mapToScene(event.pos())
        
        if self.is_selecting:
            # 更新选区
            from PyQt6.QtCore import QRectF
            rect = QRectF(self.start_pos, scene_pos).normalized()
            self.canvas_scene.selection_model.set_rect(rect)
        elif self.is_drawing:
            # 绘图
            self.canvas_scene.tool_controller.on_move(scene_pos)
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """
        鼠标释放
        """
        scene_pos = self.mapToScene(event.pos())
        
        if self.is_selecting:
            self.is_selecting = False
            # 确认选区
            self.canvas_scene.confirm_selection()
        elif self.is_drawing:
            self.is_drawing = False
            self.canvas_scene.tool_controller.on_release(scene_pos)
        
        super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event):
        """
        键盘事件
        """
        if event.key() == Qt.Key.Key_Escape:
            # ESC取消截图
            self.window().close()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # 回车确认
            if self.canvas_scene.selection_model.is_confirmed:
                self.export_and_close()
        elif event.key() == Qt.Key.Key_Z and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Ctrl+Z撤销
            self.canvas_scene.undo_stack.undo()
        elif event.key() == Qt.Key.Key_Y and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Ctrl+Y重做
            self.canvas_scene.undo_stack.redo()
        
        super().keyPressEvent(event)
    
    def export_and_close(self):
        """
        导出并关闭
        """
        from .export import ExportService
        
        # 创建导出服务（传入整个scene）
        exporter = ExportService(self.canvas_scene)
        
        # 导出选区图像
        selection_rect = self.canvas_scene.selection_model.rect()
        print(f"📸 [导出] 准备导出选区: {selection_rect}")
        
        result = exporter.export(selection_rect)
        
        if result:
            print(f"📸 [导出] 导出成功，图像大小: {result.width()}x{result.height()}")
            exporter.copy_to_clipboard(result)
            print("[CanvasView] 已复制到剪贴板")
            self.window().close()
        else:
            print("❌ [导出] 导出失败！")
