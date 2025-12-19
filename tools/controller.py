"""
工具控制器 - 管理工具切换和事件分发
"""

from PyQt6.QtCore import QPointF
from .base import Tool, ToolContext


class ToolController:
    """
    工具控制器
    """
    
    def __init__(self, ctx: ToolContext):
        self.ctx = ctx
        self.tools = {}  # 工具ID -> Tool实例
        self.current_tool = None
        
        print("[ToolController] 初始化")
    
    def register(self, tool: Tool):
        """
        注册工具
        
        Args:
            tool: 工具实例
        """
        self.tools[tool.id] = tool
        print(f"[ToolController] 注册工具: {tool.id}")
    
    def activate(self, tool_id: str):
        """
        激活工具
        
        Args:
            tool_id: 工具ID
        """
        if tool_id not in self.tools:
            print(f"[ToolController] 工具不存在: {tool_id}")
            return
        
        # 停用旧工具
        if self.current_tool:
            self.current_tool.on_deactivate(self.ctx)
        
        # 激活新工具
        self.current_tool = self.tools[tool_id]
        self.current_tool.on_activate(self.ctx)
        
        print(f"[ToolController] 激活工具: {tool_id}")
    
    def on_press(self, pos: QPointF, button):
        """
        鼠标按下事件
        """
        if self.current_tool:
            self.current_tool.on_press(pos, button, self.ctx)
    
    def on_move(self, pos: QPointF):
        """
        鼠标移动事件
        """
        if self.current_tool:
            self.current_tool.on_move(pos, self.ctx)
    
    def on_release(self, pos: QPointF):
        """
        鼠标释放事件
        """
        if self.current_tool:
            self.current_tool.on_release(pos, self.ctx)
    
    def update_style(self, color=None, width=None, opacity=None):
        """
        更新样式参数
        
        Args:
            color: 颜色
            width: 笔触宽度
            opacity: 透明度
        """
        if color is not None:
            self.ctx.color = color
        if width is not None:
            self.ctx.stroke_width = width
        if opacity is not None:
            self.ctx.opacity = opacity
