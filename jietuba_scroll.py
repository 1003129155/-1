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
    
    特性：
    - 带边框的透明窗口
    - 不拦截鼠标滚轮事件（鼠标可以直接操作后面的网页）
    - 监听全局滚轮事件，每次滚轮后1秒截图
    - 底部有完成和取消按钮
    """
    
    finished = pyqtSignal()  # 完成信号
    cancelled = pyqtSignal()  # 取消信号
    scroll_detected = pyqtSignal()  # 滚轮检测信号（用于线程安全通信）
    
    def __init__(self, capture_rect, parent=None):
        """初始化滚动截图窗口
        
        Args:
            capture_rect: QRect，截图区域（屏幕坐标）
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.capture_rect = capture_rect
        self.screenshots = []  # 存储截图的列表
        
        # 滚动检测相关
        self.last_scroll_time = 0  # 最后一次滚动的时间戳
        self.scroll_cooldown = 0.3  # 滚动后延迟截图时间（秒）- 改为更短
        self.capture_mode = "immediate"  # 截图模式: "immediate"立即 或 "wait"等待停止
        
        # 去重相关
        self.last_screenshot_hash = None  # 上一张截图的哈希值（用于去重）
        self.duplicate_threshold = 0.95  # 相似度阈值（95%以上认为重复）
        
        # 定时器
        self.capture_timer = QTimer(self)  # 截图定时器
        self.capture_timer.setSingleShot(True)
        self.capture_timer.timeout.connect(self._do_capture)
        
        self.scroll_check_timer = QTimer(self)  # 滚动检测定时器
        self.scroll_check_timer.setInterval(100)  # 每100ms检查一次
        self.scroll_check_timer.timeout.connect(self._check_scroll_stopped)
        
        # 连接滚轮检测信号到主线程处理函数
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
        
        # 提示文字标签（放在左侧）
        tip_label = QLabel("⚠️ 一方向に上から下へゆっくりスクロール")
        tip_label.setStyleSheet("color: #FFD700; font-size: 9pt; font-weight: bold;")
        button_layout.addWidget(tip_label)
        
        button_layout.addStretch()
        
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
        
    def _setup_mouse_hook(self):
        """设置Windows鼠标钩子以监听全局滚轮事件"""
        try:
            # 使用Windows API设置窗口透明鼠标事件
            hwnd = int(self.transparent_area.winId())
            
            user32 = ctypes.windll.user32
            # 获取当前扩展样式
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            # 添加透明标志，使鼠标事件穿透
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
            
            print(f"✅ 窗口已设置为鼠标穿透模式")
            
            # 使用全局事件监听
            from pynput import mouse
            
            def on_scroll(x, y, dx, dy):
                """滚轮事件回调（在pynput线程中）"""
                # 检查鼠标是否在截图区域内
                if self._is_mouse_in_capture_area(x, y):
                    print(f"🖱️ 检测到滚轮事件: ({x}, {y}), dy={dy}")
                    # 使用信号触发主线程处理（线程安全）
                    try:
                        self.scroll_detected.emit()
                    except Exception as e:
                        print(f"❌ 触发滚动信号失败: {e}")
            
            # 创建监听器
            self.mouse_listener = mouse.Listener(on_scroll=on_scroll)
            self.mouse_listener.start()
            print("✅ 全局滚轮监听器已启动")
            
        except Exception as e:
            print(f"❌ 设置鼠标钩子失败: {e}")
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
        """截取初始截图（窗口显示时的区域内容）"""
        print("🎬 截取初始截图（第1张）...")
        self._do_capture()
        
        # 为初始截图生成哈希（用于后续去重）
        if len(self.screenshots) > 0 and self.capture_mode == "immediate":
            self.last_screenshot_hash = self._calculate_image_hash(self.screenshots[0])
        
        print(f"   初始截图完成，当前共 {len(self.screenshots)} 张")
    
    def _is_mouse_in_capture_area(self, x, y):
        """检查鼠标是否在截图区域内"""
        return (self.capture_rect.x() <= x <= self.capture_rect.x() + self.capture_rect.width() and
                self.capture_rect.y() <= y <= self.capture_rect.y() + self.capture_rect.height())
    
    def _handle_scroll_in_main_thread(self):
        """在主线程中处理滚轮事件（立即截图模式）"""
        import time
        
        # 更新最后滚动时间
        self.last_scroll_time = time.time()
        
        if self.capture_mode == "immediate":
            # 立即截图模式：延迟很短时间后截图（让滚动动画完成）
            if self.capture_timer.isActive():
                self.capture_timer.stop()
            self.capture_timer.start(int(self.scroll_cooldown * 1000))  # 默认300ms
            print(f"⚡ 检测到滚动，{self.scroll_cooldown}秒后截图...")
        else:
            # 等待停止模式：启动检测定时器
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
        """执行截图（不进行去重，所有截图都保存）"""
        try:
            current_count = len(self.screenshots) + 1
            print(f"\n📸 截取第 {current_count} 张图片")
            print(f"   区域: x={self.capture_rect.x()}, y={self.capture_rect.y()}, w={self.capture_rect.width()}, h={self.capture_rect.height()}")
            
            # 使用Qt截取屏幕
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                print("❌ 无法获取屏幕")
                return
            
            # 截取指定区域（精确使用原始capture_rect，不包含边框）
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
            
            # 🆕 截图阶段不进行去重检测，所有截图都保存
            # 去重逻辑移到合成阶段（smart_stitch.py）
            
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
            # 停止所有定时器
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
