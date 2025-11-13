"""
jietuba_scroll.py - 滚动截图窗口模块

实现滚动长截图功能的窗口类,用于捕获滚动页面的多张截图。

主要功能:
- 显示半透明边框窗口标识截图区域
- 监听鼠标滚轮事件自动触发截图
- 实时显示已捕获的截图数量
- 支持手动/自动截图控制

主要类:
- ScrollCaptureWindow: 滚动截图窗口类

特点:
- 窗口透明,不拦截鼠标事件
- 使用 Windows API 监听鼠标滚轮
- 延迟截图机制避免滚动动画干扰
- 支持取消和完成截图操作

依赖模块:
- PyQt5: GUI框架
- PIL: 图像处理
- ctypes: Windows API调用
- pynput: 鼠标事件监听

使用方法:
    window = ScrollCaptureWindow(capture_rect, parent)
    window.finished.connect(on_finished)
    window.show()
"""

import os
import time
import ctypes
from ctypes import wintypes
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QDesktopWidget
from PyQt5.QtCore import Qt, QRect, QTimer, pyqtSignal, QPoint, QMetaObject, Q_ARG
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap, QGuiApplication, QImage
from PIL import Image
import io

# Windows API 常量
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020

import os
import time
import ctypes
from ctypes import wintypes
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QDesktopWidget
from PyQt5.QtCore import Qt, QRect, QTimer, pyqtSignal, QPoint, QMetaObject, Q_ARG
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap, QGuiApplication, QImage
from PIL import Image
import io

# Windows API 常量
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000


class ScrollCaptureWindow(QWidget):
    """滚动长截图窗口
    
    特性:
    - 带边框的透明窗口
    - 🆕 支持自动滚动模式(软件控制)和手动模式(用户滚轮)
    - 自动模式: 软件模拟 PageDown/ArrowDown 按键,精确控制滚动距离
    - 手动模式: 监听滚轮事件,被动触发截图
    - 底部有完成和取消按钮
    """
    
    finished = pyqtSignal()  # 完成信号
    cancelled = pyqtSignal()  # 取消信号
    scroll_detected = pyqtSignal(int)  # 滚轮检测信号(仅手动模式使用)
    
    def __init__(self, capture_rect, parent=None):
        """初始化滚动截图窗口
        
        Args:
            capture_rect: QRect，截图区域（屏幕坐标）
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.capture_rect = capture_rect
        self.screenshots = []  # 存储截图的列表
        
        # 🆕 主动滚动模式配置
        self.auto_scroll_mode = True  # True=软件控制滚动, False=用户手动滚动
        self.scroll_step_ratio = 0.3  # 每次滚动截图区域高度的30% (保证70%重叠) - 🔥 改小重叠更多
        self.scroll_interval = 0.8  # 滚动后等待时间(秒),让内容稳定
        
        # 🆕 平滑滚动配置 - 🔥 高频小步滚动
        self.smooth_scroll_enabled = True  # 启用平滑滚动(像手机长截图)
        self.smooth_scroll_speed = 20  # 每次小步滚动的像素数 🔥 改为20px超平滑
        self.smooth_scroll_delay = 0.015  # 每次小步之间的延迟(秒) 🔥 15ms高频
        
        # 滚动距离记录(用于拼接时的"大致范围")
        self.actual_scroll_distances = []  # 记录每次实际滚动的像素数
        
        # 🆕 自动滚动状态控制
        self.is_auto_scrolling = False  # 是否正在自动滚动
        self.target_window_hwnd = None  # 目标窗口句柄(需要滚动的窗口)
        
        # 定时器
        self.auto_scroll_timer = QTimer(self)  # 自动滚动定时器
        self.auto_scroll_timer.setSingleShot(True)
        self.auto_scroll_timer.timeout.connect(self._auto_scroll_and_capture)
        
        # 手动模式相关(保留兼容)
        self.last_scroll_time = 0
        self.scroll_cooldown = 0.3
        self.capture_mode = "immediate"
        self.scroll_tick_count = 0
        
        self.capture_timer = QTimer(self)
        self.capture_timer.setSingleShot(True)
        self.capture_timer.timeout.connect(self._do_capture)
        
        self.scroll_check_timer = QTimer(self)
        self.scroll_check_timer.setInterval(100)
        self.scroll_check_timer.timeout.connect(self._check_scroll_stopped)
        
        # 去重相关
        self.last_screenshot_hash = None  # 上一张截图的哈希值(用于去重)
        self.duplicate_threshold = 0.95  # 相似度阈值(95%以上认为重复)
        
        # 🆕 仅手动模式需要连接滚轮信号
        if not self.auto_scroll_mode:
            self.scroll_detected.connect(self._handle_scroll_in_main_thread)
        
        self._setup_window()
        self._setup_ui()
        self._setup_mouse_hook()
        
        # 添加强制窗口定位修复定时器（作为最后的保险）
        self._position_fix_timer = QTimer()
        self._position_fix_timer.setSingleShot(True)
        self._position_fix_timer.timeout.connect(self._force_fix_window_position)
        self._position_fix_timer.start(200)  # 200ms后再次检查并修复
    
    def _get_correct_window_position(self, border_width):
        """获取正确的窗口位置，修复多显示器环境下的定位问题"""
        try:
            # 注意：传入的capture_rect已经是真实坐标（在start_long_screenshot_mode中已转换）
            real_x = self.capture_rect.x()
            real_y = self.capture_rect.y()
            real_x1 = real_x + self.capture_rect.width()
            real_y1 = real_y + self.capture_rect.height()
            
            print(f"🎯 [长截图窗口] 截图区域坐标: ({real_x}, {real_y}) -> ({real_x1}, {real_y1})")
            
            # 使用父窗口的屏幕检测方法（与钉图窗口一致）
            target_screen = None
            if (hasattr(self, 'parent') and self.parent and 
                hasattr(self.parent, 'get_screen_for_rect')):
                target_screen = self.parent.get_screen_for_rect(real_x, real_y, real_x1, real_y1)
                screen_rect = target_screen.geometry().getRect()
                screen_x, screen_y, screen_w, screen_h = screen_rect
                print(f"🎯 [长截图] 检测到目标显示器: x={screen_x}, y={screen_y}, w={screen_w}, h={screen_h}")
            else:
                # 回退到原来的方法
                app = QApplication.instance()
                desktop = app.desktop()
                capture_center_x = real_x + self.capture_rect.width() // 2
                capture_center_y = real_y + self.capture_rect.height() // 2
                center_point = QPoint(capture_center_x, capture_center_y)
                
                screen_number = desktop.screenNumber(center_point)
                if screen_number == -1:
                    screen_number = desktop.primaryScreen()
                    print(f"⚠️ 截图区域不在任何显示器范围内，使用主显示器: {screen_number}")
                else:
                    print(f"📺 截图区域位于显示器 {screen_number}")
                
                screen_geometry = desktop.screenGeometry(screen_number)
                screen_x, screen_y = screen_geometry.x(), screen_geometry.y()
                screen_w, screen_h = screen_geometry.width(), screen_geometry.height()
                print(f"📺 显示器 {screen_number} 几何信息: x={screen_x}, y={screen_y}, w={screen_w}, h={screen_h}")
            
            # 计算窗口位置（使用真实坐标，相对于截图区域，减去边框宽度）
            window_x = real_x - border_width
            window_y = real_y - border_width
            
            # 确保窗口在目标显示器的范围内
            # 检查窗口是否会超出显示器边界
            window_width = self.capture_rect.width() + border_width * 2
            window_height = self.capture_rect.height() + border_width * 2 + 50  # +50为按钮栏高度
            
            # 如果有父窗口的adjust_position_to_screen方法，直接使用它（与钉图窗口完全一致）
            if (hasattr(self, 'parent') and self.parent and 
                hasattr(self.parent, 'adjust_position_to_screen') and target_screen):
                window_x, window_y = self.parent.adjust_position_to_screen(
                    window_x, window_y, window_width, window_height, target_screen)
                print(f"🎯 [长截图] 使用钉图窗口相同的位置调整逻辑: ({window_x}, {window_y})")
            else:
                # 回退到手动边界检查
                # 如果窗口超出右边界，调整x位置
                if window_x + window_width > screen_x + screen_w:
                    window_x = screen_x + screen_w - window_width
                    print(f"⚠️ 窗口超出右边界，调整x位置到: {window_x}")
                
                # 如果窗口超出下边界，调整y位置
                if window_y + window_height > screen_y + screen_h:
                    window_y = screen_y + screen_h - window_height
                    print(f"⚠️ 窗口超出下边界，调整y位置到: {window_y}")
                
                # 如果窗口超出左边界，调整x位置
                if window_x < screen_x:
                    window_x = screen_x
                    print(f"⚠️ 窗口超出左边界，调整x位置到: {window_x}")
                
                # 如果窗口超出上边界，调整y位置
                if window_y < screen_y:
                    window_y = screen_y
                    print(f"⚠️ 窗口超出上边界，调整y位置到: {window_y}")
            
            print(f"✅ 长截图窗口最终位置: x={window_x}, y={window_y}")
            return window_x, window_y
            
        except Exception as e:
            print(f"❌ 计算窗口位置时出错: {e}")
            # 如果出错，使用原始位置（传入的capture_rect已经是真实坐标）
            fallback_x = self.capture_rect.x()
            fallback_y = self.capture_rect.y()
            
            return (fallback_x - border_width, fallback_y - border_width)
        
    def _setup_window(self):
        """设置窗口属性"""
        # 设置窗口标志：无边框、置顶
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        
        # 设置窗口透明度和背景
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 设置窗口位置和大小（基于截图区域）
        # 窗口区域 = 截图区域 + 底部按钮栏
        button_bar_height = 50
        
        # 为边框预留空间（但截图区域不包含边框）
        border_width = 3
        
        # 修复多显示器窗口定位问题
        window_x, window_y = self._get_correct_window_position(border_width)
        
        self.setGeometry(
            window_x,
            window_y,
            self.capture_rect.width() + border_width * 2,
            self.capture_rect.height() + border_width * 2 + button_bar_height
        )
        
    def _setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)  # 为边框预留空间
        layout.setSpacing(0)
        
        # 上方透明区域（用于显示边框）
        self.transparent_area = QWidget()
        self.transparent_area.setFixedSize(
            self.capture_rect.width(),
            self.capture_rect.height()
        )
        layout.addWidget(self.transparent_area)
        
        # 底部按钮栏
        button_bar = QWidget()
        button_bar.setStyleSheet("""
            QWidget {
                background-color: rgba(40, 40, 40, 200);
                border: 2px solid #555;
                border-radius: 5px;
            }
        """)
        button_bar.setFixedHeight(50)  # 恢复原来的高度
        
        button_layout = QHBoxLayout(button_bar)  # 改回水平布局
        button_layout.setContentsMargins(10, 5, 10, 5)
        
        # 提示文字标签(放在左侧)
        if self.auto_scroll_mode:
            tip_label = QLabel("🤖 自动滚动模式 - 点击\"开始\"后软件将自动滚动截图")
        else:
            tip_label = QLabel("⚠️ 一方向に上から下へゆっくりスクロール")
        tip_label.setStyleSheet("color: #FFD700; font-size: 9pt; font-weight: bold;")
        button_layout.addWidget(tip_label)
        
        button_layout.addStretch()
        
        # 🆕 自动滚动模式的开始/停止按钮
        if self.auto_scroll_mode:
            self.start_auto_btn = QPushButton("▶ 開始自動スクロール")
            self.start_auto_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    font-size: 11pt;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
            self.start_auto_btn.clicked.connect(self._toggle_auto_scroll)
            button_layout.addWidget(self.start_auto_btn)
        
        # 截图计数标签
        self.count_label = QLabel("スクショ: 0 枚")
        self.count_label.setStyleSheet("color: white; font-size: 11pt;")
        button_layout.addWidget(self.count_label)
        
        # 完成按钮
        self.finish_btn = QPushButton("完了")
        self.finish_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 20px;
                font-size: 11pt;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.finish_btn.clicked.connect(self._on_finish)
        button_layout.addWidget(self.finish_btn)
        
        # 取消按钮
        self.cancel_btn = QPushButton("キャンセル")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 20px;
                font-size: 11pt;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addWidget(button_bar)
    
    def _toggle_auto_scroll(self):
        """切换自动滚动状态"""
        if self.is_auto_scrolling:
            # 停止滚动
            self._stop_auto_scroll()
        else:
            # 开始滚动
            self._start_auto_scroll()
    
    def _start_auto_scroll(self):
        """开始自动滚动截图"""
        print("\n🚀 开始自动滚动长截图...")
        print(f"   滚动步长: {self.scroll_step_ratio*100:.0f}% 截图区域高度")
        print(f"   重叠率: {(1-self.scroll_step_ratio)*100:.0f}%")
        
        # 🎯 获取截图区域下方的目标窗口
        self.target_window_hwnd = self._get_window_under_capture_area()
        if not self.target_window_hwnd:
            print("❌ 无法找到目标窗口,请确保截图区域下方有浏览器或应用窗口")
            return
        
        # 设置状态
        self.is_auto_scrolling = True
        
        # 更新按钮
        if hasattr(self, 'start_auto_btn'):
            self.start_auto_btn.setText("⏸ 停止")
            self.start_auto_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    font-size: 11pt;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #F57C00;
                }
            """)
        
        # 立即截取第一张
        self._do_capture()
        
        # 启动自动滚动
        QTimer.singleShot(int(self.scroll_interval * 1000), self._auto_scroll_and_capture)
    
    def _stop_auto_scroll(self):
        """停止自动滚动"""
        print("\n⏸ 停止自动滚动")
        self.is_auto_scrolling = False
        
        # 更新按钮
        if hasattr(self, 'start_auto_btn'):
            self.start_auto_btn.setText("▶ 開始自動スクロール")
            self.start_auto_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    font-size: 11pt;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
    
    def _get_window_under_capture_area(self):
        """获取截图区域下方的窗口句柄
        
        Returns:
            int: 窗口句柄,如果找不到返回None
        """
        try:
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            
            # 获取截图区域中心点坐标
            center_x = self.capture_rect.x() + self.capture_rect.width() // 2
            center_y = self.capture_rect.y() + self.capture_rect.height() // 2
            
            # 获取该点下方的窗口(忽略我们自己的透明窗口)
            point = wintypes.POINT(center_x, center_y)
            hwnd = user32.WindowFromPoint(point)
            
            if hwnd:
                # 获取窗口标题
                length = user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                
                print(f"🎯 检测到目标窗口: {title} (HWND: {hwnd})")
                return hwnd
            else:
                print("❌ 未检测到窗口")
                return None
                
        except Exception as e:
            print(f"❌ 获取目标窗口失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _auto_scroll_and_capture(self):
        """执行一次自动滚动并截图"""
        # 检查是否应该停止
        if not self.is_auto_scrolling:
            print("⏹ 自动滚动已停止")
            return
        
        try:
            # 计算滚动距离(截图区域高度 × 滚动比例)
            scroll_pixels = int(self.capture_rect.height() * self.scroll_step_ratio)
            
            print(f"\n🔽 模拟滚动 {scroll_pixels}px...")
            
            # 🆕 模拟滚动 - 发送按键到目标窗口
            success = self._simulate_scroll(scroll_pixels)
            
            if success:
                # 记录实际滚动距离
                self.actual_scroll_distances.append(scroll_pixels)
                
                # 🆕 平滑滚动需要等待滚动动画完成
                # 计算滚动总时长: steps × delay
                if self.smooth_scroll_enabled:
                    steps = max(1, scroll_pixels // self.smooth_scroll_speed)
                    scroll_duration = steps * self.smooth_scroll_delay
                    wait_time = scroll_duration + self.scroll_interval  # 滚动时间 + 稳定时间
                else:
                    wait_time = self.scroll_interval
                
                print(f"   ⏱️ 等待 {wait_time:.1f}秒 让内容稳定...")
                
                # 等待内容稳定后截图
                QTimer.singleShot(int(wait_time * 1000), lambda: self._do_capture() if self.is_auto_scrolling else None)
                
                # 继续下一次滚动(在截图后触发)
                QTimer.singleShot(int((wait_time + 0.5) * 1000), lambda: self._auto_scroll_and_capture() if self.is_auto_scrolling else None)
            else:
                print("❌ 滚动模拟失败")
                self._stop_auto_scroll()
                
        except Exception as e:
            print(f"❌ 自动滚动出错: {e}")
            import traceback
            traceback.print_exc()
            self._stop_auto_scroll()
    
    def _simulate_scroll(self, pixels: int) -> bool:
        """模拟平滑滚动指定像素距离(像手机长截图那样丝滑)
        
        Args:
            pixels: 要滚动的像素数
            
        Returns:
            bool: 是否成功
        """
        try:
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            
            # 🎯 关键: 先激活目标窗口,确保滚动发送到正确的窗口
            if self.target_window_hwnd:
                try:
                    user32.SetForegroundWindow(self.target_window_hwnd)
                    time.sleep(0.1)  # 等待窗口激活
                    print(f"   ✅ 已激活目标窗口 (HWND: {self.target_window_hwnd})")
                except Exception as e:
                    print(f"   ⚠️ 激活窗口失败: {e}, 继续尝试...")
            
            if self.smooth_scroll_enabled:
                # � 平滑滚动模式 - 多次小步滚动,模拟手机长截图效果
                print(f"   🌊 平滑滚动模式: 目标={pixels}px, 步长={self.smooth_scroll_speed}px")
                
                WHEEL_DELTA = 120
                WM_MOUSEWHEEL = 0x020A
                
                # 计算需要多少次小步滚动
                steps = max(1, pixels // self.smooth_scroll_speed)
                
                # 获取截图区域中心点(发送滚轮事件到这个位置)
                center_x = self.capture_rect.x() + self.capture_rect.width() // 2
                center_y = self.capture_rect.y() + self.capture_rect.height() // 2
                
                print(f"   📊 将分 {steps} 步滚动,每步约 {pixels//steps}px")
                
                # 平滑滚动: 多次小滚动
                for i in range(steps):
                    # 每次滚动一个 WHEEL_DELTA (负数 = 向下)
                    wparam = (-WHEEL_DELTA << 16)
                    lparam = (center_y << 16) | (center_x & 0xFFFF)
                    
                    user32.PostMessageW(
                        self.target_window_hwnd,
                        WM_MOUSEWHEEL,
                        wparam,
                        lparam
                    )
                    
                    # 小延迟让滚动丝滑连续
                    time.sleep(self.smooth_scroll_delay)
                    
                    # 进度显示(每10步显示一次)
                    if (i + 1) % 10 == 0 or i == steps - 1:
                        progress = (i + 1) / steps * 100
                        print(f"      进度: {progress:.0f}% ({i+1}/{steps})", end='\r')
                
                print()  # 换行
                return True
                
            else:
                # 🎯 快速滚动模式 - 一次性滚动(旧方式)
                WHEEL_DELTA = 120
                WM_MOUSEWHEEL = 0x020A
                
                # 计算需要的滚动次数(保守估计: 1次 ≈ 100px)
                scroll_count = max(1, pixels // 100)
                
                print(f"   🖱️ 快速滚动: {scroll_count} 次 (目标: {pixels}px)")
                
                center_x = self.capture_rect.x() + self.capture_rect.width() // 2
                center_y = self.capture_rect.y() + self.capture_rect.height() // 2
                
                for i in range(scroll_count):
                    wparam = (-WHEEL_DELTA << 16)
                    lparam = (center_y << 16) | (center_x & 0xFFFF)
                    
                    user32.PostMessageW(
                        self.target_window_hwnd,
                        WM_MOUSEWHEEL,
                        wparam,
                        lparam
                    )
                    time.sleep(0.05)
                    
                return True
            
        except Exception as e:
            print(f"❌ 模拟滚动失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def _setup_mouse_hook(self):
        """设置Windows鼠标钩子以监听全局滚轮事件(仅手动模式)"""
        # 🆕 自动滚动模式下不需要监听滚轮
        if self.auto_scroll_mode:
            print("🤖 自动滚动模式 - 跳过滚轮监听器设置")
            # 仍然设置窗口穿透
            try:
                hwnd = int(self.transparent_area.winId())
                user32 = ctypes.windll.user32
                ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
                print(f"✅ 窗口已设置为鼠标穿透模式")
            except Exception as e:
                print(f"❌ 设置窗口穿透失败: {e}")
            return
        
        # 手动模式才设置滚轮监听
        try:
            # 使用Windows API设置窗口透明鼠标事件（需在主线程执行）
            hwnd = int(self.transparent_area.winId())
            user32 = ctypes.windll.user32
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
            print(f"✅ 窗口已设置为鼠标穿透模式")

            # 将可能较慢的模块导入与监听器启动放到后台线程，避免首次阻塞UI
            import threading

            def _init_listener_bg():
                try:
                    from pynput import mouse  # 首次导入较慢，放后台

                    def on_scroll(x, y, dx, dy):
                        """滚轮事件回调(在pynput线程中)"""
                        if self._is_mouse_in_capture_area(x, y):
                            # ⚠️ 注意: pynput的dy只是滚轮刻度数(±1, ±2...),不是像素距离
                            # 实际滚动像素数受DPI、系统设置、应用缩放等影响,无法准确计算
                            # 因此这里仅作为"触发信号",实际滚动距离由图像对比反推
                            print(f"🖱️ 检测到滚轮事件: ({x}, {y}), 刻度dy={dy}")
                            try:
                                self.scroll_detected.emit(dy)  # 仅传递刻度数作为触发信号
                            except Exception as e:
                                print(f"❌ 触发滚动信号失败: {e}")

                    # 创建并启动监听器（pynput内部也会使用线程）
                    self.mouse_listener = mouse.Listener(on_scroll=on_scroll)
                    self.mouse_listener.start()
                    print("✅ 全局滚轮监听器已启动")
                except Exception as e:
                    print(f"❌ 设置鼠标钩子失败: {e}")
                    import traceback
                    traceback.print_exc()

            threading.Thread(target=_init_listener_bg, daemon=True).start()

        except Exception as e:
            print(f"❌ 设置窗口鼠标穿透时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def showEvent(self, event):
        """窗口显示事件 - 立即截取第一张图"""
        super().showEvent(event)
        
        # 验证窗口位置是否正确
        self._verify_window_position()
        
        # 使用QTimer延迟执行，确保窗口完全显示后再截图
        QTimer.singleShot(100, self._capture_initial_screenshot)
    
    def _verify_window_position(self):
        """验证窗口位置是否正确"""
        try:
            app = QApplication.instance()
            desktop = app.desktop()
            
            # 获取窗口当前位置
            window_x = self.x()
            window_y = self.y()
            window_center = QPoint(window_x + self.width() // 2, window_y + self.height() // 2)
            
            # 找到窗口所在的显示器
            current_screen = desktop.screenNumber(window_center)
            screen_geometry = desktop.screenGeometry(current_screen)
            
            print(f"🔍 窗口位置验证:")
            print(f"   窗口位置: x={window_x}, y={window_y}")
            print(f"   窗口中心: x={window_center.x()}, y={window_center.y()}")
            print(f"   所在显示器: {current_screen}")
            print(f"   显示器范围: x={screen_geometry.x()}-{screen_geometry.x() + screen_geometry.width()}, y={screen_geometry.y()}-{screen_geometry.y() + screen_geometry.height()}")
            
            # 检查截图区域中心所在的显示器
            capture_center_x = self.capture_rect.x() + self.capture_rect.width() // 2
            capture_center_y = self.capture_rect.y() + self.capture_rect.height() // 2
            capture_center = QPoint(capture_center_x, capture_center_y)
            expected_screen = desktop.screenNumber(capture_center)
            
            print(f"   截图区域中心: x={capture_center_x}, y={capture_center_y}")
            print(f"   期望显示器: {expected_screen}")
            
            if current_screen != expected_screen and expected_screen != -1:
                print(f"⚠️ 警告: 窗口显示在显示器 {current_screen}，但截图区域在显示器 {expected_screen}")
                
                # 尝试移动窗口到正确的显示器
                target_screen_geometry = desktop.screenGeometry(expected_screen)
                # 计算在目标显示器上的相对位置
                relative_x = self.capture_rect.x() - 3  # border_width = 3
                relative_y = self.capture_rect.y() - 3
                
                # 确保不超出边界
                if (relative_x >= target_screen_geometry.x() and 
                    relative_y >= target_screen_geometry.y() and
                    relative_x + self.width() <= target_screen_geometry.x() + target_screen_geometry.width() and
                    relative_y + self.height() <= target_screen_geometry.y() + target_screen_geometry.height()):
                    
                    print(f"🔧 尝试移动窗口到正确位置: x={relative_x}, y={relative_y}")
                    self.move(relative_x, relative_y)
                    self.raise_()
                    self.activateWindow()
                else:
                    print(f"⚠️ 无法移动窗口到目标位置，可能会超出显示器边界")
            else:
                print("✅ 窗口位置正确")
                
        except Exception as e:
            print(f"❌ 验证窗口位置时出错: {e}")
    
    def _force_fix_window_position(self):
        """强制修复窗口位置（最后的保险措施）"""
        try:
            # 如果窗口不可见，先让它可见
            if not self.isVisible():
                print("⚠️ 检测到窗口不可见，强制显示")
                self.show()
                self.raise_()
                self.activateWindow()
                return
            
            app = QApplication.instance()
            desktop = app.desktop()
            
            # 获取窗口当前位置
            window_rect = self.geometry()
            
            # 检查窗口是否在任何显示器上可见
            visible_on_any_screen = False
            for screen_num in range(desktop.screenCount()):
                screen_geometry = desktop.screenGeometry(screen_num)
                if screen_geometry.intersects(window_rect):
                    visible_on_any_screen = True
                    break
            
            if not visible_on_any_screen:
                print("🚨 检测到窗口在所有显示器外，执行强制修复...")
                
                # 找到截图区域所在的显示器
                capture_center_x = self.capture_rect.x() + self.capture_rect.width() // 2
                capture_center_y = self.capture_rect.y() + self.capture_rect.height() // 2
                capture_center = QPoint(capture_center_x, capture_center_y)
                
                target_screen = desktop.screenNumber(capture_center)
                if target_screen == -1:
                    target_screen = desktop.primaryScreen()
                    print(f"⚠️ 截图区域不在任何显示器内，使用主显示器 {target_screen}")
                
                target_geometry = desktop.screenGeometry(target_screen)
                
                # 将窗口移动到目标显示器的中央
                new_x = target_geometry.x() + (target_geometry.width() - self.width()) // 2
                new_y = target_geometry.y() + (target_geometry.height() - self.height()) // 2
                
                print(f"🔧 强制移动窗口到显示器 {target_screen} 中央: x={new_x}, y={new_y}")
                self.move(new_x, new_y)
                self.raise_()
                self.activateWindow()
                
                # 更新窗口标题以提示用户
                self.setWindowTitle("長スクリーンショット - 位置が修正されました")
            else:
                print("✅ 窗口位置验证通过")
                
        except Exception as e:
            print(f"❌ 强制修复窗口位置时出错: {e}")
    
    def _capture_initial_screenshot(self):
        """截取初始截图(窗口显示时的区域内容)"""
        print("🎬 截取初始截图(第1张)...")
        
        # 🆕 自动模式不在这里截图,等待用户点击"开始"按钮
        if self.auto_scroll_mode:
            print("🤖 自动模式 - 等待用户点击\"开始\"按钮...")
            return
        
        # 手动模式立即截取第一张
        self._do_capture()
        
        # 为初始截图生成哈希（用于后续去重）
        if len(self.screenshots) > 0 and self.capture_mode == "immediate":
            self.last_screenshot_hash = self._calculate_image_hash(self.screenshots[0])
        
        print(f"   初始截图完成，当前共 {len(self.screenshots)} 张")
    
    def _is_mouse_in_capture_area(self, x, y):
        """检查鼠标是否在截图区域内"""
        return (self.capture_rect.x() <= x <= self.capture_rect.x() + self.capture_rect.width() and
                self.capture_rect.y() <= y <= self.capture_rect.y() + self.capture_rect.height())
    
    def _handle_scroll_in_main_thread(self, dy):
        """在主线程中处理滚轮事件(立即截图模式)
        
        Args:
            dy: 滚轮刻度数(±1, ±2...), 仅作为触发信号,不代表精确像素距离
        """
        import time
        
        # 仅统计滚轮次数(调试用)
        self.scroll_tick_count += abs(dy)
        print(f"📊 滚轮刻度累计: {self.scroll_tick_count} (本次±{abs(dy)})")
        
        # 更新最后滚动时间
        self.last_scroll_time = time.time()
        
        if self.capture_mode == "immediate":
            # 立即截图模式: 延迟很短时间后截图(让滚动动画完成)
            if self.capture_timer.isActive():
                self.capture_timer.stop()
            self.capture_timer.start(int(self.scroll_cooldown * 1000))  # 默认300ms
            print(f"⚡ 检测到滚动, {self.scroll_cooldown}秒后截图...")
        else:
            # 等待停止模式: 启动检测定时器
            if not self.scroll_check_timer.isActive():
                self.scroll_check_timer.start()
                print("🔄 开始检测滚动停止...")
    
    def _check_scroll_stopped(self):
        """定期检查滚动是否已停止（仅在等待模式下使用）"""
        import time
        
        current_time = time.time()
        time_since_last_scroll = current_time - self.last_scroll_time
        
        # 如果距离上次滚动已经超过冷却时间
        if time_since_last_scroll >= self.scroll_cooldown:
            # 滚动已停止，停止检测定时器
            self.scroll_check_timer.stop()
            
            # 执行截图
            print(f"✋ 滚动已停止 ({time_since_last_scroll:.2f}秒)，开始截图...")
            self._do_capture()
        else:
            # 还在滚动，继续等待
            remaining = self.scroll_cooldown - time_since_last_scroll
            print(f"⏳ 等待滚动停止... (还需 {remaining:.1f}秒)", end='\r')
    
    def _calculate_image_hash(self, pil_image):
        """计算图片的感知哈希值（用于相似度比较）"""
        import hashlib
        
        # 缩小图片到8x8用于快速比较
        small_img = pil_image.resize((16, 16), Image.Resampling.LANCZOS)
        # 转为灰度
        gray_img = small_img.convert('L')
        # 计算平均值
        pixels = list(gray_img.getdata())
        avg = sum(pixels) / len(pixels)
        # 生成哈希（大于平均值为1，小于为0）
        hash_str = ''.join('1' if p > avg else '0' for p in pixels)
        return hash_str
    
    def _images_are_similar(self, hash1, hash2):
        """比较两个哈希值的相似度"""
        if hash1 is None or hash2 is None:
            return False
        
        # 计算汉明距离（不同位的数量）
        diff_bits = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
        similarity = 1 - (diff_bits / len(hash1))
        
        return similarity >= self.duplicate_threshold
    
    def _do_capture(self):
        """执行截图(不进行去重,所有截图都保存)"""
        try:
            current_count = len(self.screenshots) + 1
            
            print(f"\n📸 截取第 {current_count} 张图片")
            print(f"   区域: x={self.capture_rect.x()}, y={self.capture_rect.y()}, w={self.capture_rect.width()}, h={self.capture_rect.height()}")
            print(f"   ⚠️ 注意: 滚轮刻度≠实际像素,实际偏移由图像匹配计算")
            
            # 使用Qt截取屏幕
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                print("❌ 无法获取屏幕")
                return
            
            # 截取指定区域(精确使用原始capture_rect,不包含边框)
            pixmap = screen.grabWindow(
                0,
                self.capture_rect.x(),
                self.capture_rect.y(),
                self.capture_rect.width(),
                self.capture_rect.height()
            )
            
            if pixmap.isNull():
                print("❌ 截图失败")
                return
            
            # 将QPixmap转换为PIL Image
            qimage = pixmap.toImage()
            buffer = qimage.bits().asstring(qimage.byteCount())
            pil_image = Image.frombytes(
                'RGBA',
                (qimage.width(), qimage.height()),
                buffer,
                'raw',
                'BGRA'
            ).convert('RGB')
            
            # 截图阶段不进行去重检测,所有截图都保存
            # 去重逻辑移到合成阶段(smart_stitch.py)
            
            # 添加到截图列表
            self.screenshots.append(pil_image)
            
            # 更新计数
            self.count_label.setText(f"スクショ: {len(self.screenshots)} 枚")
            
            print(f"✅ 第 {len(self.screenshots)} 張截图完成 (尺寸: {pil_image.size[0]}x{pil_image.size[1]})")
            
        except Exception as e:
            print(f"❌ 截图时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def paintEvent(self, event):
        """绘制窗口边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制半透明边框（在窗口边缘，不影响截图区域）
        pen = QPen(QColor(0, 120, 215), 3)  # 蓝色边框，3像素
        painter.setPen(pen)
        
        # 绘制矩形边框（考虑边框宽度）
        border_width = 3
        border_rect = QRect(
            border_width // 2,
            border_width // 2,
            self.capture_rect.width() + border_width,
            self.capture_rect.height() + border_width
        )
        painter.drawRect(border_rect)
        
        painter.end()
    
    def _on_finish(self):
        """完成按钮点击"""
        print(f"✅ 完成长截图，共 {len(self.screenshots)} 张图片")
        self._cleanup()
        self.finished.emit()
        self.close()
    
    def _on_cancel(self):
        """取消按钮点击"""
        print("❌ 取消长截图")
        self.screenshots.clear()
        self._cleanup()
        self.cancelled.emit()
        self.close()
    
    def _cleanup(self):
        """清理资源"""
        try:
            # 🆕 停止自动滚动
            if hasattr(self, 'is_auto_scrolling'):
                self.is_auto_scrolling = False
            
            # 停止所有定时器
            if hasattr(self, 'auto_scroll_timer'):
                self.auto_scroll_timer.stop()
            
            if hasattr(self, 'capture_timer'):
                self.capture_timer.stop()
            
            if hasattr(self, 'scroll_check_timer'):
                self.scroll_check_timer.stop()
            
            if hasattr(self, '_position_fix_timer'):
                self._position_fix_timer.stop()
            
            # 停止鼠标监听器
            if hasattr(self, 'mouse_listener'):
                self.mouse_listener.stop()
                print("✅ 全局滚轮监听器已停止")
        except Exception as e:
            print(f"⚠️ 清理资源时出错: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self._cleanup()
        super().closeEvent(event)
    
    def get_screenshots(self):
        """获取所有截图"""
        return self.screenshots
    
    def get_scroll_distances(self):
        """获取滚动距离列表(用于拼接时的大致范围估算)
        
        Returns:
            list[int]: 每次截图之间的滚动像素数
                      自动模式: 返回模拟的滚动距离(作为初始估算)
                      手动模式: 空列表(距离未知,完全依赖图像匹配)
                      
        注意: 返回的是"理论滚动距离",实际滚动可能有偏差
             拼接算法会在此基础上用图像匹配微调
        """
        if self.auto_scroll_mode:
            # 自动模式: 返回理论滚动距离
            # 注意: 由于系统设置、浏览器行为等因素,实际滚动距离可能与理论值有10-20%偏差
            # 拼接算法应该在 ±100px 范围内搜索来容错
            return self.actual_scroll_distances
        else:
            # 手动模式: 无法预测滚动距离
            return []

