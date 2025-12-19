"""
画布场景 - 管理所有图层和绘图工具
"""

from PyQt6.QtWidgets import QGraphicsScene
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor

from .items import BackgroundItem, OverlayMaskItem, SelectionItem, OverlayPixmapItem
from .model import SelectionModel
from .undo import SnapshotUndoStack
from tools import ToolController, ToolContext
from tools import PenTool, RectTool, EllipseTool, ArrowTool
from tools import TextTool, NumberTool, HighlighterTool, MosaicTool


class CanvasScene(QGraphicsScene):
    """
    画布场景
    """
    
    selectionConfirmed = pyqtSignal()  # 选区确认信号
    
    def __init__(self, background_image, scene_rect):
        """
        Args:
            background_image: QImage - 背景图像
            scene_rect: QRectF - 场景坐标范围
        """
        super().__init__()
        
        from PyQt6.QtCore import QRectF
        self.scene_rect = QRectF(scene_rect)
        
        # 先创建选区模型
        self.selection_model = SelectionModel()
        
        # 创建图层（传入model）
        self.background = BackgroundItem(background_image, self.scene_rect)
        self.overlay_mask = OverlayMaskItem(self.scene_rect, self.selection_model)
        self.selection_item = SelectionItem(self.selection_model)
        self.overlay_pixmap = OverlayPixmapItem(self.scene_rect)
        
        self.addItem(self.background)
        self.addItem(self.overlay_mask)
        self.addItem(self.selection_item)
        self.addItem(self.overlay_pixmap)
        
        # 设置场景范围
        self.setSceneRect(self.background.boundingRect())
        
        # 撤销栈
        self.undo_stack = SnapshotUndoStack()
        
        # 工具控制器
        ctx = ToolContext(
            scene=self,
            selection=self.selection_model,
            overlay=self.overlay_pixmap,
            undo=self.undo_stack,
            color=QColor(255, 0, 0),
            stroke_width=3,
            opacity=1.0
        )
        self.tool_controller = ToolController(ctx)
        
        # 注册工具
        self.tool_controller.register(PenTool())
        self.tool_controller.register(RectTool())
        self.tool_controller.register(EllipseTool())
        self.tool_controller.register(ArrowTool())
        self.tool_controller.register(TextTool())
        self.tool_controller.register(NumberTool())
        self.tool_controller.register(HighlighterTool())
        self.tool_controller.register(MosaicTool())
        
        # 默认激活画笔工具
        self.tool_controller.activate("pen")
    
    def confirm_selection(self):
        """
        确认选区
        """
        self.selection_model.confirm()
        
        # 只隐藏选区框(8个控制点),不隐藏遮罩
        # 遮罩需要保持显示,在选区挖洞状态
        self.selection_item.hide()
        
        # 初始化撤销系统(用当前overlay图像作为初始状态)
        self.undo_stack.init_with_image(self.overlay_pixmap.image())
        
        self.selectionConfirmed.emit()

    
    def activate_tool(self, tool_id: str):
        """
        激活工具
        """
        self.tool_controller.activate(tool_id)
    
    def update_style(self, **kwargs):
        """
        更新样式
        """
        self.tool_controller.update_style(**kwargs)
