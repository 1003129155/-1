#!/usr/bin/env python3
"""
main.py - jietuba 截图工具主程序入口

这是 jietuba 截图工具的主程序文件,负责:
- 创建主窗口和应用程序实例
- 管理截图功能的启动和配置
- 处理系统托盘图标和快捷键
- 管理配置文件的读写

主要类:
- MainWindow: 主窗口类,管理截图和配置
- ConfigManager: 配置管理器,负责设置的持久化

依赖模块:
- PyQt5: GUI框架
- jietuba_screenshot: 截图核心功能模块
- jietuba_public: 公共配置和工具函数

使用方法:
    直接运行此文件启动截图工具:
    python main.py
"""
import sys
import os
import gc
import time
import threading
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QComboBox, QSystemTrayIcon, QMenu, QAction, 
    QMessageBox, QDialog, QFormLayout, QLineEdit
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPen, QBrush
from PyQt5.QtCore import pyqtSignal, QTimer, Qt, pyqtSlot, QAbstractNativeEventFilter, QSettings, QRect, QPoint

# 导入截图核心功能
from jietuba_screenshot import Slabel
from jietuba_public import CONFIG_DICT

# 内置全局快捷键实现（Windows）
# 使用 RegisterHotKey + 原生事件过滤器捕获 WM_HOTKEY
import ctypes
from ctypes import wintypes

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000  # 避免长按重复触发（Vista+）


# AppSettingsDialog类已合并到SettingsDialog中


def _parse_hotkey(hotkey: str):
    """将字符串热键解析为 (modifiers, vk)。

    支持示例：
    - "ctrl+shift+a"
    - "alt+f1"
    - "win+shift+s"
    - "ctrl+1"
    返回: (mods, vk) 或抛出 ValueError
    """
    if not hotkey or not isinstance(hotkey, str):
        raise ValueError("无效的热键字符串")

    parts = [p.strip().lower() for p in hotkey.split('+') if p.strip()]
    if not parts:
        raise ValueError("热键不能为空")

    mods = 0
    key = None

    for p in parts:
        if p in ("ctrl", "control"):  
            mods |= MOD_CONTROL
        elif p == "alt":
            mods |= MOD_ALT
        elif p in ("shift",):
            mods |= MOD_SHIFT
        elif p in ("win", "meta", "super"):
            mods |= MOD_WIN
        else:
            key = p

    if not key:
        raise ValueError("缺少主键位，如 A/F1/1")

    # 映射主键到 VK
    vk = None
    # 字母
    if len(key) == 1 and 'a' <= key <= 'z':
        vk = ord(key.upper())
    # 数字 0-9
    elif key.isdigit() and len(key) == 1:
        vk = ord(key)
    # 功能键 F1-F24
    elif key.startswith('f') and key[1:].isdigit():
        n = int(key[1:])
        if 1 <= n <= 24:
            vk = 0x70 + (n - 1)  # VK_F1=0x70
    # 常见命名
    elif key in ("printscreen", "prtSc", "prtsc"):
        vk = 0x2C

    if vk is None:
        raise ValueError(f"不支持的键: {key}")

    # 默认启用 NOREPEAT，减少误触
    mods |= MOD_NOREPEAT
    return mods, vk


class _HotkeyEventFilter(QAbstractNativeEventFilter):
    """拦截 Windows 消息，处理 WM_HOTKEY。"""

    def __init__(self, id_to_callback: dict):
        super().__init__()
        self._id_to_callback = id_to_callback

    def nativeEventFilter(self, eventType, message):
        try:
            # PyQt5 传入的是一个指针，可转为 int 地址
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                hotkey_id = msg.wParam
                cb = self._id_to_callback.get(hotkey_id)
                if cb:
                    try:
                        cb()
                    except Exception:
                        pass
                    return True, 0
        except Exception:
            # 忽略解析异常，保持应用稳定
            return False, 0
        return False, 0


class WindowsHotkeyManager:
    """轻量 Windows 全局热键管理器。"""

    def __init__(self, app: QApplication):
        self._user32 = ctypes.windll.user32
        # 定义函数原型
        self._RegisterHotKey = self._user32.RegisterHotKey
        self._RegisterHotKey.argtypes = [wintypes.HWND, wintypes.INT, wintypes.UINT, wintypes.UINT]
        self._RegisterHotKey.restype = wintypes.BOOL

        self._UnregisterHotKey = self._user32.UnregisterHotKey
        self._UnregisterHotKey.argtypes = [wintypes.HWND, wintypes.INT]
        self._UnregisterHotKey.restype = wintypes.BOOL

        self._next_id = 1
        self._id_to_callback = {}
        self._event_filter = _HotkeyEventFilter(self._id_to_callback)
        # 必须保存引用并安装过滤器
        app.installNativeEventFilter(self._event_filter)

    def register_hotkey(self, hotkey: str, callback) -> bool:
        mods, vk = _parse_hotkey(hotkey)
        hotkey_id = self._next_id
        if not self._RegisterHotKey(None, hotkey_id, mods, vk):
            return False
        self._id_to_callback[hotkey_id] = callback
        self._next_id += 1
        return True

    def unregister_all(self):
        # 注销已注册的热键
        for hotkey_id in list(self._id_to_callback.keys()):
            try:
                self._UnregisterHotKey(None, hotkey_id)
            except Exception:
                pass
            self._id_to_callback.pop(hotkey_id, None)


class SettingsDialog(QDialog):
    """应用设置对话框（包含快捷键和功能设置）"""

    def __init__(self, config_manager, current_hotkey="ctrl+shift+a", parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.current_hotkey = current_hotkey
        self.setWindowTitle("アプリケーション設定")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.resize(450, 400)  # 增大窗口尺寸以容纳更多设置
        self._setup_ui()

    def _setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 标题说明
        title_label = QLabel("アプリケーション設定")
        title_label.setStyleSheet("font-weight: bold; font-size: 14pt; color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # 快捷键设置区域
        hotkey_group = self._create_hotkey_group()
        layout.addWidget(hotkey_group)

        # 截图功能设置区域  
        screenshot_group = self._create_screenshot_group()
        layout.addWidget(screenshot_group)

        layout.addStretch()

        # 按钮区域
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setSpacing(10)

        # 确定按钮
        ok_btn = QPushButton("適用")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 20px;
                font-size: 10pt;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        btn_layout.addWidget(ok_btn)

        # 取消按钮
        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 20px;
                font-size: 10pt;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        btn_layout.addWidget(cancel_btn)

        layout.addWidget(btn_widget)
        self.setLayout(layout)

        # 设置焦点到输入框
        self.hotkey_input.setFocus()
        self.hotkey_input.selectAll()

    def _create_hotkey_group(self):
        """创建快捷键设置组"""
        from PyQt5.QtWidgets import QGroupBox, QFormLayout, QLineEdit
        
        group = QGroupBox("ショートカット設定")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ddd;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(10)
        
        # 说明文字
        desc_label = QLabel("スクリーンショットのホットキーを設定してください")
        desc_label.setStyleSheet("color: #666; font-size: 10pt;")
        group_layout.addWidget(desc_label)
        
        # 快捷键输入
        form_layout = QFormLayout()
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setText(self.current_hotkey)
        self.hotkey_input.setPlaceholderText("例: ctrl+shift+a")
        self.hotkey_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                font-size: 11pt;
                border: 2px solid #ddd;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
        """)
        form_layout.addRow("ホットキー:", self.hotkey_input)
        group_layout.addLayout(form_layout)
        
        return group
    
    def _create_screenshot_group(self):
        """创建截图功能设置组"""
        from PyQt5.QtWidgets import QGroupBox, QCheckBox
        
        group = QGroupBox("スクリーンショット機能")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ddd;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(10)
        
        # 智能选择功能
        self.smart_selection_checkbox = QCheckBox("スマート選択を有効にする")
        self.smart_selection_checkbox.setChecked(self.config_manager.get_smart_selection())
        self.smart_selection_checkbox.setStyleSheet("""
            QCheckBox {
                color: #333;
                font-size: 10pt;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #ddd;
                background-color: white;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4CAF50;
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        
        # 添加说明文字
        description = QLabel("※ スマート選択は、画面内の矩形領域（ウィンドウやボタンなど）を自動的に認識し，\n   より正確にスクリーンショットの範囲を選択できるようにします。")
        description.setStyleSheet("color: #666; font-size: 9pt; margin-left: 25px;")
        
        group_layout.addWidget(self.smart_selection_checkbox)
        group_layout.addWidget(description)
        
        # 任务栏按钮功能
        self.taskbar_button_checkbox = QCheckBox("タスクバーにスクリーンショットボタンを表示")
        self.taskbar_button_checkbox.setChecked(self.config_manager.get_taskbar_button())
        self.taskbar_button_checkbox.setStyleSheet("""
            QCheckBox {
                color: #333;
                font-size: 10pt;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #ddd;
                background-color: white;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4CAF50;
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        
        taskbar_description = QLabel("※ タスクバーにスクリーンショットボタンを固定表示します。\n   クリックするとスクリーンショットが起動します。")
        taskbar_description.setStyleSheet("color: #666; font-size: 9pt; margin-left: 25px;")
        
        group_layout.addWidget(self.taskbar_button_checkbox)
        group_layout.addWidget(taskbar_description)
        
        return group

    def get_hotkey(self):
        """获取设置的快捷键"""
        return self.hotkey_input.text().strip()
    
    def accept(self):
        """应用设置"""
        # 保存智能选择设置
        self.config_manager.set_smart_selection(self.smart_selection_checkbox.isChecked())
        print(f"💾 智能选择设置已保存: {self.smart_selection_checkbox.isChecked()}")
        
        # 保存任务栏按钮设置
        self.config_manager.set_taskbar_button(self.taskbar_button_checkbox.isChecked())
        print(f"💾 任务栏按钮设置已保存: {self.taskbar_button_checkbox.isChecked()}")
        
        super().accept()

    def keyPressEvent(self, event):
        """处理键盘事件，回车确认"""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.accept()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)




class TaskbarButton(QWidget):
    """任务栏截图按钮窗口"""
    clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("jietuba Screenshot")
        
        # 设置窗口标志：工具窗口，始终在顶层
        self.setWindowFlags(
            Qt.Tool |  # 工具窗口，会在任务栏显示
            Qt.WindowStaysOnTopHint |  # 始终置顶
            Qt.FramelessWindowHint  # 无边框
        )
        
        # 设置窗口大小和样式（支持DPI缩放）
        self._setup_dpi_aware_size()
        self.setup_ui()
        
        # 定位到屏幕左下角
        self.position_at_taskbar()
    
    def _setup_dpi_aware_size(self):
        """设置支持DPI缩放的窗口大小"""
        try:
            # 获取当前屏幕的DPI比例
            screen = QApplication.primaryScreen()
            logical_dpi = screen.logicalDotsPerInch()
            dpi_ratio = logical_dpi / 96.0
            dpi_ratio = max(0.5, min(dpi_ratio, 3.0))  # 限制范围
            
            # 基础大小（100%缩放下）- 调整为更小的尺寸
            base_size = 48
            
            # 应用DPI缩放
            scaled_size = int(base_size * dpi_ratio)
            
            self.setFixedSize(scaled_size, scaled_size)
            self._button_size = int(40 * dpi_ratio)  # 保存按钮大小供后续使用
            
            print(f"任务栏按钮DPI适配: {scaled_size}x{scaled_size} (DPI比例: {dpi_ratio:.2f})")
        except Exception as e:
            print(f"任务栏按钮DPI适配失败: {e}")
            self.setFixedSize(60, 60)
            self._button_size = 50
        
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)  # 减小边距让按钮更紧凑
        
        # 创建按钮
        self.btn = QPushButton()
        button_size = getattr(self, '_button_size', 50)
        self.btn.setFixedSize(button_size, button_size)
        self.btn.setIcon(create_app_icon())
        self.btn.setIconSize(self.btn.size())
        self.btn.clicked.connect(self.clicked.emit)
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(245, 245, 245, 200);
                border: 2px solid #999;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: rgba(230, 230, 230, 220);
                border: 2px solid #666;
            }
            QPushButton:pressed {
                background-color: rgba(200, 200, 200, 240);
                border: 2px solid #333;
            }
        """)
        self.btn.setToolTip("左クリック: スクリーンショット開始\n右クリック: ボタン位置を移動")
        
        layout.addWidget(self.btn)
        self.setLayout(layout)
        
        # 设置窗口背景透明
        self.setAttribute(Qt.WA_TranslucentBackground)
        
    def position_at_taskbar(self):
        """定位到任务栏左侧，确保不被任务栏遮挡"""
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        
        # 定位到左下角，留出任务栏空间
        x = 10  # 距离左边10像素
        
        # 设置最低Y坐标，防止被任务栏挡住（距离底部至少125像素）
        min_y_from_bottom = 125  # 任务栏预留空间
        y = screen.height() - min_y_from_bottom
        
        self.move(x, y)
        print(f"任务栏按钮定位: ({x}, {y}) 屏幕尺寸: {screen.width()}x{screen.height()}")
    
    def mousePressEvent(self, event):
        """鼠标按下事件 - 右键拖动窗口"""
        if event.button() == Qt.RightButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 右键拖动窗口，支持多显示器，只限制Y坐标防止被任务栏遮挡"""
        if event.buttons() == Qt.RightButton and hasattr(self, 'drag_position'):
            new_pos = event.globalPos() - self.drag_position
            
            # 获取鼠标所在的显示器
            current_screen = QApplication.screenAt(event.globalPos())
            if current_screen is None:
                current_screen = QApplication.primaryScreen()
            
            screen_rect = current_screen.geometry()
            
            # X坐标不限制，允许跨显示器移动
            x = new_pos.x()
            
            # 只限制Y坐标，防止被任务栏遮挡
            min_y_from_bottom = 125  # 任务栏预留空间
            max_y = screen_rect.bottom() - min_y_from_bottom + 1  # +1是因为bottom()返回的是包含边界
            
            # Y坐标限制：不能超出当前屏幕顶部，不能太接近底部
            y = max(screen_rect.top(), min(new_pos.y(), max_y))
            
            # 应用位置
            self.move(x, y)
            event.accept()
        else:
            super().mouseMoveEvent(event)


def create_app_icon():
    """创建应用程序图标 - 相机样式"""
    # 创建32x32的图标
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)  # 透明背景
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 设置画笔和画刷
    pen = QPen(Qt.black, 2)
    painter.setPen(pen)
    
    # 画相机主体 (矩形)
    camera_body = QRect(4, 12, 24, 16)
    painter.fillRect(camera_body, Qt.darkGray)
    painter.drawRect(camera_body)
    
    # 画镜头 (圆形)
    lens_center = QPoint(16, 20)
    painter.setBrush(QBrush(Qt.black))
    painter.drawEllipse(lens_center, 6, 6)
    
    # 画镜头内圈
    painter.setBrush(QBrush(Qt.lightGray))
    painter.drawEllipse(lens_center, 4, 4)
    
    # 画取景器
    viewfinder = QRect(10, 8, 12, 4)
    painter.fillRect(viewfinder, Qt.lightGray)
    painter.drawRect(viewfinder)
    
    # 画闪光灯
    flash = QRect(24, 8, 3, 3)
    painter.fillRect(flash, Qt.yellow)
    painter.drawRect(flash)
    
    painter.end()
    return QIcon(pixmap)


class ConfigManager:
    """配置管理器"""
    def __init__(self):
        # 使用与项目一致的设置命名空间
        self.settings = QSettings('Fandes', 'jietuba')
        self.hotkey_default = "ctrl+shift+a"
        self.right_click_close_default = True
        self.smart_selection_default = False  # 智能选择默认关闭
        self.taskbar_button_default = False  # 任务栏按钮默认关闭
    
    def get_hotkey(self):
        return self.settings.value('hotkey/global', self.hotkey_default, type=str)
    
    def set_hotkey(self, hotkey):
        self.settings.setValue('hotkey/global', hotkey)
    
    def get_right_click_close(self):
        return self.settings.value('ui/right_click_close', self.right_click_close_default, type=bool)
    
    def get_smart_selection(self):
        return self.settings.value('screenshot/smartcursor', self.smart_selection_default, type=bool)
    
    def set_smart_selection(self, enabled):
        self.settings.setValue('screenshot/smartcursor', enabled)
    
    def get_taskbar_button(self):
        """获取任务栏按钮开关状态"""
        return self.settings.value('ui/taskbar_button', self.taskbar_button_default, type=bool)
    
    def set_taskbar_button(self, enabled):
        """设置任务栏按钮开关状态"""
        self.settings.setValue('ui/taskbar_button', enabled)
    
    # 绘画工具配置管理
    def get_tool_settings(self):
        """获取所有绘画工具的配置"""
        # 默认工具配置
        default_settings = {
            'pen_on': {'size': 3, 'alpha': 255, 'color': '#ff0000'},           # 画笔：细一些，完全不透明，红色
            'highlight_on': {'size': 30, 'alpha': 255, 'color': '#ffeb3b'},    # 荧光笔：更粗，完全不透明，黄色
            'drawarrow_on': {'size': 2, 'alpha': 255, 'color': '#ff0000'},     # 箭头：更细，完全不透明，红色
            'drawrect_bs_on': {'size': 2, 'alpha': 200, 'color': '#ff0000'},   # 矩形：细边框，半透明，红色
            'drawcircle_on': {'size': 2, 'alpha': 200, 'color': '#ff0000'},    # 圆形：细边框，半透明，红色
            'drawtext_on': {'size': 16, 'alpha': 255, 'color': '#ff0000'},     # 文字：16像素字体，完全不透明，红色
        }
        
        # 从配置文件读取，如果没有则使用默认值
        saved_settings = {}
        for tool_name, default_config in default_settings.items():
            saved_settings[tool_name] = {
                'size': self.settings.value(f'tools/{tool_name}/size', default_config['size'], type=int),
                'alpha': self.settings.value(f'tools/{tool_name}/alpha', default_config['alpha'], type=int),
                'color': self.settings.value(f'tools/{tool_name}/color', default_config['color'], type=str)
            }
        
        return saved_settings
    
    def set_tool_setting(self, tool_name, setting_key, value):
        """保存单个工具的设置"""
        self.settings.setValue(f'tools/{tool_name}/{setting_key}', value)
        print(f"💾 [配置保存] 工具 {tool_name} 的 {setting_key} 已保存: {value}")
    
    def get_tool_setting(self, tool_name, setting_key, default_value):
        """获取单个工具的设置"""
        return self.settings.value(f'tools/{tool_name}/{setting_key}', default_value)


class MainWindow(QMainWindow):
    """主窗口"""
    screenshot_signal = pyqtSignal()

    def __init__(self, single_instance=None):
        super().__init__()
        self.single_instance = single_instance
        
        # 初始化截图组件
        self.screenshot_widget = None
        self.freeze_imgs = []  # 储存固定截屏在屏幕上的数组
        self._just_created_pin_window = False  # 标志是否刚刚创建了钉图窗口

        # 初始化组件
        self.config_manager = ConfigManager()
        
        # 初始化快捷键管理器
        self.hotkey_manager = None
        self.current_hotkey_id = None
        self._init_hotkey_manager()
        
        # 加载配置
        self._load_config()
        
        # 初始化界面
        self._setup_window()
        self._setup_ui()
        self._setup_tray()
        self._setup_signals()

        # 初始化截图组件
        self._setup_screenshot()

        # 设置窗口状态监控
        self._setup_window_monitor()
        
        # 初始化任务栏按钮
        self.taskbar_button = None
        self._setup_taskbar_button()

        # 标记程序是否真正退出
        self.really_quit = False

        # 程序启动后做一次“长截图”相关的轻量预热，避免首次点击时卡顿
        self._schedule_long_screenshot_warm_up()

    def _schedule_long_screenshot_warm_up(self):
        """异步预热长截图所需的重资源，减少首次点击卡顿。

        预热内容：
        - 后台线程导入 pynput 并启动/停止一次 Listener（初始化底层钩子）
        - 后台线程触发 Pillow 的基本路径（Image.new + tobytes）
        - UI 线程做一次极小区域的屏幕抓取，初始化 Qt 截屏通道
        """
        try:
            # 后台模块预热：避免阻塞UI
            def _bg_warmup():
                try:
                    from pynput import mouse
                    # 启停一次监听器，完成底层钩子初始化
                    l = mouse.Listener(on_scroll=lambda *a, **k: None)
                    l.start()
                    l.stop()
                except Exception as e:
                    print(f"[warmup] 跳过pynput预热: {e}")

                try:
                    from PIL import Image as _PILImage
                    _ = _PILImage.new('RGB', (1, 1)).tobytes()
                except Exception as e:
                    print(f"[warmup] 跳过Pillow预热: {e}")

            threading.Thread(target=_bg_warmup, daemon=True).start()

            # UI线程预热：做一次1x1像素抓取，初始化Qt截图路径
            def _ui_warmup():
                try:
                    screen = QApplication.primaryScreen()
                    if screen is not None:
                        # 一些平台上宽或高为0会失败，使用 1x1
                        _ = screen.grabWindow(0, 0, 0, 1, 1)
                except Exception as e:
                    print(f"[warmup] 跳过Qt抓取预热: {e}")

            QTimer.singleShot(800, _ui_warmup)
        except Exception as e:
            print(f"[warmup] 预热调度失败: {e}")
    
    def _setup_window_monitor(self):
        """设置窗口状态监控，防止窗口状态异常"""
        # 记录初始显示器配置
        self._last_screen_count = len(QApplication.screens())
        self._last_primary_screen_geometry = QApplication.primaryScreen().geometry()
        self._last_dpi_ratio = self._get_current_screen_dpi_ratio(QApplication.primaryScreen())
        
        self.window_monitor_timer = QTimer()
        self.window_monitor_timer.timeout.connect(self._check_window_state)
        self.window_monitor_timer.start(5000)  # 5秒检查一次（更频繁以快速响应显示器变化）
        print("🔍 [DEBUG] 窗口状态监控已启动")
    
    def _check_window_state(self):
        """检查窗口状态，自动修复异常，包括显示器配置变化"""
        try:
            # 检查显示器配置是否发生变化
            current_screen_count = len(QApplication.screens())
            current_primary_screen_geometry = QApplication.primaryScreen().geometry()
            current_dpi_ratio = self._get_current_screen_dpi_ratio(QApplication.primaryScreen())
            
            # 检测到显示器配置变化
            screen_config_changed = (
                current_screen_count != self._last_screen_count or
                current_primary_screen_geometry != self._last_primary_screen_geometry or
                abs(current_dpi_ratio - self._last_dpi_ratio) > 0.1  # DPI变化超过10%
            )
            
            if screen_config_changed:
                print("🔍 [MONITOR] 检测到显示器配置变化，重新调整窗口大小...")
                print(f"   屏幕数量: {self._last_screen_count} -> {current_screen_count}")
                print(f"   主屏几何: {self._last_primary_screen_geometry} -> {current_primary_screen_geometry}")
                print(f"   DPI比例: {self._last_dpi_ratio:.2f} -> {current_dpi_ratio:.2f}")
                
                # 通知截图模块刷新屏幕缓存
                if hasattr(self, 'screenshot_widget') and self.screenshot_widget:
                    self.screenshot_widget.refresh_screen_cache()
                
                # 重新设置窗口大小以适应新的显示器配置
                self._setup_window_size()
                
                # 重新定位任务栏按钮（如果存在）
                if hasattr(self, 'taskbar_button') and self.taskbar_button and self.taskbar_button.isVisible():
                    self.taskbar_button.position_at_taskbar()
                
                # 更新记录
                self._last_screen_count = current_screen_count
                self._last_primary_screen_geometry = current_primary_screen_geometry
                self._last_dpi_ratio = current_dpi_ratio
            
            # 检查窗口是否意外变透明
            if self.windowOpacity() < 0.5:
                print("⚠️ [WARN] 检测到窗口透明度异常，正在修复...")
                self.setWindowOpacity(1)
            
            # 检查窗口是否在所有屏幕外（支持多显示器）
            all_screens_geometry = QRect()
            for screen in QApplication.screens():
                all_screens_geometry = all_screens_geometry.united(screen.geometry())
            
            window_center_x = self.x() + self.width() // 2
            window_center_y = self.y() + self.height() // 2
            
            if not all_screens_geometry.contains(window_center_x, window_center_y):
                print("⚠️ [WARN] 检测到窗口位置异常，正在修复...")
                primary_geometry = QApplication.primaryScreen().geometry()
                center_x = primary_geometry.x() + (primary_geometry.width() - self.width()) // 2
                center_y = primary_geometry.y() + (primary_geometry.height() - self.height()) // 2
                self.move(center_x, center_y)
                
        except Exception as e:
            print(f"❌ [ERROR] 窗口状态检查时出错: {e}")

    def _setup_screenshot(self):
        """初始化截图组件"""
        self.screenshot_widget = Slabel(self)
        self.screenshot_widget.close_signal.connect(self._on_screenshot_end)
    
    def _setup_taskbar_button(self):
        """初始化任务栏按钮"""
        if self.config_manager.get_taskbar_button():
            self._show_taskbar_button()
        else:
            self._hide_taskbar_button()
    
    def _show_taskbar_button(self):
        """显示任务栏按钮"""
        if self.taskbar_button is None:
            self.taskbar_button = TaskbarButton()
            self.taskbar_button.clicked.connect(self.start_screenshot)
            print("✅ 任务栏按钮已创建")
        self.taskbar_button.show()
        print("✅ 任务栏按钮已显示")
    
    def _hide_taskbar_button(self):
        """隐藏任务栏按钮"""
        if self.taskbar_button is not None:
            self.taskbar_button.hide()
            print("✅ 任务栏按钮已隐藏")
    
    def _toggle_taskbar_button(self, enabled):
        """切换任务栏按钮显示状态"""
        if enabled:
            self._show_taskbar_button()
        else:
            self._hide_taskbar_button()
    
    def _init_hotkey_manager(self):
        """初始化快捷键管理器（Windows 原生实现）。"""
        try:
            app = QApplication.instance()
            if os.name == 'nt' and app is not None:
                self.hotkey_manager = WindowsHotkeyManager(app)
                print("快捷键管理器初始化成功 (Windows 原生)")
            else:
                self.hotkey_manager = None
                print("快捷键管理器不可用（非 Windows 或 App 未就绪）")
        except Exception as e:
            print(f"初始化快捷键管理器失败: {e}")
            self.hotkey_manager = None
    
    def _register_hotkey(self, hotkey_str):
        """注册全局快捷键"""
        print(f"🔍 [DEBUG] 尝试注册快捷键: {hotkey_str}")
        
        if not self.hotkey_manager:
            print("❌ 快捷键管理器未初始化")
            return False
            
        try:
            # 先注销之前的快捷键
            print(f"🔍 [DEBUG] 注销现有快捷键")
            self.hotkey_manager.unregister_all()
            
            # 注册新快捷键
            print(f"🔍 [DEBUG] 注册新快捷键: {hotkey_str}")
            success = self.hotkey_manager.register_hotkey(hotkey_str, self.start_screenshot)
            if success:
                print(f"✅ 全局快捷键注册成功: {hotkey_str}")
                return True
            else:
                print(f"❌ 全局快捷键注册失败: {hotkey_str}")
                return False
        except Exception as e:
            print(f"❌ 注册快捷键时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def _on_screenshot_end(self):
        """截图结束回调"""
        print("截图完成")
        
    def _setup_window(self):
        """设置窗口属性"""
        self.setWindowTitle("jietuba")
        self.setWindowIcon(create_app_icon())
        self._setup_window_size()

    def _setup_window_size(self):
        """设置窗口大小 - 支持DPI缩放适配"""
        try:
            app = QApplication.instance()
            
            # 获取当前主显示器
            primary_screen = app.primaryScreen()
            screen_geometry = primary_screen.geometry()
            
            # 获取DPI缩放比例
            dpi_ratio = self._get_current_screen_dpi_ratio(primary_screen)
            
            # 基础尺寸（在100% DPI下的理想大小）- 调整为更小的尺寸
            base_width = 180
            base_height = 100
            base_min_width = 260
            base_min_height = 200
            base_max_width = 480
            base_max_height = 360
            
            # 应用DPI缩放
            width = int(base_width * dpi_ratio)
            height = int(base_height * dpi_ratio)
            min_width = int(base_min_width * dpi_ratio)
            min_height = int(base_min_height * dpi_ratio)
            max_width = int(base_max_width * dpi_ratio)
            max_height = int(base_max_height * dpi_ratio)

            # 居中定位
            x = (screen_geometry.width() - width) // 2
            y = (screen_geometry.height() - height) // 2
            
            self.setGeometry(x, y, width, height)
            self.setMinimumSize(min_width, min_height)
            self.setMaximumSize(max_width, max_height)

            print(f"窗口大小已设置: {width}x{height} (DPI缩放: {dpi_ratio:.2f})")
            
        except Exception as e:
            print(f"设置窗口大小时出错: {e}")
            # 回退到固定大小
            self.setGeometry(300, 300, 400, 320)
            self.setMinimumSize(400, 320)
            self.setMaximumSize(520, 416)
    
    def _get_current_screen_dpi_ratio(self, screen):
        """获取当前屏幕的DPI缩放比例"""
        try:
            # 获取逻辑DPI
            logical_dpi = screen.logicalDotsPerInch()
            # 标准DPI是96
            dpi_ratio = logical_dpi / 96.0
            
            # 限制缩放比例在合理范围内
            dpi_ratio = max(0.5, min(dpi_ratio, 3.0))
            
            return dpi_ratio
        except Exception as e:
            print(f"获取DPI比例失败: {e}")
            return 1.0  # 默认不缩放

    def _setup_ui(self):
        """设置用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ffffff;
            }
            QWidget {
                font-family: 'Microsoft YaHei', Arial, sans-serif;
                font-size: 9pt;
            }
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 6px 12px;
                color: #495057;
                min-height: 16px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
            QPushButton#primaryButton {
                background-color: #007bff;
                color: white;
                border-color: #007bff;
                font-weight: 500;
            }
            QPushButton#primaryButton:hover {
                background-color: #0056b3;
            }
            QPushButton#dangerButton {
                background-color: #dc3545;
                color: white;
                border-color: #dc3545;
            }
            QPushButton#dangerButton:hover {
                background-color: #c82333;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 16px;
            }
            QComboBox:hover {
                border-color: #80bdff;
            }
            QLabel {
                color: #495057;
            }
            QLabel#statusLabel {
                color: #6c757d;
                font-size: 8pt;
                padding: 2px 6px;
                background-color: #f8f9fa;
                border-radius: 3px;
            }
            QLabel#hotkeyLabel {
                color: #28a745;
                font-size: 8pt;
                font-weight: 500;
                padding: 2px 6px;
                background-color: #d4edda;
                border: 1px solid #c3e6cb;
                border-radius: 3px;
            }
            QLabel#versionLabel {
                color: #6c757d;
                font-size: 7pt;
                font-weight: 400;
                margin-top: 4px;
            }
        """)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        
        # 主要操作按钮
        self._create_main_buttons(main_layout)
        
        # 控制按钮
        self._create_control_buttons(main_layout)
        
        # 状态信息
        self._create_status_section(main_layout)
        
        main_layout.addStretch()

    def _create_main_buttons(self, parent_layout):
        """创建主要操作按钮"""
        self.screenshot_btn = QPushButton("スクショ開始")
        self.screenshot_btn.setObjectName("primaryButton")
        self.screenshot_btn.clicked.connect(self.start_screenshot)
        parent_layout.addWidget(self.screenshot_btn)
    
    def _create_control_buttons(self, parent_layout):
        """创建控制按钮"""
        control_layout = QHBoxLayout()
        control_layout.setSpacing(6)
        
        # 设置按钮
        self.settings_btn = QPushButton("設定")
        self.settings_btn.clicked.connect(self.open_settings)

        # 最小化到托盘按钮
        self.minimize_btn = QPushButton("トレイに最小化")
        self.minimize_btn.clicked.connect(self.hide_to_tray)
        
        control_layout.addWidget(self.settings_btn)
        control_layout.addWidget(self.minimize_btn)
        parent_layout.addLayout(control_layout)
        
        # 退出按钮单独一行
        self.exit_btn = QPushButton("アプリを終了")
        self.exit_btn.setObjectName("dangerButton")
        self.exit_btn.clicked.connect(self.quit_application)
        parent_layout.addWidget(self.exit_btn)
    
    def _create_status_section(self, parent_layout):
        """创建状态信息区域"""
        status_layout = QVBoxLayout()
        status_layout.setSpacing(4)
        
        # 快捷键显示标签
        self.hotkey_label = QLabel()
        self.hotkey_label.setObjectName("hotkeyLabel")
        self.hotkey_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.hotkey_label)

        # 状态信息
        self.status_label = QLabel("待機中")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.status_label)
        
        # 版本信息
        self.version_label = QLabel("バージョン: 1.03 | 更新日: 2025.11/13")
        self.version_label.setObjectName("versionLabel")
        self.version_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.version_label)
        
        parent_layout.addLayout(status_layout)

        # 更新快捷键显示
        self._update_hotkey_display()

    def _setup_tray(self):
        """设置系统托盘"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "システムトレイ", "システムはトレイ機能をサポートしていません")
            return

        icon = create_app_icon()
        self.tray_icon = QSystemTrayIcon(icon, self)
        
        # 创建托盘菜单
        self._create_tray_menu()
        
        self.tray_icon.setToolTip("jietuba - ダブルクリックでメインウィンドウを表示")
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
        self.tray_icon.show()

    def _create_tray_menu(self):
        """创建托盘菜单"""
        tray_menu = QMenu()
        
        screenshot_action = QAction("スクリーンショット", self)
        screenshot_action.triggered.connect(self.start_screenshot)
        tray_menu.addAction(screenshot_action)
        
        show_action = QAction("メインウィンドウを表示", self)
        show_action.triggered.connect(self.show_main_window)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("終了", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)

    def _setup_signals(self):
        """设置信号连接"""
        self.screenshot_signal.connect(self.start_screenshot)

    def _load_config(self):
        """加载配置"""
        # 读取并应用快捷键
        self.current_hotkey = self.config_manager.get_hotkey()
        self.right_click_close = self.config_manager.get_right_click_close()
        print(f"加载配置完成 - 快捷键: {self.current_hotkey}")
        
        # 注册全局快捷键
        self._register_hotkey(self.current_hotkey)

    def _update_hotkey_display(self):
        """更新快捷键显示"""
        self.hotkey_label.setText(f"ショートカット: {self.current_hotkey}")

    def start_screenshot(self):
        """开始截图"""
        print("开始截图...")
        self.status_label.setText("スクリーンショット中...")
        
        # 关闭所有打开的对话框（包括设置对话框）
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                print(f"🔍 [截图准备] 发现打开的对话框，正在关闭: {widget.windowTitle()}")
                widget.close()
        
        # 安全地隐藏主窗口 - 使用hide()而不是透明度和移动
        self._was_visible = self.isVisible()  # 记录原始可见状态
        if self._was_visible:
            self.temppos = [self.x(), self.y()]  # 保存位置
            self.hide()  # 简单隐藏，不使用透明度
        
        # 隐藏任务栏按钮（如果存在）
        self._taskbar_button_was_visible = False
        if hasattr(self, 'taskbar_button') and self.taskbar_button and self.taskbar_button.isVisible():
            self._taskbar_button_was_visible = True
            self.taskbar_button.hide()
            print("✅ 任务栏按钮已隐藏用于截图")
        
        # 延迟一小段时间确保窗口完全隐藏
        QTimer.singleShot(50, self._do_screenshot)
    
    def _do_screenshot(self):
        """实际执行截图"""
        # 开始截图
        if self.screenshot_widget:
            self.screenshot_widget.screen_shot()

    def _on_screenshot_end(self):
        """截图结束处理"""
        print("截图结束")
        self.status_label.setText("待機中")
        
        # 恢复任务栏按钮（如果之前是显示的）
        if hasattr(self, '_taskbar_button_was_visible') and self._taskbar_button_was_visible:
            if hasattr(self, 'taskbar_button') and self.taskbar_button:
                self.taskbar_button.show()
                print("✅ 任务栏按钮已恢复显示")
            self._taskbar_button_was_visible = False  # 重置标志
        
        # 检查是否刚刚创建了钉图窗口
        just_created_pin = getattr(self, '_just_created_pin_window', False)
        if just_created_pin:
            print("🔒 刚刚创建了钉图窗口，保持主窗口在托盘状态")
            self._just_created_pin_window = False  # 重置标志
        else:
            # 安全地恢复主窗口 - 只有在非钉图创建的情况下才恢复
            try:
                if hasattr(self, '_was_visible') and self._was_visible:
                    # 恢复位置和显示状态
                    if hasattr(self, 'temppos'):
                        self.move(self.temppos[0], self.temppos[1])
                    self.show()
                    self.setWindowOpacity(1)  # 确保不透明
                    self.raise_()
                    self.activateWindow()
                print("✅ 主窗口已恢复显示")
            except Exception as e:
                print(f"⚠️ 恢复主窗口时出错: {e}")
                # 强制恢复
                self.show()
                self.setWindowOpacity(1)
                self.raise_()
        
        # 重新创建截图组件
        try:
            del self.screenshot_widget
            gc.collect()
            self.screenshot_widget = Slabel(self)
            self.screenshot_widget.close_signal.connect(self._on_screenshot_end)
        except Exception as e:
            print(f"⚠️ 重新创建截图组件时出错: {e}")

    def open_settings(self):
        """打开应用设置对话框（包含快捷键和功能设置）"""
        try:
            print(f"🔍 [DEBUG] 打开应用设置对话框，当前快捷键: {self.current_hotkey}")
            
            dialog = SettingsDialog(self.config_manager, self.current_hotkey, self)
            print("🔍 [DEBUG] 设置对话框已创建")
            
            result = dialog.exec_()
            print(f"🔍 [DEBUG] 对话框执行结果: {result}")
            
            if result == QDialog.Accepted:
                new_hotkey = dialog.get_hotkey()
                print(f"🔍 [DEBUG] 用户输入的新快捷键: '{new_hotkey}'")
                
                if new_hotkey and new_hotkey != self.current_hotkey:
                    print(f"🔍 [DEBUG] 开始更新快捷键: {self.current_hotkey} -> {new_hotkey}")
                    # 注册新的快捷键
                    if self._register_hotkey(new_hotkey):
                        self.current_hotkey = new_hotkey
                        self.config_manager.set_hotkey(new_hotkey)
                        # 立即刷新主界面显示的快捷键信息
                        self._update_hotkey_display()
                        print(f"✅ 快捷键已更新: {new_hotkey}")
                        
                        # 显示成功消息
                        QMessageBox.information(
                            self, 
                            "設定完了", 
                            f"ホットキーが正常に設定されました:\n{new_hotkey}"
                        )
                        
                        # 系统托盘提示
                        if hasattr(self, 'tray_icon'):
                            self.tray_icon.showMessage(
                                "jietuba - ホットキー更新",
                                f"新しいホットキー: {new_hotkey}",
                                QSystemTrayIcon.Information,
                                3000
                            )
                    else:
                        print(f"❌ 快捷键注册失败")
                        # 快捷键注册失败
                        QMessageBox.warning(
                            self,
                            "設定エラー",
                            f"ホットキーの設定に失敗しました:\n{new_hotkey}\n\n他のアプリケーションが使用している可能性があります。"
                        )
                else:
                    print(f"🔍 [DEBUG] 快捷键未改变或为空")
                
                # 更新任务栏按钮状态
                taskbar_enabled = self.config_manager.get_taskbar_button()
                self._toggle_taskbar_button(taskbar_enabled)
                print(f"✅ 任务栏按钮状态已更新: {taskbar_enabled}")
            else:
                print(f"🔍 [DEBUG] 用户取消了设置")
        except Exception as e:
            print(f"❌ 快捷键设置过程中出错: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(
                self,
                "エラー",
                f"ホットキー設定中にエラーが発生しました:\n{str(e)}"
            )

    # 语言设置已整合至热键对话框

    def hide_to_tray(self):
        """最小化到托盘"""
        self.hide()
        self.tray_icon.showMessage(
            "jietuba",
            "アプリケーションはトレイに最小化されました",
            QSystemTrayIcon.Information,
            2000
        )

    def show_main_window(self):
        """显示主窗口 - 增强版，确保窗口能正确显示"""
        try:
            print(f"🔍 [DEBUG] 显示主窗口: 当前状态 visible={self.isVisible()}, opacity={self.windowOpacity()}")
            
            # 确保窗口不透明
            self.setWindowOpacity(1)
            
            # 如果窗口被移动到屏幕外，恢复到屏幕中央
            screen_geometry = QApplication.desktop().screenGeometry()
            if (self.x() < 0 or self.y() < 0 or 
                self.x() > screen_geometry.width() or 
                self.y() > screen_geometry.height()):
                # 窗口在屏幕外，移动到屏幕中央
                center_x = (screen_geometry.width() - self.width()) // 2
                center_y = (screen_geometry.height() - self.height()) // 2
                self.move(center_x, center_y)
                print(f"🔧 [DEBUG] 窗口被移动到屏幕中央: ({center_x}, {center_y})")
            
            # 显示窗口
            self.show()
            self.raise_()
            self.activateWindow()
            
            # 额外的显示保障 - 使用弱引用避免对象被删除时的错误
            import weakref
            weak_self = weakref.ref(self)
            def ensure_visible():
                obj = weak_self()
                if obj is not None:
                    obj._ensure_window_visible()
            QTimer.singleShot(100, ensure_visible)
            
            print(f"✅ [DEBUG] 主窗口显示完成: visible={self.isVisible()}")
        except Exception as e:
            print(f"❌ [ERROR] 显示主窗口时出错: {e}")
    
    def _ensure_window_visible(self):
        """确保窗口可见的额外保障"""
        try:
            if not self.isVisible():
                print("⚠️ [WARN] 窗口仍然不可见，强制显示")
                self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
                self.show()
                self.raise_()
                self.activateWindow()
        except Exception as e:
            print(f"❌ [ERROR] 确保窗口可见时出错: {e}")

    def tray_icon_activated(self, reason):
        """托盘图标激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_main_window()

    def quit_application(self):
        """退出应用程序"""
        reply = QMessageBox.question(
            self, "確認", "アプリケーションを終了しますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.really_quit = True
            
            print("🔄 开始应用程序清理...")
            
            # 清理所有钉图窗口
            if hasattr(self, 'freeze_imgs') and self.freeze_imgs:
                print(f"🧹 清理 {len(self.freeze_imgs)} 个钉图窗口...")
                for window in self.freeze_imgs[:]:  # 使用切片副本避免列表修改问题
                    try:
                        if window:
                            window.clear()
                            window.deleteLater()
                    except:
                        pass
                self.freeze_imgs.clear()
                print("🧹 所有钉图窗口已清理")
            
            # 清理截图组件
            if hasattr(self, 'screenshot_widget') and self.screenshot_widget:
                try:
                    self.screenshot_widget.deleteLater()
                    self.screenshot_widget = None
                    print("🧹 截图组件已清理")
                except:
                    pass
            
            # 清理快捷键
            if self.hotkey_manager:
                self.hotkey_manager.unregister_all()
                print("已注销所有全局快捷键")
            
            # 清理窗口监控定时器
            if hasattr(self, 'window_monitor_timer'):
                self.window_monitor_timer.stop()
                self.window_monitor_timer.deleteLater()
                print("🧹 窗口监控定时器已清理")
            
            # 清理任务栏按钮
            if hasattr(self, 'taskbar_button') and self.taskbar_button:
                try:
                    self.taskbar_button.close()
                    self.taskbar_button.deleteLater()
                    self.taskbar_button = None
                    print("🧹 任务栏按钮已清理")
                except:
                    pass
            
            # 强制垃圾回收
            gc.collect()
            print("🧹 垃圾回收完成")
            
            QApplication.quit()

    def closeEvent(self, event):
        """窗口关闭事件"""
        if not self.really_quit and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "jietuba",
                "アプリケーションはトレイに最小化されました",
                QSystemTrayIcon.Information,
                2000
            )
        else:
            event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    # 托盘应用关键设置：避免所有窗口被隐藏/关闭时自动退出
    # 解决在托盘状态下执行截图、翻译或ESC退出导致程序无提示退出的问题
    try:
        app.setQuitOnLastWindowClosed(False)
    except Exception:
        pass
    
    # 设置DPI感知模式
    try:
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
            if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, 'PassThrough'):
                app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
            else:
                app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Round)
        
        print(f"✅ DPI设置完成: EnableHighDpiScaling={app.testAttribute(Qt.AA_EnableHighDpiScaling)}")
    except Exception as dpi_error:
        print(f"⚠️ DPI设置失败: {dpi_error}")
    
    # 设置应用程序信息
    app.setApplicationName("jietuba")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("ScreenshotMaster")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    print("jietuba启动完成")
    
    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
