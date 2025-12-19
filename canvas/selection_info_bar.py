"""
选区信息条 - Selection Info Bar
功能:
1. 浮动显示选区的 x, y, w, h
2. 半透明背景
3. 自动定位(避免遮挡选区)
4. 单位切换(px/百分比)
"""

from PyQt6.QtCore import QRectF, QPointF, Qt, QSize
from PyQt6.QtGui import QPainter, QColor, QFont, QPen
from PyQt6.QtWidgets import QWidget
from typing import Optional


class SelectionInfoBar(QWidget):
    """
    选区信息条控件
    
    特性:
    - 实时显示选区尺寸和位置
    - 半透明黑色背景 + 白色文字
    - 智能定位(避免遮挡选区)
    - 紧凑设计,不干扰用户操作
    
    使用方法:
    ```python
    info_bar = SelectionInfoBar(canvas_widget)
    info_bar.update_info(selection_rect)
    info_bar.show()
    ```
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # 样式配置
        self.bg_color = QColor(0, 0, 0, 180)      # 半透明黑色
        self.text_color = QColor(255, 255, 255)   # 白色
        self.border_color = QColor(255, 0, 0, 200)  # 红色边框
        
        self.font = QFont("Arial", 10)
        self.font.setBold(True)
        
        # 内边距
        self.padding = 6
        
        # 当前显示的信息
        self._text = ""
        self._selection_rect: Optional[QRectF] = None
        
        # 单位模式: "px" | "percent"
        self.unit_mode = "px"
        
        # 窗口属性
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # 鼠标穿透
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        
        # 初始隐藏
        self.hide()
    
    def update_info(self, selection: QRectF):
        """
        更新显示信息
        
        Args:
            selection: 选区矩形
        """
        self._selection_rect = QRectF(selection)
        
        # 生成显示文本
        x = int(selection.x())
        y = int(selection.y())
        w = int(selection.width())
        h = int(selection.height())
        
        if self.unit_mode == "px":
            self._text = f"X: {x}  Y: {y}  W: {w}  H: {h}"
        else:
            # 百分比模式(相对于画布)
            if self.parent():
                pw = self.parent().width()
                ph = self.parent().height()
                px = int(x / pw * 100) if pw > 0 else 0
                py = int(y / ph * 100) if ph > 0 else 0
                pww = int(w / pw * 100) if pw > 0 else 0
                phh = int(h / ph * 100) if ph > 0 else 0
                self._text = f"X: {px}%  Y: {py}%  W: {pww}%  H: {phh}%"
            else:
                self._text = f"X: {x}  Y: {y}  W: {w}  H: {h}"
        
        # 调整自身大小和位置
        self._adjust_size_and_position()
        
        # 触发重绘
        self.update()
    
    def _adjust_size_and_position(self):
        """调整信息条的大小和位置"""
        if not self._selection_rect or not self.parent():
            return
        
        # 计算所需尺寸
        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self._text)
        text_height = fm.height()
        
        bar_width = text_width + self.padding * 2
        bar_height = text_height + self.padding * 2
        
        self.setFixedSize(bar_width, bar_height)
        
        # 智能定位:避免遮挡选区
        sel = self._selection_rect
        canvas_rect = self.parent().rect()
        
        # 默认位置:选区上方居中
        target_x = sel.center().x() - bar_width / 2
        target_y = sel.top() - bar_height - 10  # 上方10px间隔
        
        # 边界检查:如果上方放不下,放下方
        if target_y < 0:
            target_y = sel.bottom() + 10
        
        # 边界检查:如果下方也放不下,放选区内部顶部
        if target_y + bar_height > canvas_rect.height():
            target_y = sel.top() + 10
        
        # 左右边界检查
        if target_x < 0:
            target_x = 5
        elif target_x + bar_width > canvas_rect.width():
            target_x = canvas_rect.width() - bar_width - 5
        
        # 应用位置
        self.move(int(target_x), int(target_y))
    
    def paintEvent(self, event):
        """绘制信息条"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制背景
        painter.fillRect(self.rect(), self.bg_color)
        
        # 绘制边框
        pen = QPen(self.border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        
        # 绘制文字
        painter.setPen(self.text_color)
        painter.setFont(self.font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)
    
    def toggle_unit_mode(self):
        """切换单位模式"""
        self.unit_mode = "percent" if self.unit_mode == "px" else "px"
        
        # 更新显示
        if self._selection_rect:
            self.update_info(self._selection_rect)
    
    def sizeHint(self) -> QSize:
        """建议尺寸"""
        fm = self.fontMetrics()
        # 假设最大文本长度
        max_text = "X: 9999  Y: 9999  W: 9999  H: 9999"
        text_width = fm.horizontalAdvance(max_text)
        text_height = fm.height()
        return QSize(
            text_width + self.padding * 2,
            text_height + self.padding * 2
        )


class SelectionInfoBarRenderer:
    """
    选区信息条渲染器(不使用独立 QWidget)
    
    直接在画布上绘制信息条,避免创建额外窗口
    适用于不想引入独立控件的场景
    """
    
    def __init__(self):
        self.bg_color = QColor(0, 0, 0, 180)
        self.text_color = QColor(255, 255, 255)
        self.border_color = QColor(255, 0, 0, 200)
        self.font = QFont("Arial", 10)
        self.font.setBold(True)
        self.padding = 6
        self.unit_mode = "px"
    
    def render(self, painter: QPainter, selection: QRectF, canvas_rect: QRectF):
        """
        在画布上渲染信息条
        
        Args:
            painter: QPainter 实例
            selection: 选区矩形
            canvas_rect: 画布矩形
        """
        # 生成文本
        x = int(selection.x())
        y = int(selection.y())
        w = int(selection.width())
        h = int(selection.height())
        
        text = f"X: {x}  Y: {y}  W: {w}  H: {h}"
        
        # 计算信息条尺寸
        painter.save()
        painter.setFont(self.font)
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(text)
        text_height = fm.height()
        
        bar_width = text_width + self.padding * 2
        bar_height = text_height + self.padding * 2
        
        # 计算位置(选区上方居中)
        bar_x = selection.center().x() - bar_width / 2
        bar_y = selection.top() - bar_height - 10
        
        # 边界检查
        if bar_y < 0:
            bar_y = selection.bottom() + 10
        if bar_y + bar_height > canvas_rect.height():
            bar_y = selection.top() + 10
        
        if bar_x < 0:
            bar_x = 5
        elif bar_x + bar_width > canvas_rect.width():
            bar_x = canvas_rect.width() - bar_width - 5
        
        bar_rect = QRectF(bar_x, bar_y, bar_width, bar_height)
        
        # 绘制背景
        painter.fillRect(bar_rect, self.bg_color)
        
        # 绘制边框
        pen = QPen(self.border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(bar_rect)
        
        # 绘制文字
        painter.setPen(self.text_color)
        painter.drawText(bar_rect, Qt.AlignmentFlag.AlignCenter, text)
        
        painter.restore()


# 测试函数
def test_info_bar():
    """测试信息条"""
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # 创建测试窗口
    test_widget = QWidget()
    test_widget.setGeometry(100, 100, 1920, 1080)
    test_widget.setStyleSheet("background: #333;")
    
    # 创建信息条
    info_bar = SelectionInfoBar(test_widget)
    
    # 模拟选区
    selection = QRectF(200, 200, 800, 600)
    info_bar.update_info(selection)
    info_bar.show()
    
    test_widget.show()
    
    print("✅ 信息条测试窗口已打开")
    print("   应该看到半透明黑色背景的信息条")
    print("   显示选区的位置和尺寸")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    test_info_bar()
