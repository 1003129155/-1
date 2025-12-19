"""
工具栏 - 截图工具栏UI (完整商业版本)
"""
import os
import sys
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRect, QPoint
from PyQt6.QtGui import QIcon, QColor, QCursor
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QSlider, QLabel, 
    QApplication, QColorDialog
)

# 资源路径辅助函数
def resource_path(relative_path):
    """获取资源文件的绝对路径"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class Toolbar(QWidget):
    """
    截图工具栏
    """
    # 信号定义
    tool_changed = pyqtSignal(str)  # 工具切换信号(tool_id)
    save_clicked = pyqtSignal()  # 保存按钮
    copy_clicked = pyqtSignal()  # 复制按钮
    confirm_clicked = pyqtSignal()  # 确认按钮
    undo_clicked = pyqtSignal()  # 撤销
    redo_clicked = pyqtSignal()  # 重做
    color_changed = pyqtSignal(QColor)  # 颜色改变
    stroke_width_changed = pyqtSignal(int)  # 线宽改变
    opacity_changed = pyqtSignal(int)  # 透明度改变(0-255)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 当前选中的工具
        self.current_tool = "pen"
        
        # 当前颜色
        self.current_color = QColor(255, 0, 0)  # 默认红色
        
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        # 设置窗口属性
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        btn_width = 45
        btn_height = 45
        
        # 左侧按钮区域
        left_x = 0
        
        # 1. 保存按钮
        self.save_btn = QPushButton(self)
        self.save_btn.setGeometry(left_x, 0, 50, btn_height)
        self.save_btn.setToolTip('ファイルに保存')
        self.save_btn.clicked.connect(self.save_clicked.emit)
        left_x += 50
        
        # 2. 复制按钮
        self.copy_btn = QPushButton(self)
        self.copy_btn.setGeometry(left_x, 0, 50, btn_height)
        self.copy_btn.setToolTip('画像をコピー')
        self.copy_btn.clicked.connect(self.copy_clicked.emit)
        left_x += 50
        
        # 3. 画笔工具
        self.pen_btn = QPushButton(self)
        self.pen_btn.setGeometry(left_x, 0, btn_width, btn_height)
        self.pen_btn.setToolTip('ペンツール')
        self.pen_btn.setCheckable(True)
        self.pen_btn.setChecked(True)
        self.pen_btn.clicked.connect(lambda: self._on_tool_clicked("pen"))
        left_x += btn_width
        
        # 4. 荧光笔工具
        self.highlighter_btn = QPushButton(self)
        self.highlighter_btn.setGeometry(left_x, 0, btn_width, btn_height)
        self.highlighter_btn.setToolTip('蛍光ペン')
        self.highlighter_btn.setCheckable(True)
        self.highlighter_btn.clicked.connect(lambda: self._on_tool_clicked("highlighter"))
        left_x += btn_width
        
        # 5. 箭头工具
        self.arrow_btn = QPushButton(self)
        self.arrow_btn.setGeometry(left_x, 0, btn_width, btn_height)
        self.arrow_btn.setToolTip('矢印を描画')
        self.arrow_btn.setCheckable(True)
        self.arrow_btn.clicked.connect(lambda: self._on_tool_clicked("arrow"))
        left_x += btn_width
        
        # 6. 序号工具
        self.number_btn = QPushButton(self)
        self.number_btn.setGeometry(left_x, 0, btn_width, btn_height)
        self.number_btn.setToolTip('番号を追加')
        self.number_btn.setCheckable(True)
        self.number_btn.clicked.connect(lambda: self._on_tool_clicked("number"))
        left_x += btn_width
        
        # 7. 矩形工具
        self.rect_btn = QPushButton(self)
        self.rect_btn.setGeometry(left_x, 0, btn_width, btn_height)
        self.rect_btn.setToolTip('矩形を描画')
        self.rect_btn.setCheckable(True)
        self.rect_btn.clicked.connect(lambda: self._on_tool_clicked("rect"))
        left_x += btn_width
        
        # 8. 圆形工具
        self.ellipse_btn = QPushButton(self)
        self.ellipse_btn.setGeometry(left_x, 0, btn_width, btn_height)
        self.ellipse_btn.setToolTip('円を描画')
        self.ellipse_btn.setCheckable(True)
        self.ellipse_btn.clicked.connect(lambda: self._on_tool_clicked("ellipse"))
        left_x += btn_width
        
        # 9. 文字工具
        self.text_btn = QPushButton(self)
        self.text_btn.setGeometry(left_x, 0, btn_width, btn_height)
        self.text_btn.setToolTip('テキストを追加')
        self.text_btn.setCheckable(True)
        self.text_btn.clicked.connect(lambda: self._on_tool_clicked("text"))
        left_x += btn_width
        
        # 10. 撤销按钮
        self.undo_btn = QPushButton(self)
        self.undo_btn.setGeometry(left_x, 0, btn_width, btn_height)
        self.undo_btn.setToolTip('元に戻す')
        self.undo_btn.clicked.connect(self.undo_clicked.emit)
        left_x += btn_width
        
        # 11. 重做按钮
        self.redo_btn = QPushButton(self)
        self.redo_btn.setGeometry(left_x, 0, btn_width, btn_height)
        self.redo_btn.setToolTip('やり直す')
        self.redo_btn.clicked.connect(self.redo_clicked.emit)
        left_x += btn_width
        
        # 右侧按钮区域
        right_buttons_width = 70  # 确定按钮宽度
        toolbar_total_width = left_x + 20 + right_buttons_width
        
        # 确定按钮(吸附最右边)
        self.confirm_btn = QPushButton("確定", self)
        self.confirm_btn.setGeometry(toolbar_total_width - 70, 0, 70, btn_height)
        self.confirm_btn.setToolTip('確定して保存')
        self.confirm_btn.clicked.connect(self.confirm_clicked.emit)
        
        # 设置工具栏大小
        self.resize(toolbar_total_width, btn_height)
        
        # 设置样式
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 2px solid #333333;
                border-radius: 6px;
                padding: 2px;
            }
            QPushButton {
                background-color: rgba(0, 0, 0, 0.02);
                border: none;
                border-radius: 0px;
                color: #333;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.08);
            }
            QPushButton:pressed {
                background-color: rgba(0, 0, 0, 0.15);
            }
            QPushButton:checked {
                background-color: rgba(64, 224, 208, 0.3);
                border: 1px solid #40E0D0;
            }
        """)
        
        # 收集所有工具按钮
        self.tool_buttons = {
            "pen": self.pen_btn,
            "highlighter": self.highlighter_btn,
            "arrow": self.arrow_btn,
            "number": self.number_btn,
            "rect": self.rect_btn,
            "ellipse": self.ellipse_btn,
            "text": self.text_btn,
        }
        
        # 创建二级菜单(绘画工具选项)
        self.init_paint_menu()
        
    def init_paint_menu(self):
        """初始化绘画工具二级菜单(颜色、大小、透明度)"""
        self.paint_menu = QWidget(self, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.paint_menu.resize(485, 55)
        self.paint_menu.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QPushButton {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border: 1px solid #bbb;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
            QSlider {
                background-color: transparent;
            }
            QLabel {
                background-color: transparent;
                color: rgb(51,51,51);
                font-size: 12px;
            }
        """)
        
        # 1. 画笔大小
        QLabel("大小:", self.paint_menu).setGeometry(5, 8, 35, 18)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal, self.paint_menu)
        self.size_slider.setGeometry(40, 8, 80, 18)
        self.size_slider.setRange(1, 99)
        self.size_slider.setValue(5)
        self.size_slider.setToolTip('ペンのサイズを設定')
        self.size_slider.valueChanged.connect(self._on_size_changed)
        
        self.size_label = QLabel("5", self.paint_menu)
        self.size_label.setGeometry(125, 8, 25, 18)
        
        # 2. 透明度
        QLabel("透明:", self.paint_menu).setGeometry(5, 32, 35, 18)
        
        self.alpha_slider = QSlider(Qt.Orientation.Horizontal, self.paint_menu)
        self.alpha_slider.setGeometry(40, 32, 80, 18)
        self.alpha_slider.setRange(1, 255)
        self.alpha_slider.setValue(255)
        self.alpha_slider.setToolTip('ペンの透明度を設定')
        self.alpha_slider.valueChanged.connect(self._on_alpha_changed)
        
        self.alpha_label = QLabel("255", self.paint_menu)
        self.alpha_label.setGeometry(125, 32, 30, 18)
        
        # 3. 颜色选择按钮
        self.color_picker_btn = QPushButton("🎨", self.paint_menu)
        self.color_picker_btn.setGeometry(185, 9, 40, 40)
        self.color_picker_btn.setToolTip('ペンの色を選択')
        self.color_picker_btn.clicked.connect(self._pick_color)
        
        # 4. 颜色预设按钮(6个)
        preset_colors = [
            ("#FF0000", "赤色"),     # 红色
            ("#FFFF00", "黄色"),     # 黄色
            ("#00FF00", "緑色"),     # 绿色
            ("#0000FF", "青色"),     # 蓝色
            ("#000000", "黒色"),     # 黑色
            ("#FFFFFF", "白色"),     # 白色
        ]
        
        self.preset_buttons = []
        preset_start_x = 240
        preset_y = 11
        preset_size = 34
        preset_spacing = 38
        
        for i, (color, tooltip) in enumerate(preset_colors):
            btn = QPushButton("●", self.paint_menu)
            btn.setGeometry(preset_start_x + i * preset_spacing, preset_y, preset_size, preset_size)
            btn.setToolTip(f"{tooltip}\n{color}")
            btn.setProperty("preset_color", color)
            btn.clicked.connect(lambda checked, c=color: self._apply_preset_color(c))
            
            # 设置按钮样式(根据颜色)
            btn.setStyleSheet(self._get_preset_button_style(color))
            
            self.preset_buttons.append(btn)
        
        self.paint_menu.hide()
        
    def _get_preset_button_style(self, color: str) -> str:
        """根据颜色生成预设按钮样式"""
        # 简化样式,使用纯色
        if color == "#FFFFFF":
            text_color = "rgb(100, 100, 100)"
            border_color = "#CCCCCC"
        elif color == "#000000":
            text_color = "rgb(200, 200, 200)"
            border_color = "#333333"
        else:
            text_color = color
            border_color = color
        
        return f"""
            QPushButton {{
                background-color: {color};
                color: {text_color};
                border: 3px solid {border_color};
                border-radius: 8px;
                font-size: 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border: 3px solid #000;
            }}
        """
        
    def _on_tool_clicked(self, tool_id: str):
        """工具按钮点击"""
        # 取消所有工具按钮的选中状态
        for tid, btn in self.tool_buttons.items():
            btn.setChecked(tid == tool_id)
        
        self.current_tool = tool_id
        self.tool_changed.emit(tool_id)
        
        # 如果是绘画工具(pen/highlighter),显示二级菜单
        if tool_id in ["pen", "highlighter"]:
            self.show_paint_menu()
        else:
            self.paint_menu.hide()
    
    def _on_size_changed(self, value: int):
        """画笔大小改变"""
        self.size_label.setText(str(value))
        self.stroke_width_changed.emit(value)
    
    def _on_alpha_changed(self, value: int):
        """透明度改变"""
        self.alpha_label.setText(str(value))
        self.opacity_changed.emit(value)
    
    def _pick_color(self):
        """打开颜色选择器"""
        color = QColorDialog.getColor(self.current_color, self, "ペンの色を選択")
        if color.isValid():
            self.current_color = color
            self.color_changed.emit(color)
    
    def _apply_preset_color(self, color_hex: str):
        """应用预设颜色"""
        self.current_color = QColor(color_hex)
        self.color_changed.emit(self.current_color)
    
    def show_paint_menu(self):
        """显示绘画工具菜单"""
        # 定位在工具栏下方
        menu_x = self.x()
        menu_y = self.y() + self.height() + 5
        
        # 检查是否超出屏幕
        screen = QApplication.primaryScreen().geometry()
        if menu_y + self.paint_menu.height() > screen.height():
            # 显示在工具栏上方
            menu_y = self.y() - self.paint_menu.height() - 5
        
        self.paint_menu.move(menu_x, menu_y)
        self.paint_menu.show()
        self.paint_menu.raise_()
    
    def position_near_rect(self, rect):
        """
        将工具栏定位在矩形附近
        Args:
            rect: QRectF - 选区矩形
        """
        screen = QApplication.primaryScreen().geometry()
        
        # 尝试定位在选区下方
        x = int(rect.x())
        y = int(rect.y() + rect.height() + 10)
        
        # 确保不超出屏幕
        if x + self.width() > screen.width():
            x = screen.width() - self.width() - 10
        if x < 10:
            x = 10
        
        if y + self.height() > screen.height():
            # 定位在选区上方
            y = int(rect.y() - self.height() - 10)
        
        if y < 10:
            y = 10
        
        self.move(x, y)
