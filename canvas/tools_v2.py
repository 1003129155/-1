"""
工具系统 V2 - 基于Document的新架构
专业做法:拖拽时预览,松开时push command
"""

from abc import ABC, abstractmethod
from typing import Optional
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QUndoStack

from .document import Document, Layer, LayerStyle


class ToolContext:
    """
    工具上下文 - 传递给工具的环境
    
    包含:
    - document: 数据模型
    - undo_stack: 撤销栈
    - style: 当前样式
    - canvas: 画布(用于更新显示)
    """
    
    def __init__(
        self,
        document: Document,
        undo_stack: QUndoStack,
        style: LayerStyle,
        canvas=None
    ):
        self.document = document
        self.undo_stack = undo_stack
        self.style = style
        self.canvas = canvas
    
    def update_style(self, **kwargs):
        """
        更新样式
        
        Args:
            color: QColor
            stroke_width: int
            opacity: float
        """
        if 'color' in kwargs:
            self.style.color = kwargs['color']
        if 'stroke_width' in kwargs:
            self.style.stroke_width = kwargs['stroke_width']
        if 'opacity' in kwargs:
            self.style.opacity = kwargs['opacity']


class Tool(ABC):
    """
    工具基类 - 状态机模式
    
    核心理念:
    1. 拖拽时创建preview_layer,不修改document
    2. 鼠标松开时,将preview_layer封装成Command推入undo_stack
    3. 所有对document的修改都通过Command
    
    生命周期:
    - on_press: 开始操作,创建preview_layer
    - on_move: 更新preview_layer,触发重绘
    - on_release: 提交命令,清除preview
    - on_cancel: 取消操作,清除preview
    """
    
    def __init__(self, tool_id: str, name: str):
        self.id = tool_id
        self.name = name
        self.active = False
        
        # 预览图层(拖拽中)
        self.preview_layer: Optional[Layer] = None
    
    # ========================================================================
    #  抽象方法 - 子类必须实现
    # ========================================================================
    
    @abstractmethod
    def on_press(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """
        鼠标按下
        
        Args:
            pos: 位置
            event: 鼠标事件
            ctx: 工具上下文
        """
        pass
    
    @abstractmethod
    def on_move(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """
        鼠标移动
        
        Args:
            pos: 位置
            event: 鼠标事件
            ctx: 工具上下文
        """
        pass
    
    @abstractmethod
    def on_release(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """
        鼠标松开
        
        Args:
            pos: 位置
            event: 鼠标事件
            ctx: 工具上下文
        """
        pass
    
    # ========================================================================
    #  可选方法
    # ========================================================================
    
    def on_cancel(self, ctx: ToolContext):
        """取消操作(ESC)"""
        if self.preview_layer and ctx.canvas:
            ctx.canvas.clear_preview()
        self.preview_layer = None
    
    def on_key_press(self, event: QKeyEvent, ctx: ToolContext):
        """键盘按下"""
        if event.key() == 16777216:  # ESC
            self.on_cancel(ctx)
    
    def on_activate(self, ctx: ToolContext):
        """工具被激活"""
        self.active = True
    
    def on_deactivate(self, ctx: ToolContext):
        """工具被停用"""
        self.active = False
        self.on_cancel(ctx)
    
    # ========================================================================
    #  辅助方法
    # ========================================================================
    
    def set_preview(self, layer: Layer, ctx: ToolContext):
        """设置预览图层"""
        self.preview_layer = layer
        if ctx.canvas:
            ctx.canvas.set_preview_layer(layer)
    
    def clear_preview(self, ctx: ToolContext):
        """清除预览"""
        self.preview_layer = None
        if ctx.canvas:
            ctx.canvas.clear_preview()
    
    def push_layer(self, layer: Layer, ctx: ToolContext):
        """
        推入图层命令
        
        这是提交图层的唯一入口!
        """
        from .commands import AddLayerCommand
        cmd = AddLayerCommand(ctx.document, layer)
        ctx.undo_stack.push(cmd)


class ToolController:
    """
    工具控制器 - 管理工具注册/切换
    """
    
    def __init__(self, context: ToolContext):
        self.context = context
        self.tools = {}  # {tool_id: Tool}
        self.active_tool: Optional[Tool] = None
        
        print("[ToolController] 初始化")
    
    def register(self, tool: Tool):
        """注册工具"""
        self.tools[tool.id] = tool
        print(f"[ToolController] 注册工具: {tool.id}")
    
    def activate(self, tool_id: str):
        """激活工具"""
        if tool_id not in self.tools:
            print(f"⚠️ [ToolController] 工具不存在: {tool_id}")
            return
        
        # 停用当前工具
        if self.active_tool:
            self.active_tool.on_deactivate(self.context)
        
        # 激活新工具
        self.active_tool = self.tools[tool_id]
        self.active_tool.on_activate(self.context)
        
        print(f"[ToolController] 激活工具: {tool_id}")
    
    def get_active(self) -> Optional[Tool]:
        """获取当前工具"""
        return self.active_tool
    
    def update_style(self, **kwargs):
        """更新样式"""
        self.context.update_style(**kwargs)
    
    # ========================================================================
    #  事件转发
    # ========================================================================
    
    def on_press(self, pos: QPointF, event: QMouseEvent):
        """转发鼠标按下"""
        if self.active_tool:
            self.active_tool.on_press(pos, event, self.context)
    
    def on_move(self, pos: QPointF, event: QMouseEvent):
        """转发鼠标移动"""
        if self.active_tool:
            self.active_tool.on_move(pos, event, self.context)
    
    def on_release(self, pos: QPointF, event: QMouseEvent):
        """转发鼠标松开"""
        if self.active_tool:
            self.active_tool.on_release(pos, event, self.context)
    
    def on_key_press(self, event: QKeyEvent):
        """转发键盘按下"""
        if self.active_tool:
            self.active_tool.on_key_press(event, self.context)
