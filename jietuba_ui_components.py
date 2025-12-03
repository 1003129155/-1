"""
jietuba_ui_components.py - UI组件模块

包含截图工具使用的各种UI组件和辅助类：
- 多屏幕调试工具
- 颜色按钮、悬停按钮等UI控件
- 智能窗口选择器(基于 Windows API)
- 自动调整大小的文本编辑器

"""
import os
import math
import win32gui
import win32api
import win32con
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPoint
from PyQt5.QtGui import QFont, QColor, QCursor, QPainter, QPen, QInputMethodEvent
from PyQt5.QtWidgets import QPushButton, QGroupBox, QTextEdit, QFrame

# ================== 多屏调试开关 ==================
DEBUG_MONITOR = os.environ.get("JSS_DEBUG_MONITOR", "0") not in ("0", "false", "False")


def _debug_print(msg: str):
    """多屏幕调试信息输出"""
    if DEBUG_MONITOR:
        print(f"[MultiScreenDebug] {msg}")


def _enumerate_win_monitors():
    """使用 Win32 API 枚举系统所有物理/逻辑显示器，返回列表。
    作用：用于与 Qt 的 QApplication.screens() 对比，诊断 Qt 未识别外接屏问题。
    """
    monitors = []
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        class MONITORINFOEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
                ("szDevice", wintypes.WCHAR * 32),
            ]

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )

        get_monitor_info = user32.GetMonitorInfoW
        get_monitor_info.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFOEXW)]

        def _callback(hmonitor, hdc, lprect, lparam):
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if get_monitor_info(hmonitor, ctypes.byref(info)):
                left = info.rcMonitor.left
                top = info.rcMonitor.top
                right = info.rcMonitor.right
                bottom = info.rcMonitor.bottom
                monitors.append({
                    "device": info.szDevice,
                    "rect": (left, top, right, bottom),
                    "bounds": (left, top, right - left, bottom - top),
                    "primary": bool(info.dwFlags & 1),
                })
            return True

        enum_display_monitors = user32.EnumDisplayMonitors
        enum_display_monitors(None, None, MonitorEnumProc(_callback), 0)
    except Exception as exc:
        _debug_print(f"EnumDisplayMonitors failed: {exc}")
    return monitors


def _enumerate_monitor_dpi():
    """返回每个显示器的 DPI 信息及缩放."""
    monitors = []
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        shcore = ctypes.windll.shcore if hasattr(ctypes.windll, 'shcore') else None

        class MONITORINFOEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
                ("szDevice", wintypes.WCHAR * 32),
            ]

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )

        # 设置 GetMonitorInfoW 的参数类型
        user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFOEXW)]
        user32.GetMonitorInfoW.restype = wintypes.BOOL

        def _callback(hmonitor, hdc, lprect, lparam):
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                left = info.rcMonitor.left
                top = info.rcMonitor.top
                right = info.rcMonitor.right
                bottom = info.rcMonitor.bottom
                dpi_x = ctypes.c_uint(96)
                dpi_y = ctypes.c_uint(96)
                scale = 1.0
                if shcore is not None:
                    try:
                        shcore.GetDpiForMonitor(hmonitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
                    except Exception as _dpi_err:
                        _debug_print(f"GetDpiForMonitor failed: {_dpi_err}")
                else:
                    # 回退：使用设备上下文计算 DPI
                    hdc_local = user32.GetDC(None)
                    if hdc_local:
                        LOGPIXELSX = 88
                        LOGPIXELSY = 90
                        dpi_x = ctypes.c_uint(ctypes.windll.gdi32.GetDeviceCaps(hdc_local, LOGPIXELSX))
                        dpi_y = ctypes.c_uint(ctypes.windll.gdi32.GetDeviceCaps(hdc_local, LOGPIXELSY))
                        user32.ReleaseDC(None, hdc_local)
                if dpi_x.value:
                    scale = dpi_x.value / 96.0
                monitors.append({
                    "name": info.szDevice,
                    "rect": (left, top, right, bottom),
                    "dpi_x": dpi_x.value,
                    "dpi_y": dpi_y.value,
                    "scale": scale,
                })
            return True

        user32.EnumDisplayMonitors(None, None, MonitorEnumProc(_callback), 0)
    except Exception as exc:
        _debug_print(f"_enumerate_monitor_dpi failed: {exc}")
    return monitors


class ColorButton(QPushButton):
    """颜色选择按钮"""
    select_color_signal = pyqtSignal(str)

    def __init__(self, color, parent):
        super(ColorButton, self).__init__("", parent)
        self.color = QColor(color).name()
        self.setStyleSheet("background-color:{}".format(self.color))
        self.clicked.connect(self.sendcolor)

    def sendcolor(self):
        self.select_color_signal.emit(self.color)


class HoverButton(QPushButton):
    """支持悬停事件的按钮"""
    hoversignal = pyqtSignal(int)

    def enterEvent(self, e) -> None:
        super(HoverButton, self).enterEvent(e)
        self.hoversignal.emit(1)
        print("enter")

    def leaveEvent(self, e):
        super(HoverButton, self).leaveEvent(e)
        self.hoversignal.emit(0)
        print("leave")


class HoverGroupbox(QGroupBox):
    """支持悬停事件的分组框"""
    hoversignal = pyqtSignal(int)

    def enterEvent(self, e) -> None:
        super(HoverGroupbox, self).enterEvent(e)
        self.hoversignal.emit(1)
        print("enter")

    def leaveEvent(self, e):
        super(HoverGroupbox, self).leaveEvent(e)
        self.hoversignal.emit(0)
        print("leave")


class CanMoveGroupbox(QGroupBox):
    """可拖动移动的分组框"""
    def __init__(self, parent):
        super(CanMoveGroupbox, self).__init__(parent)
        self.drag = False
        self.p_x, self.p_y = 0, 0

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.x() < 100:
            self.setCursor(Qt.SizeAllCursor)
            self.drag = True
            self.p_x, self.p_y = event.x(), event.y()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ArrowCursor)
            self.drag = False

    def mouseMoveEvent(self, event):
        if self.isVisible():
            if self.drag:
                self.move(event.x() + self.x() - self.p_x, event.y() + self.y() - self.p_y)


class Finder:
    """智能窗口选择器 - 基于 Windows API 的窗口检测"""
    def __init__(self, parent):
        self.parent = parent
        self.windows = []  # 存储所有窗口信息 [(hwnd, rect), ...]
        self.screen_offset_x = 0
        self.screen_offset_y = 0

    def _refresh_screen_offsets(self):
        """根据截图窗口的虚拟桌面信息更新偏移量，确保多屏坐标正确"""
        offset_x = 0
        offset_y = 0

        try:
            slabel = self.parent
            if slabel is not None:
                # 优先使用虚拟桌面偏移（多屏截图时由 Slabel 维护）
                if hasattr(slabel, 'virtual_desktop_offset_x'):
                    offset_x = int(getattr(slabel, 'virtual_desktop_offset_x', 0))
                elif hasattr(slabel, 'virtual_desktop_min_x'):
                    offset_x = int(getattr(slabel, 'virtual_desktop_min_x', 0))

                if hasattr(slabel, 'virtual_desktop_offset_y'):
                    offset_y = int(getattr(slabel, 'virtual_desktop_offset_y', 0))
                elif hasattr(slabel, 'virtual_desktop_min_y'):
                    offset_y = int(getattr(slabel, 'virtual_desktop_min_y', 0))

                # 兼容旧逻辑：若仍为0且主窗口记录了当前屏几何，作为兜底
                if offset_x == 0 and offset_y == 0 and hasattr(slabel, 'parent'):
                    main_window = slabel.parent
                    if hasattr(main_window, 'screen_geometry'):
                        screen_geo = main_window.screen_geometry
                        offset_x = int(screen_geo.x())
                        offset_y = int(screen_geo.y())
        except Exception as e:
            _debug_print(f"Finder 偏移刷新失败: {e}")

        self.screen_offset_x = offset_x
        self.screen_offset_y = offset_y
        if DEBUG_MONITOR:
            print(f"🧭 [智能选区] 使用偏移: ({self.screen_offset_x}, {self.screen_offset_y})")

    def find_contours_setup(self):
        """枚举所有可见窗口"""
        self.windows = []
        self._refresh_screen_offsets()
        
        def enum_windows_callback(hwnd, _):
            """枚举窗口回调函数"""
            try:
                # 1. 只处理可见窗口
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                
                # 2. 检查窗口样式（排除工具窗口、消息窗口等）
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                
                # 跳过没有标题栏的窗口（通常是弹出窗口或工具栏）
                if not (style & win32con.WS_CAPTION):
                    return True
                
                # 跳过工具窗口
                if ex_style & win32con.WS_EX_TOOLWINDOW:
                    return True
                
                # 3. 必须有窗口标题
                title = win32gui.GetWindowText(hwnd)
                if not title or len(title.strip()) == 0:
                    return True
                
                # 4. 检查窗口是否真的可以接收输入（不是透明遮罩）
                if ex_style & win32con.WS_EX_TRANSPARENT:
                    return True
                
                # 5. 获取窗口矩形
                rect = win32gui.GetWindowRect(hwnd)
                x1, y1, x2, y2 = rect
                
                # 6. 窗口必须有合理的大小（排除太小的窗口）
                width = x2 - x1
                height = y2 - y1
                if width < 30 or height < 30:  # 提高最小尺寸阈值
                    return True
                
                # 7. 窗口必须在屏幕可见区域内（至少部分可见）
                # 排除完全在屏幕外的窗口
                if x2 < -1000 or y2 < -1000 or x1 > 10000 or y1 > 10000:
                    return True
                
                # 8. 检查窗口类名，排除一些特殊的系统窗口
                try:
                    class_name = win32gui.GetClassName(hwnd)
                    # 排除一些已知的不需要选择的窗口类
                    excluded_classes = [
                        'Windows.UI.Core.CoreWindow',  # UWP后台窗口
                        'ApplicationFrameWindow',      # UWP框架窗口（有时是空的）
                        'WorkerW',                     # 桌面工作窗口
                        'Progman',                     # 程序管理器
                    ]
                    if class_name in excluded_classes:
                        return True
                except Exception:
                    pass
                
                # 9. 转换为相对于截图区域的坐标
                x1 -= self.screen_offset_x
                y1 -= self.screen_offset_y
                x2 -= self.screen_offset_x
                y2 -= self.screen_offset_y
                
                self.windows.append((hwnd, [x1, y1, x2, y2], title))
                
            except Exception as e:
                # 静默处理异常，继续枚举下一个窗口
                pass
            
            return True
        
        try:
            win32gui.EnumWindows(enum_windows_callback, None)
            print(f'🔍 [智能选区] 找到 {len(self.windows)} 个有效窗口')
            
            # 调试：输出前5个窗口信息
            if DEBUG_MONITOR and self.windows:
                print("📋 [智能选区] 检测到的窗口列表（前5个）:")
                for i, (hwnd, rect, title) in enumerate(self.windows[:5]):
                    print(f"  {i+1}. 标题: {title[:30]}, 大小: {rect[2]-rect[0]}x{rect[3]-rect[1]}, 位置: ({rect[0]}, {rect[1]})")
                    
        except Exception as e:
            print(f'❌ [智能选区] 枚举窗口失败: {e}')
            self.windows = []

    def find_targetrect(self, point):
        """根据鼠标位置查找最顶层的包含窗口（基于 Z-order）"""
        x, y = point
        target_rect = None
        found_window_title = None
        
        # 查找所有包含该点的窗口
        matching_windows = []
        for idx, (hwnd, rect, title) in enumerate(self.windows):
            x1, y1, x2, y2 = rect
            # 检查点是否在窗口内
            if x1 <= x <= x2 and y1 <= y <= y2:
                area = (x2 - x1) * (y2 - y1)
                # idx 就是 Z-order（EnumWindows 按从顶到底的顺序枚举）
                matching_windows.append((idx, area, hwnd, rect, title))
        
        # 如果找到多个重叠窗口
        if matching_windows:
            # 排序策略：优先选择 Z-order 最小的（最顶层），其次选择面积最小的（最精确）
            matching_windows.sort(key=lambda w: (w[0], w[1]))  # (z_order, area)
            z_order, area, hwnd, target_rect, found_window_title = matching_windows[0]
            
            # 调试信息
            if DEBUG_MONITOR:
                print(f"🎯 [智能选区] 鼠标({x}, {y})处找到窗口: '{found_window_title[:30]}', 大小: {target_rect[2]-target_rect[0]}x{target_rect[3]-target_rect[1]}, Z-order: {z_order}")
                if len(matching_windows) > 1:
                    print(f"   共有 {len(matching_windows)} 个重叠窗口，已选择最顶层的")
                    # 输出其他候选窗口
                    for i, (z, a, h, r, t) in enumerate(matching_windows[1:3], 1):
                        print(f"   候选{i}: '{t[:20]}', Z-order: {z}, 面积: {a}")
        
        # 如果没找到窗口，返回全屏
        if target_rect is None:
            if DEBUG_MONITOR:
                print(f"ℹ️ [智能选区] 在鼠标位置({x}, {y})未找到有效窗口，返回全屏")
            try:
                w = self.parent.width()
                h = self.parent.height()
                target_rect = [0, 0, w, h]
            except Exception:
                target_rect = [0, 0, 1920, 1080]
        
        return target_rect

    def clear_setup(self):
        """清理数据"""
        self.windows = []
        self.screen_offset_x = 0
        self.screen_offset_y = 0



class AutotextEdit(QTextEdit):
    """自动调整大小的文本编辑框，支持实时预览"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = self.document()
        self.document.contentsChanged.connect(self.textAreaChanged)
        self.setLineWrapMode(QTextEdit.NoWrap)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.paint = False  # True 表示提交阶段
        self.parent = parent
        try:
            self.textChanged.connect(self._handle_text_changed)
        except Exception as e:
            print(f"绑定实时文字预览失败: {e}")
        
        self.setFrameStyle(QFrame.NoFrame)
        self.setStyleSheet("background:rgba(0,0,0,0);color:rgba(0,0,0,0);")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        if self.viewport():
            self.viewport().setMouseTracking(True)
            self.viewport().setCursor(Qt.IBeamCursor)
        
        self._cursor_visible = True
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._toggle_cursor)
        self._cursor_timer.start(500)
        self._dragging = False
        self._drag_start_pos = QPoint()
        self._drag_start_global = QPoint()
        self._preedit_text = ""
        self._preedit_cursor_pos = 0

    def textAreaChanged(self, minsize=0):
        """根据文本内容自动调整大小"""
        self.document.adjustSize()
        newWidth = int(self.document.size().width() + 25)
        newHeight = int(self.document.size().height() + 15)
        if newWidth != self.width():
            self.setFixedWidth(minsize if newWidth < minsize else newWidth)
        if newHeight != self.height():
            self.setFixedHeight(minsize if newHeight < minsize else newHeight)

    def clear(self):
        """重写clear方法，确保同时清除锚点信息"""
        super().clear()
        if hasattr(self, '_anchor_base'):
            delattr(self, '_anchor_base')
        self.paint = False
        self._preedit_text = ""
        self._preedit_cursor_pos = 0

    def keyPressEvent(self, e):
        """处理按键事件"""
        if e.key() == Qt.Key_Return:
            if e.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(e)  # 换行
            else:
                # 提交
                self.paint = True
                self.hide()
                self._trigger_parent_redraw(commit=True)
        elif e.key() == Qt.Key_Escape:
            print("📝 [文字框] 按下ESC，取消文字输入")
            self.clear()
            self.hide()
            if hasattr(self, '_anchor_base'):
                delattr(self, '_anchor_base')
            if (self.parent and hasattr(self.parent, 'drawtext_pointlist') and 
                len(self.parent.drawtext_pointlist) > 0):
                self.parent.drawtext_pointlist.pop()
            if self.parent and hasattr(self.parent, 'change_tools_fun'):
                self.parent.change_tools_fun("")
            
            # 🆕 关键修复：失去焦点并停止事件传播
            self.clearFocus()
            e.accept()  # 接受事件，阻止传播到父窗口
            return  # 直接返回，不调用父类方法
        else:
            super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        """处理按键释放事件"""
        if e.key() == Qt.Key_Return:
            if not (e.modifiers() & Qt.ShiftModifier):
                if (hasattr(self.parent, 'mode') and self.parent.mode == "pinned" and 
                    hasattr(self.parent, 'current_pinned_window')):
                    if hasattr(self.parent.current_pinned_window, 'paintlayer'):
                        self.parent.current_pinned_window.paintlayer.update()
                else:
                    if hasattr(self.parent, 'paintlayer'):
                        self.parent.paintlayer.update()
        super().keyReleaseEvent(e)

    def inputMethodEvent(self, event):
        """跟踪输入法预编辑文本，便于在预览层展示拼音/候选字符"""
        if event is not None:
            try:
                self._preedit_text = event.preeditString() or ""
                self._preedit_cursor_pos = 0
                for attr in event.attributes() or []:
                    if attr.type == QInputMethodEvent.Cursor:
                        self._preedit_cursor_pos = attr.start
                        break
            except Exception:
                self._preedit_text = event.preeditString() or ""
                self._preedit_cursor_pos = 0
        super().inputMethodEvent(event)
        if not self._preedit_text:
            self._preedit_cursor_pos = 0
        self._live_preview_refresh(force_cursor_visible=True)

    def focusOutEvent(self, event):
        self._preedit_text = ""
        self._preedit_cursor_pos = 0
        super().focusOutEvent(event)

    def _handle_text_changed(self):
        """文本内容变化时，立即刷新预览并重置光标状态"""
        self._cursor_visible = True
        self._live_preview_refresh(force_cursor_visible=True)

    def _live_preview_refresh(self, force_cursor_visible=False):
        """实时预览刷新"""
        try:
            if self.paint:
                return
            if (hasattr(self.parent, 'mode') and self.parent.mode == 'pinned' and 
                hasattr(self.parent, 'current_pinned_window') and 
                hasattr(self.parent.current_pinned_window, 'paintlayer')):
                self.parent.current_pinned_window.paintlayer.update()
            elif hasattr(self.parent, 'paintlayer'):
                self.parent.paintlayer.update()
        except Exception as e:
            print(f"实时预览刷新失败: {e}")
        else:
            if force_cursor_visible:
                self._cursor_visible = True

    def _trigger_parent_redraw(self, commit=False):
        """触发父窗口重绘"""
        try:
            if (hasattr(self.parent, 'mode') and self.parent.mode == 'pinned' and 
                hasattr(self.parent, 'current_pinned_window') and 
                hasattr(self.parent.current_pinned_window, 'paintlayer')):
                self.parent.current_pinned_window.paintlayer.update()
            elif hasattr(self.parent, 'paintlayer'):
                self.parent.paintlayer.update()
        except Exception as e:
            print(f"提交后刷新失败: {e}")

    def paintEvent(self, event):
        """绘制自定义虚线边框，保持内部透明"""
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        border_color = QColor(255, 255, 255, 180)
        try:
            if self.parent and hasattr(self.parent, 'pencolor'):
                custom = QColor(self.parent.pencolor)
                border_color = QColor(custom.red(), custom.green(), custom.blue(), 200)
        except Exception:
            pass
        pen = QPen(border_color)
        pen.setStyle(Qt.DashLine)
        pen.setWidth(1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        rect = self.viewport().rect().adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(rect, 4, 4)
        painter.end()

    def _toggle_cursor(self):
        """切换光标显示状态"""
        if self.paint or not self.isVisible():
            return
        self._cursor_visible = not self._cursor_visible
        self._live_preview_refresh()

    def wheelEvent(self, event):
        """处理滚轮事件，用于调整字体大小"""
        if self.parent and hasattr(self.parent, 'tool_width'):
            angleDelta = event.angleDelta() / 8
            dy = angleDelta.y()
            
            # 调整字体大小
            if dy > 0:
                self.parent.tool_width += 1
            elif self.parent.tool_width > 1:
                self.parent.tool_width -= 1
            
            # 更新文字框字体
            self.setFont(QFont('', self.parent.tool_width))
            self.textAreaChanged()
            
            # 更新size_slider（如果存在）
            if hasattr(self.parent, 'size_slider'):
                self.parent.size_slider.setValue(self.parent.tool_width)
            
            print(f"📝 [文字框滚轮] 字体大小调整为: {self.parent.tool_width}px")
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        """虚线框拖动起始"""
        if event.button() == Qt.LeftButton and self._is_on_border(event.pos()):
            self._dragging = True
            self._drag_start_pos = QPoint(self.x(), self.y())
            self._drag_start_global = event.globalPos()
            if self.viewport():
                self.viewport().setCursor(Qt.SizeAllCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """虚线框拖动过程及边缘命中提示"""
        if self._dragging:
            delta = event.globalPos() - self._drag_start_global
            target = self._drag_start_pos + delta
            target = self._clamp_to_parent(target)
            if target != self.pos():
                old_pos = QPoint(self.x(), self.y())
                self.move(target)
                self._shift_anchor(target.x() - old_pos.x(), target.y() - old_pos.y())
                self._live_preview_refresh()
            event.accept()
            return

        if self._is_on_border(event.pos()):
            if self.viewport():
                self.viewport().setCursor(Qt.SizeAllCursor)
        else:
            if self.viewport():
                self.viewport().setCursor(Qt.IBeamCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """虚线框拖动结束"""
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            if self.viewport():
                self.viewport().setCursor(Qt.IBeamCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _is_on_border(self, pos, margin=6):
        """判断鼠标是否落在虚线边缘区域"""
        if not self.viewport():
            return False
        rect = self.viewport().rect()
        if not rect.contains(pos):
            return False
        inner = rect.adjusted(margin, margin, -margin, -margin)
        return not inner.contains(pos)

    def compose_preview_text(self):
        """返回与输入法预编辑合并后的文本及光标信息"""
        base_text = self.toPlainText()
        cursor_pos = self.textCursor().position()
        preedit = getattr(self, '_preedit_text', '') or ''
        combined = base_text
        preedit_start = cursor_pos if preedit else -1
        if preedit:
            combined = base_text[:cursor_pos] + preedit + base_text[cursor_pos:]
        caret_index = cursor_pos
        if preedit:
            caret_index = preedit_start + min(max(0, self._preedit_cursor_pos), len(preedit))
        return combined, caret_index, preedit_start, preedit

    def _clamp_to_parent(self, pos):
        """确保拖动后的文本框仍在父窗口范围内"""
        parent = self.parent
        if not parent:
            return pos
        max_x = max(0, parent.width() - self.width())
        max_y = max(0, parent.height() - self.height())
        clamped_x = max(0, min(pos.x(), max_x))
        clamped_y = max(0, min(pos.y(), max_y))
        return QPoint(clamped_x, clamped_y)

    def _shift_anchor(self, dx, dy):
        """拖动虚线框时同步更新文字绘制锚点"""
        if hasattr(self, '_anchor_base') and isinstance(self._anchor_base, tuple):
            ax, ay = self._anchor_base
            self._anchor_base = (ax + dx, ay + dy)
