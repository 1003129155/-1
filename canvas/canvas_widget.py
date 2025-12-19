"""
CanvasWidget - 专业截图软件的画布渲染控件
替换 QGraphicsView,使用纯 QPainter 渲染
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QCursor, QKeyEvent, QMouseEvent, QPaintEvent

from .document import Document
from .renderers import LayerRenderer, SelectionRenderer, ActiveLayerRenderer
from .selection_controller import SelectionController, HandlePosition


class CanvasWidget(QWidget):
    """
    画布控件 - 专业截图软件架构
    
    职责:
    1. 渲染: paintEvent() 绘制所有内容
    2. 交互: 鼠标/键盘事件转发给工具
    3. 信号: 通知外部事件
    
    渲染顺序:
    1. 背景(截图)
    2. 图层列表(向量渲染)
    3. 蒙层(四周暗化)
    4. 选区框 + 8控制点
    5. 选中图层高亮
    6. 临时预览(拖拽中的图形)
    """
    
    # 信号
    selection_confirmed = pyqtSignal(QRectF)  # 选区确认(双击/回车)
    export_requested = pyqtSignal()           # 导出请求
    cancel_requested = pyqtSignal()           # 取消(ESC)
    
    def __init__(self, document: Document):
        super().__init__()
        
        # 数据模型
        self.doc = document
        
        # 渲染器
        self.layer_renderer = LayerRenderer(document.background)
        self.selection_renderer = SelectionRenderer()
        self.active_layer_renderer = ActiveLayerRenderer()
        
        # 选区控制器
        self.selection_ctrl = SelectionController(document.rect)
        
        # 临时预览(拖拽中的图层,鼠标松开后加入Document)
        self.preview_layer = None
        
        # 工具系统
        self.tool_controller = None  # 由外部设置
        self.current_tool = None     # 废弃,使用tool_controller
        
        # 配置窗口
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # 设置尺寸
        self.setGeometry(document.rect.toRect())
        
        # 连接Document信号
        self.doc.selection_changed.connect(self.update)
        self.doc.layer_added.connect(lambda: self.update())
        self.doc.layer_removed.connect(lambda: self.update())
        self.doc.layer_updated.connect(lambda: self.update())
        self.doc.active_layer_changed.connect(self.update)
        
        print(f"✅ [CanvasWidget] 创建: {document.rect}")
    
    # ========================================================================
    #  渲染 (核心!)
    # ========================================================================
    
    def paintEvent(self, event: QPaintEvent):
        """
        渲染所有内容
        
        顺序:
        1. 背景截图
        2. 所有图层(向量渲染)
        3. 蒙层(选区外暗化)
        4. 选区框 + 控制点
        5. 选中图层高亮
        6. 预览图层(拖拽中)
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 1. 绘制背景截图
        painter.drawImage(0, 0, self.doc.background)
        
        # 2. 绘制所有图层(向量)
        for layer in self.doc.layers:
            self.layer_renderer.render(painter, layer)
        
        # 3. 绘制预览图层(拖拽中)
        if self.preview_layer:
            self.layer_renderer.render(painter, self.preview_layer)
        
        # 4. 绘制蒙层(选区外暗化)
        if self.doc.selection:
            self.selection_renderer.render_mask(painter, self.doc.rect, self.doc.selection)
        
        # 5. 绘制选区框 + 8控制点
        if self.doc.selection:
            self.selection_renderer.render_border(painter, self.doc.selection)
            self.selection_renderer.render_handles(painter, self.doc.selection)
        
        # 6. 绘制选中图层高亮
        active_layer = self.doc.get_active_layer()
        if active_layer:
            self.active_layer_renderer.render(painter, active_layer)
        
        painter.end()
    
    # ========================================================================
    #  鼠标事件 (转发给工具)
    # ========================================================================
    
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下"""
        pos = QPointF(event.pos())
        
        # 如果有工具控制器,转发给工具
        if self.tool_controller:
            self.tool_controller.on_press(pos, event)
            return
        
        # 默认行为:选区工具
        self._handle_selection_press(pos, event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动"""
        pos = QPointF(event.pos())
        
        # 如果有工具控制器,转发给工具
        if self.tool_controller:
            self.tool_controller.on_move(pos, event)
            return
        
        # 默认行为:选区工具
        self._handle_selection_move(pos, event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标松开"""
        pos = QPointF(event.pos())
        
        # 如果有工具控制器,转发给工具
        if self.tool_controller:
            self.tool_controller.on_release(pos, event)
            return
        
        # 默认行为:选区工具
        self._handle_selection_release(pos, event)
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """双击确认选区"""
        if self.doc.has_selection():
            self.selection_confirmed.emit(self.doc.selection)
    
    # ========================================================================
    #  键盘事件
    # ========================================================================
    
    def keyPressEvent(self, event: QKeyEvent):
        """键盘按下"""
        key = event.key()
        
        if key == Qt.Key.Key_Escape:
            # ESC 取消
            self.cancel_requested.emit()
        
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            # 回车确认选区
            if self.doc.has_selection():
                self.selection_confirmed.emit(self.doc.selection)
        
        elif key == Qt.Key.Key_Delete:
            # 删除选中图层
            if self.doc.active_layer_id:
                # TODO: 应该通过 RemoveLayerCommand
                self.doc.remove_layer(self.doc.active_layer_id)
        
        elif self.tool_controller:
            # 转发给工具控制器
            self.tool_controller.on_key_press(event)
    
    # ========================================================================
    #  选区工具(默认行为)
    # ========================================================================
    
    def _handle_selection_press(self, pos: QPointF, event: QMouseEvent):
        """选区工具:按下"""
        # 命中测试
        handle = self.selection_ctrl.hit_test(pos)
        
        # 开始拖拽
        self.selection_ctrl.start_drag(pos, handle)
        
        # 如果点击在外部,清除选中图层
        if handle == HandlePosition.NONE:
            self.doc.set_active_layer(None)
    
    def _handle_selection_move(self, pos: QPointF, event: QMouseEvent):
        """选区工具:移动"""
        # 更新光标
        if not event.buttons():
            # 没按住鼠标,只是悬停 → 更新光标
            handle = self.selection_ctrl.hit_test(pos)
            cursor = self.selection_ctrl.get_cursor(handle)
            self.setCursor(QCursor(cursor))
            return
        
        # 拖拽中 → 更新临时选区
        keep_ratio = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        temp_selection = self.selection_ctrl.drag_to(pos, keep_ratio)
        
        # 临时更新(不触发信号)
        self.selection_ctrl.selection = temp_selection
        self.update()
    
    def _handle_selection_release(self, pos: QPointF, event: QMouseEvent):
        """选区工具:松开"""
        # 结束拖拽
        keep_ratio = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        final_rect = self.selection_ctrl.drag_to(pos, keep_ratio)
        
        # 确认选区(应该通过 SetSelectionCommand,这里简化)
        self.selection_ctrl.end_drag(final_rect)
        self.doc.set_selection(final_rect)
    
    # ========================================================================
    #  工具接口
    # ========================================================================
    
    def set_tool_controller(self, controller):
        """
        设置工具控制器
        
        Args:
            controller: ToolController实例
        """
        self.tool_controller = controller
        # 工具控制器的上下文需要引用canvas
        controller.context.canvas = self
    
    def set_tool(self, tool):
        """设置当前工具(直接设置单个工具)"""
        self.current_tool = tool
    
    def set_preview_layer(self, layer):
        """设置预览图层(拖拽中)"""
        self.preview_layer = layer
        self.update()
    
    def clear_preview(self):
        """清除预览"""
        self.preview_layer = None
        self.update()
