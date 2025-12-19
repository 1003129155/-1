"""
图层编辑系统 - Layer Editor
功能:
1. 统一的图层编辑控制点系统
2. 支持拖拽调整图层属性
3. 可撤销的编辑操作
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Tuple
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QCursor


# ============================================================================
#  编辑控制点类型
# ============================================================================

class HandleType(Enum):
    """控制点类型"""
    # 通用类型
    CORNER_TL = "corner_tl"      # 左上角
    CORNER_TR = "corner_tr"      # 右上角
    CORNER_BR = "corner_br"      # 右下角
    CORNER_BL = "corner_bl"      # 左下角
    EDGE_T = "edge_t"            # 上边
    EDGE_R = "edge_r"            # 右边
    EDGE_B = "edge_b"            # 下边
    EDGE_L = "edge_l"            # 左边
    CENTER = "center"            # 中心(移动)
    
    # 特殊类型
    ARROW_START = "arrow_start"  # 箭头起点
    ARROW_END = "arrow_end"      # 箭头终点
    ARROW_HEAD = "arrow_head"    # 箭头头部
    
    # 路径类型
    PATH_POINT = "path_point"    # 路径点(自由画笔)


@dataclass
class EditHandle:
    """
    编辑控制点
    
    属性:
        id: 唯一标识
        handle_type: 控制点类型
        position: 当前位置
        cursor: 鼠标光标样式
        size: 显示大小(px)
    """
    id: int
    handle_type: HandleType
    position: QPointF
    cursor: Qt.CursorShape = Qt.CursorShape.ArrowCursor
    size: int = 8
    
    def get_rect(self) -> QRectF:
        """获取控制点的矩形区域(用于命中测试)"""
        half = self.size / 2
        return QRectF(
            self.position.x() - half,
            self.position.y() - half,
            self.size,
            self.size
        )
    
    def contains(self, pos: QPointF) -> bool:
        """检查点是否在控制点内"""
        return self.get_rect().contains(pos)


# ============================================================================
#  图层编辑器
# ============================================================================

class LayerEditor:
    """
    图层编辑器 - 统一的图层编辑控制点管理
    
    职责:
    - 管理当前编辑的图层
    - 生成和渲染编辑控制点
    - 处理控制点的拖拽逻辑
    - 提供撤销/重做支持
    
    使用流程:
    1. start_edit(layer) - 开始编辑某个图层
    2. hit_test(pos) - 检测鼠标是否点击控制点
    3. start_drag(handle_id) - 开始拖拽
    4. drag_to(pos) - 拖拽到新位置
    5. end_drag() - 结束拖拽,返回修改后的图层
    """
    
    # 配置
    HANDLE_SIZE = 8           # 控制点大小
    HANDLE_COLOR = QColor(0, 120, 215)      # 蓝色
    HANDLE_FILL = QColor(255, 255, 255)     # 白色填充
    HOVER_COLOR = QColor(255, 120, 0)       # 橙色(悬停)
    
    def __init__(self):
        # 当前编辑状态
        self.active_layer = None
        self.handles: List[EditHandle] = []
        
        # 拖拽状态
        self.dragging_handle: Optional[EditHandle] = None
        self.drag_start_pos: Optional[QPointF] = None
        self.initial_layer_state = None  # 拖拽前的图层状态字典(用于撤销)
        self.initial_layer = None  # 拖拽前的图层副本(用于重置)
        
        # 悬停状态
        self.hovered_handle: Optional[EditHandle] = None
    
    # ========================================================================
    #  编辑会话管理
    # ========================================================================
    
    def start_edit(self, layer) -> bool:
        """
        开始编辑图层
        
        Args:
            layer: 要编辑的图层
            
        Returns:
            是否成功(某些图层可能不支持编辑)
        """
        if not layer:
            return False
        
        self.active_layer = layer
        self.handles = self._generate_handles(layer)
        
        if not self.handles:
            self.active_layer = None
            return False
        
        print(f"🎨 [LayerEditor] 开始编辑图层: {layer.__class__.__name__}, 控制点数: {len(self.handles)}")
        return True
    
    def stop_edit(self):
        """停止编辑"""
        self.active_layer = None
        self.handles = []
        self.dragging_handle = None
        self.hovered_handle = None
    
    def is_editing(self) -> bool:
        """是否正在编辑"""
        return self.active_layer is not None
    
    # ========================================================================
    #  控制点生成
    # ========================================================================
    
    def _generate_handles(self, layer) -> List[EditHandle]:
        """
        为图层生成编辑控制点
        
        Args:
            layer: 图层对象
            
        Returns:
            控制点列表
        """
        # 检查图层是否实现了 get_edit_handles 方法
        if hasattr(layer, 'get_edit_handles'):
            return layer.get_edit_handles()
        
        # 默认实现:为矩形图层生成8个控制点
        from canvas.document import RectLayer, EllipseLayer, MosaicLayer
        
        if isinstance(layer, (RectLayer, EllipseLayer, MosaicLayer)):
            return self._generate_rect_handles(layer.rect)
        
        return []
    
    def _generate_rect_handles(self, rect: QRectF) -> List[EditHandle]:
        """为矩形生成8个控制点"""
        handles = []
        
        # 四个角
        handles.append(EditHandle(
            0, HandleType.CORNER_TL,
            rect.topLeft(),
            Qt.CursorShape.SizeFDiagCursor
        ))
        handles.append(EditHandle(
            1, HandleType.CORNER_TR,
            rect.topRight(),
            Qt.CursorShape.SizeBDiagCursor
        ))
        handles.append(EditHandle(
            2, HandleType.CORNER_BR,
            rect.bottomRight(),
            Qt.CursorShape.SizeFDiagCursor
        ))
        handles.append(EditHandle(
            3, HandleType.CORNER_BL,
            rect.bottomLeft(),
            Qt.CursorShape.SizeBDiagCursor
        ))
        
        # 四条边
        handles.append(EditHandle(
            4, HandleType.EDGE_T,
            QPointF(rect.center().x(), rect.top()),
            Qt.CursorShape.SizeVerCursor
        ))
        handles.append(EditHandle(
            5, HandleType.EDGE_R,
            QPointF(rect.right(), rect.center().y()),
            Qt.CursorShape.SizeHorCursor
        ))
        handles.append(EditHandle(
            6, HandleType.EDGE_B,
            QPointF(rect.center().x(), rect.bottom()),
            Qt.CursorShape.SizeVerCursor
        ))
        handles.append(EditHandle(
            7, HandleType.EDGE_L,
            QPointF(rect.left(), rect.center().y()),
            Qt.CursorShape.SizeHorCursor
        ))
        
        return handles
    
    # ========================================================================
    #  命中测试
    # ========================================================================
    
    def hit_test(self, pos: QPointF) -> Optional[EditHandle]:
        """
        命中测试 - 检查鼠标是否点击控制点
        
        Args:
            pos: 鼠标位置
            
        Returns:
            被点击的控制点,或None
        """
        for handle in self.handles:
            if handle.contains(pos):
                return handle
        return None
    
    def update_hover(self, pos: QPointF):
        """更新悬停状态"""
        self.hovered_handle = self.hit_test(pos)
    
    def get_cursor(self, pos: QPointF) -> Qt.CursorShape:
        """
        获取当前位置应该显示的光标
        
        Args:
            pos: 鼠标位置
            
        Returns:
            光标样式
        """
        handle = self.hit_test(pos)
        if handle:
            return handle.cursor
        return Qt.CursorShape.ArrowCursor
    
    # ========================================================================
    #  拖拽操作
    # ========================================================================
    
    def start_drag(self, handle: EditHandle, pos: QPointF):
        """
        开始拖拽控制点
        
        Args:
            handle: 被拖拽的控制点
            pos: 起始位置
        """
        self.dragging_handle = handle
        self.drag_start_pos = pos
        
        # 保存初始状态(用于撤销和重置)
        self.initial_layer_state = self._copy_layer_state(self.active_layer)
        
        # 保存初始图层的完整副本(用于每次计算delta)
        self.initial_layer = self.active_layer.clone()
        
        print(f"🖱️ [LayerEditor] 开始拖拽: {handle.handle_type.value}")
    
    def drag_to(self, pos: QPointF, keep_ratio: bool = False):
        """
        拖拽到新位置
        
        Args:
            pos: 当前位置
            keep_ratio: 是否保持比例(Shift键)
        """
        if not self.dragging_handle or not self.drag_start_pos or not self.initial_layer:
            return
        
        # 计算总偏移量(相对于初始位置)
        delta = pos - self.drag_start_pos
        
        # 恢复到初始状态
        self._restore_layer_state(self.active_layer, self.initial_layer)
        
        # 应用拖拽到图层
        self._apply_handle_drag(
            self.active_layer,
            self.dragging_handle,
            delta,
            keep_ratio
        )
        
        # 更新控制点位置
        self.handles = self._generate_handles(self.active_layer)
    
    def end_drag(self) -> Tuple[any, any]:
        """
        结束拖拽
        
        Returns:
            (旧图层状态, 新图层状态) 用于生成撤销命令
        """
        old_state = self.initial_layer_state
        new_state = self._copy_layer_state(self.active_layer)
        
        self.dragging_handle = None
        self.drag_start_pos = None
        self.initial_layer_state = None
        self.initial_layer = None  # 清理初始图层副本
        
        return old_state, new_state
    
    # ========================================================================
    #  拖拽算法
    # ========================================================================
    
    def _apply_handle_drag(self, layer, handle: EditHandle, delta: QPointF, keep_ratio: bool):
        """
        应用控制点拖拽到图层
        
        Args:
            layer: 图层对象
            handle: 被拖拽的控制点
            delta: 偏移量
            keep_ratio: 是否保持比例
        """
        # 优先使用图层自己的实现
        if hasattr(layer, 'apply_handle_drag'):
            layer.apply_handle_drag(handle.id, delta, keep_ratio)
            return
        
        # 默认实现:矩形图层的8控制点调整
        from canvas.document import RectLayer, EllipseLayer, MosaicLayer
        
        if isinstance(layer, (RectLayer, EllipseLayer, MosaicLayer)):
            self._apply_rect_handle_drag(layer, handle, delta, keep_ratio)
    
    def _apply_rect_handle_drag(self, layer, handle: EditHandle, delta: QPointF, keep_ratio: bool):
        """应用矩形控制点拖拽"""
        rect = layer.rect
        
        # 根据控制点类型调整矩形
        if handle.handle_type == HandleType.CORNER_TL:
            rect.setTopLeft(rect.topLeft() + delta)
        elif handle.handle_type == HandleType.CORNER_TR:
            rect.setTopRight(rect.topRight() + delta)
        elif handle.handle_type == HandleType.CORNER_BR:
            rect.setBottomRight(rect.bottomRight() + delta)
        elif handle.handle_type == HandleType.CORNER_BL:
            rect.setBottomLeft(rect.bottomLeft() + delta)
        elif handle.handle_type == HandleType.EDGE_T:
            rect.setTop(rect.top() + delta.y())
        elif handle.handle_type == HandleType.EDGE_R:
            rect.setRight(rect.right() + delta.x())
        elif handle.handle_type == HandleType.EDGE_B:
            rect.setBottom(rect.bottom() + delta.y())
        elif handle.handle_type == HandleType.EDGE_L:
            rect.setLeft(rect.left() + delta.x())
        
        # 确保矩形合法
        rect = rect.normalized()
        
        # 应用回图层
        layer.rect = rect
    
    # ========================================================================
    #  渲染
    # ========================================================================
    
    def render(self, painter: QPainter):
        """
        渲染编辑控制点
        
        Args:
            painter: QPainter实例
        """
        if not self.is_editing():
            return
        
        painter.save()
        
        for handle in self.handles:
            # 判断是否悬停
            is_hovered = (self.hovered_handle and 
                         self.hovered_handle.id == handle.id)
            
            # 选择颜色
            border_color = self.HOVER_COLOR if is_hovered else self.HANDLE_COLOR
            
            # 绘制控制点
            pen = QPen(border_color, 2)
            brush = QBrush(self.HANDLE_FILL)
            painter.setPen(pen)
            painter.setBrush(brush)
            painter.drawRect(handle.get_rect())
        
        painter.restore()
    
    # ========================================================================
    #  辅助方法
    # ========================================================================
    
    def _copy_layer_state(self, layer):
        """
        复制图层状态(用于撤销)
        
        Returns:
            状态字典 {属性名: 值}
        """
        if not layer:
            return None
        
        from canvas.document import RectLayer, EllipseLayer, ArrowLayer, MosaicLayer
        
        state = {}
        
        # 根据图层类型复制关键属性
        if isinstance(layer, (RectLayer, EllipseLayer, MosaicLayer)):
            state['rect'] = QRectF(layer.rect)  # 深拷贝 QRectF
        elif isinstance(layer, ArrowLayer):
            state['start'] = QPointF(layer.start)  # 深拷贝 QPointF
            state['end'] = QPointF(layer.end)
            state['arrow_size'] = layer.arrow_size
        
        return state
    
    def _restore_layer_state(self, target_layer, source_layer):
        """
        从源图层恢复目标图层的状态
        
        Args:
            target_layer: 目标图层(要修改的)
            source_layer: 源图层(参考的)
        """
        from canvas.document import RectLayer, EllipseLayer, ArrowLayer, MosaicLayer
        
        if isinstance(target_layer, (RectLayer, EllipseLayer, MosaicLayer)):
            target_layer.rect = QRectF(source_layer.rect)
        elif isinstance(target_layer, ArrowLayer):
            target_layer.start = QPointF(source_layer.start)
            target_layer.end = QPointF(source_layer.end)
            target_layer.arrow_size = source_layer.arrow_size


# 测试函数
def test_layer_editor():
    """测试LayerEditor"""
    print("🧪 测试 LayerEditor")
    
    from canvas.document import RectLayer, DrawStyle
    from PyQt6.QtGui import QColor
    
    # 创建测试图层
    style = DrawStyle(color=QColor(255, 0, 0), stroke_width=3)
    rect_layer = RectLayer(QRectF(100, 100, 200, 150), style)
    
    # 创建编辑器
    editor = LayerEditor()
    
    # 开始编辑
    success = editor.start_edit(rect_layer)
    print(f"✅ 开始编辑: {success}")
    print(f"   控制点数量: {len(editor.handles)}")
    
    # 测试命中
    handle = editor.hit_test(QPointF(100, 100))
    print(f"✅ 命中测试: {handle.handle_type.value if handle else 'None'}")
    
    # 测试拖拽
    if handle:
        editor.start_drag(handle, QPointF(100, 100))
        editor.drag_to(QPointF(120, 120))
        old, new = editor.end_drag()
        print(f"✅ 拖拽完成")
        print(f"   原始大小: {old.rect.size()}")
        print(f"   新大小: {new.rect.size()}")


if __name__ == "__main__":
    test_layer_editor()
