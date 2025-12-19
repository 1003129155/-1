"""
选区控制系统 - 拖拽创建 + 移动 + 8控制点缩放
专业截图软件标准实现

新增功能:
- 吸附系统(屏幕边缘/窗口边缘/像素网格)
- 选区信息条(实时显示尺寸)
"""

from enum import Enum
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor
from typing import Optional

# 导入吸附系统
try:
    from canvas.snap_system import SnapSystem
    from canvas.selection_info_bar import SelectionInfoBarRenderer
    HAS_SNAP = True
except ImportError:
    HAS_SNAP = False
    print("⚠️ [SelectionController] 吸附系统未找到,功能受限")


# ============================================================================
#  控制点枚举
# ============================================================================

class HandlePosition(Enum):
    """控制点位置"""
    NONE = 0        # 无
    MOVE = 1        # 移动(选区内部)
    
    # 8个控制点
    TOP_LEFT = 10
    TOP = 11
    TOP_RIGHT = 12
    RIGHT = 13
    BOTTOM_RIGHT = 14
    BOTTOM = 15
    BOTTOM_LEFT = 16
    LEFT = 17


# ============================================================================
#  选区控制器
# ============================================================================

class SelectionController:
    """
    选区控制器 - 处理选区的交互
    
    功能:
    - 命中测试(hit test):判断鼠标落在哪个控制点/内部/外部
    - 拖拽创建:按下→拖拽→松开
    - 移动选区:拖内部
    - 缩放选区:拖8个控制点
    - 约束:不超出范围/最小尺寸/Shift保持比例
    """
    
    # 配置
    HANDLE_SIZE = 8  # 控制点大小
    MIN_SIZE = 10    # 最小选区尺寸
    
    def __init__(self, canvas_rect: QRectF, snap_system: Optional['SnapSystem'] = None):
        """
        Args:
            canvas_rect: 画布范围(截图范围)
            snap_system: 吸附系统(可选)
        """
        self.canvas_rect = canvas_rect
        self.selection: QRectF = None
        
        # 当前操作状态
        self.handle: HandlePosition = HandlePosition.NONE
        self.drag_start: QPointF = None
        self.initial_rect: QRectF = None
        
        # 吸附系统
        self.snap_system = snap_system
        self.enable_snap = True  # 吸附开关
        
        # 信息条渲染器
        self.info_bar_renderer = SelectionInfoBarRenderer() if HAS_SNAP else None
    
    # ========================================================================
    #  命中测试
    # ========================================================================
    
    def hit_test(self, pt: QPointF) -> HandlePosition:
        """
        命中测试 - 判断点击位置
        
        Args:
            pt: 鼠标位置
            
        Returns:
            HandlePosition: NONE/MOVE/TOP_LEFT/TOP/...
        """
        if not self.selection or self.selection.isEmpty():
            return HandlePosition.NONE
        
        # 1. 优先测试控制点(从小范围到大范围)
        handles = self._get_handle_rects()
        for handle, rect in handles.items():
            if rect.contains(pt):
                return handle
        
        # 2. 测试选区内部(移动)
        if self.selection.contains(pt):
            return HandlePosition.MOVE
        
        # 3. 外部
        return HandlePosition.NONE
    
    def _get_handle_rects(self) -> dict:
        """
        获取8个控制点的矩形
        
        Returns:
            {HandlePosition: QRectF}
        """
        if not self.selection:
            return {}
        
        rect = self.selection
        half = self.HANDLE_SIZE / 2
        
        # 四角
        tl = QPointF(rect.left(), rect.top())
        tr = QPointF(rect.right(), rect.top())
        bl = QPointF(rect.left(), rect.bottom())
        br = QPointF(rect.right(), rect.bottom())
        
        # 四边中点
        t = QPointF(rect.center().x(), rect.top())
        b = QPointF(rect.center().x(), rect.bottom())
        l = QPointF(rect.left(), rect.center().y())
        r = QPointF(rect.right(), rect.center().y())
        
        def make_rect(pt: QPointF) -> QRectF:
            return QRectF(pt.x() - half, pt.y() - half, self.HANDLE_SIZE, self.HANDLE_SIZE)
        
        return {
            HandlePosition.TOP_LEFT: make_rect(tl),
            HandlePosition.TOP: make_rect(t),
            HandlePosition.TOP_RIGHT: make_rect(tr),
            HandlePosition.RIGHT: make_rect(r),
            HandlePosition.BOTTOM_RIGHT: make_rect(br),
            HandlePosition.BOTTOM: make_rect(b),
            HandlePosition.BOTTOM_LEFT: make_rect(bl),
            HandlePosition.LEFT: make_rect(l),
        }
    
    # ========================================================================
    #  拖拽操作
    # ========================================================================
    
    def start_drag(self, pt: QPointF, handle: HandlePosition):
        """
        开始拖拽
        
        Args:
            pt: 起始点
            handle: 控制点类型
        """
        self.drag_start = pt
        self.handle = handle
        
        if self.selection:
            self.initial_rect = QRectF(self.selection)
        else:
            self.initial_rect = None
    
    def drag_to(self, pt: QPointF, keep_ratio: bool = False) -> QRectF:
        """
        拖拽到新位置(支持吸附)
        
        Args:
            pt: 当前位置
            keep_ratio: 是否保持比例(Shift)
            
        Returns:
            新选区(临时预览,不修改self.selection)
        """
        if not self.drag_start:
            return self.selection
        
        dx = pt.x() - self.drag_start.x()
        dy = pt.y() - self.drag_start.y()
        
        if self.handle == HandlePosition.NONE:
            # 创建新选区
            rect = self._create_selection(self.drag_start, pt, keep_ratio)
        
        elif self.handle == HandlePosition.MOVE:
            # 移动选区
            rect = self._move_selection(dx, dy)
        
        else:
            # 缩放选区
            rect = self._resize_selection(dx, dy, keep_ratio)
        
        # 应用吸附
        if self.enable_snap and self.snap_system and HAS_SNAP:
            rect = self.snap_system.snap_rect(rect)
        
        return rect
    
    def end_drag(self, final_rect: QRectF):
        """
        结束拖拽,确认选区
        
        Args:
            final_rect: 最终选区
        """
        self.selection = final_rect
        self.handle = HandlePosition.NONE
        self.drag_start = None
        self.initial_rect = None
    
    # ========================================================================
    #  拖拽算法
    # ========================================================================
    
    def _create_selection(self, p1: QPointF, p2: QPointF, keep_ratio: bool) -> QRectF:
        """创建新选区(从两点生成矩形)"""
        rect = QRectF(p1, p2).normalized()
        
        if keep_ratio:
            # 保持1:1比例
            side = min(rect.width(), rect.height())
            if p2.x() >= p1.x() and p2.y() >= p1.y():
                rect = QRectF(p1.x(), p1.y(), side, side)
            elif p2.x() < p1.x() and p2.y() >= p1.y():
                rect = QRectF(p1.x() - side, p1.y(), side, side)
            elif p2.x() >= p1.x() and p2.y() < p1.y():
                rect = QRectF(p1.x(), p1.y() - side, side, side)
            else:
                rect = QRectF(p1.x() - side, p1.y() - side, side, side)
        
        return self._constrain_rect(rect)
    
    def _move_selection(self, dx: float, dy: float) -> QRectF:
        """移动选区"""
        if not self.initial_rect:
            return self.selection
        
        rect = QRectF(self.initial_rect)
        rect.translate(dx, dy)
        
        # 约束:不超出画布
        if rect.left() < self.canvas_rect.left():
            rect.moveLeft(self.canvas_rect.left())
        if rect.top() < self.canvas_rect.top():
            rect.moveTop(self.canvas_rect.top())
        if rect.right() > self.canvas_rect.right():
            rect.moveRight(self.canvas_rect.right())
        if rect.bottom() > self.canvas_rect.bottom():
            rect.moveBottom(self.canvas_rect.bottom())
        
        return rect
    
    def _resize_selection(self, dx: float, dy: float, keep_ratio: bool) -> QRectF:
        """缩放选区(拖控制点)"""
        if not self.initial_rect:
            return self.selection
        
        rect = QRectF(self.initial_rect)
        
        # 根据控制点调整矩形
        if self.handle == HandlePosition.TOP_LEFT:
            rect.setTopLeft(rect.topLeft() + QPointF(dx, dy))
        elif self.handle == HandlePosition.TOP:
            rect.setTop(rect.top() + dy)
        elif self.handle == HandlePosition.TOP_RIGHT:
            rect.setTopRight(rect.topRight() + QPointF(dx, dy))
        elif self.handle == HandlePosition.RIGHT:
            rect.setRight(rect.right() + dx)
        elif self.handle == HandlePosition.BOTTOM_RIGHT:
            rect.setBottomRight(rect.bottomRight() + QPointF(dx, dy))
        elif self.handle == HandlePosition.BOTTOM:
            rect.setBottom(rect.bottom() + dy)
        elif self.handle == HandlePosition.BOTTOM_LEFT:
            rect.setBottomLeft(rect.bottomLeft() + QPointF(dx, dy))
        elif self.handle == HandlePosition.LEFT:
            rect.setLeft(rect.left() + dx)
        
        rect = rect.normalized()
        
        if keep_ratio:
            # 保持初始比例
            initial_ratio = self.initial_rect.width() / self.initial_rect.height()
            if rect.width() / rect.height() > initial_ratio:
                # 宽度过大,调整宽度
                new_width = rect.height() * initial_ratio
                if self.handle in [HandlePosition.TOP_LEFT, HandlePosition.LEFT, HandlePosition.BOTTOM_LEFT]:
                    rect.setLeft(rect.right() - new_width)
                else:
                    rect.setRight(rect.left() + new_width)
            else:
                # 高度过大,调整高度
                new_height = rect.width() / initial_ratio
                if self.handle in [HandlePosition.TOP_LEFT, HandlePosition.TOP, HandlePosition.TOP_RIGHT]:
                    rect.setTop(rect.bottom() - new_height)
                else:
                    rect.setBottom(rect.top() + new_height)
        
        return self._constrain_rect(rect)
    
    def _constrain_rect(self, rect: QRectF) -> QRectF:
        """
        约束矩形
        - 不超出画布
        - 最小尺寸
        """
        # 限制在画布内
        if rect.left() < self.canvas_rect.left():
            rect.setLeft(self.canvas_rect.left())
        if rect.top() < self.canvas_rect.top():
            rect.setTop(self.canvas_rect.top())
        if rect.right() > self.canvas_rect.right():
            rect.setRight(self.canvas_rect.right())
        if rect.bottom() > self.canvas_rect.bottom():
            rect.setBottom(self.canvas_rect.bottom())
        
        # 最小尺寸
        if rect.width() < self.MIN_SIZE:
            rect.setWidth(self.MIN_SIZE)
        if rect.height() < self.MIN_SIZE:
            rect.setHeight(self.MIN_SIZE)
        
        return rect
    
    # ========================================================================
    #  渲染
    # ========================================================================
    
    def paint(self, painter: QPainter):
        """
        绘制选区框和控制点
        
        Args:
            painter: QPainter
        """
        if not self.selection or self.selection.isEmpty():
            return
        
        # 1. 绘制选区边框
        pen = QPen(QColor(0, 120, 215), 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.selection)
        
        # 2. 绘制8个控制点
        handles = self._get_handle_rects()
        brush = QBrush(QColor(255, 255, 255))
        border_pen = QPen(QColor(0, 120, 215), 1)
        
        for handle_rect in handles.values():
            painter.setPen(border_pen)
            painter.setBrush(brush)
            painter.drawRect(handle_rect)
    
    # ========================================================================
    #  光标
    # ========================================================================
    
    def get_cursor(self, handle: HandlePosition) -> Qt.CursorShape:
        """
        根据控制点返回光标样式
        
        Args:
            handle: 控制点位置
            
        Returns:
            Qt.CursorShape
        """
        cursor_map = {
            HandlePosition.NONE: Qt.CursorShape.CrossCursor,
            HandlePosition.MOVE: Qt.CursorShape.SizeAllCursor,
            HandlePosition.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
            HandlePosition.TOP: Qt.CursorShape.SizeVerCursor,
            HandlePosition.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
            HandlePosition.RIGHT: Qt.CursorShape.SizeHorCursor,
            HandlePosition.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
            HandlePosition.BOTTOM: Qt.CursorShape.SizeVerCursor,
            HandlePosition.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
            HandlePosition.LEFT: Qt.CursorShape.SizeHorCursor,
        }
        return cursor_map.get(handle, Qt.CursorShape.ArrowCursor)
