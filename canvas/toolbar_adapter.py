"""
工具栏适配器 - 将 toolbar_full.py 适配到新架构
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor

from ui.toolbar_full import Toolbar
from canvas.tools_v2 import ToolController


class ToolbarAdapter(QObject):
    """
    工具栏适配器 - 连接专业工具栏和新架构
    
    职责:
    1. 将工具栏信号转发到 ToolController
    2. 同步样式变化到 ToolContext
    3. 处理撤销/重做/保存等操作
    """
    
    # 对外信号
    save_requested = pyqtSignal()
    copy_requested = pyqtSignal()
    confirm_requested = pyqtSignal()
    
    def __init__(self, toolbar: Toolbar, tool_controller: ToolController, undo_stack):
        super().__init__()
        
        self.toolbar = toolbar
        self.tool_controller = tool_controller
        self.undo_stack = undo_stack
        
        # 工具映射(工具栏ID → 新架构ID)
        self.tool_map = {
            "pen": "pen",
            "highlighter": "highlighter",
            "arrow": "arrow",
            "number": "number",
            "rect": "rect",
            "ellipse": "ellipse",
            "text": "text",
            "mosaic": "mosaic",  # 工具栏暂无,但架构支持
        }
        
        # 连接信号
        self._connect_signals()
        
        print("✅ [ToolbarAdapter] 工具栏适配器初始化")
    
    def _connect_signals(self):
        """连接工具栏信号"""
        
        # 1. 工具切换
        self.toolbar.tool_changed.connect(self._on_tool_changed)
        
        # 2. 样式变化
        self.toolbar.color_changed.connect(self._on_color_changed)
        self.toolbar.stroke_width_changed.connect(self._on_stroke_width_changed)
        self.toolbar.opacity_changed.connect(self._on_opacity_changed)
        
        # 3. 撤销/重做
        self.toolbar.undo_clicked.connect(self._on_undo)
        self.toolbar.redo_clicked.connect(self._on_redo)
        
        # 4. 保存/复制/确认
        self.toolbar.save_clicked.connect(self.save_requested.emit)
        self.toolbar.copy_clicked.connect(self.copy_requested.emit)
        self.toolbar.confirm_clicked.connect(self.confirm_requested.emit)
    
    # ========================================================================
    #  信号处理
    # ========================================================================
    
    def _on_tool_changed(self, tool_id: str):
        """工具切换"""
        # 映射工具ID
        new_tool_id = self.tool_map.get(tool_id, tool_id)
        
        # 激活工具
        self.tool_controller.activate(new_tool_id)
        print(f"🔧 [工具切换] {tool_id} → {new_tool_id}")
    
    def _on_color_changed(self, color: QColor):
        """颜色变化"""
        self.tool_controller.update_style(color=color)
        print(f"🎨 [颜色] {color.name()}")
    
    def _on_stroke_width_changed(self, width: int):
        """线宽变化"""
        self.tool_controller.update_style(stroke_width=width)
        print(f"📏 [线宽] {width}")
    
    def _on_opacity_changed(self, opacity_255: int):
        """透明度变化(0-255)"""
        # 转换为0.0-1.0
        opacity = opacity_255 / 255.0
        self.tool_controller.update_style(opacity=opacity)
        print(f"✨ [透明度] {opacity:.2f}")
    
    def _on_undo(self):
        """撤销"""
        if self.undo_stack.canUndo():
            self.undo_stack.undo()
            print(f"↩️ [撤销] 剩余: {self.undo_stack.count()}")
    
    def _on_redo(self):
        """重做"""
        if self.undo_stack.canRedo():
            self.undo_stack.redo()
            print(f"↪️ [重做] 剩余: {self.undo_stack.count()}")
    
    # ========================================================================
    #  工具栏控制
    # ========================================================================
    
    def show_at(self, x: int, y: int):
        """显示工具栏"""
        self.toolbar.move(x, y)
        self.toolbar.show()
    
    def hide(self):
        """隐藏工具栏"""
        self.toolbar.hide()
    
    def set_tool(self, tool_id: str):
        """设置当前工具(同步到工具栏UI)"""
        # 工具栏内部会处理按钮状态
        pass
