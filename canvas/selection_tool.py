"""
选择工具 - 选中和移动图层
"""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from .tools_v2 import Tool, ToolContext
from .document import Layer
from .commands import UpdateLayerCommand
from .layer_editor import LayerEditor, EditHandle
from .edit_layer_command import EditLayerHandleCommand


class SelectionTool(Tool):
    """
    选择工具 - 选中和移动图层
    
    功能:
    1. 点击图层 → 选中(显示包围框)
    2. 拖拽选中的图层 → 移动
    3. 双击图层 → 进入编辑模式(显示控制点)
    4. 拖拽控制点 → 调整图层形状
    5. 点击空白 → 取消选中
    """
    
    def __init__(self):
        super().__init__("selection", "选择")
        self.selected_layer: Layer = None
        self.dragging = False
        self.drag_start_pos = None
        self.layer_original_state = None
        
        # 编辑模式相关
        self.editing = False
        self.layer_editor = LayerEditor()
        self.editing_handle: EditHandle = None
        self.last_click_time = 0  # 用于双击检测
    
    def on_press(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """鼠标按下"""
        import time
        
        # 如果正在编辑模式
        if self.editing and self.selected_layer:
            # 检测是否点击了控制点
            handle = self.layer_editor.hit_test(pos)
            if handle:
                # 开始拖拽控制点
                self.editing_handle = handle
                self.layer_editor.start_drag(handle, pos)
                ctx.canvas_widget.setCursor(handle.cursor)
                print(f"[SelectionTool] 开始拖拽控制点: {handle.handle_type.name}")
                return
            else:
                # 点击空白,退出编辑模式
                self._exit_edit_mode(ctx)
        
        # 命中测试:查找点击的图层
        hit_layer = ctx.document.hit_test_layer(pos)
        
        if hit_layer:
            # 双击检测
            current_time = time.time()
            is_double_click = (current_time - self.last_click_time < 0.3 and 
                              self.selected_layer is hit_layer)
            self.last_click_time = current_time
            
            if is_double_click:
                # 双击 → 进入编辑模式
                self._enter_edit_mode(hit_layer, ctx)
                print(f"[SelectionTool] 双击进入编辑模式: {hit_layer.__class__.__name__}")
            else:
                # 单击 → 选中图层(退出之前的编辑模式)
                if self.editing:
                    self._exit_edit_mode(ctx)
                
                self.selected_layer = hit_layer
                ctx.document.set_active_layer(hit_layer.id)
                
                # 准备拖拽移动
                self.dragging = True
                self.drag_start_pos = pos
                self.layer_original_state = hit_layer.clone()
                
                print(f"[SelectionTool] 选中图层: {hit_layer.__class__.__name__} (ID:{hit_layer.id})")
        else:
            # 取消选中
            if self.editing:
                self._exit_edit_mode(ctx)
            self.selected_layer = None
            ctx.document.set_active_layer(None)
            print(f"[SelectionTool] 取消选中")
    
    def on_move(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """鼠标移动"""
        # 如果在拖拽控制点
        if self.editing and self.editing_handle:
            # 按住Shift保持比例
            keep_ratio = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self.layer_editor.drag_to(pos, keep_ratio)
            ctx.document.update_layer(self.selected_layer.id)
            return
        
        # 如果在拖拽移动图层
        if self.dragging and self.selected_layer and not self.editing:
            # 计算偏移
            dx = pos.x() - self.drag_start_pos.x()
            dy = pos.y() - self.drag_start_pos.y()
            
            # 移动图层
            self._move_layer(self.selected_layer, dx, dy)
            
            # 触发重绘
            ctx.document.update_layer(self.selected_layer.id)
    
    def on_release(self, pos: QPointF, event: QMouseEvent, ctx: ToolContext):
        """鼠标松开"""
        # 如果在拖拽控制点
        if self.editing and self.editing_handle:
            # 完成拖拽,推入命令
            old_state, new_state = self.layer_editor.end_drag()
            if old_state and new_state:
                layer_index = ctx.document.layers.index(self.selected_layer)
                cmd = EditLayerHandleCommand(ctx.document, layer_index, old_state, new_state)
                ctx.undo_stack.push(cmd)
                print(f"[SelectionTool] 完成控制点拖拽")
            
            self.editing_handle = None
            ctx.canvas_widget.setCursor(Qt.CursorShape.ArrowCursor)
            return
        
        # 如果在拖拽移动图层
        if self.dragging and self.selected_layer and self.layer_original_state:
            # 计算最终偏移
            dx = pos.x() - self.drag_start_pos.x()
            dy = pos.y() - self.drag_start_pos.y()
            
            # 如果有移动,推入命令
            if abs(dx) > 1 or abs(dy) > 1:
                # 创建更新后的图层状态
                new_layer = self.layer_original_state.clone()
                self._move_layer(new_layer, dx, dy)
                
                # 推入更新命令
                cmd = UpdateLayerCommand(
                    ctx.document,
                    self.selected_layer.id,
                    self.layer_original_state,
                    new_layer
                )
                ctx.undo_stack.push(cmd)
                
                print(f"[SelectionTool] 移动图层: dx={dx:.1f}, dy={dy:.1f}")
        
        # 重置状态
        self.dragging = False
        self.drag_start_pos = None
        self.layer_original_state = None
    
    def render(self, painter, ctx: ToolContext):
        """渲染选中的图层(包围框/控制点)"""
        if not self.selected_layer:
            return
        
        # 如果在编辑模式,渲染控制点
        if self.editing:
            self.layer_editor.render(painter)
        else:
            # 否则渲染包围框
            from PyQt6.QtGui import QPen, QColor
            from PyQt6.QtCore import Qt
            
            pen = QPen(QColor(0, 120, 215), 2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            bounds = self.selected_layer.bounds()
            painter.drawRect(bounds)
    
    def _enter_edit_mode(self, layer: Layer, ctx: ToolContext):
        """进入编辑模式"""
        self.editing = True
        self.selected_layer = layer
        self.layer_editor.start_edit(layer)
        ctx.document.set_active_layer(layer.id)
        
    def _exit_edit_mode(self, ctx: ToolContext):
        """退出编辑模式"""
        self.editing = False
        self.editing_handle = None
        ctx.canvas_widget.setCursor(Qt.CursorShape.ArrowCursor)
    
    def _move_layer(self, layer: Layer, dx: float, dy: float):
        """
        移动图层位置
        
        根据图层类型移动其关键点
        """
        from .document import (
            StrokeLayer, RectLayer, EllipseLayer, ArrowLayer,
            TextLayer, NumberLayer, HighlighterLayer, MosaicLayer
        )
        
        if isinstance(layer, (StrokeLayer, HighlighterLayer)):
            # 画笔/荧光笔:移动所有点
            for i in range(len(layer.points)):
                layer.points[i] = QPointF(
                    layer.points[i].x() + dx,
                    layer.points[i].y() + dy
                )
        
        elif isinstance(layer, (RectLayer, EllipseLayer, MosaicLayer)):
            # 矩形/椭圆/马赛克:移动矩形
            layer.rect.translate(dx, dy)
        
        elif isinstance(layer, ArrowLayer):
            # 箭头:移动起点和终点
            layer.start = QPointF(layer.start.x() + dx, layer.start.y() + dy)
            layer.end = QPointF(layer.end.x() + dx, layer.end.y() + dy)
        
        elif isinstance(layer, (TextLayer, NumberLayer)):
            # 文字/序号:移动位置
            layer.pos = QPointF(layer.pos.x() + dx, layer.pos.y() + dy)
