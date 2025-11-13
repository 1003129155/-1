"""
jietuba_ui_components.py - UI组件模块

包含截图工具使用的各种UI组件和辅助类：
- 多屏幕调试工具
- 颜色按钮、悬停按钮等UI控件
- 智能选区查找器
- 自动调整大小的文本编辑器

从 jietuba_screenshot.py 拆分而来，降低单文件复杂度
"""
import os
import cv2
import math
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QCursor
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
    """智能选区查找器 - 基于OpenCV的轮廓检测"""
    def __init__(self, parent):
        self.h = self.w = 0
        self.rect_list = self.contours = []
        self.area_threshold = 200
        self.parent = parent
        self.img = None

    def find_contours_setup(self):
        """准备轮廓数据"""
        try:
            self.area_threshold = self.parent.parent.ss_areathreshold.value()
        except Exception:
            self.area_threshold = 200

        if self.img is None:
            return

        self.h, self.w, _ = self.img.shape
        gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
        th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY, 5, 2)
        self.contours = cv2.findContours(th, cv2.RETR_LIST,
                                         cv2.CHAIN_APPROX_SIMPLE)[-2]
        self.find_contours()

    def find_contours(self):
        """查找所有符合条件的轮廓矩形"""
        draw_img = cv2.drawContours(self.img.copy(), self.contours, -1, (0, 255, 0), 1)
        self.rect_list = [[0, 0, self.w, self.h]]
        for i in self.contours:
            x, y, w, h = cv2.boundingRect(i)
            area = cv2.contourArea(i)
            if area > self.area_threshold and w > 10 and h > 10:
                self.rect_list.append([x, y, x + w, y + h])
        print('contours:', len(self.contours), 'left', len(self.rect_list))

    def find_targetrect(self, point):
        """根据鼠标位置查找最小包含矩形"""
        target_rect = [0, 0, self.w, self.h]
        target_area = 1920 * 1080
        for rect in self.rect_list:
            if point[0] in range(rect[0], rect[2]):
                if point[1] in range(rect[1], rect[3]):
                    area = (rect[3] - rect[1]) * (rect[2] - rect[0])
                    if area < target_area:
                        target_rect = rect
                        target_area = area
        return target_rect

    def clear_setup(self):
        """清理数据"""
        self.h = self.w = 0
        self.rect_list = self.contours = []
        self.img = None


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
            self.textChanged.connect(self._live_preview_refresh)
        except Exception as e:
            print(f"绑定实时文字预览失败: {e}")
        
        self.setFrameStyle(QFrame.NoFrame)
        self.setStyleSheet("background:rgba(0,0,0,0);color:rgba(0,0,0,0);")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        
        self._cursor_visible = True
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._toggle_cursor)
        self._cursor_timer.start(500)

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

    def _live_preview_refresh(self):
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
        """覆盖原本的文字显示，实现"无输入框"视觉效果"""
        pass

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
