"""
Document 数据模型 - 专业截图软件架构
纯数据模型,不包含UI逻辑
"""

from typing import List, Optional
from dataclasses import dataclass
from PyQt6.QtCore import QRectF, QPointF, Qt, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QColor


# ============================================================================
#  图层基类
# ============================================================================

@dataclass
class LayerStyle:
    """图层样式"""
    color: QColor
    stroke_width: int = 3
    opacity: float = 1.0  # 0.0 - 1.0


class Layer:
    """
    图层基类 - 向量数据(不是位图!)
    每个图层存储绘制参数,在paintEvent时动态渲染
    
    新增功能:
    - get_edit_handles(): 返回编辑控制点(用于二次编辑)
    - apply_handle_drag(): 应用控制点拖拽
    """
    _next_id = 1
    
    def __init__(self, style: LayerStyle):
        self.id = Layer._next_id
        Layer._next_id += 1
        
        self.style = style
        self.visible = True
        self.locked = False
    
    def bounds(self) -> QRectF:
        """图层包围框(用于选中高亮、命中测试)"""
        raise NotImplementedError
    
    def contains_point(self, pt: QPointF) -> bool:
        """点击测试"""
        return self.bounds().contains(pt)
    
    def clone(self):
        """克隆图层(用于撤销系统)"""
        raise NotImplementedError
    
    # ========================================================================
    #  图层编辑接口 (二次编辑功能)
    # ========================================================================
    
    def get_edit_handles(self) -> List:
        """
        返回编辑控制点列表
        
        Returns:
            List[EditHandle]: 控制点列表(来自 layer_editor.py)
            
        Note:
            子类可以重写此方法提供自定义控制点
            返回空列表表示不支持编辑
        """
        return []
    
    def apply_handle_drag(self, handle_id: int, delta: QPointF, keep_ratio: bool = False):
        """
        应用控制点拖拽
        
        Args:
            handle_id: 控制点ID
            delta: 拖拽偏移量
            keep_ratio: 是否保持比例(Shift键)
            
        Note:
            子类应该重写此方法实现具体的拖拽逻辑
        """
        pass


# ============================================================================
#  具体图层类型
# ============================================================================

class StrokeLayer(Layer):
    """画笔图层 - 存储路径点列表"""
    
    def __init__(self, style: LayerStyle, points: List[QPointF] = None):
        super().__init__(style)
        self.points = points or []
    
    def add_point(self, pt: QPointF):
        self.points.append(pt)
    
    def bounds(self) -> QRectF:
        if not self.points:
            return QRectF()
        
        xs = [p.x() for p in self.points]
        ys = [p.y() for p in self.points]
        padding = self.style.stroke_width
        
        return QRectF(
            min(xs) - padding,
            min(ys) - padding,
            max(xs) - min(xs) + padding * 2,
            max(ys) - min(ys) + padding * 2
        )
    
    def clone(self):
        return StrokeLayer(self.style, self.points.copy())


class RectLayer(Layer):
    """矩形图层"""
    
    def __init__(self, style: LayerStyle, rect: QRectF = None):
        super().__init__(style)
        self.rect = rect or QRectF()
        self.filled = False
    
    def bounds(self) -> QRectF:
        padding = self.style.stroke_width
        return self.rect.adjusted(-padding, -padding, padding, padding)
    
    def clone(self):
        layer = RectLayer(self.style, QRectF(self.rect))
        layer.filled = self.filled
        return layer
    
    def get_edit_handles(self):
        """返回8个控制点:4角+4边"""
        from canvas.layer_editor import EditHandle, HandleType
        from PyQt6.QtCore import Qt
        
        rect = self.rect
        handles = [
            # 四个角点
            EditHandle(0, HandleType.CORNER_TL, rect.topLeft(), Qt.CursorShape.SizeFDiagCursor),
            EditHandle(1, HandleType.CORNER_TR, rect.topRight(), Qt.CursorShape.SizeBDiagCursor),
            EditHandle(2, HandleType.CORNER_BR, rect.bottomRight(), Qt.CursorShape.SizeFDiagCursor),
            EditHandle(3, HandleType.CORNER_BL, rect.bottomLeft(), Qt.CursorShape.SizeBDiagCursor),
            # 四条边的中点
            EditHandle(4, HandleType.EDGE_T, QPointF(rect.center().x(), rect.top()), Qt.CursorShape.SizeVerCursor),
            EditHandle(5, HandleType.EDGE_R, QPointF(rect.right(), rect.center().y()), Qt.CursorShape.SizeHorCursor),
            EditHandle(6, HandleType.EDGE_B, QPointF(rect.center().x(), rect.bottom()), Qt.CursorShape.SizeVerCursor),
            EditHandle(7, HandleType.EDGE_L, QPointF(rect.left(), rect.center().y()), Qt.CursorShape.SizeHorCursor),
        ]
        return handles
    
    def apply_handle_drag(self, handle_id: int, delta: QPointF, keep_ratio: bool):
        """应用控制点拖拽"""
        from PyQt6.QtCore import QRectF
        
        # 保存原始rect用于比例计算
        orig_rect = QRectF(self.rect)
        orig_ratio = orig_rect.width() / orig_rect.height() if orig_rect.height() != 0 else 1.0
        
        # 根据控制点ID调整rect
        if handle_id == 0:  # 左上角
            new_left = orig_rect.left() + delta.x()
            new_top = orig_rect.top() + delta.y()
            if keep_ratio:
                # 保持比例,以中心为基准
                new_width = orig_rect.right() - new_left
                new_height = new_width / orig_ratio
                new_top = orig_rect.bottom() - new_height
            self.rect.setTopLeft(QPointF(new_left, new_top))
            
        elif handle_id == 1:  # 右上角
            new_right = orig_rect.right() + delta.x()
            new_top = orig_rect.top() + delta.y()
            if keep_ratio:
                new_width = new_right - orig_rect.left()
                new_height = new_width / orig_ratio
                new_top = orig_rect.bottom() - new_height
            self.rect.setTopRight(QPointF(new_right, new_top))
            
        elif handle_id == 2:  # 右下角
            new_right = orig_rect.right() + delta.x()
            new_bottom = orig_rect.bottom() + delta.y()
            if keep_ratio:
                new_width = new_right - orig_rect.left()
                new_height = new_width / orig_ratio
                new_bottom = orig_rect.top() + new_height
            self.rect.setBottomRight(QPointF(new_right, new_bottom))
            
        elif handle_id == 3:  # 左下角
            new_left = orig_rect.left() + delta.x()
            new_bottom = orig_rect.bottom() + delta.y()
            if keep_ratio:
                new_width = orig_rect.right() - new_left
                new_height = new_width / orig_ratio
                new_bottom = orig_rect.top() + new_height
            self.rect.setBottomLeft(QPointF(new_left, new_bottom))
            
        elif handle_id == 4:  # 上边
            new_top = orig_rect.top() + delta.y()
            if keep_ratio:
                new_height = orig_rect.bottom() - new_top
                new_width = new_height * orig_ratio
                center_x = orig_rect.center().x()
                self.rect = QRectF(center_x - new_width/2, new_top, new_width, new_height)
            else:
                self.rect.setTop(new_top)
                
        elif handle_id == 5:  # 右边
            new_right = orig_rect.right() + delta.x()
            if keep_ratio:
                new_width = new_right - orig_rect.left()
                new_height = new_width / orig_ratio
                center_y = orig_rect.center().y()
                self.rect = QRectF(orig_rect.left(), center_y - new_height/2, new_width, new_height)
            else:
                self.rect.setRight(new_right)
                
        elif handle_id == 6:  # 下边
            new_bottom = orig_rect.bottom() + delta.y()
            if keep_ratio:
                new_height = new_bottom - orig_rect.top()
                new_width = new_height * orig_ratio
                center_x = orig_rect.center().x()
                self.rect = QRectF(center_x - new_width/2, orig_rect.top(), new_width, new_height)
            else:
                self.rect.setBottom(new_bottom)
                
        elif handle_id == 7:  # 左边
            new_left = orig_rect.left() + delta.x()
            if keep_ratio:
                new_width = orig_rect.right() - new_left
                new_height = new_width / orig_ratio
                center_y = orig_rect.center().y()
                self.rect = QRectF(new_left, center_y - new_height/2, new_width, new_height)
            else:
                self.rect.setLeft(new_left)
        
        # 确保rect合法(宽高>0)
        self.rect = self.rect.normalized()


class EllipseLayer(Layer):
    """椭圆图层"""
    
    def __init__(self, style: LayerStyle, rect: QRectF = None):
        super().__init__(style)
        self.rect = rect or QRectF()
        self.filled = False
    
    def bounds(self) -> QRectF:
        padding = self.style.stroke_width
        return self.rect.adjusted(-padding, -padding, padding, padding)
    
    def clone(self):
        layer = EllipseLayer(self.style, QRectF(self.rect))
        layer.filled = self.filled
        return layer
    
    def get_edit_handles(self):
        """椭圆与矩形使用相同的8控制点"""
        from canvas.layer_editor import EditHandle, HandleType
        from PyQt6.QtCore import Qt
        
        rect = self.rect
        handles = [
            # 四个角点
            EditHandle(0, HandleType.CORNER_TL, rect.topLeft(), Qt.CursorShape.SizeFDiagCursor),
            EditHandle(1, HandleType.CORNER_TR, rect.topRight(), Qt.CursorShape.SizeBDiagCursor),
            EditHandle(2, HandleType.CORNER_BR, rect.bottomRight(), Qt.CursorShape.SizeFDiagCursor),
            EditHandle(3, HandleType.CORNER_BL, rect.bottomLeft(), Qt.CursorShape.SizeBDiagCursor),
            # 四条边的中点
            EditHandle(4, HandleType.EDGE_T, QPointF(rect.center().x(), rect.top()), Qt.CursorShape.SizeVerCursor),
            EditHandle(5, HandleType.EDGE_R, QPointF(rect.right(), rect.center().y()), Qt.CursorShape.SizeHorCursor),
            EditHandle(6, HandleType.EDGE_B, QPointF(rect.center().x(), rect.bottom()), Qt.CursorShape.SizeVerCursor),
            EditHandle(7, HandleType.EDGE_L, QPointF(rect.left(), rect.center().y()), Qt.CursorShape.SizeHorCursor),
        ]
        return handles
    
    def apply_handle_drag(self, handle_id: int, delta: QPointF, keep_ratio: bool):
        """应用控制点拖拽,与RectLayer相同逻辑"""
        from PyQt6.QtCore import QRectF
        
        orig_rect = QRectF(self.rect)
        orig_ratio = orig_rect.width() / orig_rect.height() if orig_rect.height() != 0 else 1.0
        
        if handle_id == 0:  # 左上角
            new_left = orig_rect.left() + delta.x()
            new_top = orig_rect.top() + delta.y()
            if keep_ratio:
                new_width = orig_rect.right() - new_left
                new_height = new_width / orig_ratio
                new_top = orig_rect.bottom() - new_height
            self.rect.setTopLeft(QPointF(new_left, new_top))
            
        elif handle_id == 1:  # 右上角
            new_right = orig_rect.right() + delta.x()
            new_top = orig_rect.top() + delta.y()
            if keep_ratio:
                new_width = new_right - orig_rect.left()
                new_height = new_width / orig_ratio
                new_top = orig_rect.bottom() - new_height
            self.rect.setTopRight(QPointF(new_right, new_top))
            
        elif handle_id == 2:  # 右下角
            new_right = orig_rect.right() + delta.x()
            new_bottom = orig_rect.bottom() + delta.y()
            if keep_ratio:
                new_width = new_right - orig_rect.left()
                new_height = new_width / orig_ratio
                new_bottom = orig_rect.top() + new_height
            self.rect.setBottomRight(QPointF(new_right, new_bottom))
            
        elif handle_id == 3:  # 左下角
            new_left = orig_rect.left() + delta.x()
            new_bottom = orig_rect.bottom() + delta.y()
            if keep_ratio:
                new_width = orig_rect.right() - new_left
                new_height = new_width / orig_ratio
                new_bottom = orig_rect.top() + new_height
            self.rect.setBottomLeft(QPointF(new_left, new_bottom))
            
        elif handle_id == 4:  # 上边
            new_top = orig_rect.top() + delta.y()
            if keep_ratio:
                new_height = orig_rect.bottom() - new_top
                new_width = new_height * orig_ratio
                center_x = orig_rect.center().x()
                self.rect = QRectF(center_x - new_width/2, new_top, new_width, new_height)
            else:
                self.rect.setTop(new_top)
                
        elif handle_id == 5:  # 右边
            new_right = orig_rect.right() + delta.x()
            if keep_ratio:
                new_width = new_right - orig_rect.left()
                new_height = new_width / orig_ratio
                center_y = orig_rect.center().y()
                self.rect = QRectF(orig_rect.left(), center_y - new_height/2, new_width, new_height)
            else:
                self.rect.setRight(new_right)
                
        elif handle_id == 6:  # 下边
            new_bottom = orig_rect.bottom() + delta.y()
            if keep_ratio:
                new_height = new_bottom - orig_rect.top()
                new_width = new_height * orig_ratio
                center_x = orig_rect.center().x()
                self.rect = QRectF(center_x - new_width/2, orig_rect.top(), new_width, new_height)
            else:
                self.rect.setBottom(new_bottom)
                
        elif handle_id == 7:  # 左边
            new_left = orig_rect.left() + delta.x()
            if keep_ratio:
                new_width = orig_rect.right() - new_left
                new_height = new_width / orig_ratio
                center_y = orig_rect.center().y()
                self.rect = QRectF(new_left, center_y - new_height/2, new_width, new_height)
            else:
                self.rect.setLeft(new_left)
        
        self.rect = self.rect.normalized()


class ArrowLayer(Layer):
    """箭头图层"""
    
    def __init__(self, style: LayerStyle, start: QPointF = None, end: QPointF = None):
        super().__init__(style)
        self.start = start or QPointF()
        self.end = end or QPointF()
        self.arrow_size = 15
    
    def bounds(self) -> QRectF:
        padding = max(self.style.stroke_width, self.arrow_size)
        x1, y1 = self.start.x(), self.start.y()
        x2, y2 = self.end.x(), self.end.y()
        
        return QRectF(
            min(x1, x2) - padding,
            min(y1, y2) - padding,
            abs(x2 - x1) + padding * 2,
            abs(y2 - y1) + padding * 2
        )
    
    def clone(self):
        layer = ArrowLayer(self.style, QPointF(self.start), QPointF(self.end))
        layer.arrow_size = self.arrow_size
        return layer
    
    def get_edit_handles(self):
        """返回3个控制点:起点、终点、箭头大小调节点"""
        from canvas.layer_editor import EditHandle, HandleType
        from PyQt6.QtCore import Qt
        
        # 计算箭头方向和调节点位置
        mid = QPointF((self.start.x() + self.end.x()) / 2, 
                      (self.start.y() + self.end.y()) / 2)
        
        handles = [
            EditHandle(0, HandleType.ARROW_START, self.start, Qt.CursorShape.SizeAllCursor),
            EditHandle(1, HandleType.ARROW_END, self.end, Qt.CursorShape.SizeAllCursor),
            EditHandle(2, HandleType.ARROW_HEAD, mid, Qt.CursorShape.PointingHandCursor),  # 箭头大小调节点
        ]
        return handles
    
    def apply_handle_drag(self, handle_id: int, delta: QPointF, keep_ratio: bool):
        """应用控制点拖拽"""
        if handle_id == 0:  # 起点
            self.start += delta
        elif handle_id == 1:  # 终点
            self.end += delta
        elif handle_id == 2:  # 箭头大小(通过拖拽中点垂直调整)
            # 使用垂直偏移量调整箭头大小
            self.arrow_size = max(5, min(50, self.arrow_size + delta.y() * 0.5))


class TextLayer(Layer):
    """文字图层"""
    
    def __init__(self, style: LayerStyle, pos: QPointF = None, text: str = ""):
        super().__init__(style)
        self.pos = pos or QPointF()
        self.text = text
        self.font_size = 16
    
    def bounds(self) -> QRectF:
        # 简化计算,实际应该用 QFontMetrics
        width = len(self.text) * self.font_size * 0.6
        height = self.font_size * 1.5
        return QRectF(self.pos.x(), self.pos.y(), width, height)
    
    def clone(self):
        layer = TextLayer(self.style, QPointF(self.pos), self.text)
        layer.font_size = self.font_size
        return layer


class NumberLayer(Layer):
    """序号图层"""
    
    def __init__(self, style: LayerStyle, pos: QPointF = None, number: int = 1):
        super().__init__(style)
        self.pos = pos or QPointF()
        self.number = number
        self.radius = 20
    
    def bounds(self) -> QRectF:
        return QRectF(
            self.pos.x() - self.radius,
            self.pos.y() - self.radius,
            self.radius * 2,
            self.radius * 2
        )
    
    def clone(self):
        layer = NumberLayer(self.style, QPointF(self.pos), self.number)
        layer.radius = self.radius
        return layer


class HighlighterLayer(Layer):
    """荧光笔图层(半透明画笔)"""
    
    def __init__(self, style: LayerStyle, points: List[QPointF] = None):
        super().__init__(style)
        self.points = points or []
        # 荧光笔默认半透明
        if self.style.opacity == 1.0:
            self.style.opacity = 0.3
    
    def add_point(self, pt: QPointF):
        self.points.append(pt)
    
    def bounds(self) -> QRectF:
        if not self.points:
            return QRectF()
        
        xs = [p.x() for p in self.points]
        ys = [p.y() for p in self.points]
        padding = self.style.stroke_width
        
        return QRectF(
            min(xs) - padding,
            min(ys) - padding,
            max(xs) - min(xs) + padding * 2,
            max(ys) - min(ys) + padding * 2
        )
    
    def clone(self):
        return HighlighterLayer(self.style, self.points.copy())


class MosaicLayer(Layer):
    """马赛克图层 - 存储区域,渲染时从背景生成马赛克"""
    
    def __init__(self, style: LayerStyle, rect: QRectF = None):
        super().__init__(style)
        self.rect = rect or QRectF()
        self.block_size = 10  # 马赛克块大小
    
    def bounds(self) -> QRectF:
        return QRectF(self.rect)
    
    def clone(self):
        layer = MosaicLayer(self.style, QRectF(self.rect))
        layer.block_size = self.block_size
        return layer
    
    def get_edit_handles(self):
        """马赛克与矩形使用相同的8控制点"""
        from canvas.layer_editor import EditHandle, HandleType
        from PyQt6.QtCore import Qt
        
        rect = self.rect
        handles = [
            # 四个角点
            EditHandle(0, HandleType.CORNER_TL, rect.topLeft(), Qt.CursorShape.SizeFDiagCursor),
            EditHandle(1, HandleType.CORNER_TR, rect.topRight(), Qt.CursorShape.SizeBDiagCursor),
            EditHandle(2, HandleType.CORNER_BR, rect.bottomRight(), Qt.CursorShape.SizeFDiagCursor),
            EditHandle(3, HandleType.CORNER_BL, rect.bottomLeft(), Qt.CursorShape.SizeBDiagCursor),
            # 四条边的中点
            EditHandle(4, HandleType.EDGE_T, QPointF(rect.center().x(), rect.top()), Qt.CursorShape.SizeVerCursor),
            EditHandle(5, HandleType.EDGE_R, QPointF(rect.right(), rect.center().y()), Qt.CursorShape.SizeHorCursor),
            EditHandle(6, HandleType.EDGE_B, QPointF(rect.center().x(), rect.bottom()), Qt.CursorShape.SizeVerCursor),
            EditHandle(7, HandleType.EDGE_L, QPointF(rect.left(), rect.center().y()), Qt.CursorShape.SizeHorCursor),
        ]
        return handles
    
    def apply_handle_drag(self, handle_id: int, delta: QPointF, keep_ratio: bool):
        """应用控制点拖拽,与RectLayer相同逻辑"""
        from PyQt6.QtCore import QRectF
        
        orig_rect = QRectF(self.rect)
        orig_ratio = orig_rect.width() / orig_rect.height() if orig_rect.height() != 0 else 1.0
        
        if handle_id == 0:  # 左上角
            new_left = orig_rect.left() + delta.x()
            new_top = orig_rect.top() + delta.y()
            if keep_ratio:
                new_width = orig_rect.right() - new_left
                new_height = new_width / orig_ratio
                new_top = orig_rect.bottom() - new_height
            self.rect.setTopLeft(QPointF(new_left, new_top))
            
        elif handle_id == 1:  # 右上角
            new_right = orig_rect.right() + delta.x()
            new_top = orig_rect.top() + delta.y()
            if keep_ratio:
                new_width = new_right - orig_rect.left()
                new_height = new_width / orig_ratio
                new_top = orig_rect.bottom() - new_height
            self.rect.setTopRight(QPointF(new_right, new_top))
            
        elif handle_id == 2:  # 右下角
            new_right = orig_rect.right() + delta.x()
            new_bottom = orig_rect.bottom() + delta.y()
            if keep_ratio:
                new_width = new_right - orig_rect.left()
                new_height = new_width / orig_ratio
                new_bottom = orig_rect.top() + new_height
            self.rect.setBottomRight(QPointF(new_right, new_bottom))
            
        elif handle_id == 3:  # 左下角
            new_left = orig_rect.left() + delta.x()
            new_bottom = orig_rect.bottom() + delta.y()
            if keep_ratio:
                new_width = orig_rect.right() - new_left
                new_height = new_width / orig_ratio
                new_bottom = orig_rect.top() + new_height
            self.rect.setBottomLeft(QPointF(new_left, new_bottom))
            
        elif handle_id == 4:  # 上边
            new_top = orig_rect.top() + delta.y()
            if keep_ratio:
                new_height = orig_rect.bottom() - new_top
                new_width = new_height * orig_ratio
                center_x = orig_rect.center().x()
                self.rect = QRectF(center_x - new_width/2, new_top, new_width, new_height)
            else:
                self.rect.setTop(new_top)
                
        elif handle_id == 5:  # 右边
            new_right = orig_rect.right() + delta.x()
            if keep_ratio:
                new_width = new_right - orig_rect.left()
                new_height = new_width / orig_ratio
                center_y = orig_rect.center().y()
                self.rect = QRectF(orig_rect.left(), center_y - new_height/2, new_width, new_height)
            else:
                self.rect.setRight(new_right)
                
        elif handle_id == 6:  # 下边
            new_bottom = orig_rect.bottom() + delta.y()
            if keep_ratio:
                new_height = new_bottom - orig_rect.top()
                new_width = new_height * orig_ratio
                center_x = orig_rect.center().x()
                self.rect = QRectF(center_x - new_width/2, orig_rect.top(), new_width, new_height)
            else:
                self.rect.setBottom(new_bottom)
                
        elif handle_id == 7:  # 左边
            new_left = orig_rect.left() + delta.x()
            if keep_ratio:
                new_width = orig_rect.right() - new_left
                new_height = new_width / orig_ratio
                center_y = orig_rect.center().y()
                self.rect = QRectF(new_left, center_y - new_height/2, new_width, new_height)
            else:
                self.rect.setLeft(new_left)
        
        self.rect = self.rect.normalized()


# ============================================================================
#  Document 数据模型
# ============================================================================

class Document(QObject):
    """
    Document 数据模型 - 专业截图软件架构
    
    职责:
    - 存储数据(背景/选区/图层)
    - 提供数据访问接口
    - 发送变更信号(让View重绘)
    
    不包含:
    - UI渲染(由CanvasWidget负责)
    - 交互逻辑(由Tool负责)
    - 撤销管理(由QUndoStack负责)
    """
    
    # 信号:数据变更通知
    selection_changed = pyqtSignal()  # 选区改变
    layer_added = pyqtSignal(int)     # 添加图层(layer_id)
    layer_removed = pyqtSignal(int)   # 删除图层(layer_id)
    layer_updated = pyqtSignal(int)   # 图层更新(layer_id)
    active_layer_changed = pyqtSignal()  # 选中图层改变
    
    def __init__(self, background: QImage):
        super().__init__()
        
        # 背景截图(不可变)
        self.background = background
        self.rect = QRectF(0, 0, background.width(), background.height())
        
        # 选区(可撤销)
        self.selection: Optional[QRectF] = None
        
        # 图层列表(按顺序渲染)
        self.layers: List[Layer] = []
        
        # 当前选中图层ID(用于编辑、移动、删除)
        self.active_layer_id: Optional[int] = None
    
    # ========================================================================
    #  选区操作
    # ========================================================================
    
    def set_selection(self, rect: QRectF):
        """设置选区(由SetSelectionCommand调用)"""
        self.selection = rect
        self.selection_changed.emit()
    
    def clear_selection(self):
        """清除选区"""
        self.selection = None
        self.selection_changed.emit()
    
    def has_selection(self) -> bool:
        """是否有选区"""
        return self.selection is not None and not self.selection.isEmpty()
    
    # ========================================================================
    #  图层操作
    # ========================================================================
    
    def add_layer(self, layer: Layer, index: int = -1):
        """
        添加图层(由AddLayerCommand调用)
        
        Args:
            layer: 图层对象
            index: 插入位置(-1=末尾)
        """
        if index < 0:
            self.layers.append(layer)
        else:
            self.layers.insert(index, layer)
        
        self.layer_added.emit(layer.id)
    
    def remove_layer(self, layer_id: int):
        """删除图层(由RemoveLayerCommand调用)"""
        for i, layer in enumerate(self.layers):
            if layer.id == layer_id:
                self.layers.pop(i)
                
                # 如果删除的是选中图层,清除选中
                if self.active_layer_id == layer_id:
                    self.active_layer_id = None
                    self.active_layer_changed.emit()
                
                self.layer_removed.emit(layer_id)
                return
    
    def get_layer(self, layer_id: int) -> Optional[Layer]:
        """获取图层"""
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None
    
    def update_layer(self, layer_id: int):
        """通知图层已更新(由UpdateLayerCommand调用)"""
        self.layer_updated.emit(layer_id)
    
    def set_active_layer(self, layer_id: Optional[int]):
        """设置选中图层"""
        if self.active_layer_id != layer_id:
            self.active_layer_id = layer_id
            self.active_layer_changed.emit()
    
    def get_active_layer(self) -> Optional[Layer]:
        """获取当前选中图层"""
        if self.active_layer_id is None:
            return None
        return self.get_layer(self.active_layer_id)
    
    # ========================================================================
    #  命中测试
    # ========================================================================
    
    def hit_test_layer(self, pt: QPointF) -> Optional[Layer]:
        """
        命中测试:查找点击的图层(从上到下)
        
        Args:
            pt: 点击位置
            
        Returns:
            命中的图层(最上层)
        """
        # 从上到下遍历(倒序)
        for layer in reversed(self.layers):
            if layer.visible and layer.contains_point(pt):
                return layer
        
        return None
