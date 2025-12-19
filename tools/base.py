"""
工具基类和上下文
"""

from dataclasses import dataclass
from PyQt6.QtGui import QColor
from PyQt6.QtCore import QPointF


@dataclass
class ToolContext:
    """
    工具上下文 - 包含工具所需的所有依赖
    """
    scene: object          # CanvasScene
    selection: object      # SelectionModel
    overlay: object        # OverlayPixmapItem
    undo: object           # SnapshotUndoStack
    color: QColor          # 当前颜色
    stroke_width: int      # 笔触宽度
    opacity: float         # 透明度 (0.0-1.0)


class Tool:
    """
    工具基类 - 所有绘图工具的父类
    """
    
    id = "base"  # 工具ID（子类必须重写）
    
    def on_press(self, pos: QPointF, button, ctx: ToolContext):
        """
        鼠标按下事件
        
        Args:
            pos: 鼠标位置（场景坐标）
            button: 鼠标按钮
            ctx: 工具上下文
        """
        pass
    
    def on_move(self, pos: QPointF, ctx: ToolContext):
        """
        鼠标移动事件
        
        Args:
            pos: 鼠标位置（场景坐标）
            ctx: 工具上下文
        """
        pass
    
    def on_release(self, pos: QPointF, ctx: ToolContext):
        """
        鼠标释放事件
        
        Args:
            pos: 鼠标位置（场景坐标）
            ctx: 工具上下文
        """
        pass
    
    def on_activate(self, ctx: ToolContext):
        """
        工具激活时调用
        
        Args:
            ctx: 工具上下文
        """
        pass
    
    def on_deactivate(self, ctx: ToolContext):
        """
        工具停用时调用
        
        Args:
            ctx: 工具上下文
        """
        pass
