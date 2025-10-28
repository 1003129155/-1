"""
jietuba_screenshot.py - 截图核心功能模块

实现截图工具的核心截图和编辑功能。
支持多屏幕、区域选择、绘图工具、钉图、长截图等功能。

主要类:
- Slabel: 主截图窗口类
- PaintLayer: 绘画层类

绘图工具:
画笔、直线、箭头、矩形、圆形、文字、马赛克、模糊等

依赖模块:
jietuba_widgets, jietuba_public, jietuba_scroll, jietuba_smart_stitch
"""
import gc
import math
import os
import re
import sys
import time

import cv2
from collections import deque
from numpy import array, zeros, uint8, float32,array
from PyQt5.QtCore import QPoint, QRectF, QMimeData, QSize
from PyQt5.QtCore import QRect, Qt, pyqtSignal, QStandardPaths, QTimer, QSettings, QUrl
from PyQt5.QtGui import QCursor, QBrush, QScreen,QWindow
from PyQt5.QtGui import QPixmap, QPainter, QPen, QIcon, QFont, QImage, QColor, QPolygon
from PyQt5.QtWidgets import *  # 包含 QFrame 以支持透明输入框无边框设置
from PyQt5.QtWidgets import QSlider, QColorDialog, QWidget
from jietuba_widgets import FramelessEnterSendQTextEdit,Freezer

# OCR功能已移除 - 相关导入已禁用
# from jietuba_public import OcrimgThread, Commen_Thread, TipsShower, PLATFORM_SYS,CONFIG_DICT, get_screenshot_save_dir
from jietuba_public import Commen_Thread, TipsShower, PLATFORM_SYS,CONFIG_DICT, get_screenshot_save_dir
import jietuba_resource
from pynput.mouse import Controller

# ================== 多屏调试开关 ==================
# 环境变量 JSS_DEBUG_MONITOR=1 时输出更详细的多显示器调试信息（默认关闭）
DEBUG_MONITOR = os.environ.get("JSS_DEBUG_MONITOR", "0") not in ("0", "false", "False")

def _debug_print(msg: str):
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


def get_line_interpolation(p1, p0):
    """为两点之间生成插值点，平滑笔迹"""
    if not p1 or not p0:
        return None
    x0, y0 = p0[:2]
    x1, y1 = p1[:2]
    dx = x1 - x0
    dy = y1 - y0
    distance = max(abs(dx), abs(dy))
    if distance <= 1:
        return None
    steps = int(distance)
    if steps <= 1:
        return None
    interpolated = []
    for step in range(1, steps):
        t = step / float(steps)
        interpolated.append([
            int(round(x0 + dx * t)),
            int(round(y0 + dy * t)),
        ])
    return interpolated


class ColorButton(QPushButton):
    select_color_signal = pyqtSignal(str)

    def __init__(self, color, parent):
        super(ColorButton, self).__init__("", parent)
        self.color = QColor(color).name()
        self.setStyleSheet("background-color:{}".format(self.color))
        self.clicked.connect(self.sendcolor)

    def sendcolor(self):
        self.select_color_signal.emit(self.color)


class HoverButton(QPushButton):
    hoversignal = pyqtSignal(int)

    def enterEvent(self, e) -> None:
        super(HoverButton, self).enterEvent(e)
        self.hoversignal.emit(1)
        print("enter")

    def leaveEvent(self, e):
        super(HoverButton, self).leaveEvent(e)
        # time.sleep(2)
        self.hoversignal.emit(0)
        print("leave")


class HoverGroupbox(QGroupBox):
    hoversignal = pyqtSignal(int)

    def enterEvent(self, e) -> None:
        super(HoverGroupbox, self).enterEvent(e)
        self.hoversignal.emit(1)
        print("enter")

    def leaveEvent(self, e):
        super(HoverGroupbox, self).leaveEvent(e)
        # time.sleep(2)
        self.hoversignal.emit(0)
        print("leave")


class CanMoveGroupbox(QGroupBox):  # 移动groupbox
    def __init__(self, parent):
        super(CanMoveGroupbox, self).__init__(parent)
        self.drag = False
        self.p_x, self.p_y = 0, 0

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.x() < 100:
            self.setCursor(Qt.SizeAllCursor)
            self.drag = True
            self.p_x, self.p_y = event.x(), event.y()
        # super(CanMoveGroupbox, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ArrowCursor)
            self.drag = False
        # super(CanMoveGroupbox, self).mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.isVisible():
            if self.drag:
                self.move(event.x() + self.x() - self.p_x, event.y() + self.y() - self.p_y)

        # super(CanMoveGroupbox, self).mouseMoveEvent(event)


class Finder():  # 选择智能选区
    def __init__(self, parent):
        self.h = self.w = 0
        self.rect_list = self.contours = []
        self.area_threshold = 200
        self.parent = parent
        self.img = None

    def find_contours_setup(self):
        """准备轮廓数据（保持原逻辑，修正缩进错误）"""
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
        # print('setuptime', t2 - t1, t3 - t2, t4 - t3)

    def find_contours(self):
        draw_img = cv2.drawContours(self.img.copy(), self.contours, -1, (0, 255, 0), 1)
        # cv2.imshow("tt", draw_img)
        # cv2.imwrite("test.png", self.img.copy())
        # cv2.waitKey(0)
        # newcontours = []
        self.rect_list = [[0, 0, self.w, self.h]]
        for i in self.contours:
            x, y, w, h = cv2.boundingRect(i)
            area = cv2.contourArea(i)
            if area > self.area_threshold and w > 10 and h > 10:
                # cv2.rectangle(self.img, (x, y), (x + w, y + h), (0, 0, 255), 1)
                # newcontours.append(i)
                self.rect_list.append([x, y, x + w, y + h])
        print('contours:', len(self.contours), 'left', len(self.rect_list))

    def find_targetrect(self, point):
        # print(len(self.rect_list))
        # point = (1000, 600)
        target_rect = [0, 0, self.w, self.h]
        target_area = 1920 * 1080
        for rect in self.rect_list:
            if point[0] in range(rect[0], rect[2]):
                # print('xin',rect)
                if point[1] in range(rect[1], rect[3]):
                    # print('yin', rect)
                    area = (rect[3] - rect[1]) * (rect[2] - rect[0])
                    # print(area,target_area)
                    if area < target_area:
                        target_rect = rect
                        target_area = area
                        # print('target', target_area, target_rect)
                        # x,y,w,h=target_rect[0],target_rect[1],target_rect[2]-target_rect[0],target_rect[3]-target_rect[1]
                        # cv2.rectangle(self.img, (x, y), (x + w, y + h), (0, 0, 255), 1)
        # cv2.imwrite("img.png", self.img)
        return target_rect

    def clear_setup(self):
        self.h = self.w = 0
        self.rect_list = self.contours = []
        self.img = None


class MaskLayer(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.parent.on_init:
            print('oninit return')
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 正常显示选区
        rect = QRect(min(self.parent.x0, self.parent.x1), min(self.parent.y0, self.parent.y1),
                     abs(self.parent.x1 - self.parent.x0), abs(self.parent.y1 - self.parent.y0))

        painter.setPen(QPen(QColor(64, 224, 208), 2, Qt.SolidLine))
        painter.drawRect(rect)
        painter.drawRect(0, 0, self.width(), self.height())
        painter.setPen(QPen(QColor(48, 200, 192), 8, Qt.SolidLine))
        painter.drawPoint(
            QPoint(self.parent.x0, min(self.parent.y1, self.parent.y0) + abs(self.parent.y1 - self.parent.y0) // 2))
        painter.drawPoint(
            QPoint(min(self.parent.x1, self.parent.x0) + abs(self.parent.x1 - self.parent.x0) // 2, self.parent.y0))
        painter.drawPoint(
            QPoint(self.parent.x1, min(self.parent.y1, self.parent.y0) + abs(self.parent.y1 - self.parent.y0) // 2))
        painter.drawPoint(
            QPoint(min(self.parent.x1, self.parent.x0) + abs(self.parent.x1 - self.parent.x0) // 2, self.parent.y1))
        painter.drawPoint(QPoint(self.parent.x0, self.parent.y0))
        painter.drawPoint(QPoint(self.parent.x0, self.parent.y1))
        painter.drawPoint(QPoint(self.parent.x1, self.parent.y0))
        painter.drawPoint(QPoint(self.parent.x1, self.parent.y1))

        x = y = 100
        if self.parent.x1 > self.parent.x0:
            x = self.parent.x0 + 5
        else:
            x = self.parent.x0 - 72
        if self.parent.y1 > self.parent.y0:
            y = self.parent.y0 + 15
        else:
            y = self.parent.y0 - 5
        painter.setPen(QPen(QColor(32, 178, 170), 2, Qt.SolidLine))
        painter.drawText(x, y,
                         '{}x{}'.format(abs(self.parent.x1 - self.parent.x0), abs(self.parent.y1 - self.parent.y0)))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawRect(0, 0, self.width(), min(self.parent.y1, self.parent.y0))
        painter.drawRect(0, min(self.parent.y1, self.parent.y0), min(self.parent.x1, self.parent.x0),
                         self.height() - min(self.parent.y1, self.parent.y0))
        painter.drawRect(max(self.parent.x1, self.parent.x0), min(self.parent.y1, self.parent.y0),
                         self.width() - max(self.parent.x1, self.parent.x0),
                         self.height() - min(self.parent.y1, self.parent.y0))
        painter.drawRect(min(self.parent.x1, self.parent.x0), max(self.parent.y1, self.parent.y0),
                         max(self.parent.x1, self.parent.x0) - min(self.parent.x1, self.parent.x0),
                         self.height() - max(self.parent.y1, self.parent.y0))
        
        # 以下为鼠标放大镜
        if not (self.parent.painter_tools['drawcircle_on'] or
                self.parent.painter_tools['drawrect_bs_on'] or
                self.parent.painter_tools['pen_on'] or
                self.parent.painter_tools['highlight_on'] or
                self.parent.painter_tools['drawtext_on'] or
                self.parent.move_rect):

            # 鼠标放大镜功能

            if self.parent.mouse_posx > self.width() - 140:
                enlarge_box_x = self.parent.mouse_posx - 140
            else:
                enlarge_box_x = self.parent.mouse_posx + 20
            if self.parent.mouse_posy > self.height() - 140:
                enlarge_box_y = self.parent.mouse_posy - 120
            else:
                enlarge_box_y = self.parent.mouse_posy + 20
            enlarge_rect = QRect(enlarge_box_x, enlarge_box_y, 120, 120)
            painter.setPen(QPen(QColor(64, 224, 208), 1, Qt.SolidLine))
            painter.drawRect(enlarge_rect)
            painter.setBrush(QBrush(QColor(80, 80, 80, 180)))
            painter.drawRect(QRect(enlarge_box_x, enlarge_box_y - 60, 160, 60))
            painter.setBrush(Qt.NoBrush)

            # 安全获取像素颜色 - 修复负坐标问题
            color = QColor(255, 255, 255)

            # 检查坐标是否在有效范围内
            mouse_x = self.parent.mouse_posx
            mouse_y = self.parent.mouse_posy

            if hasattr(self.parent, 'qimg') and self.parent.qimg:
                img = self.parent.qimg
                if 0 <= mouse_x < img.width() and 0 <= mouse_y < img.height():
                    color = QColor(img.pixelColor(mouse_x, mouse_y))
            else:
                pixmap = self.parent.pixmap()
                if pixmap and not pixmap.isNull():
                    img = pixmap.toImage()
                    if 0 <= mouse_x < img.width() and 0 <= mouse_y < img.height():
                        color = QColor(img.pixelColor(mouse_x, mouse_y))

            RGB_color = [color.red(), color.green(), color.blue()]
            HSV_color = cv2.cvtColor(array([[RGB_color]], dtype=uint8), cv2.COLOR_RGB2HSV).tolist()[0][0]

            painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.SolidLine))
            painter.drawText(enlarge_box_x, enlarge_box_y - 8,
                             ' POS:({},{}) '.format(self.parent.mouse_posx, self.parent.mouse_posy))
            painter.drawText(enlarge_box_x, enlarge_box_y - 24,
                             " HSV:({},{},{})".format(HSV_color[0], HSV_color[1], HSV_color[2]))
            painter.drawText(enlarge_box_x, enlarge_box_y - 40,
                             " RGB:({},{},{})".format(RGB_color[0], RGB_color[1], RGB_color[2]))

            try:
                painter.setCompositionMode(QPainter.CompositionMode_Source)
                rpix = QPixmap(self.width() + 120, self.height() + 120)
                rpix.fill(QColor(0, 0, 0))
                rpixpainter = QPainter(rpix)
                rpixpainter.drawPixmap(60, 60, self.parent.pixmap())
                rpixpainter.end()
                larger_pix = rpix.copy(self.parent.mouse_posx, self.parent.mouse_posy, 120, 120).scaled(
                    120 + self.parent.tool_width * 10, 120 + self.parent.tool_width * 10)
                pix = larger_pix.copy(larger_pix.width() // 2 - 60, larger_pix.height() // 2 - 60, 120, 120)
                painter.drawPixmap(enlarge_box_x, enlarge_box_y, pix)
                painter.setPen(QPen(QColor(64, 224, 208), 1, Qt.SolidLine))
                painter.drawLine(enlarge_box_x, enlarge_box_y + 60, enlarge_box_x + 120, enlarge_box_y + 60)
                painter.drawLine(enlarge_box_x + 60, enlarge_box_y, enlarge_box_x + 60, enlarge_box_y + 120)
            except:
                print('draw_enlarge_box fail')

        painter.end()


class PaintLayer(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # self.setAutoFillBackground(False)
        # self.setPixmap(QPixmap())
        self.setMouseTracking(True)
        self.px = self.py = -50
        self.pixPainter = None  # 初始化pixPainter
        # 标记 pixmap 是否在本次 paintEvent 中成功 begin，防止重复 begin
        self._pixpainter_started_in_event = False

    def _begin_pix_painter(self):
        """确保 self.pixPainter 指向一个已 begin 的 QPainter。
        失败返回 False。"""
        if self.pixPainter and isinstance(self.pixPainter, QPainter):
            try:
                if self.pixPainter.isActive():
                    return True
            except Exception:
                # 失效则抛弃重新创建
                self.pixPainter = None
        # 检查 pixmap 可用
        pm = self.pixmap()
        if not pm or pm.isNull():
            return False
        self.pixPainter = QPainter()
        if not self.pixPainter.begin(pm):
            self.pixPainter = None
            return False
        self.pixPainter.setRenderHint(QPainter.Antialiasing)
        self._pixpainter_started_in_event = True
        return True

    def paintEvent(self, e):
        super().paintEvent(e)
        
        # 检查父窗口是否正在关闭
        if not self.parent or getattr(self.parent, 'closed', False):
            return
            
        if self.parent.on_init:
            print('oninit return')
            return
        if 1 in self.parent.painter_tools.values():  # 如果有画笔工具打开
            painter = QPainter(self)
            color = QColor(self.parent.pencolor)
            color.setAlpha(255)

            width = self.parent.tool_width
            painter.setPen(QPen(color, 1, Qt.SolidLine))
            rect = QRectF(self.px - width // 2, self.py - width // 2,
                          width, width)
            painter.drawEllipse(rect)  # 画鼠标圆
            painter.end()
        # self.pixPainter.begin()
        try:
            # 确保pixPainter在使用前被正确清理
            if hasattr(self, 'pixPainter') and self.pixPainter:
                try:
                    if self.pixPainter.isActive():
                        self.pixPainter.end()
                except:
                    pass
                self.pixPainter = None
            
            # 检查pixmap是否有效
            if self.pixmap() and not self.pixmap().isNull():
                self.pixPainter = QPainter()
                if not self.pixPainter.begin(self.pixmap()):
                    print('QPainter begin failed')
                    return
                self.pixPainter.setRenderHint(QPainter.Antialiasing)
            else:
                print('pixmap invalid, skip painting')
                return
        except Exception as e:
            print(f'pixpainter init fail: {e}')
            return

        def get_ture_pen_alpha_color():
            color = QColor(self.parent.pencolor)
            if color.alpha() != 255:
                al = self.parent.pencolor.alpha() / (self.parent.tool_width / 2)
                if al > 1:
                    color.setAlpha(al)
                else:
                    color.setAlpha(1)
            return color

        base_painter = None
        if self.parent.painter_tools.get('highlight_on'):
            base_pixmap = self.parent.pixmap()
            if base_pixmap and not base_pixmap.isNull():
                # 直接在截图底图上绘制并使用正片叠底混合，实现真实的荧光笔效果
                base_painter = QPainter(base_pixmap)
                base_painter.setRenderHint(QPainter.Antialiasing)
                base_painter.setCompositionMode(QPainter.CompositionMode_Multiply)

        while len(self.parent.pen_pointlist):  # 画笔工具
            color = get_ture_pen_alpha_color()
            pen_painter = base_painter if base_painter else self.pixPainter
            pen_painter.setBrush(color)
            pen_painter.setPen(Qt.NoPen)
            pen_painter.setRenderHint(QPainter.Antialiasing)
            new_pen_point = self.parent.pen_pointlist.pop(0)
            if self.parent.old_pen is None:
                self.parent.old_pen = new_pen_point
                continue
            if self.parent.old_pen[0] != -2 and new_pen_point[0] != -2:
                # 荧光笔使用正方形笔刷，普通画笔使用圆形笔刷
                if self.parent.painter_tools.get('highlight_on'):
                    pen_painter.drawRect(new_pen_point[0] - self.parent.tool_width / 2,
                                         new_pen_point[1] - self.parent.tool_width / 2,
                                         self.parent.tool_width, self.parent.tool_width)
                else:
                    pen_painter.drawEllipse(new_pen_point[0] - self.parent.tool_width / 2,
                                            new_pen_point[1] - self.parent.tool_width / 2,
                                            self.parent.tool_width, self.parent.tool_width)
                if abs(new_pen_point[0] - self.parent.old_pen[0]) > 1 or abs(
                        new_pen_point[1] - self.parent.old_pen[1]) > 1:
                    interpolateposs = get_line_interpolation(new_pen_point[:], self.parent.old_pen[:])
                    if interpolateposs is not None:
                        for pos in interpolateposs:
                            x, y = pos
                            # 荧光笔使用正方形笔刷，普通画笔使用圆形笔刷
                            if self.parent.painter_tools.get('highlight_on'):
                                pen_painter.drawRect(x - self.parent.tool_width / 2,
                                                     y - self.parent.tool_width / 2,
                                                     self.parent.tool_width, self.parent.tool_width)
                            else:
                                pen_painter.drawEllipse(x - self.parent.tool_width / 2,
                                                        y - self.parent.tool_width / 2,
                                                        self.parent.tool_width, self.parent.tool_width)

            self.parent.old_pen = new_pen_point
        if base_painter:
            base_painter.end()
            if hasattr(self.parent, 'showing_imgpix') and self.parent.pixmap():
                try:
                    # 钉图窗口会读取showing_imgpix保存内容，这里同步更新
                    self.parent.showing_imgpix = self.parent.pixmap().copy()
                except Exception as sync_err:
                    print(f"⚠️ 正片叠底同步失败: {sync_err}")
            if hasattr(self.parent, 'qimg'):
                try:
                    self.parent.qimg = self.parent.pixmap().toImage()
                except Exception as image_sync_err:
                    print(f"⚠️ 正片叠底图像同步失败: {image_sync_err}")
            self.parent.update()
        if self.parent.drawrect_pointlist[0][0] != -2 and self.parent.drawrect_pointlist[1][0] != -2:  # 画矩形工具
            # print(self.parent.drawrect_pointlist)
            try:
                temppainter = QPainter(self)
                temppainter.setPen(QPen(self.parent.pencolor, self.parent.tool_width, Qt.SolidLine))

                poitlist = self.parent.drawrect_pointlist
                temppainter.drawRect(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                     abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                temppainter.end()
            except Exception as e:
                print(f"画矩形临时QPainter错误: {e}")
                
            if self.parent.drawrect_pointlist[2] == 1:
                try:
                    self.pixPainter.setPen(QPen(self.parent.pencolor, self.parent.tool_width, Qt.SolidLine))
                    self.pixPainter.drawRect(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                             abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                    self.parent.drawrect_pointlist = [[-2, -2], [-2, -2], 0]
                    # 矩形绘制完成后创建备份
                    print(f"矩形撤销调试: paintEvent中绘制完成，创建备份")
                    self.parent.backup_shortshot()
                except Exception as e:
                    print(f"画矩形pixPainter错误: {e}")
                # print("panit",self.parent.drawrect_pointlist)
                # self.parent.drawrect_pointlist[0] = [-2, -2]

        if self.parent.drawcircle_pointlist[0][0] != -2 and self.parent.drawcircle_pointlist[1][0] != -2:  # 画圆工具
            try:
                temppainter = QPainter(self)
                temppainter.setPen(QPen(self.parent.pencolor, self.parent.tool_width, Qt.SolidLine))
                poitlist = self.parent.drawcircle_pointlist
                temppainter.drawEllipse(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                        abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                temppainter.end()
            except Exception as e:
                print(f"画圆临时QPainter错误: {e}")
                
            if self.parent.drawcircle_pointlist[2] == 1:
                try:
                    self.pixPainter.setPen(QPen(self.parent.pencolor, self.parent.tool_width, Qt.SolidLine))
                    self.pixPainter.drawEllipse(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                                abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                    self.parent.drawcircle_pointlist = [[-2, -2], [-2, -2], 0]
                    # 圆形绘制完成后创建备份
                    print(f"圆形撤销调试: paintEvent中绘制完成，创建备份")
                    self.parent.backup_shortshot()
                except Exception as e:
                    print(f"画圆pixPainter错误: {e}")
                # self.parent.drawcircle_pointlist[0] = [-2, -2]

        if self.parent.drawarrow_pointlist[0][0] != -2 and self.parent.drawarrow_pointlist[1][0] != -2:  # 画箭头
            # print(self.parent.drawarrow_pointlist)
            # self.pixPainter = QPainter(self.pixmap())
            try:
                temppainter = QPainter(self)
                temppainter.setPen(QPen(self.parent.pencolor, self.parent.tool_width, Qt.SolidLine))
                temppainter.setBrush(QBrush(self.parent.pencolor))
                poitlist = self.parent.drawarrow_pointlist
                
                # 计算箭头参数
                start_x, start_y = poitlist[0][0], poitlist[0][1]
                end_x, end_y = poitlist[1][0], poitlist[1][1]
                
                # 绘制箭头线条
                temppainter.drawLine(start_x, start_y, end_x, end_y)
                
                # 计算箭头头部
                angle = math.atan2(end_y - start_y, end_x - start_x)
                arrow_length = max(self.parent.tool_width * 2, 15)  # 箭头长度根据工具宽度调整，最小15
                arrow_width = max(self.parent.tool_width * 1.5, 10)  # 箭头宽度根据工具宽度调整，最小10
                
                # 箭头头部的三个点
                arrow_p1_x = end_x - arrow_length * math.cos(angle - math.pi / 6)
                arrow_p1_y = end_y - arrow_length * math.sin(angle - math.pi / 6)
                arrow_p2_x = end_x - arrow_length * math.cos(angle + math.pi / 6)
                arrow_p2_y = end_y - arrow_length * math.sin(angle + math.pi / 6)
                
                # 绘制箭头头部
                arrow_head = QPolygon([
                    QPoint(int(end_x), int(end_y)),
                    QPoint(int(arrow_p1_x), int(arrow_p1_y)),
                    QPoint(int(arrow_p2_x), int(arrow_p2_y))
                ])
                temppainter.drawPolygon(arrow_head)
                temppainter.end()
            except Exception as e:
                print(f"画箭头临时QPainter错误: {e}")
                
            if self.parent.drawarrow_pointlist[2] == 1:
                try:
                    # 在真正写入底层 pixmap 前再次确保 painter 可用
                    if not self._begin_pix_painter():
                        raise RuntimeError('pixPainter 初始化失败，无法提交箭头')
                    self.pixPainter.setPen(QPen(self.parent.pencolor, self.parent.tool_width, Qt.SolidLine))
                    self.pixPainter.setBrush(QBrush(self.parent.pencolor))
                    
                    # 计算箭头参数
                    start_x, start_y = poitlist[0][0], poitlist[0][1]
                    end_x, end_y = poitlist[1][0], poitlist[1][1]
                    
                    # 绘制箭头线条
                    self.pixPainter.drawLine(start_x, start_y, end_x, end_y)
                    
                    # 计算箭头头部
                    angle = math.atan2(end_y - start_y, end_x - start_x)
                    arrow_length = max(self.parent.tool_width * 2, 15)  # 箭头长度根据工具宽度调整，最小15
                    arrow_width = max(self.parent.tool_width * 1.5, 10)  # 箭头宽度根据工具宽度调整，最小10
                    
                    # 箭头头部的三个点
                    arrow_p1_x = end_x - arrow_length * math.cos(angle - math.pi / 6)
                    arrow_p1_y = end_y - arrow_length * math.sin(angle - math.pi / 6)
                    arrow_p2_x = end_x - arrow_length * math.cos(angle + math.pi / 6)
                    arrow_p2_y = end_y - arrow_length * math.sin(angle + math.pi / 6)
                    
                    # 绘制箭头头部
                    arrow_head = QPolygon([
                        QPoint(int(end_x), int(end_y)),
                        QPoint(int(arrow_p1_x), int(arrow_p1_y)),
                        QPoint(int(arrow_p2_x), int(arrow_p2_y))
                    ])
                    self.pixPainter.drawPolygon(arrow_head)
                    self.parent.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
                    # 箭头绘制完成后创建备份
                    print(f"箭头撤销调试: paintEvent中绘制完成，创建备份")
                    self.parent.backup_shortshot()
                except Exception as e:
                    print(f"画箭头pixPainter错误: {e}")
                # self.parent.drawarrow_pointlist[0] = [-2, -2]

        # ---- 实时文字提交阶段 ----
        if len(self.parent.drawtext_pointlist) > 1 or self.parent.text_box.paint:  # 提交绘制
            from jietuba_text_drawer import UnifiedTextDrawer
            # 统一逻辑：此时 text_box.paint==True 表示提交
            if self.parent.text_box.paint:
                # 使用统一处理（不再手写重复逻辑）
                try:
                    UnifiedTextDrawer.process_text_drawing(self.parent, self.pixPainter, self.parent.text_box)
                except Exception as e:
                    print(f"统一文字提交错误: {e}")
            else:
                # 兼容旧分支（可能len>1)，保持原来弹出逻辑
                try:
                    text = self.parent.text_box.toPlainText()
                    self.parent.text_box.clear()
                    pos = self.parent.drawtext_pointlist.pop(0)
                    if text and text.strip():
                        self.pixPainter.setFont(QFont('', self.parent.tool_width))
                        self.pixPainter.setPen(QPen(self.parent.pencolor, 3, Qt.SolidLine))
                        lines = text.split('\n')
                        line_height = self.parent.tool_width * 2.0
                        base_x = pos[0] + self.parent.text_box.document.size().height() / 8 - 3
                        base_y = pos[1] + self.parent.text_box.document.size().height() * 32 / 41 - 2
                        for i, line in enumerate(lines):
                            if line.strip():
                                self.pixPainter.drawText(base_x, base_y + i * line_height, line)
                        self.parent.backup_shortshot()
                        self.parent.setFocus()
                    else:
                        print("文字撤销调试: 空文本提交跳过")
                except Exception as e:
                    print(f"旧文字提交兼容错误: {e}")

        # ---- 实时文字预览: 尚未提交时绘制到前景(不写入pixmap) ----
        try:
            from jietuba_text_drawer import UnifiedTextDrawer
            if (hasattr(self.parent, 'text_box') and
                hasattr(self.parent, 'drawtext_pointlist') and
                len(self.parent.drawtext_pointlist) > 0 and
                not self.parent.text_box.paint):
                UnifiedTextDrawer.render_live_preview(self, self.parent, self.parent.text_box)
        except Exception as e:
            print(f"截图实时文字预览错误: {e}")
        try:
            if hasattr(self, 'pixPainter') and self.pixPainter:
                if self.pixPainter.isActive():
                    self.pixPainter.end()
                self.pixPainter = None
        except Exception as e:
            print(f"pixpainter end error: {e}")
            # 强制清理
            self.pixPainter = None

        # 选区预览与手柄绘制（移动/缩放已绘制文字/图形）
        try:
            if hasattr(self.parent, 'selection_active') and self.parent.selection_active:
                overlay = QPainter(self)
                overlay.setRenderHint(QPainter.Antialiasing)
                # 绘制选中的像素预览
                if getattr(self.parent, 'selection_scaled_pixmap', None) is not None:
                    overlay.drawPixmap(self.parent.selection_rect.topLeft(), self.parent.selection_scaled_pixmap)
                # 绘制虚线边框
                pen = QPen(QColor(0, 120, 215), 1, Qt.DashLine)
                overlay.setPen(pen)
                overlay.setBrush(Qt.NoBrush)
                overlay.drawRect(self.parent.selection_rect)
                # 绘制8个缩放手柄
                handle_size = 6
                r = self.parent.selection_rect
                cx = r.x() + r.width() // 2
                cy = r.y() + r.height() // 2
                handles = [
                    QRect(r.left()-handle_size//2, r.top()-handle_size//2, handle_size, handle_size),       # tl
                    QRect(cx-handle_size//2, r.top()-handle_size//2, handle_size, handle_size),             # t
                    QRect(r.right()-handle_size//2, r.top()-handle_size//2, handle_size, handle_size),      # tr
                    QRect(r.left()-handle_size//2, cy-handle_size//2, handle_size, handle_size),            # l
                    QRect(r.right()-handle_size//2, cy-handle_size//2, handle_size, handle_size),           # r
                    QRect(r.left()-handle_size//2, r.bottom()-handle_size//2, handle_size, handle_size),   # bl
                    QRect(cx-handle_size//2, r.bottom()-handle_size//2, handle_size, handle_size),          # b
                    QRect(r.right()-handle_size//2, r.bottom()-handle_size//2, handle_size, handle_size),  # br
                ]
                overlay.setBrush(QBrush(QColor(0, 120, 215)))
                for h in handles:
                    overlay.drawRect(h)
                overlay.end()
        except Exception as e:
            print(f"selection overlay draw error: {e}")

    def clear(self):
        """清理PaintLayer的绘画数据和QPainter"""
        try:
            # 停止并清理painter
            if hasattr(self, 'pixPainter') and self.pixPainter:
                try:
                    if self.pixPainter.isActive():
                        self.pixPainter.end()
                except:
                    pass
                self.pixPainter = None
            
            # 清理pixmap
            empty_pix = QPixmap(1, 1)
            empty_pix.fill(Qt.transparent)
            self.setPixmap(empty_pix)
            
            # 断开引用
            self.parent = None
            
            print("🧹 [内存清理] PaintLayer清理完成")
        except Exception as e:
            print(f"⚠️ PaintLayer清理时出错: {e}")

    def __del__(self):
        """析构函数，确保QPainter被正确清理"""
        try:
            if hasattr(self, 'pixPainter') and self.pixPainter:
                try:
                    if self.pixPainter.isActive():
                        self.pixPainter.end()
                except:
                    pass
                self.pixPainter = None
        except:
            pass


class AutotextEdit(QTextEdit):
    """文字输入编辑框，增加实时预览刷新功能"""
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
        # 设置基本样式，让文字框在输入时可见
        # 移除原来的完全透明样式，改为半透明背景便于用户输入
        self.setFrameStyle(QFrame.NoFrame)
        # 初始设置为透明，将在mousePressEvent中根据模式设置具体样式
        self.setStyleSheet("background:rgba(0,0,0,0);color:rgba(0,0,0,0);")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)  # 仍接收输入
        self._cursor_visible = True
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._toggle_cursor)
        self._cursor_timer.start(500)

    def textAreaChanged(self, minsize=0):
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
        # 清除锚点信息，确保下次新建输入框时重新计算位置
        if hasattr(self, '_anchor_base'):
            delattr(self, '_anchor_base')
        # 重置paint状态
        self.paint = False

    def keyPressEvent(self, e):
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
            self.clear(); self.hide()
            # 清除锚点信息，避免影响下次新建输入框
            if hasattr(self, '_anchor_base'):
                delattr(self, '_anchor_base')
            if (self.parent and hasattr(self.parent, 'drawtext_pointlist') and len(self.parent.drawtext_pointlist) > 0):
                self.parent.drawtext_pointlist.pop()
            if self.parent and hasattr(self.parent, 'change_tools_fun'):
                self.parent.change_tools_fun("")
        else:
            super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Return:
            if not (e.modifiers() & Qt.ShiftModifier):
                if (hasattr(self.parent, 'mode') and self.parent.mode == "pinned" and hasattr(self.parent, 'current_pinned_window')):
                    if hasattr(self.parent.current_pinned_window, 'paintlayer'):
                        self.parent.current_pinned_window.paintlayer.update()
                else:
                    if hasattr(self.parent, 'paintlayer'):
                        self.parent.paintlayer.update()
        super().keyReleaseEvent(e)

    # ===== 实时预览 =====
    def _live_preview_refresh(self):
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
            # 重置光标闪烁
            self._cursor_visible = True

    def _trigger_parent_redraw(self, commit=False):
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
        # 覆盖原本的文字显示：不在输入框自身绘制任何文字，实现“无输入框”视觉
        # 仅在调试时可打开以下一行查看边界
        # painter = QPainter(self); painter.setPen(QColor(0,255,0,120)); painter.drawRect(self.rect()); painter.end()
        pass

    def _toggle_cursor(self):
        if self.paint or not self.isVisible():
            return
        self._cursor_visible = not self._cursor_visible
        # 触发外层重绘（光标在外层预览里画）
        self._live_preview_refresh()

    def wheelEvent(self, event):
        """文字输入框的滚轮事件：调整字体大小"""
        if self.parent and hasattr(self.parent, 'tool_width'):
            angleDelta = event.angleDelta() / 8
            dy = angleDelta.y()
            
            print(f"💬 [文字框滚轮] 当前字体大小: {self.parent.tool_width}px")
            
            # 调整字体大小
            if dy > 0:
                self.parent.tool_width += 1
            elif self.parent.tool_width > 1:
                self.parent.tool_width -= 1
            
            # 同步更新size_slider
            if hasattr(self.parent, 'size_slider'):
                self.parent.size_slider.setValue(self.parent.tool_width)
            
            # 更新文字框字体和大小
            self.setFont(QFont('', self.parent.tool_width))
            self.textAreaChanged()
            
            print(f"💬 [文字框滚轮] 字体大小调整为: {self.parent.tool_width}px")
            
            # 阻止事件传播，避免被父窗口处理
            event.accept()
        else:
            # 如果没有parent或tool_width，使用默认处理
            super().wheelEvent(event)

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
            
            # 显示提示（如果存在）
            print(f"📝 [文字框滚轮] 字体大小调整为: {self.parent.tool_width}px")
        else:
            # 如果没有父窗口或tool_width，使用默认行为
            super().wheelEvent(event)




class Slabel(QLabel):  # 区域截图功能
    showm_signal = pyqtSignal(str)
    close_signal = pyqtSignal()
    ocr_image_signal = pyqtSignal(str)
    screen_shot_result_signal = pyqtSignal(str)
    screen_shot_end_show_sinal = pyqtSignal(QPixmap)
    set_area_result_signal = pyqtSignal(list)
    getpix_result_signal = pyqtSignal(tuple,QPixmap)
    def __init__(self, parent=None):
        super().__init__()
        # self.ready_flag = False
        self.parent = parent
        
        # 使用新的截图保存目录（桌面上的スクショ文件夹）
        self.screenshot_save_dir = get_screenshot_save_dir()
        
        # 为了兼容性，仍然创建j_temp目录（用于临时文件）
        if not os.path.exists("j_temp"):
            os.mkdir("j_temp")
        # self.pixmap()=QPixmap()
        # 立即初始化选区相关状态，防止在 setup/init_parameters 之前被事件访问
        self.selection_active = False
        self.selection_rect = QRect(-1, -1, 0, 0)
        self.selection_pixmap = None
        self.selection_scaled_pixmap = None
        self.selection_original_rect = QRect(-1, -1, 0, 0)
        self.selection_dragging = False
        self.selection_resize_edge = None
        self.selection_press_offset = QPoint(0, 0)
        self.selection_press_pos = QPoint(0, 0)
        self.selection_press_rect = QRect(-1, -1, 0, 0)
        self.selection_mask = None
        self.left_button_push = False

    def _ensure_selection_state(self):
        """兜底：若因早期事件导致属性缺失则补齐。"""
        if not hasattr(self, 'selection_active'):
            self.selection_active = False
        if not hasattr(self, 'selection_rect'):
            self.selection_rect = QRect(-1, -1, 0, 0)
        if not hasattr(self, 'selection_pixmap'):
            self.selection_pixmap = None
        if not hasattr(self, 'selection_scaled_pixmap'):
            self.selection_scaled_pixmap = None
        if not hasattr(self, 'selection_original_rect'):
            self.selection_original_rect = QRect(-1, -1, 0, 0)
        if not hasattr(self, 'selection_dragging'):
            self.selection_dragging = False
        if not hasattr(self, 'selection_resize_edge'):
            self.selection_resize_edge = None
        if not hasattr(self, 'selection_press_offset'):
            self.selection_press_offset = QPoint(0, 0)
        if not hasattr(self, 'selection_press_pos'):
            self.selection_press_pos = QPoint(0, 0)
        if not hasattr(self, 'selection_press_rect'):
            self.selection_press_rect = QRect(-1, -1, 0, 0)
        if not hasattr(self, 'selection_mask'):
            self.selection_mask = None
        if not hasattr(self, 'left_button_push'):
            self.left_button_push = False

    def setup(self,mode = "screenshot"):  # 初始化界面
        self.on_init = True
        self.closed = False  # QPainter安全标记
        self.mode = mode
        self.paintlayer = PaintLayer(self)  # 绘图层
        self.mask = MaskLayer(self)  # 遮罩层
        self.text_box = AutotextEdit(self)  # 文字工具类
        self.ocr_freezer = None
        self.shower = FramelessEnterSendQTextEdit(self, enter_tra=True)  # 截屏时文字识别的小窗口
        self.settings = QSettings('Fandes', 'jietuba')
        self.setMouseTracking(True)
        
        # 优化：预先设置窗口属性，避免后续闪烁
        if PLATFORM_SYS == "darwin":
            self.setWindowFlags(Qt.FramelessWindowHint)
        else:
            self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)  # Sheet
            
        # 预先隐藏窗口，避免显示过程中的跳动
        self.hide()
        self.setWindowOpacity(0)  # 先设为透明
        # self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.botton_box = QGroupBox(self)  # botton_box是截屏选框旁边那个按钮堆的box
        self.save_botton = QPushButton(QIcon(":/saveicon.png"), '', self.botton_box)
        self.save_botton.clicked.connect(self.handle_save_button_click)
        # OCR和翻译功能已移除
        # self.ocr_botton = QPushButton(self.botton_box)
        # self.translate_botton = QPushButton(self.botton_box)  # 添加翻译按钮
        self.copy_botton = QPushButton(self.botton_box)  # 添加复制按钮
        self.sure_btn = QPushButton("完了", self.botton_box)
        self.freeze_img_botton = QPushButton(self.botton_box)
        self.long_screenshot_btn = QPushButton(self.botton_box)  # 长截图按钮
        self.pencolor = QColor(Qt.red)
        
        # 创建二级菜单容器 - 用于显示绘画工具的调节控件
        self.paint_tools_menu = QWidget(self)
        self.paint_tools_menu.setStyleSheet("QWidget{background-color:rgba(80,80,80,180);border:1px solid #666;}")
        self.paint_tools_menu.hide()
        
        # 将调节控件移到二级菜单中
        self.choice_clor_btn = HoverButton('', self.botton_box)  # 移动到底部导航栏
        self.size_slider = QSlider(Qt.Horizontal, self.paint_tools_menu)
        self.alpha_slider = QSlider(Qt.Horizontal, self.paint_tools_menu)
        self.sizetextlabel = QLabel(self.paint_tools_menu)
        self.alphatextlabel = QLabel(self.paint_tools_menu)
        self.size_slider_label = QLabel(self.paint_tools_menu)
        self.alpha_slider_label = QLabel(self.paint_tools_menu)
        
        # 添加3个预设按钮
        self.preset_btn_1 = QPushButton('1', self.paint_tools_menu)
        self.preset_btn_2 = QPushButton('2', self.paint_tools_menu)
        self.preset_btn_3 = QPushButton('3', self.paint_tools_menu)
        
        self.pen = QPushButton('', self.botton_box)  # 移动到底部导航栏
        self.highlighter = QPushButton('', self.botton_box)  # 独立的荧光笔工具
        self.drawarrow = QPushButton('', self.botton_box)  # 移动到底部导航栏
        self.drawcircle = QPushButton('', self.botton_box)  # 移动到底部导航栏
        self.bs = QPushButton('', self.botton_box)  # 移动到底部导航栏
        self.drawtext = QPushButton('', self.botton_box)  # 移动到底部导航栏
        # 在主界面设置中管理智能选区开关；为了兼容旧代码中对
        # self.smartcursor_btn 的引用，这里仍创建一个隐藏的按钮实例
        # 避免因属性缺失导致的 AttributeError
        self.smartcursor_btn = QPushButton('', self.botton_box)
        self.smartcursor_btn.setVisible(False)  # 工具栏不显示该按钮
        # 保留对象以兼容后续代码（仍可通过设置界面或调试显示）
        self.lastbtn = QPushButton("", self.botton_box)  # 移动到底部导航栏
        self.nextbtn = QPushButton("", self.botton_box)  # 移动到底部导航栏
        self.finder = Finder(self)  # 智能选区的寻找器
        self.Tipsshower = TipsShower("  ", targetarea=(100, 70, 0, 0), parent=self)  # 左上角的大字提示
        self.Tipsshower.hide()
        # 移除了信号连接以避免显示提示
        if PLATFORM_SYS == "darwin":
            self.init_slabel_ui()
            print("init slabel ui")
        else:
            self.init_slabel_ui()
            print("init slabel ui")
            # self.init_slabel_thread = Commen_Thread(self.init_slabel_ui)
            # self.init_slabel_thread.start()
        if mode != "screenshot":#非截屏模式(jietuba中也会调用截屏工具进行选取录屏或者文字识别)
            self.save_botton.hide()
            self.freeze_img_botton.hide()
            # OCR和翻译按钮已移除
            # self.ocr_botton.hide()
            # self.translate_botton.hide()
            
        # self.setVisible(False)
        # self.setWindowOpacity(0)
        # self.showFullScreen()
        # self.hide()
        # self.setWindowOpacity(1)
        
        self.init_parameters()
        self.backup_ssid = 0  # 当前备份数组的id,用于确定回退了几步
        self.backup_pic_list = []  # 备份页面的数组,用于前进/后退
        self._in_undo_operation = False  # 防止撤销操作冲突的标志
        self.on_init = False

    def init_parameters(self):  # 初始化参数
        self.NpainterNmoveFlag = self.choicing = self.move_rect = self.move_y0 = self.move_x0 = self.move_x1 \
            = self.change_alpha = self.move_y1 = False
        self.x0 = self.y0 = self.rx0 = self.ry0 = self.x1 = self.y1 = -50
        # 鼠标位置初始化为一个安全的正数位置，避免负坐标导致pixelColor错误
        self.mouse_posx = self.mouse_posy = 100
        self.bx = self.by = 0
        self.alpha = 255  # 透明度值
        # 修改：智能选区默认关闭，避免启动时卡顿
        self.smartcursor_on = self.settings.value("screenshot/smartcursor", False, type=bool)  # 默认改为False
        self.finding_rect = True  # 正在自动寻找选取的控制变量,就进入截屏之后会根据鼠标移动到的位置自动选取,
        self.tool_width = 5
        # 画笔相关属性初始化
        self.pen_drawn_points_count = 0  # 画笔绘制的点数计数器
        self.pen_start_point = [0, 0]  # 画笔起始点
        self.pen_last_point = [0, 0]  # 画笔最后一个点
        # 新增：防止外部 paintLayer / jamWidgets 使用前属性缺失
        self.old_pen = None
        # 画笔点列表（实时绘制队列）
        self.pen_pointlist = []
        # 其他绘图工具点列表，统一初始化防止 AttributeError
        self.drawrect_pointlist = [[-2, -2], [-2, -2], 0]
        self.drawcircle_pointlist = [[-2, -2], [-2, -2], 0]
        self.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
        self.drawtext_pointlist = []
        # 钉图模式下的 paintlayer 可能复用这些结构
        self.painter_tools = {
            'pen_on': 0,
            'highlight_on': 0,
            'drawarrow_on': 0,
            'drawrect_bs_on': 0,
            'drawcircle_on': 0,
            'drawtext_on': 0,
        }
        
        # 初始化虚拟桌面偏移量和几何信息
        self.virtual_desktop_offset_x = 0
        self.virtual_desktop_offset_y = 0
        self.virtual_desktop_width = 0
        self.virtual_desktop_height = 0
        self.virtual_desktop_min_x = 0
        self.virtual_desktop_min_y = 0
        self.virtual_desktop_max_x = 0
        self.virtual_desktop_max_y = 0
        
        # 为每个工具创建独立的设置
        # 初始化工具设置（从配置文件加载或使用默认值）
        self.tool_settings = self._load_tool_settings()
        
        self.pen_pointlist = []
        self.pen_drawn_points_count = 0  # 记录实际绘制的画笔点数
        self.drawtext_pointlist = []
        self.drawrect_pointlist = [[-2, -2], [-2, -2], 0]
        self.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
        self.drawcircle_pointlist = [[-2, -2], [-2, -2], 0]
        self.painter_tools = {
            'drawarrow_on': 0,
            'drawcircle_on': 0,
            'drawrect_bs_on': 0,
            'pen_on': 0,
            'highlight_on': 0,
            'drawtext_on': 0
        }

    def _build_highlighter_icon(self, icon_size: QSize = QSize(24, 24)) -> QIcon:
        """Create a simple highlighter icon using vector painting."""
        ratio = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        width = float(icon_size.width()) * ratio
        height = float(icon_size.height()) * ratio
        pixmap = QPixmap(int(max(1, round(width))), int(max(1, round(height))))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        painter.save()
        painter.translate(width * 0.55, height * 0.55)
        painter.rotate(-32)

        body_width = width * 0.62
        body_height = height * 0.28
        body_rect = QRectF(-body_width / 2.0, -body_height / 2.0, body_width, body_height)

        outline_pen = QPen(QColor(70, 70, 70))
        outline_pen.setWidthF(max(1.0, width * 0.035))
        painter.setPen(outline_pen)
        painter.setBrush(QColor(255, 236, 132))
        painter.drawRoundedRect(body_rect, body_height * 0.45, body_height * 0.45)

        nib_width = body_height * 0.95
        nib_rect = QRectF(body_rect.right() - nib_width, body_rect.top() - body_height * 0.1,
                          nib_width, body_height * 1.2)
        painter.setBrush(QColor(255, 210, 85))
        painter.drawRoundedRect(nib_rect, body_height * 0.4, body_height * 0.4)

        cap_rect = QRectF(body_rect.left() - body_height * 0.38, body_rect.top() + body_height * 0.15,
                          body_height * 0.5, body_height * 0.7)
        painter.setBrush(QColor(55, 55, 55))
        painter.drawRoundedRect(cap_rect, body_height * 0.25, body_height * 0.25)
        painter.restore()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 244, 120, 200))
        stroke_height = height * 0.2
        stroke_rect = QRectF(width * 0.22, height * 0.72, width * 0.56, stroke_height)
        painter.drawRoundedRect(stroke_rect, stroke_height * 0.4, stroke_height * 0.4)

        # 在右上角添加"荧"字
        painter.setPen(QPen(QColor(255, 100, 100), max(1.0, width * 0.03)))  # 红色字体
        painter.setBrush(QColor(255, 100, 100))
        
        # 设置字体 - 增大字体以更醒目
        font = QFont("Microsoft YaHei", int(max(10, width * 0.5)))
        font.setBold(True)
        painter.setFont(font)
        
        # 计算"荧"字的位置 - 右上角，增大区域
        text_rect = QRectF(width * 0.5, height * 0.0, width * 0.5, height * 0.5)
        painter.drawText(text_rect, Qt.AlignCenter, "荧")

        painter.end()
        return QIcon(pixmap)
    def init_slabel_ui(self):  # 初始化界面的参数

        self.shower.hide()
        # self.shower.setWindowOpacity(0.8)
        # if PLATFORM_SYS == "darwin":
        #     self.move(-QApplication.desktop().width(), -QApplication.desktop().height())

        self.setToolTip("左クリックで選択、右クリックで戻る")

        # 使用左右分布布局：左侧吸附其他按钮，右侧吸附钉图和确定按钮
        btn_width = 35
        btn_height = 35
        
        # 左侧按钮从0开始布局
        left_btn_x = 0
        
        # 长截图按钮放在最左边
        self.long_screenshot_btn.setGeometry(left_btn_x, 0, 40, btn_height)
        left_btn_x += 40
        
        # 保存按钮在长截图按钮右边
        self.save_botton.setGeometry(left_btn_x, 0, 40, btn_height)
        self.save_botton.setToolTip('ファイルに保存')
        left_btn_x += 40
        
        # OCR和翻译按钮已移除
        # self.ocr_botton.setGeometry(self.save_botton.x() + self.save_botton.width(), 0, 40, 35)
        # self.ocr_botton.setIcon(QIcon(":/OCR.png"))
        # self.ocr_botton.setToolTip('文字识别')
        # self.ocr_botton.clicked.connect(self.ocr)

        # self.translate_botton.setGeometry(self.ocr_botton.x() + self.ocr_botton.width(), 0, 40, 35)
        # self.translate_botton.setIcon(QIcon(":/tra.png"))
        # self.translate_botton.setToolTip('详细翻译')
        # self.translate_botton.clicked.connect(self.open_translate)

        # 复制按钮直接跟在保存按钮后面
        self.copy_botton.setGeometry(left_btn_x, 0, 40, btn_height)
        self.copy_botton.setIcon(QIcon(":/copy.png"))
        self.copy_botton.setToolTip('画像をコピー')
        self.copy_botton.clicked.connect(self.copy_pinned_image)
        self.copy_botton.hide()  # 默认隐藏,只在钉图模式下显示
        # left_btn_x += 40  # 由于复制按钮隐藏，不占用空间

        # 画笔工具
        self.pen.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width

        # 荧光笔工具
        self.highlighter.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width

        # 箭头工具
        self.drawarrow.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 矩形工具
        self.bs.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 圆形工具
        self.drawcircle.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 文字工具
        self.drawtext.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 颜色选择
        self.choice_clor_btn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 智能选区按钮已移到主界面设置，不占用工具栏空间
        # self.smartcursor_btn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        # left_btn_x += btn_width  # 不再为隐藏按钮分配空间
        
        # 上一步
        self.lastbtn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 下一步
        self.nextbtn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width

        # 计算工具栏总宽度，为右侧按钮预留空间
        right_buttons_width = 40 + 60  # 钉图按钮40px + 确定按钮60px
        toolbar_total_width = left_btn_x + 20 + right_buttons_width  # 左侧按钮 + 间隔 + 右侧按钮
        
        # 右侧按钮从右往左布局
        right_btn_x = toolbar_total_width - 60  # 确定按钮位置（从右边开始）
        
        # 确定按钮吸附最右边
        self.sure_btn.setGeometry(right_btn_x, 0, 60, 35)
        self.sure_btn.clicked.connect(self.handle_sure_btn_click)
        
        # 钉图按钮在确定按钮左边
        right_btn_x -= 40
        self.freeze_img_botton.setGeometry(right_btn_x, 0, 40, 35)

        # 调整工具栏大小
        self.botton_box.resize(toolbar_total_width, btn_height)
        self.botton_box.hide()

        # 初始化二级菜单的布局和控件
        self.init_paint_tools_menu()

        # 设置钉图按钮的属性
        self.freeze_img_botton.setIcon(QIcon(":/freeze.png"))
        self.freeze_img_botton.setToolTip('画像を画面に固定')
        self.freeze_img_botton.clicked.connect(self.freeze_img)
        
        # 设置长截图按钮的属性
        self.long_screenshot_btn.setText("📜")  # 使用emoji图标
        self.long_screenshot_btn.setToolTip('長スクリーンショット（スクロール）')
        self.long_screenshot_btn.clicked.connect(self.start_long_screenshot_mode)

        # 设置按钮工具提示和图标（这些按钮现在在底部导航栏中）
        self.pen.setToolTip('ペンツール')
        self.pen.setIcon(QIcon(":/pen.png"))
        self.pen.clicked.connect(self.change_pen_fun)

        self.highlighter.setToolTip('蛍光ペン')
        self.highlighter.setIcon(self._build_highlighter_icon())
        self.highlighter.setIconSize(QSize(24, 24))
        self.highlighter.clicked.connect(self.change_highlighter_fun)

        self.drawarrow.setToolTip('矢印を描画')
        self.drawarrow.setIcon(QIcon(":/arrowicon.png"))
        self.drawarrow.clicked.connect(self.draw_arrow_fun)
        
        self.bs.setToolTip('矩形を描画')
        self.bs.setIcon(QIcon(":/rect.png"))
        self.bs.clicked.connect(self.change_bs_fun)
        
        self.drawcircle.setToolTip('円を描画')
        self.drawcircle.setIcon(QIcon(":/circle.png"))
        self.drawcircle.clicked.connect(self.drawcircle_fun)
        
        self.drawtext.setToolTip('テキストを描画')
        self.drawtext.setIcon(QIcon(":/texticon.png"))
        self.drawtext.clicked.connect(self.drawtext_fun)
        
        self.choice_clor_btn.setToolTip('ペンの色を選択、クリックで詳細選択')
        self.choice_clor_btn.setIcon(QIcon(":/yst.png"))
        self.choice_clor_btn.clicked.connect(self.get_color)
        self.choice_clor_btn.hoversignal.connect(self.Color_hoveraction)

        # 智能选择功能已移至主界面设置，不再需要工具栏按钮
        # self.smartcursor_btn.setToolTip("スマート選択")
        # self.smartcursor_btn.setIcon(QIcon(":/smartcursor.png"))
        # self.smartcursor_btn.clicked.connect(self.change_smartcursor)

        self.lastbtn.setToolTip("元に戻す Ctrl+Z")
        self.lastbtn.setIcon(QIcon(":/last.png"))
        self.lastbtn.clicked.connect(self.last_step)

        self.nextbtn.setToolTip("やり直し Ctrl+Y")
        self.nextbtn.setIcon(QIcon(":/next.png"))
        self.nextbtn.clicked.connect(self.next_step)

        # 保留材质选择按钮在painter_box中（已删除材质功能）

        tipsfont = QFont("", 35)
        # tipsfont.setBold(True)
        self.Tipsshower.setFont(tipsfont)
        self.choice_clor_btn.setStyleSheet('background-color:rgb(255,0,0);')
        # 按钮样式应该反映智能选区的默认关闭状态
        if self.settings.value("screenshot/smartcursor", False, type=bool):  # 默认改为False
            self.smartcursor_btn.setStyleSheet("background-color:rgb(50,50,50);")

    def Color_hoveraction(self, hover):  # 鼠标滑过选色按钮时触发的
        if hover:
            try:
                self.closenomalcolorboxtimer.stop()
                self.nomalcolorbox.show()
                print("nomalcolorbox show")
            except AttributeError:
                self.nomalcolorbox = HoverGroupbox(self)
                self.closenomalcolorboxtimer = QTimer(self)
                btnscolors = [Qt.red, Qt.darkRed, Qt.green, Qt.darkGreen, Qt.blue, Qt.darkBlue, Qt.yellow,
                              Qt.darkYellow,
                              Qt.darkCyan, Qt.darkMagenta, Qt.white, QColor(200, 200, 200), Qt.gray, Qt.darkGray,
                              Qt.black,
                              QColor(50, 50, 50)]
                y1 = 0
                y2 = 30
                d = 30
                for i in range((len(btnscolors) + 1) // 2):
                    btn1 = ColorButton(btnscolors[2 * i], self.nomalcolorbox)
                    btn1.resize(d, d)
                    btn1.select_color_signal.connect(self.selectnomal_color)
                    btn1.move(5 + i * d, y1)
                    if len(btnscolors) > 2 * i + 1:
                        btn2 = ColorButton(btnscolors[2 * i + 1], self.nomalcolorbox)
                        btn2.resize(d, d)
                        btn2.select_color_signal.connect(self.selectnomal_color)
                        btn2.move(5 + i * d, y2)
                self.nomalcolorbox.setGeometry(
                    self.botton_box.x() + self.choice_clor_btn.x() + self.choice_clor_btn.width() + 1,
                    self.botton_box.y() - y2 * 2 - 5,
                    (len(btnscolors) // 2 + 1) * 50 + 10, y2 * 2)
            except:
                print(sys.exc_info(), 1150)

            self.nomalcolorbox.hoversignal.connect(self.closenomalcolorboxsignalhandle)
            self.nomalcolorbox.show()
            self.nomalcolorbox.raise_()

            self.closenomalcolorboxtimer.timeout.connect(self.closenomalcolorbox)
            self.closenomalcolorboxtimer.start(2000)

            # self.refresh_hideclosenomalsignal()
        # else:

    def closenomalcolorboxsignalhandle(self, s):  # 关闭常见颜色浮窗的函数
        if s:
            try:
                self.closenomalcolorboxtimer.stop()
            except:
                print(sys.exc_info(), 1162)
        else:
            print("离开box信号", s)

            self.closenomalcolorboxtimer.start(1000)

    def closenomalcolorbox(self):
        try:
            if hasattr(self, 'nomalcolorbox') and self.nomalcolorbox:
                self.nomalcolorbox.hide()
                self.nomalcolorbox = None
            if hasattr(self, 'closenomalcolorboxtimer'):
                self.closenomalcolorboxtimer.stop()
        except:
            print(sys.exc_info())

    def selectnomal_color(self, color):
        # print(color)
        self.get_color(QColor(color))
        # self.nomalcolorbox = None

    def get_color(self, color: QColor = None):  # 选择颜色
        if type(color) is not QColor:
            # 移除了提示消息
            try:
                self.nomalcolorbox.hide()
            except:
                print(sys.exc_info())
            colordialog = QColorDialog(self)
            colordialog.setCurrentColor(self.pencolor)
            colordialog.setOption(QColorDialog.ShowAlphaChannel)
            
            # 智能定位颜色对话框
            if hasattr(self, 'botton_box') and self.botton_box.isVisible():
                dialog_width = 640  # 颜色对话框的大概宽度
                dialog_height = 480  # 颜色对话框的大概高度
                
                # 检查是否在钉图模式下（工具栏是独立窗口）
                if hasattr(self, 'mode') and self.mode == "pinned":
                    # 钉图模式：工具栏是独立窗口，使用全局坐标
                    # 获取颜色选择按钮的全局位置
                    color_btn_global_pos = self.choice_clor_btn.mapToGlobal(QPoint(0, 0))
                    color_btn_x = color_btn_global_pos.x()
                    color_btn_y = color_btn_global_pos.y()
                    color_btn_width = self.choice_clor_btn.width()
                    color_btn_height = self.choice_clor_btn.height()
                    
                    # 获取当前屏幕信息
                    screen = QApplication.screenAt(QPoint(color_btn_x, color_btn_y))
                    if screen is None:
                        screen = QApplication.primaryScreen()
                    screen_rect = screen.geometry()
                    
                    # 优先尝试显示在颜色选择按钮下方
                    below_y = color_btn_y + color_btn_height + 5
                    
                    if below_y + dialog_height <= screen_rect.bottom():
                        # 下方有足够空间，对齐到按钮左边
                        dialog_x = max(screen_rect.left(), min(color_btn_x, screen_rect.right() - dialog_width))
                        dialog_y = below_y
                    else:
                        # 下方空间不足，显示在按钮上方
                        above_y = color_btn_y - dialog_height - 5
                        if above_y >= screen_rect.top():
                            dialog_x = max(screen_rect.left(), min(color_btn_x, screen_rect.right() - dialog_width))
                            dialog_y = above_y
                        else:
                            # 上下都不够，显示在按钮右边
                            right_x = color_btn_x + color_btn_width + 5
                            if right_x + dialog_width <= screen_rect.right():
                                dialog_x = right_x
                                dialog_y = max(screen_rect.top(), min(color_btn_y, screen_rect.bottom() - dialog_height))
                            else:
                                # 右边也不够，居中显示在屏幕上
                                dialog_x = screen_rect.left() + (screen_rect.width() - dialog_width) // 2
                                dialog_y = screen_rect.top() + (screen_rect.height() - dialog_height) // 2
                    
                    colordialog.move(dialog_x, dialog_y)
                else:
                    # 截图模式：工具栏是子组件，使用相对坐标
                    below_y = self.botton_box.y() + self.botton_box.height() + 10
                    
                    if below_y + dialog_height <= self.height():
                        # 下方有足够空间
                        dialog_x = max(0, min(self.botton_box.x(), self.width() - dialog_width))
                        dialog_y = below_y
                    else:
                        # 下方空间不足，显示在上方
                        above_y = self.botton_box.y() - dialog_height - 10
                        if above_y >= 0:
                            dialog_x = max(0, min(self.botton_box.x(), self.width() - dialog_width))
                            dialog_y = above_y
                        else:
                            # 上下都不够，居中显示
                            dialog_x = (self.width() - dialog_width) // 2
                            dialog_y = (self.height() - dialog_height) // 2
                    
                    # 转换为全局坐标
                    global_pos = self.mapToGlobal(QPoint(dialog_x, dialog_y))
                    colordialog.move(global_pos)
            
            colordialog.exec()
            new_color = colordialog.currentColor()
            # 保持当前的透明度设置，不使用新颜色的默认透明度
            current_alpha = self.alpha if hasattr(self, 'alpha') else self.alpha_slider.value()
            new_color.setAlpha(current_alpha)
            self.pencolor = new_color
        else:
            # 对于预设颜色，也保持当前透明度
            current_alpha = self.alpha if hasattr(self, 'alpha') else self.alpha_slider.value()
            color.setAlpha(current_alpha)
            self.pencolor = color
        
        # 不更新alpha_slider的值，保持用户设置的透明度
        # self.alpha_slider.setValue(self.pencolor.alpha())  # 注释掉这行

        self.text_box.setTextColor(self.pencolor)
        self.choice_clor_btn.setStyleSheet('background-color:{0};'.format(self.pencolor.name()))
        
        # 保存当前工具的颜色设置到配置文件
        current_tool = self.get_current_tool()
        if current_tool and hasattr(self, 'tool_settings') and current_tool in self.tool_settings:
            color_value = self.pencolor.name()  # 获取颜色的十六进制字符串
            self.settings.setValue(f'tools/{current_tool}/color', color_value)
            print(f"💾 [配置保存] 工具 {current_tool} 颜色设置已保存: {color_value}")

    def change_smartcursor(self):
        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
            # 钉图模式下，智能选区按钮变成置顶功能
            self.toggle_pinned_window_ontop()
        else:
            # 正常截图模式下的智能选区功能
            self.settings.setValue("screenshot/smartcursor",
                                   not self.settings.value("screenshot/smartcursor", False, type=bool))  # 默认改为False
            if self.settings.value("screenshot/smartcursor", False, type=bool):  # 默认改为False
                self.smartcursor_btn.setStyleSheet("background-color:rgb(50,50,50);")
                self.smartcursor_on = True
                # 启用智能选区时立即初始化
                if not self._smart_selection_initialized:
                    self._lazy_init_smart_selection()
                # 移除了智能选区开启提示
            else:
                self.smartcursor_on = False
                self.smartcursor_btn.setStyleSheet("")
                # 移除了智能选区关闭提示
    
    def toggle_pinned_window_ontop(self):
        """切换钉图窗口的置顶状态"""
        if hasattr(self, 'current_pinned_window') and self.current_pinned_window:
            self.current_pinned_window.change_ontop()
            if self.current_pinned_window.on_top:
                self.smartcursor_btn.setStyleSheet("background-color:rgb(50,50,50);")
                # 移除了钉图置顶开启提示
            else:
                self.smartcursor_btn.setStyleSheet("")
                # 移除了钉图置顶关闭提示
    
    def _ensure_text_box_focus(self):
        """确保文字框获得焦点（延迟检查）"""
        try:
            if hasattr(self, 'text_box') and self.text_box.isVisible():
                if not self.text_box.hasFocus():
                    print("文字框失去焦点，重新设置焦点")
                    self.text_box.setFocus(Qt.OtherFocusReason)
                    self.text_box.raise_()
                    self.text_box.activateWindow()
                else:
                    print("文字框焦点正常")
        except Exception as e:
            print(f"检查文字框焦点时出错: {e}")
    
    def _reset_text_box_completely(self):
        """完全重置文字输入框状态，但在重置前先保存当前正在输入的文字"""
        try:
            if hasattr(self, 'text_box') and self.text_box.isVisible():
                print("🔄 检查文字输入框是否需要保存")
                
                # 检查是否有正在输入的文字内容
                current_text = self.text_box.toPlainText().strip()
                
                if current_text:
                    print(f"💾 发现正在输入的文字内容: '{current_text}'，先保存后再重置")
                    
                    # 触发文字保存：设置paint标志并触发绘制
                    self.text_box.paint = True
                    
                    # 触发文字绘制处理 - 改进的保存逻辑
                    try:
                        from jietuba_text_drawer import UnifiedTextDrawer
                        
                        # 在钉图模式下处理
                        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
                            if hasattr(self.current_pinned_window, 'paintlayer') and self.current_pinned_window.paintlayer:
                                paint_pixmap = self.current_pinned_window.paintlayer.pixmap()
                                if paint_pixmap:
                                    painter = QPainter(paint_pixmap)
                                    painter.setRenderHint(QPainter.Antialiasing)
                                    success = UnifiedTextDrawer.process_text_drawing(self, painter, self.text_box)
                                    painter.end()
                                    
                                    if success:
                                        self.current_pinned_window.paintlayer.setPixmap(paint_pixmap)
                                        print("钉图模式: 文字已保存到钉图paintlayer")
                                    else:
                                        print("钉图模式: 文字保存可能失败")
                                else:
                                    print("钉图模式: paintlayer pixmap无效")
                        else:
                            # 正常截图模式处理
                            if hasattr(self, 'paintlayer') and self.paintlayer:
                                paint_pixmap = self.paintlayer.pixmap()
                                if paint_pixmap:
                                    painter = QPainter(paint_pixmap)
                                    painter.setRenderHint(QPainter.Antialiasing)
                                    success = UnifiedTextDrawer.process_text_drawing(self, painter, self.text_box)
                                    painter.end()
                                    
                                    if success:
                                        self.paintlayer.setPixmap(paint_pixmap)
                                        print("正常模式: 文字已保存到paintlayer")
                                    else:
                                        print("正常模式: 文字保存可能失败")
                                else:
                                    print("正常模式: paintlayer pixmap无效")
                        
                        # 强制刷新显示
                        self.update()
                        QApplication.processEvents()
                        print("✅ 文字已保存到画布")
                        
                    except Exception as save_error:
                        print(f"保存文字时出错: {save_error}")
                else:
                    print("🔄 没有文字内容需要保存，直接重置")
                
                # 现在进行重置操作
                print("🔄 开始重置文字输入框状态")
                
                # 隐藏并清空
                self.text_box.hide()
                self.text_box.clear()
                self.text_box.paint = False
                
                # 清除锚点信息
                if hasattr(self.text_box, '_anchor_base'):
                    delattr(self.text_box, '_anchor_base')
                
                # 重置父窗口关系和窗口属性
                try:
                    self.text_box.setParent(self)
                    self.text_box.setWindowFlags(Qt.Widget)
                    self.text_box.setAttribute(Qt.WA_TranslucentBackground, False)
                except Exception as e:
                    print(f"重置窗口属性时出错: {e}")
                
                print("✅ 文字输入框状态重置完成")
                
        except Exception as e:
            print(f"重置文字输入框时出错: {e}")

    def setoriginalpix(self):
        self.change_tools_fun("")
        self.setCursor(Qt.ArrowCursor)
        self.screen_shot(self.originalPix)

        # 移除了清除所有修改提示

    def drawcircle_fun(self):
        if self.painter_tools['drawcircle_on']:
            # 关闭工具前先保存当前文字输入（如果有的话）
            self._reset_text_box_completely()
            self.painter_tools['drawcircle_on'] = 0
            self.drawcircle.setStyleSheet('')
            # 强制隐藏二级菜单（因为工具被关闭）
            self.paint_tools_menu.hide()
        else:
            self.change_tools_fun('drawcircle_on')
            self.apply_tool_settings('drawcircle_on')
            self.drawcircle.setStyleSheet('background-color:rgb(50,50,50)')
            # 移除了圆形框工具提示
            # 激活绘画工具时确保工具栏可见
            if hasattr(self, 'botton_box'):
                self.botton_box.show()
            self.show_paint_tools_menu()

    def draw_arrow_fun(self):
        if self.painter_tools['drawarrow_on']:
            # 关闭工具前先保存当前文字输入（如果有的话）
            self._reset_text_box_completely()
            self.painter_tools['drawarrow_on'] = 0
            self.drawarrow.setStyleSheet('')
            # 强制隐藏二级菜单（因为工具被关闭）
            self.paint_tools_menu.hide()
        else:
            self.change_tools_fun('drawarrow_on')
            self.apply_tool_settings('drawarrow_on')
            self.drawarrow.setStyleSheet('background-color:rgb(50,50,50)')
            self.setCursor(QCursor(QPixmap(":/arrowicon.png").scaled(32, 32, Qt.KeepAspectRatio), 0, 32))
            # 移除了箭头工具提示
            # 激活绘画工具时确保工具栏可见
            if hasattr(self, 'botton_box'):
                self.botton_box.show()
            self.show_paint_tools_menu()

    def drawtext_fun(self):
        if self.painter_tools['drawtext_on']:
            # 关闭文字工具前，先保存当前正在输入的文字
            print("🎯 [文字工具] 用户点击关闭文字工具，检查是否需要保存当前输入")
            self._reset_text_box_completely()  # 这个方法已经包含了保存逻辑
            
            # 然后关闭工具
            self.painter_tools['drawtext_on'] = 0
            self.drawtext.setStyleSheet('')
            # 强制隐藏二级菜单（因为工具被关闭）
            self.paint_tools_menu.hide()
            print("✅ [文字工具] 文字工具已关闭")
        else:
            self.change_tools_fun('drawtext_on')
            self.apply_tool_settings('drawtext_on')
            self.drawtext.setStyleSheet('background-color:rgb(50,50,50)')
            self.setCursor(QCursor(QPixmap(":/texticon.png").scaled(16, 16, Qt.KeepAspectRatio), 0, 0))
            # 移除了绘制文本提示
            # 激活绘画工具时确保工具栏可见
            if hasattr(self, 'botton_box'):
                self.botton_box.show()
            self.show_paint_tools_menu()

    def init_paint_tools_menu(self):
        """初始化绘画工具二级菜单"""
        menu_width = 385  # 增加宽度以容纳大型emoji按钮
        menu_height = 60  # 缩小高度
        
        # 设置二级菜单的大小和样式
        self.paint_tools_menu.resize(menu_width, menu_height)
        
        # 布局调节控件（更紧凑的布局）
        # 画笔大小滑动条
        self.size_slider.setGeometry(5, 25, 80, 18)  # 缩小尺寸
        self.size_slider.setOrientation(Qt.Horizontal)
        self.size_slider.setToolTip('ペンのサイズを設定、マウスホイールでも調整可能')
        self.size_slider.valueChanged.connect(self.change_size_fun)
        self.size_slider.setMaximum(99)
        self.size_slider.setValue(5)
        self.size_slider.setMinimum(1)
        
        self.sizetextlabel.setText("大小")
        self.sizetextlabel.setGeometry(5, 5, 30, 16)  # 缩小并重新定位
        self.sizetextlabel.setStyleSheet('color: rgb(255,255,255); font-size: 12px;')
        
        self.size_slider_label.setGeometry(90, 25, 25, 18)  # 调整位置
        self.size_slider_label.setStyleSheet('color: rgb(255,255,255); font-size: 12px;')
        self.size_slider_label.setText("5")
        
        # 透明度滑动条
        self.alpha_slider.setGeometry(130, 25, 80, 18)  # 缩小并重新定位
        self.alpha_slider.setOrientation(Qt.Horizontal)
        self.alpha_slider.setToolTip('ペンの透明度を設定、Ctrl+ホイールでも調整可能')
        self.alpha_slider.valueChanged.connect(self.change_alpha_fun)
        self.alpha_slider.setMaximum(255)
        self.alpha_slider.setValue(255)
        self.alpha_slider.setMinimum(1)
        
        self.alphatextlabel.setText("透明度")
        self.alphatextlabel.setGeometry(130, 5, 50, 16)  # 缩小并重新定位
        self.alphatextlabel.setStyleSheet('color: rgb(255,255,255); font-size: 12px;')
        
        self.alpha_slider_label.setGeometry(215, 25, 30, 18)  # 调整位置
        self.alpha_slider_label.setStyleSheet('color: rgb(255,255,255); font-size: 12px;')
        self.alpha_slider_label.setText("255")
        
        # 设置3个预设按钮 - 水平排列，大emoji按钮设计，突出各自特性
        preset_btn_size = 40   # 正方形按钮，更大更容易点击
        preset_start_x = 250   # 起始位置
        preset_y = 10          # 垂直居中位置
        preset_spacing = 45    # 按钮间距
        
        # 预设1: 细笔，不透明，黄绿色调
        self.preset_btn_1.setGeometry(preset_start_x, preset_y, preset_btn_size, preset_btn_size)
        self.preset_btn_1.setText("●")  # 小圆点表示细笔
        self.preset_btn_1.setToolTip('細ペン\n大きさ10 透明度255\n不透明の細いペン')
        self.preset_btn_1.clicked.connect(self.apply_preset_1)
        
        # 预设2: 普通笔 - 中等粗细，不透明，蓝色调
        self.preset_btn_2.setGeometry(preset_start_x + preset_spacing, preset_y, preset_btn_size, preset_btn_size)
        self.preset_btn_2.setText("●")  # 中等圆点表示普通笔
        self.preset_btn_2.setToolTip('普通ペン\n大きさ30 透明度255\n標準的なペン')
        self.preset_btn_2.clicked.connect(self.apply_preset_2)
        
        # 预设3: 粗笔 - 粗画笔，完全不透明，红色调
        self.preset_btn_3.setGeometry(preset_start_x + preset_spacing * 2, preset_y, preset_btn_size, preset_btn_size)
        self.preset_btn_3.setText("●")  # 大圆点表示粗笔
        self.preset_btn_3.setToolTip('極太ペン\n大きさ60 透明度255\n太い描画ペン')
        self.preset_btn_3.clicked.connect(self.apply_preset_3)
        
        # 设置各个预设按钮的统一样式，只通过圆点大小区分
        # 小圆点样式 - 细笔
        small_dot_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(100, 149, 237, 180), stop:1 rgba(70, 130, 180, 180));
                color: rgb(255, 255, 255);
                border: 3px solid #4169E1;
                border-radius: 8px;
                font-size: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(100, 149, 237, 220), stop:1 rgba(70, 130, 180, 220));
                border: 3px solid #6495ED;
                transform: scale(1.05);
            }
            QPushButton:pressed {
                background: rgba(65, 105, 225, 250);
                border: 3px solid #0000FF;
                transform: scale(0.95);
            }
        """
        
        # 中等圆点样式 - 普通笔
        medium_dot_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(100, 149, 237, 180), stop:1 rgba(70, 130, 180, 180));
                color: rgb(255, 255, 255);
                border: 3px solid #4169E1;
                border-radius: 8px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(100, 149, 237, 220), stop:1 rgba(70, 130, 180, 220));
                border: 3px solid #6495ED;
                transform: scale(1.05);
            }
            QPushButton:pressed {
                background: rgba(65, 105, 225, 250);
                border: 3px solid #0000FF;
                transform: scale(0.95);
            }
        """
        
        # 大圆点样式 - 粗笔
        large_dot_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(100, 149, 237, 180), stop:1 rgba(70, 130, 180, 180));
                color: rgb(255, 255, 255);
                border: 3px solid #4169E1;
                border-radius: 8px;
                font-size: 32px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(100, 149, 237, 220), stop:1 rgba(70, 130, 180, 220));
                border: 3px solid #6495ED;
                transform: scale(1.05);
            }
            QPushButton:pressed {
                background: rgba(178, 34, 34, 250);
                border: 3px solid #B22222;
                transform: scale(0.95);
            }
        """
        
        self.preset_btn_1.setStyleSheet(small_dot_style)
        self.preset_btn_2.setStyleSheet(medium_dot_style)
        self.preset_btn_3.setStyleSheet(large_dot_style)
        
        # 颜色选择按钮已经在底部导航栏中了
        
    def show_paint_tools_menu(self):
        """显示绘画工具二级菜单"""
        if hasattr(self, 'botton_box') and self.botton_box.isVisible():
            # 钉图模式：使用全局坐标与目标屏幕边界
            if hasattr(self, 'mode') and self.mode == 'pinned':
                try:
                    toolbar_pos = self.botton_box.pos()
                    screen = QApplication.screenAt(toolbar_pos)
                    if screen is None:
                        screen = QApplication.primaryScreen()
                    sx, sy, sw, sh = screen.geometry().getRect()

                    menu_x = self.botton_box.x()
                    menu_y_below = self.botton_box.y() + self.botton_box.height() + 5
                    menu_y_above = self.botton_box.y() - self.paint_tools_menu.height() - 5

                    if menu_y_below + self.paint_tools_menu.height() <= sy + sh:
                        menu_y = menu_y_below
                    elif menu_y_above >= sy:
                        menu_y = menu_y_above
                    else:
                        menu_y = min(max(sy, self.botton_box.y()), sy + sh - self.paint_tools_menu.height())

                    if menu_x + self.paint_tools_menu.width() > sx + sw:
                        menu_x = sx + sw - self.paint_tools_menu.width() - 5
                    if menu_x < sx + 5:
                        menu_x = sx + 5

                    self.paint_tools_menu.move(menu_x, menu_y)
                    self.paint_tools_menu.show()
                    self.paint_tools_menu.raise_()
                    return
                except Exception as _e:
                    print(f"⚠️ 钉图模式显示画笔菜单失败，退回普通逻辑: {_e}")

            # 截图模式：使用应用窗口坐标
            menu_x = self.botton_box.x()
            
            # 优先尝试显示在工具栏下方
            menu_y_below = self.botton_box.y() + self.botton_box.height() + 5
            menu_y_above = self.botton_box.y() - self.paint_tools_menu.height() - 5
            
            # 检查下方是否有足够空间
            screen_height = QApplication.desktop().height()
            if menu_y_below + self.paint_tools_menu.height() + 20 <= screen_height:
                # 下方有足够空间，优先显示在下方
                menu_y = menu_y_below
            else:
                # 下方空间不足，显示在上方
                menu_y = menu_y_above
                
            # 确保不会超出屏幕左右边界
            screen_width = QApplication.desktop().width()
            if menu_x + self.paint_tools_menu.width() > screen_width:
                menu_x = screen_width - self.paint_tools_menu.width() - 5
            if menu_x < 5:
                menu_x = 5
                
            self.paint_tools_menu.move(menu_x, menu_y)
            self.paint_tools_menu.show()
            self.paint_tools_menu.raise_()
            
        # 控制预设按钮的显示 - 只有画笔工具时才显示
        self.update_preset_buttons_visibility()
    
    def update_preset_buttons_visibility(self):
        """根据当前激活的工具更新预设按钮的显示状态"""
        current_tool = self.get_current_tool()
        is_pen_tool = current_tool in ('pen_on', 'highlight_on')
        
        # 只有画笔工具时才显示预设按钮
        if hasattr(self, 'preset_btn_1'):
            self.preset_btn_1.setVisible(is_pen_tool)
        if hasattr(self, 'preset_btn_2'):
            self.preset_btn_2.setVisible(is_pen_tool)
        if hasattr(self, 'preset_btn_3'):
            self.preset_btn_3.setVisible(is_pen_tool)
        
        if is_pen_tool:
            print("🎨 [画笔工具] 显示预设按钮")
        else:
            print(f"🎨 [其他工具] 隐藏预设按钮 (当前工具: {current_tool})")
    
    def hide_paint_tools_menu(self):
        """隐藏绘画工具二级菜单"""
        # 检查是否有绘画工具激活，如果有则不隐藏二级菜单
        if hasattr(self, 'painter_tools') and 1 in self.painter_tools.values():
            print("绘画工具激活中，不隐藏二级菜单")
            return
        self.paint_tools_menu.hide()
        # 隐藏菜单时也隐藏预设按钮
        self.update_preset_buttons_visibility()

    def change_pen_fun(self):
        if self.painter_tools['pen_on']:
            # 关闭工具前先保存当前文字输入（如果有的话）
            self._reset_text_box_completely()
            self.painter_tools['pen_on'] = 0
            self.pen.setStyleSheet('')
            # 强制隐藏二级菜单（因为工具被关闭）
            self.paint_tools_menu.hide()
        else:
            self.change_tools_fun('pen_on')
            self.pen.setStyleSheet('background-color:rgb(50,50,50)')
            self.apply_tool_settings('pen_on')  # 应用画笔的设置
            # 移除了画笔提示
            self.setCursor(QCursor(QPixmap(":/pen.png").scaled(32, 32, Qt.KeepAspectRatio), 0, 32))
            # 激活绘画工具时确保工具栏可见
            if hasattr(self, 'botton_box'):
                self.botton_box.show()
            self.show_paint_tools_menu()

    def change_highlighter_fun(self):
        if self.painter_tools['highlight_on']:
            self._reset_text_box_completely()
            self.painter_tools['highlight_on'] = 0
            self.highlighter.setStyleSheet('')
            self.paint_tools_menu.hide()
        else:
            self.change_tools_fun('highlight_on')
            self.highlighter.setStyleSheet('background-color:rgb(50,50,50)')
            # 应用荧光笔设置
            self.apply_tool_settings('highlight_on')
            # 确保荧光笔使用正确的黄色 - 强制设置
            if hasattr(self, 'tool_settings') and 'highlight_on' in self.tool_settings:
                highlight_color = self.tool_settings['highlight_on']['color']
                self.pencolor = QColor(highlight_color)
                self.pencolor.setAlpha(self.alpha)
                # 更新颜色按钮显示
                if hasattr(self, 'choice_clor_btn'):
                    self.choice_clor_btn.setStyleSheet('background-color:{0};'.format(self.pencolor.name()))
                print(f"🟡 [荧光笔] 强制应用黄色: {highlight_color}")
            
            self.setCursor(QCursor(QPixmap(":/pen.png").scaled(32, 32, Qt.KeepAspectRatio), 0, 32))
            if hasattr(self, 'botton_box'):
                self.botton_box.show()
            self.show_paint_tools_menu()

    def change_size_fun(self):
        self.size_slider_label.setText(str(self.size_slider.value()))
        self.tool_width = self.size_slider.value()
        # 保存当前工具的大小设置到内存和配置文件
        current_tool = self.get_current_tool()
        if current_tool and hasattr(self, 'tool_settings') and current_tool in self.tool_settings:
            self.tool_settings[current_tool]['size'] = self.tool_width
            # 保存到配置文件
            self.settings.setValue(f'tools/{current_tool}/size', self.tool_width)
            print(f"💾 [配置保存] 工具 {current_tool} 尺寸设置已保存: {self.tool_width}")

    def change_alpha_fun(self):
        self.alpha_slider_label.setText(str(self.alpha_slider.value()))
        self.alpha = self.alpha_slider.value()
        self.pencolor.setAlpha(self.alpha)
        # 保存当前工具的透明度设置到内存和配置文件
        current_tool = self.get_current_tool()
        if current_tool and hasattr(self, 'tool_settings') and current_tool in self.tool_settings:
            self.tool_settings[current_tool]['alpha'] = self.alpha
            # 保存到配置文件
            self.settings.setValue(f'tools/{current_tool}/alpha', self.alpha)
            print(f"💾 [配置保存] 工具 {current_tool} 透明度设置已保存: {self.alpha}")
    
    def apply_preset_1(self):
        """应用预设1：細笔，半透明（大小10，透明度255）"""
        self.apply_preset_settings(10, 255)
        print("🎯 [预设切换] 应用预设1: 细画笔 (大小10, 透明度255)")

    def apply_preset_2(self):
        """应用预设2：普通笔，中等透明度（大小40，透明度255）"""
        self.apply_preset_settings(30, 255)
        print("🎯 [预设切换] 应用预设2: 中画笔 (大小30, 透明度255)")

    def apply_preset_3(self):
        """应用预设3：粗画笔，完全不透明（大小60，透明度255）"""
        self.apply_preset_settings(60, 255)
        print("🎯 [预设切换] 应用预设3: 粗画笔 (大小60, 透明度255)")

    def apply_preset_settings(self, size, alpha):
        """应用预设的尺寸和透明度设置"""
        # 更新内部参数
        self.tool_width = size
        self.alpha = alpha
        self.pencolor.setAlpha(self.alpha)
        
        # 更新滑动条和标签显示
        self.size_slider.setValue(size)
        self.alpha_slider.setValue(alpha)
        self.size_slider_label.setText(str(size))
        self.alpha_slider_label.setText(str(alpha))
        
        # 保存当前工具的设置到内存和配置文件
        current_tool = self.get_current_tool()
        if current_tool and hasattr(self, 'tool_settings') and current_tool in self.tool_settings:
            self.tool_settings[current_tool]['size'] = self.tool_width
            self.tool_settings[current_tool]['alpha'] = self.alpha
            # 保存到配置文件
            self.settings.setValue(f'tools/{current_tool}/size', self.tool_width)
            self.settings.setValue(f'tools/{current_tool}/alpha', self.alpha)
    
    def get_current_tool(self):
        """获取当前激活的工具"""
        if not hasattr(self, 'painter_tools'):
            return None
        for tool, active in self.painter_tools.items():
            if active:
                return tool
        return None
    
    def _is_brush_tool_active(self):
        """画笔/荧光笔是否激活"""
        if not hasattr(self, 'painter_tools'):
            return False
        return bool(self.painter_tools.get('pen_on', 0) or self.painter_tools.get('highlight_on', 0))
    
    def _load_tool_settings(self):
        """从配置文件加载工具设置"""
        # 默认工具配置
        default_settings = {
            'pen_on': {'size': 3, 'alpha': 255, 'color': '#ff0000'},            # 画笔：细一些，完全不透明，红色
            'highlight_on': {'size': 30, 'alpha': 255, 'color': "#e1ffd3ff"},      # 荧光笔：更粗，完全不透明，绿色
            'drawarrow_on': {'size': 2, 'alpha': 255, 'color': '#ff0000'},      # 箭头：更细，完全不透明，红色
            'drawrect_bs_on': {'size': 2, 'alpha': 255, 'color': '#ff0000'},    # 矩形：细边框，半透明，红色
            'drawcircle_on': {'size': 2, 'alpha': 255, 'color': '#ff0000'},     # 圆形：细边框，半透明，红色
            'drawtext_on': {'size': 16, 'alpha': 255, 'color': '#ff0000'},      # 文字：16像素字体，完全不透明，红色
        }
        
        # 从配置文件读取，如果没有则使用默认值
        loaded_settings = {}
        for tool_name, default_config in default_settings.items():
            loaded_settings[tool_name] = {
                'size': self.settings.value(f'tools/{tool_name}/size', default_config['size'], type=int),
                'alpha': self.settings.value(f'tools/{tool_name}/alpha', default_config['alpha'], type=int),
                'color': self.settings.value(f'tools/{tool_name}/color', default_config['color'], type=str)
            }
        
        print(f"🔧 [配置加载] 已加载工具设置: {loaded_settings}")
        return loaded_settings
    
    def _save_current_tool_settings(self):
        """保存当前工具的设置到配置文件"""
        current_tool = self.get_current_tool()
        if current_tool and hasattr(self, 'tool_settings') and current_tool in self.tool_settings:
            # 保存到内存中的设置
            self.tool_settings[current_tool]['size'] = self.tool_width
            self.tool_settings[current_tool]['alpha'] = self.alpha
            
            # 保存到配置文件
            self.settings.setValue(f'tools/{current_tool}/size', self.tool_width)
            self.settings.setValue(f'tools/{current_tool}/alpha', self.alpha)
            
            print(f"💾 [配置保存] 工具 {current_tool} 设置已保存: size={self.tool_width}, alpha={self.alpha}")

    def apply_tool_settings(self, tool_name):
        """应用指定工具的设置"""
        if hasattr(self, 'tool_settings') and tool_name in self.tool_settings:
            settings = self.tool_settings[tool_name]
            # 更新工具参数
            self.tool_width = settings['size']
            self.alpha = settings['alpha']
            
            # 更新颜色（如果有保存的颜色配置）
            if 'color' in settings:
                self.pencolor = QColor(settings['color'])
                self.pencolor.setAlpha(self.alpha)
                # 更新颜色按钮显示
                if hasattr(self, 'choice_clor_btn'):
                    self.choice_clor_btn.setStyleSheet('background-color:{0};'.format(self.pencolor.name()))
                # 更新文本框颜色
                if hasattr(self, 'text_box'):
                    self.text_box.setTextColor(self.pencolor)
            else:
                self.pencolor.setAlpha(self.alpha)
            
            # 更新滑动条显示
            if hasattr(self, 'size_slider'):
                self.size_slider.setValue(self.tool_width)
            if hasattr(self, 'alpha_slider'):
                self.alpha_slider.setValue(self.alpha)
            if hasattr(self, 'size_slider_label'):
                self.size_slider_label.setText(str(self.tool_width))
            if hasattr(self, 'alpha_slider_label'):
                self.alpha_slider_label.setText(str(self.alpha))
            
            print(f"🔧 [工具设置] 已应用工具 {tool_name} 设置: size={self.tool_width}, alpha={self.alpha}, color={self.pencolor.name()}")

    # 钉图窗口工具栏支持方法
    def show_toolbar_for_pinned_window(self, pinned_window):
        """为钉图窗口显示工具栏"""
        if hasattr(self, 'botton_box'):
            # 保存二级菜单的当前状态
            menu_was_visible = False
            if hasattr(self, 'paint_tools_menu') and self.paint_tools_menu is not None:
                menu_was_visible = self.paint_tools_menu.isVisible()
                
            # 让工具栏成为独立的顶级窗口，而不是显示整个截图窗口
            try:
                # 脱离父级，确保成为真正的顶层工具窗口
                self.botton_box.setParent(None)
            except Exception:
                pass
            self.botton_box.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
            # 钉图模式：将画笔设置二级菜单提升为顶层工具窗口，脱离截图窗口
            if hasattr(self, 'paint_tools_menu') and self.paint_tools_menu is not None:
                try:
                    # 暂时隐藏以便重新设置窗口标志
                    self.paint_tools_menu.hide()
                    self.paint_tools_menu.setParent(None)
                    self.paint_tools_menu.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
                except Exception as _e:
                    print(f"⚠️ 提升画笔二级菜单为顶层失败: {_e}")
            
            self.position_toolbar_for_pinned_window(pinned_window)
            self.botton_box.show()
            
            # 如果二级菜单之前是可见的，并且有绘画工具激活，则重新显示它
            if (menu_was_visible and hasattr(self, 'painter_tools') and 
                1 in self.painter_tools.values()):
                print("🎨 恢复二级菜单的显示状态")
                self.show_paint_tools_menu()
            
            # 切换到钉图模式 - 修改一些按钮的功能
            self.mode = "pinned"
            self.current_pinned_window = pinned_window
            
            # 只有在第一次初始化或者模式切换时才重新布局，避免重复布局
            if not hasattr(self, '_pinned_toolbar_initialized') or not self._pinned_toolbar_initialized:
                print("钉图工具栏: 开始初始化布局")
                # 设置编辑环境 - 钉图模式下不需要绘画层覆盖
                if hasattr(self, 'paintlayer'):
                    self.paintlayer.hide()  # 隐藏绘画层，直接在钉图窗口上绘制
                    
                    # 钉图模式下不重置绘画数据，保留之前的绘画内容
                    # self.pen_pointlist = []
                    # self.drawtext_pointlist = []
                    # self.drawrect_pointlist = [[-2, -2], [-2, -2], 0]
                    # self.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
                    # self.drawcircle_pointlist = [[-2, -2], [-2, -2], 0]
                    
                # 创建钉图模式的初始备份（只在第一次切换到钉图模式时创建）
                if not hasattr(self, '_pinned_backup_initialized') or not self._pinned_backup_initialized:
                    if hasattr(pinned_window, 'paintlayer') and pinned_window.paintlayer:
                        initial_pixmap = pinned_window.paintlayer.pixmap()
                        if initial_pixmap:
                            self.backup_pic_list = [QPixmap(initial_pixmap)]
                            self.backup_ssid = 0
                            self._pinned_backup_initialized = True
                            print("钉图模式: 创建初始备份")
                    else:
                        # 如果没有paintlayer，使用原始图像
                        self.backup_pic_list = [QPixmap(pinned_window.showing_imgpix)]
                        self.backup_ssid = 0
                        self._pinned_backup_initialized = True
                        print("钉图模式: 使用原始图像创建初始备份")
                    
                # 设置选择区域为整个钉图窗口
                self.x0, self.y0 = pinned_window.x(), pinned_window.y()
                self.x1, self.y1 = pinned_window.x() + pinned_window.width(), pinned_window.y() + pinned_window.height()
                
                # 设置最终图像为钉图窗口的当前图像
                self.final_get_img = pinned_window.showing_imgpix
                
                # 修改钉图模式下的按钮功能
                # 原需求: 隐藏钉图窗口工具栏的閉じる按钮，仅隐藏显示，其他逻辑不改。
                # 这里保持内部行为不变，仅不显示该按钮。
                self.sure_btn.setText("閉じる")
                self.sure_btn.setToolTip("ピン留め画像ウィンドウを閉じる")
                # 隐藏按钮
                self.sure_btn.hide()
                
                # 修改智能选区按钮为置顶功能
                self.smartcursor_btn.setToolTip("ピン留め画像の最前面表示を切替")
                if self.current_pinned_window.on_top:
                    self.smartcursor_btn.setStyleSheet("background-color:rgb(50,50,50);")
                else:
                    self.smartcursor_btn.setStyleSheet("")
                
                # 隐藏钉图模式下不需要的按钮
                # 保留OCR和翻译功能，钉图模式下也很有用
                # self.ocr_botton.hide()
                # self.translate_botton.hide()
                self.freeze_img_botton.hide()  # 隐藏钉图按钮，避免重复创建窗口
                self.long_screenshot_btn.hide()  # 隐藏长截图按钮,钉图模式下不需要
                
                # 在钉图模式下显示复制按钮
                self.copy_botton.show()
                # 保留撤销和重做按钮，钉图模式下也需要这些功能
                # self.lastbtn.hide()
                # self.nextbtn.hide()
                
                # 隐藏箭头按钮
                if hasattr(self, 'drawarrow'):
                    self.drawarrow.hide()
                
                # 重新布局按钮以移除空隙
                self.relayout_toolbar_for_pinned_mode()
                
                # 恢复绘画工具按钮的视觉状态
                self.restore_painter_tools_visual_state()
                
                # 标记为已初始化
                self._pinned_toolbar_initialized = True
                print("钉图工具栏: 完成初始化布局")
            else:
                print("钉图工具栏: 跳过重复布局，保持现有状态")
    
    def relayout_toolbar_for_pinned_mode(self):
        """重新布局钉图模式下的工具栏按钮 - 支持DPI缩放，移除取色器和箭头，保持左右分布"""
        # 根据当前显示器的DPI缩放调整按钮尺寸（调得更小一些）
        dpi_scale = self.get_current_dpi_scale()
        btn_width = int(25 * dpi_scale)
        btn_height = int(25 * dpi_scale)

        print(f"🔧 工具栏重新布局: DPI缩放={dpi_scale:.2f}, 按钮尺寸={btn_width}x{btn_height}")

        # 左侧按钮收集
        left_buttons = []
        if self.save_botton.isVisible():
            left_buttons.append((self.save_botton, int(30 * dpi_scale)))
        # OCR和翻译按钮已移除
        # if self.ocr_botton.isVisible():
        #     left_buttons.append((self.ocr_botton, int(30 * dpi_scale)))
        # if self.translate_botton.isVisible():
        #     left_buttons.append((self.translate_botton, int(30 * dpi_scale)))
        # 在钉图模式下显示复制按钮
        if self.copy_botton.isVisible():
            left_buttons.append((self.copy_botton, int(30 * dpi_scale)))

        paint_buttons = [self.pen, self.highlighter, self.bs, self.drawcircle, self.drawtext, self.choice_clor_btn]
        for btn in paint_buttons:
            if btn.isVisible():
                left_buttons.append((btn, btn_width))

        if self.smartcursor_btn.isVisible():
            left_buttons.append((self.smartcursor_btn, btn_width))
        if self.lastbtn.isVisible():
            left_buttons.append((self.lastbtn, btn_width))
        if self.nextbtn.isVisible():
            left_buttons.append((self.nextbtn, btn_width))

        # 右侧按钮（需求：隐藏閉じる按钮，因此不加入 sure_btn）
        right_buttons = []
        # 如果未来需要恢复，只需 self.sure_btn.show() 后此逻辑仍兼容
        if self.sure_btn.isVisible():  # 当前逻辑下不会进入
            right_buttons.append((self.sure_btn, int(50 * dpi_scale)))

        left_total_width = sum(w for _, w in left_buttons)
        right_total_width = sum(w for _, w in right_buttons)
        spacing = 20 if left_buttons and right_buttons else 0
        toolbar_total_width = left_total_width + spacing + right_total_width

        # 左侧布局
        cur_x = 0
        for btn, w in left_buttons:
            btn.setGeometry(cur_x, 0, w, btn_height)
            cur_x += w

        # 右侧布局（从右往左）
        right_x = toolbar_total_width
        for btn, w in reversed(right_buttons):
            right_x -= w
            btn.setGeometry(right_x, 0, w, btn_height)

        # 隐藏不需要的按钮（箭头）
        if hasattr(self, 'drawarrow'):
            self.drawarrow.setVisible(False)

        if toolbar_total_width > 0:
            self.botton_box.resize(toolbar_total_width, btn_height)
            print(f"工具栏重新布局完成: {toolbar_total_width}x{btn_height}")

        # 顶层保持与重新定位
        try:
            if getattr(self, 'mode', None) == 'pinned' and getattr(self, 'current_pinned_window', None):
                try:
                    self.botton_box.setParent(None)
                except Exception:
                    pass
                self.botton_box.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
                self.position_toolbar_for_pinned_window(self.current_pinned_window)
                if not self.botton_box.isVisible():
                    self.botton_box.show()
        except Exception as _e:
            print(f"⚠️ 钉图模式重新布局后更新工具栏失败: {_e}")
    
    def get_current_dpi_scale(self):
        """获取当前的DPI缩放比例"""
        try:
            # 获取主窗口当前所在的显示器
            screens = QApplication.screens()
            current_screen = None
            
            # 如果有钉图窗口，使用钉图窗口的显示器
            if hasattr(self, 'freeze_imgs') and self.freeze_imgs:
                pinned_window = self.freeze_imgs[0]  # 取第一个钉图窗口
                window_center_x = pinned_window.x() + pinned_window.width() // 2
                window_center_y = pinned_window.y() + pinned_window.height() // 2
                
                for screen in screens:
                    geometry = screen.geometry()
                    if (window_center_x >= geometry.x() and window_center_x < geometry.x() + geometry.width() and
                        window_center_y >= geometry.y() and window_center_y < geometry.y() + geometry.height()):
                        current_screen = screen
                        break
            
            # 如果没有找到，使用主窗口的显示器
            if current_screen is None:
                window_center_x = self.x() + self.width() // 2
                window_center_y = self.y() + self.height() // 2
                
                for screen in screens:
                    geometry = screen.geometry()
                    if (window_center_x >= geometry.x() and window_center_x < geometry.x() + geometry.width() and
                        window_center_y >= geometry.y() and window_center_y < geometry.y() + geometry.height()):
                        current_screen = screen
                        break
            
            # 如果还是没找到，使用主显示器
            if current_screen is None:
                current_screen = QApplication.primaryScreen()
            
            # 计算DPI缩放比例（使用Windows系统缩放设置）
            try:
                import ctypes
                from ctypes import wintypes
                print("🔍 检测所有显示器DPI (Win32 枚举对比):")
                raw_list = _enumerate_monitor_dpi()
                # 建立 rect->dpi 映射，方便匹配 Qt 屏幕
                for i, raw in enumerate(raw_list):
                    l, t, r, b = raw['rect']
                    print(f"   [Raw{i+1}] rect=({l},{t})~({r},{b}) dpi={raw['dpi_x']} scale={raw['scale']:.2f}")

                # Qt 屏幕中心点测试
                for i, screen in enumerate(screens):
                    g = screen.geometry()
                    cx = g.x() + g.width() // 2
                    cy = g.y() + g.height() // 2
                    try:
                        pt = wintypes.POINT()
                        pt.x = int(cx)
                        pt.y = int(cy)
                        hmon = ctypes.windll.user32.MonitorFromPoint(pt, 2)
                        dpi_x = ctypes.c_uint()
                        dpi_y = ctypes.c_uint()
                        ctypes.windll.shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
                        print(f"   [Qt{i+1}] center=({cx},{cy}) QtGeo=({g.x()},{g.y()},{g.width()}x{g.height()}) -> DPI={dpi_x.value} scale={dpi_x.value/96.0:.2f}")
                    except Exception as _e:
                        print(f"   [Qt{i+1}] center=({cx},{cy}) 检测失败: {_e}")

                # 当前窗口对应显示器 DPI
                pt = wintypes.POINT()
                pt.x = int(window_center_x)
                pt.y = int(window_center_y)
                monitor = ctypes.windll.user32.MonitorFromPoint(pt, 2)
                dpi_x = ctypes.c_uint()
                dpi_y = ctypes.c_uint()
                ctypes.windll.shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
                real_dpi_scale = dpi_x.value / 96.0
                print(f"🔍 当前窗口DPI: center=({window_center_x},{window_center_y}) dpi={dpi_x.value} scale={real_dpi_scale:.2f}")

                # 右侧屏幕错判场景修正：如果所有 Qt 屏幕 x>=0 且 real_dpi_scale == 主屏 scale，但窗口中心不在主屏 geo 内 -> 强制用最匹配 raw rect 的 scale
                primary_geo = QApplication.primaryScreen().geometry()
                if all(sc.geometry().x() >= 0 for sc in screens) and not (primary_geo.x() <= window_center_x < primary_geo.x() + primary_geo.width() and primary_geo.y() <= window_center_y < primary_geo.y() + primary_geo.height()):
                    # 匹配 raw rect
                    for raw in raw_list:
                        l, t, r, b = raw['rect']
                        if l <= window_center_x < r and t <= window_center_y < b:
                            if abs(raw['scale'] - real_dpi_scale) > 1e-3:
                                print(f"⚠️ 发现可能的右侧屏幕误判，修正 DPI scale {real_dpi_scale:.2f} -> {raw['scale']:.2f}")
                                real_dpi_scale = raw['scale']
                            break
            except Exception as e:
                print(f"⚠️ 获取系统DPI失败，使用Qt DPI: {e}")
                logical_dpi = current_screen.logicalDotsPerInch()
                real_dpi_scale = logical_dpi / 96.0
            
            # 使用变化系数减缓缩放变化
            change_factor = 0.9  # 变化系数，值越小变化越缓和
            
            if real_dpi_scale > 1.0:
                # 高DPI：减缓放大效果
                dpi_scale = 1.0 + (real_dpi_scale - 1.0) * change_factor
            else:
                # 低DPI：减缓缩小效果  
                dpi_scale = real_dpi_scale + (1.0 - real_dpi_scale) * (1.0 - change_factor)
            
            # 限制缩放范围
            dpi_scale = max(0.8, min(dpi_scale, 1.8))
            
            print(f"🔍 DPI计算结果: 原始={real_dpi_scale:.2f} -> 调整后={dpi_scale:.2f}")
            
            return dpi_scale
            
        except Exception as e:
            print(f"❌ 获取DPI缩放失败: {e}")
            return 1.0  # 默认缩放
    
    def restore_painter_tools_visual_state(self):
        """恢复绘画工具按钮的视觉状态"""
        # 恢复所有绘画工具按钮的状态
        for tool_name, is_active in self.painter_tools.items():
            if is_active:
                if tool_name == "pen_on":
                    self.pen.setStyleSheet("background-color:rgb(50,50,50);")
                elif tool_name == "highlight_on":
                    self.highlighter.setStyleSheet("background-color:rgb(50,50,50);")
                elif tool_name == "drawrect_bs_on":
                    self.bs.setStyleSheet("background-color:rgb(50,50,50);")
                elif tool_name == "drawcircle_on":
                    self.drawcircle.setStyleSheet("background-color:rgb(50,50,50);")
                elif tool_name == "drawarrow_on":
                    self.drawarrow.setStyleSheet("background-color:rgb(50,50,50);")
                elif tool_name == "drawtext_on":
                    self.drawtext.setStyleSheet("background-color:rgb(50,50,50);")
            else:
                # 重置未激活按钮的样式
                if tool_name == "pen_on":
                    self.pen.setStyleSheet("")
                elif tool_name == "highlight_on":
                    self.highlighter.setStyleSheet("")
                elif tool_name == "drawrect_bs_on":
                    self.bs.setStyleSheet("")
                elif tool_name == "drawcircle_on":
                    self.drawcircle.setStyleSheet("")
                elif tool_name == "drawarrow_on":
                    self.drawarrow.setStyleSheet("")
                elif tool_name == "drawtext_on":
                    self.drawtext.setStyleSheet("")
    
    def hide_toolbar_for_pinned_window(self):
        """隐藏钉图窗口的工具栏"""
        if hasattr(self, 'botton_box'):
            self.botton_box.hide()
            self.hide_paint_tools_menu()
            
            # 重置初始化标志，下次显示时可以重新初始化（如果需要）
            if hasattr(self, '_pinned_toolbar_initialized'):
                self._pinned_toolbar_initialized = False
                print("钉图工具栏: 重置初始化标志")
            
            # 隐藏文字输入框（如果正在显示）
            if hasattr(self, 'text_box') and self.text_box.isVisible():
                self.text_box.hide()
                self.text_box.clear()
                # 将文字框恢复为主窗口的子组件
                try:
                    self.text_box.setParent(self)
                    self.text_box.setWindowFlags(Qt.Widget)
                except Exception:
                    pass
            
            # 还原画笔二级菜单为截图窗口的子部件
            if hasattr(self, 'paint_tools_menu') and self.paint_tools_menu is not None:
                try:
                    self.paint_tools_menu.hide()
                    self.paint_tools_menu.setParent(self)
                    self.paint_tools_menu.setWindowFlags(Qt.Widget)
                except Exception as _e:
                    print(f"⚠️ 还原画笔二级菜单父子关系失败: {_e}")
            
            # 恢复工具栏为截图窗口的子组件
            try:
                self.botton_box.setParent(self)
            except Exception:
                pass
            self.botton_box.setWindowFlags(Qt.Widget)
            
            # 恢复按钮的原始状态
            self.sure_btn.setText("确定")
            self.sure_btn.setToolTip("")
            # 退出钉图模式时恢复显示
            if not self.sure_btn.isVisible():
                self.sure_btn.show()
            
            # 恢复智能选区按钮
            self.smartcursor_btn.setToolTip("スマート選択")
            if self.settings.value("screenshot/smartcursor", True, type=bool):
                self.smartcursor_btn.setStyleSheet("background-color:rgb(50,50,50);")
            else:
                self.smartcursor_btn.setStyleSheet("")
            
            # 恢复所有按钮的显示
            # OCR和翻译按钮已移除
            # self.ocr_botton.show()
            # self.translate_botton.show()
            self.freeze_img_botton.show()  # 恢复钉图按钮
            self.long_screenshot_btn.show()  # 恢复长截图按钮
            self.copy_botton.hide()  # 隐藏复制按钮，只在钉图模式下使用
            self.lastbtn.show()
            self.nextbtn.show()
            if hasattr(self, 'drawarrow'):
                self.drawarrow.show()  # 恢复箭头按钮
            
            # 恢复原始的按钮布局
            self.restore_original_toolbar_layout()
            
            # 钉图模式下不要清理编辑环境，因为绘画数据在钉图窗口中
            # 只在退出钉图模式时才清理
            # if hasattr(self, 'paintlayer'):
            #     self.paintlayer.hide()
                
            self.mode = "screenshot"
            self.current_pinned_window = None
            
            # 钉图模式下不要清理工具状态，保留绘画工具的选择状态
            # self.change_tools_fun('pen_on')
            # for tool in self.painter_tools:
            #     self.painter_tools[tool] = 0
    
    def restore_original_toolbar_layout(self):
        """恢复截图模式的原始工具栏布局"""
        # 使用左右分布布局：左侧吸附其他按钮，右侧吸附钉图和确定按钮
        btn_width = 35
        btn_height = 35
        
        # 左侧按钮从0开始布局
        left_btn_x = 0
        
        # 长截图按钮放在最左边
        self.long_screenshot_btn.setGeometry(left_btn_x, 0, 40, btn_height)
        left_btn_x += 40
        
        # 保存按钮在长截图按钮右边
        self.save_botton.setGeometry(left_btn_x, 0, 40, btn_height)
        left_btn_x += 40
        
        # 画笔工具
        self.pen.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 荧光笔工具
        self.highlighter.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 箭头工具
        self.drawarrow.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 矩形工具
        self.bs.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 圆形工具
        self.drawcircle.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 文字工具
        self.drawtext.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 颜色选择
        self.choice_clor_btn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width

        # 智能选区按钮已移到主界面设置，不占用工具栏空间  
        # self.smartcursor_btn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        # left_btn_x += btn_width  # 不再为隐藏按钮分配空间
        
        # 上一步
        self.lastbtn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 下一步
        self.nextbtn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width

        # 计算工具栏总宽度，为右侧按钮预留空间
        right_buttons_width = 40 + 60  # 钉图按钮40px + 确定按钮60px
        toolbar_total_width = left_btn_x + 20 + right_buttons_width  # 左侧按钮 + 间隔 + 右侧按钮
        
        # 右侧按钮从右往左布局
        right_btn_x = toolbar_total_width - 60  # 确定按钮位置（从右边开始）
        
        # 确定按钮吸附最右边
        self.sure_btn.setGeometry(right_btn_x, 0, 60, 35)
        
        # 钉图按钮在确定按钮左边
        right_btn_x -= 40
        self.freeze_img_botton.setGeometry(right_btn_x, 0, 40, 35)

        # 恢复工具栏大小
        self.botton_box.resize(toolbar_total_width, btn_height)
        print(f"恢复截图模式: 工具栏大小为 {toolbar_total_width}x{btn_height}")
        
        # 隐藏截图窗口
        self.hide()
    
    def position_toolbar_for_pinned_window(self, pinned_window):
        """为钉图窗口定位工具栏 - 支持多显示器"""
        if hasattr(self, 'botton_box') and pinned_window:
            # 获取钉图窗口所在的显示器
            pinned_screen = self.get_screen_for_point(
                pinned_window.x() + pinned_window.width() // 2,
                pinned_window.y() + pinned_window.height() // 2
            )
            
            screen_rect = pinned_screen.geometry().getRect()
            screen_x, screen_y, screen_w, screen_h = screen_rect
            
            toolbar_width = self.botton_box.width()
            toolbar_height = self.botton_box.height()
            
            # 计算工具栏位置，优先显示在钉图窗口右侧对齐下边缘
            # 首先尝试钉图窗口下方右对齐
            below_y = pinned_window.y() + pinned_window.height() + 0
            # 右对齐：工具栏右边缘与钉图窗口右边缘对齐
            toolbar_x_right_aligned = pinned_window.x() + pinned_window.width() - toolbar_width
            
            if below_y + toolbar_height <= screen_y + screen_h and toolbar_x_right_aligned >= screen_x:
                # 下方有足够空间且右对齐位置合理
                toolbar_x = max(screen_x, toolbar_x_right_aligned)
                toolbar_y = below_y
            else:
                # 下方空间不足或右对齐位置不合理，尝试上方右对齐
                above_y = pinned_window.y() - toolbar_height - 0
                if above_y >= screen_y and toolbar_x_right_aligned >= screen_x:
                    toolbar_x = max(screen_x, toolbar_x_right_aligned)
                    toolbar_y = above_y
                else:
                    # 上下都不够或右对齐不合理，显示在右侧
                    toolbar_x = pinned_window.x() + pinned_window.width() + 0
                    toolbar_y = max(screen_y, pinned_window.y())
                    
                    if toolbar_x + toolbar_width > screen_x + screen_w:
                        # 右侧也不够，显示在左侧
                        toolbar_x = pinned_window.x() - toolbar_width - 0
                        if toolbar_x < screen_x:
                            # 左侧也不够，显示在钉图窗口内部右下角
                            toolbar_x = pinned_window.x() + pinned_window.width() - toolbar_width - 0
                            toolbar_y = pinned_window.y() + pinned_window.height() - toolbar_height - 0
            
            # 确保工具栏完全在目标显示器内
            toolbar_x, toolbar_y = self.adjust_position_to_screen(
                toolbar_x, toolbar_y, toolbar_width, toolbar_height, pinned_screen)
            
            print(f"钉图工具栏定位: 显示器{screen_rect}, 工具栏({toolbar_x}, {toolbar_y})")
            self.botton_box.move(toolbar_x, toolbar_y)
    
    def is_toolbar_under_mouse(self):
        """检查工具栏或画笔设置菜单是否在鼠标下方，以及是否正在与UI交互"""
        if hasattr(self, 'botton_box') and self.botton_box.isVisible():
            if self.botton_box.underMouse():
                return True
        
        # 也检查画笔设置二级菜单
        if hasattr(self, 'paint_tools_menu') and self.paint_tools_menu.isVisible():
            if self.paint_tools_menu.underMouse():
                return True
            
            # 检查二级菜单中的任何子控件是否有焦点或正在被使用
            for child in self.paint_tools_menu.findChildren(QWidget):
                if child.hasFocus() or child.underMouse():
                    return True
            
            # 如果有绘画工具激活，给二级菜单更多保护时间
            if (hasattr(self, 'painter_tools') and 1 in self.painter_tools.values()):
                # 检查鼠标是否刚刚离开二级菜单区域（给一个小的缓冲时间和空间）
                cursor_pos = QCursor.pos()
                menu_rect = self.paint_tools_menu.geometry()
                # 稍微扩大二级菜单的检测范围
                buffer = 10
                expanded_menu_rect = QRect(
                    menu_rect.x() - buffer, 
                    menu_rect.y() - buffer,
                    menu_rect.width() + 2 * buffer, 
                    menu_rect.height() + 2 * buffer
                )
                
                # 将本地坐标转换为全局坐标
                if hasattr(self.paint_tools_menu, 'parent') and self.paint_tools_menu.parent():
                    global_menu_rect = QRect(
                        self.paint_tools_menu.mapToGlobal(expanded_menu_rect.topLeft()),
                        expanded_menu_rect.size()
                    )
                else:
                    global_menu_rect = expanded_menu_rect
                    
                if global_menu_rect.contains(cursor_pos):
                    return True
                
        return False
    
    def handle_sure_btn_click(self):
        """处理确定按钮点击 - 根据当前模式执行不同操作"""
        # 在执行确定操作前，先保存当前的绘制状态（如果有正在输入的文字）
        print("✅ [确定] 执行确定前，保存当前绘制状态")
        self._reset_text_box_completely()
        
        if hasattr(self, 'mode') and self.mode == "pinned":
            # 钉图模式下，关闭钉图窗口
            self.close_pinned_window()
        else:
            # 正常截图模式
            self.cutpic()
    
    def close_pinned_window(self):
        """关闭钉图窗口的编辑模式，但保持窗口存活"""
        if hasattr(self, 'current_pinned_window') and self.current_pinned_window:
            # 不要调用clear()！这会清理showing_imgpix和origin_imgpix
            # 只需要隐藏工具栏并退出编辑模式
            print("🔒 关闭钉图编辑模式，但保持窗口存活")
            
            # 确保钉图窗口不再处于编辑状态
            if hasattr(self.current_pinned_window, '_is_editing'):
                self.current_pinned_window._is_editing = False
            
            self.hide_toolbar_for_pinned_window()
    
    def apply_edits_to_pinned_window(self):
        """将编辑应用到钉图窗口"""
        if hasattr(self, 'current_pinned_window') and self.current_pinned_window:
            # 获取当前钉图窗口的图像并应用编辑
            current_img = self.current_pinned_window.showing_imgpix.copy()
            
            # 检查是否有绘画层内容
            if hasattr(self, 'paintlayer') and self.paintlayer.pixmap():
                paint_pixmap = self.paintlayer.pixmap()
                if not paint_pixmap.isNull():
                    painter = QPainter(current_img)
                    painter.setRenderHint(QPainter.Antialiasing)
                    # 直接将绘画层内容绘制到图像上，因为它们应该是相同尺寸
                    painter.drawPixmap(0, 0, paint_pixmap)
                    painter.end()
            
            # 更新钉图窗口的图像
            self.current_pinned_window.showing_imgpix = current_img
            self.current_pinned_window.setPixmap(current_img.scaled(
                self.current_pinned_window.width(), 
                self.current_pinned_window.height(), 
                Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
            # 清理绘画层
            if hasattr(self, 'paintlayer'):
                paint_pixmap = QPixmap(self.current_pinned_window.width(), self.current_pinned_window.height())
                paint_pixmap.fill(Qt.transparent)
                self.paintlayer.setPixmap(paint_pixmap)
            
            # 隐藏工具栏
            self.hide_toolbar_for_pinned_window()
            
            # 移除了编辑已应用到钉图提示

    def change_tools_fun(self, r):  # 更改工具时统一调用的函数,用于重置所有样式
        self.pen.setStyleSheet('')
        self.highlighter.setStyleSheet('')
        self.bs.setStyleSheet('')
        self.drawarrow.setStyleSheet('')
        self.drawcircle.setStyleSheet('')
        self.drawtext.setStyleSheet('')
        
        # 完全重置文字输入框状态
        self._reset_text_box_completely()
        
        for tool in self.painter_tools:
            if tool == r:
                self.painter_tools[tool] = 1
            else:
                self.painter_tools[tool] = 0
                
        # 如果没有激活任何工具（r为空字符串），强制隐藏二级菜单
        if not r or r == "":
            self.paint_tools_menu.hide()
            
        self.update()

    def change_bs_fun(self):
        # print('cahngegbs')
        if self.painter_tools['drawrect_bs_on']:
            # 关闭工具前先保存当前文字输入（如果有的话）
            self._reset_text_box_completely()
            self.painter_tools['drawrect_bs_on'] = 0
            self.bs.setStyleSheet('')
            # 强制隐藏二级菜单（因为工具被关闭）
            self.paint_tools_menu.hide()
        else:
            self.change_tools_fun('drawrect_bs_on')
            self.apply_tool_settings('drawrect_bs_on')
            self.bs.setStyleSheet('background-color:rgb(50,50,50)')
            # 移除了矩形框工具提示
            self.show_paint_tools_menu()

    def search_in_which_screen(self):
        mousepos=Controller().position
        screens = QApplication.screens()
        secondscreen = QApplication.primaryScreen()
        for i in screens:
            rect=i.geometry().getRect()
            if mousepos[0]in range(rect[0],rect[0]+rect[2]) and mousepos[1]in range(rect[1],rect[1]+rect[3]):
                secondscreen = i
                break
        print("t", self.x(), QApplication.desktop().width(),QApplication.primaryScreen().geometry(),secondscreen.geometry(),mousepos)
        return secondscreen
    
    def get_screen_for_point(self, x, y):
        """根据坐标点获取对应的显示器"""
        screens = QApplication.screens()
        for screen in screens:
            rect = screen.geometry().getRect()
            if x >= rect[0] and x < rect[0] + rect[2] and y >= rect[1] and y < rect[1] + rect[3]:
                return screen
        return QApplication.primaryScreen()
    
    def get_screen_for_rect(self, x0, y0, x1, y1):
        """根据矩形区域获取最合适的显示器（取矩形中心点所在显示器）"""
        center_x = (x0 + x1) // 2
        center_y = (y0 + y1) // 2
        return self.get_screen_for_point(center_x, center_y)
    
    def adjust_position_to_screen(self, x, y, width, height, screen=None):
        """调整窗口位置以确保完全在指定显示器内"""
        if screen is None:
            screen = self.get_screen_for_point(x, y)
        
        screen_rect = screen.geometry().getRect()
        screen_x, screen_y, screen_w, screen_h = screen_rect
        
        # 确保窗口不超出显示器边界
        if x + width > screen_x + screen_w:
            x = screen_x + screen_w - width
        if y + height > screen_y + screen_h:
            y = screen_y + screen_h - height
        if x < screen_x:
            x = screen_x
        if y < screen_y:
            y = screen_y
            
        return x, y

    def capture_all_screens(self):
        """捕获所有显示器截图并拼接成虚拟桌面 (含调试输出)"""
        try:
            screens = QApplication.screens()
            _debug_print(f"Qt 检测到 {len(screens)} 个 QScreen")

            win_monitors = _enumerate_win_monitors()
            if win_monitors:
                for idx, m in enumerate(win_monitors, 1):
                    _debug_print(f"Win32 显示器{idx}: 设备={m['device']} 区域={m['rect']} 主屏={m['primary']}")
            else:
                _debug_print("Win32 未能枚举到显示器或枚举失败")

            if len(screens) != len(win_monitors) and win_monitors:
                _debug_print("⚠️ Qt 与 Win32 显示器数量不一致，可能 Qt 未感知外接屏 (DPI/权限/会话)")

            # 汇总边界
            min_x = min_y = float('inf')
            max_x = max_y = float('-inf')
            captures = []

            for i, screen in enumerate(screens):
                pm = screen.grabWindow(0)
                geo = screen.geometry()
                try:
                    name = screen.name()
                except Exception:
                    name = f"Screen{i+1}"
                _debug_print(f"QScreen {i+1}: 名称={name} 分辨率={geo.width()}x{geo.height()} 位置=({geo.x()},{geo.y()}) dpr={screen.devicePixelRatio():.2f}")
                _debug_print(f"  抓取Pixmap={pm.width()}x{pm.height()}")

                captures.append({
                    'pixmap': pm,
                    'x': geo.x(),
                    'y': geo.y(),
                    'w': geo.width(),
                    'h': geo.height(),
                })
                min_x = min(min_x, geo.x())
                min_y = min(min_y, geo.y())
                max_x = max(max_x, geo.x() + geo.width())
                max_y = max(max_y, geo.y() + geo.height())

            total_width = max_x - min_x
            total_height = max_y - min_y
            _debug_print(f"虚拟桌面: size={total_width}x{total_height} offset=({min_x},{min_y})")

            if len(captures) == 1:
                _debug_print("只有一个显示器 -> 直接返回")
                self.virtual_desktop_offset_x = 0
                self.virtual_desktop_offset_y = 0
                self.virtual_desktop_width = captures[0]['w']
                self.virtual_desktop_height = captures[0]['h']
                self.virtual_desktop_min_x = 0
                self.virtual_desktop_min_y = 0
                self.virtual_desktop_max_x = captures[0]['w']
                self.virtual_desktop_max_y = captures[0]['h']
                return captures[0]['pixmap']

            combined = QPixmap(total_width, total_height)
            combined.fill(Qt.black)
            painter = QPainter(combined)
            for i, cap in enumerate(captures):
                rx = cap['x'] - min_x
                ry = cap['y'] - min_y
                painter.drawPixmap(rx, ry, cap['pixmap'])
                _debug_print(f"合成: Screen{i+1} -> ({rx},{ry}) size={cap['w']}x{cap['h']}")
            painter.end()

            # 保存位置信息
            self.virtual_desktop_offset_x = min_x
            self.virtual_desktop_offset_y = min_y
            self.virtual_desktop_width = total_width
            self.virtual_desktop_height = total_height
            self.virtual_desktop_min_x = min_x
            self.virtual_desktop_min_y = min_y
            self.virtual_desktop_max_x = max_x
            self.virtual_desktop_max_y = max_y
            _debug_print(f"合成完成: {combined.width()}x{combined.height()} 范围=({min_x},{min_y})~({max_x},{max_y})")
            return combined
        except Exception as e:
            _debug_print(f"捕获多屏失败，回退主屏: {e}")
            primary = QApplication.primaryScreen().grabWindow(0)
            # 基本默认
            self.virtual_desktop_offset_x = 0
            self.virtual_desktop_offset_y = 0
            self.virtual_desktop_width = primary.width()
            self.virtual_desktop_height = primary.height()
            self.virtual_desktop_min_x = 0
            self.virtual_desktop_min_y = 0
            self.virtual_desktop_max_x = primary.width()
            self.virtual_desktop_max_y = primary.height()
            return primary

    def screen_shot(self, pix=None,mode = "screenshot"):
        """mode: screenshot 、orc、set_area、getpix。screenshot普通截屏;非截屏模式:orc获取ocr源图片; set_area用于设置区域、getpix提取区域"""
        # 截屏函数,功能有二:当有传入pix时直接显示pix中的图片作为截屏背景,否则截取当前屏幕作为背景;前者用于重置所有修改
        # if PLATFORM_SYS=="darwin":
        self.sshoting = True
        t1 = time.process_time()
        
        # 修复DPI缩放问题：不使用设备像素比率，确保1:1显示
        # pixRat = QWindow().devicePixelRatio()  # 注释掉这行，避免DPI缩放
        
        if type(pix) is QPixmap:
            get_pix = pix
            self.init_parameters()
        else:
            self.setup(mode)  # 初始化截屏
            
            # 修改：现在截取所有显示器而不是单个显示器
            get_pix = self.capture_all_screens()
            # get_pix.setDevicePixelRatio(pixRat)  # 注释掉这行，避免DPI缩放
            
        pixmap = QPixmap(get_pix.width(), get_pix.height())
        # pixmap.setDevicePixelRatio(pixRat)  # 注释掉这行，避免DPI缩放
        pixmap.fill(Qt.transparent)  # 填充透明色,不然没有透明通道

        painter = QPainter(pixmap)
        # painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(0, 0, get_pix)
        painter.end()  # 一定要end
        self.originalPix = pixmap.copy()
        
        # 关键修复：确保QLabel图像显示属性正确，避免DPI缩放
        self.setScaledContents(False)  # 禁用自动缩放，保持原始尺寸1:1显示
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)  # 确保图像从左上角开始显示
        
        self.setPixmap(pixmap)
        self.mask.setGeometry(0, 0, get_pix.width(), get_pix.height())
        self.paintlayer.setGeometry(0, 0, get_pix.width(), get_pix.height())
        self.paintlayer.setPixmap(QPixmap(get_pix.width(), get_pix.height()))
        self.paintlayer.pixmap().fill(Qt.transparent)  # 重点,不然不透明
        
        self.text_box.hide()
        self.botton_box.hide()

        # 关键改进：修复多显示器预览偏移问题
        # 根本解决方案：窗口位置从(0,0)开始，但尺寸覆盖整个虚拟桌面
        # 这样图像内容(从0,0开始)就能正确对应到屏幕位置
        
        # 根据是否有多显示器信息来决定显示方式
        # 判断多显示器的更健壮方式：通过 QApplication.screens() 数量
        multi_screen = len(QApplication.screens()) > 1
        if multi_screen:
            # 多显示器：使用 capture_all_screens 生成的几何
            _debug_print(f"多显示器模式：偏移({self.virtual_desktop_offset_x},{self.virtual_desktop_offset_y}) 尺寸={self.virtual_desktop_width}x{self.virtual_desktop_height}")
            # 先锁定大小，避免 QLabel 根据内容再次回缩
            self.setMinimumSize(self.virtual_desktop_width, self.virtual_desktop_height)
            self.setMaximumSize(self.virtual_desktop_width, self.virtual_desktop_height)
            self.move(self.virtual_desktop_min_x, self.virtual_desktop_min_y)
            self.resize(self.virtual_desktop_width, self.virtual_desktop_height)
            QApplication.processEvents()
            self.show()
            self.raise_()
            QApplication.processEvents()
            g2 = self.geometry()
            _debug_print(f"初次显示几何: pos=({g2.x()},{g2.y()}) size={g2.width()}x{g2.height()}")
            if g2.width() != self.virtual_desktop_width or g2.height() != self.virtual_desktop_height:
                _debug_print(f"初次几何不匹配，尝试Win32强制设置 {g2.width()}x{g2.height()} -> {self.virtual_desktop_width}x{self.virtual_desktop_height}")
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    SWP_NOZORDER = 0x0004
                    SWP_NOACTIVATE = 0x0010
                    hwnd = int(self.winId())
                    user32.SetWindowPos(hwnd, 0, self.virtual_desktop_min_x, self.virtual_desktop_min_y,
                                        self.virtual_desktop_width, self.virtual_desktop_height,
                                        SWP_NOZORDER | SWP_NOACTIVATE)
                    QApplication.processEvents()
                    g3 = self.geometry()
                    _debug_print(f"Win32后几何: pos=({g3.x()},{g3.y()}) size={g3.width()}x{g3.height()}")
                except Exception as e:
                    _debug_print(f"Win32 SetWindowPos 失败: {e}")
        else:
            self.showFullScreen()
            _debug_print("单显示器模式：全屏显示")
        
        # 显示子控件
        self.mask.show()
        self.paintlayer.show()
        
        # 处理事件队列
        QApplication.processEvents()
        
        # 恢复完全不透明
        self.setWindowOpacity(1.0)
        
        # 最后恢复完全可见，这样可以避免跳动
        self.setWindowOpacity(1)
        
        if type(pix) is not QPixmap:
            # 初始化时，确保备份列表只包含初始状态
            self.backup_ssid = 0
            self.backup_pic_list = [self.originalPix.copy()]
            print(f"撤销系统: 初始化备份列表，创建初始状态 (backup_ssid={self.backup_ssid}, list_length={len(self.backup_pic_list)})")
        else:
            # 确保有初始备份，但只在必要时创建
            if not hasattr(self, 'backup_pic_list') or len(self.backup_pic_list) == 0:
                self.backup_ssid = 0
                self.backup_pic_list = [self.originalPix.copy()]
                print(f"撤销系统: 补充创建初始备份 (backup_ssid={self.backup_ssid}, list_length={len(self.backup_pic_list)})")
            else:
                # 如果已有备份列表，重置到初始状态
                self.backup_ssid = 0
                self.backup_pic_list = [self.originalPix.copy()]
                print(f"撤销系统: 重置备份列表到初始状态 (backup_ssid={self.backup_ssid}, list_length={len(self.backup_pic_list)})")

        # 延迟初始化智能选区，避免启动时卡顿
        # self.init_ss_thread_fun(get_pix)  # 注释掉自动初始化
        self._screenshot_pix = get_pix  # 保存截图数据，用于延迟初始化
        self._smart_selection_initialized = False  # 标记智能选区是否已初始化
        
        self.paintlayer.pixpng = QPixmap(":/msk.jpg")
        self.text_box.setTextColor(self.pencolor)
        # 以下设置样式 (保持输入框完全透明，仅作输入容器)
        if hasattr(self, 'text_box'):
            self.text_box.setStyleSheet("background:rgba(0,0,0,0);color:rgba(0,0,0,0);border:0px;")
        self.setStyleSheet("QPushButton{color:black;background-color:rgb(239,239,239);padding:1px 4px;}"
                           "QPushButton:hover{color:green;background-color:rgb(200,200,100);}"
                           "QGroupBox{border:none;}")
        
        print('sstime:', time.process_time() - t1)
        self.setFocus()
        self.setMouseTracking(True)
        self.activateWindow()
        self.raise_()
        self.update()

    # _schedule_geometry_fix 逻辑已移除，改为一次性强制

    def init_ss_thread_fun(self, get_pix):  # 后台初始化截屏线程,用于寻找所有智能选区

        self.x0 = self.y0 = 0
        # 使用实际截图的尺寸而不是桌面尺寸
        self.x1 = get_pix.width()
        self.y1 = get_pix.height()
        # 修复：鼠标位置不能是负数，会导致pixelColor错误
        self.mouse_posx = self.mouse_posy = 200  # 使用安全的正数位置
        self.qimg = get_pix.toImage()
        temp_shape = (self.qimg.height(), self.qimg.width(), 4)
        ptr = self.qimg.bits()
        ptr.setsize(self.qimg.byteCount())
        result = array(ptr, dtype=uint8).reshape(temp_shape)[..., :3]
        self.finder.img = result
        self.finder.find_contours_setup()
        QApplication.processEvents()
    
    def _lazy_init_smart_selection(self):
        """延迟初始化智能选区，避免启动时卡顿"""
        if self._smart_selection_initialized or not hasattr(self, '_screenshot_pix'):
            return
            
        try:
            print("🔍 初始化智能选区...")
            self.init_ss_thread_fun(self._screenshot_pix)
            self._smart_selection_initialized = True
            print("✅ 智能选区初始化完成")
        except Exception as e:
            print(f"⚠️ 智能选区初始化失败: {e}")
            # 即使失败也标记为已初始化，避免重复尝试
            self._smart_selection_initialized = True

    def backup_shortshot(self):
        # 防止在撤销操作过程中进行备份
        if hasattr(self, '_in_undo_operation') and self._in_undo_operation:
            print("撤销系统: 跳过备份 - 正在进行撤销操作")
            return
        
        # 防止在钉图创建过程中进行意外备份
        if hasattr(self, '_creating_pinned_window') and self._creating_pinned_window:
            print("撤销系统: 跳过备份 - 正在创建钉图窗口")
            return
            
        # 改进的备份逻辑：只有在用户执行了撤销操作后再进行新操作时，才清除后续步骤
        # 正常连续操作时不应该清除步骤
        current_list_length = len(self.backup_pic_list)
        
        # 调试信息：显示当前状态
        print(f"撤销系统: 准备备份 - 当前位置:{self.backup_ssid}, 列表长度:{current_list_length}")
        
        # 如果当前位置不在列表末尾，说明用户之前撤销了一些步骤
        # 现在要进行新操作，需要清除当前位置之后的所有步骤
        if current_list_length > 0 and self.backup_ssid < current_list_length - 1:
            steps_to_remove = current_list_length - self.backup_ssid - 1
            print(f"撤销系统: 检测到撤销后的新操作，清除位置{self.backup_ssid + 1}之后的{steps_to_remove}个步骤")
            self.backup_pic_list = self.backup_pic_list[:self.backup_ssid + 1]
            print(f"撤销系统: 清除后列表长度:{len(self.backup_pic_list)}")
        
        # 限制历史记录长度为10步，但要保证至少有一个初始状态
        while len(self.backup_pic_list) >= 10:
            self.backup_pic_list.pop(0)
            if self.backup_ssid > 0:
                self.backup_ssid -= 1
            print(f"撤销系统: 达到最大长度，移除最旧记录，当前位置调整为:{self.backup_ssid}")
            
        # 在钉图模式下，备份钉图窗口的paintlayer内容
        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
            # 获取钉图窗口的paintlayer的pixmap
            if hasattr(self.current_pinned_window, 'paintlayer') and self.current_pinned_window.paintlayer:
                paintlayer_pixmap = self.current_pinned_window.paintlayer.pixmap()
                if paintlayer_pixmap and not paintlayer_pixmap.isNull():
                    allpix = paintlayer_pixmap
                    print("撤销系统: 钉图模式 - 备份paintlayer图像")
                else:
                    allpix = self.cutpic(save_as=3)
                    print("撤销系统: 钉图模式 - paintlayer无效，使用cutpic")
            else:
                allpix = self.cutpic(save_as=3)
                print("撤销系统: 钉图模式 - 无paintlayer，使用cutpic")
        else:
            allpix = self.cutpic(save_as=3)
            print("撤销系统: 正常模式 - 使用cutpic")
            
        # 安全检查：确保allpix有效
        if allpix is None or (hasattr(allpix, 'isNull') and allpix.isNull()):
            print("⚠️ 撤销系统: 获取的图像无效，跳过备份")
            return
            
        try:
            backup_pixmap = QPixmap(allpix)
            if backup_pixmap.isNull():
                print("⚠️ 撤销系统: 创建备份QPixmap失败")
                return
                
            self.backup_pic_list.append(backup_pixmap)
            self.backup_ssid = len(self.backup_pic_list) - 1
            print(f"撤销系统: 备份完成 - 当前步骤:{self.backup_ssid}, 总步骤:{len(self.backup_pic_list)}")
        except Exception as e:
            print(f"⚠️ 撤销系统: 创建备份时出错: {e}")
            # 确保backup_ssid状态正确
            if hasattr(self, 'backup_pic_list') and len(self.backup_pic_list) > 0:
                self.backup_ssid = len(self.backup_pic_list) - 1

    def last_step(self):
        try:
            # 检查是否在钉图模式下
            if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
                # 钉图模式下，调用钉图窗口的撤销方法
                if hasattr(self.current_pinned_window, 'last_step'):
                    self.current_pinned_window.last_step()
                else:
                    print("⚠️ 钉图窗口没有撤销方法")
                return
            
            # 设置撤销操作标志，防止在撤销过程中进行备份
            self._in_undo_operation = True
            
            # 检查是否有有效的备份可以撤销
            # backup_ssid > 0 表示当前不在初始状态
            # len(self.backup_pic_list) > 1 表示确实有多个备份状态
            if self.backup_ssid > 0 and len(self.backup_pic_list) > 1:
                # 移除了上一步提示
                self.backup_ssid -= 1
                self.return_shortshot()
                print(f"撤销调试: 撤销到步骤 {self.backup_ssid}")
            else:
                # 移除了没有上一步了提示
                print(f"撤销调试: 已经是第一步，不能再撤销 (backup_ssid={self.backup_ssid}, list_length={len(self.backup_pic_list) if hasattr(self, 'backup_pic_list') else 0})")
        except Exception as e:
            print(f"⚠️ 撤销操作出错: {e}")
            # 移除了撤销失败提示
            # 重置撤销状态防止进一步错误
            try:
                if hasattr(self, 'backup_pic_list') and len(self.backup_pic_list) > 0:
                    self.backup_ssid = min(self.backup_ssid, len(self.backup_pic_list) - 1)
                    self.backup_ssid = max(0, self.backup_ssid)
            except:
                self.backup_ssid = 0
        finally:
            # 清除撤销操作标志
            self._in_undo_operation = False

    def next_step(self):
        # 检查是否在钉图模式下
        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
            # 钉图模式下，调用钉图窗口的前进方法
            if hasattr(self.current_pinned_window, 'next_step'):
                self.current_pinned_window.next_step()
            else:
                print("⚠️ 钉图窗口没有前进方法")
            return
        
        if self.backup_ssid < len(self.backup_pic_list) - 1:
            # 移除了下一步提示
            self.backup_ssid += 1
            self.return_shortshot()
        else:
            # 移除了没有下一步了提示
            print("重做调试: 已经是最新步骤，不能再重做")

    def return_shortshot(self):
        try:
            print("还原", self.backup_ssid, len(self.backup_pic_list))
            
            # 安全检查：确保索引有效
            if not hasattr(self, 'backup_pic_list') or not self.backup_pic_list:
                print("⚠️ backup_pic_list为空，无法还原")
                return
                
            if self.backup_ssid < 0 or self.backup_ssid >= len(self.backup_pic_list):
                print(f"⚠️ backup_ssid索引无效: {self.backup_ssid}, 列表长度: {len(self.backup_pic_list)}")
                self.backup_ssid = max(0, min(self.backup_ssid, len(self.backup_pic_list) - 1))
                
            pix = self.backup_pic_list[self.backup_ssid]
            
            # 检查pixmap是否有效
            if pix is None or pix.isNull():
                print("⚠️ 备份的pixmap无效，跳过还原")
                return
            
            # 检查是否在钉图模式下
            if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
                # 钉图模式下，更新钉图窗口的paintlayer
                if hasattr(self.current_pinned_window, 'paintlayer') and self.current_pinned_window.paintlayer:
                    # 将撤回的图像缩放到当前钉图窗口尺寸，避免范围回退和变形
                    try:
                        target_w = int(self.current_pinned_window.width())
                        target_h = int(self.current_pinned_window.height())
                        if pix.width() != target_w or pix.height() != target_h:
                            scaled_pix = pix.scaled(target_w, target_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                        else:
                            scaled_pix = pix
                        self.current_pinned_window.paintlayer.setPixmap(scaled_pix)
                        # 再次同步绘画层几何与内容，确保完全对齐
                        if hasattr(self.current_pinned_window, '_sync_paintlayer_on_resize'):
                            self.current_pinned_window._sync_paintlayer_on_resize(target_w, target_h)
                        self.current_pinned_window.paintlayer.update()
                        print("钉图模式撤销: 更新并缩放paintlayer以匹配当前尺寸")
                    except Exception as e:
                        print(f"⚠️ 钉图模式撤销缩放失败: {e}")
                else:
                    # 没有绘画层时，直接更新底图，也按当前窗口尺寸缩放
                    try:
                        target_w = int(self.current_pinned_window.width())
                        target_h = int(self.current_pinned_window.height())
                        if pix.width() != target_w or pix.height() != target_h:
                            scaled_pix = pix.scaled(target_w, target_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                        else:
                            scaled_pix = pix
                        self.current_pinned_window.setPixmap(scaled_pix)
                        self.current_pinned_window.update()
                        print("钉图模式撤销: 更新并缩放钉图窗口底图")
                    except Exception as e:
                        print(f"⚠️ 钉图模式撤销（无绘画层）缩放失败: {e}")
            else:
                # 正常截图模式
                self.setPixmap(pix)
                if hasattr(self, 'paintlayer') and self.paintlayer and self.paintlayer.pixmap():
                    self.paintlayer.pixmap().fill(Qt.transparent)
                    self.paintlayer.update()
                self.update()
                
        except Exception as e:
            print(f"⚠️ 还原截图时出错: {e}")
            print(f"详细错误信息: {sys.exc_info()}")
            # 尝试恢复到安全状态
            try:
                if hasattr(self, 'backup_pic_list') and len(self.backup_pic_list) > 0:
                    self.backup_ssid = 0  # 回到初始状态
                    if not self.backup_pic_list[0].isNull():
                        self.setPixmap(self.backup_pic_list[0])
                        self.update()
            except:
                pass
    
    def start_long_screenshot_mode(self):
        """启动长截图模式"""
        print("🖱️ 启动长截图模式...")
        
        # 获取当前选中的区域
        if hasattr(self, 'x0') and hasattr(self, 'y0') and hasattr(self, 'x1') and hasattr(self, 'y1'):
            x0, y0, x1, y1 = self.x0, self.y0, self.x1, self.y1
            
            # 确保坐标有效
            if x0 >= 0 and y0 >= 0 and x1 > x0 and y1 > y0:
                # 获取真实的屏幕坐标（需要考虑虚拟桌面偏移）- 与钉图窗口逻辑一致
                real_x0 = min(x0, x1)
                real_y0 = min(y0, y1)
                real_width = abs(x1 - x0)
                real_height = abs(y1 - y0)
                
                # 如果有虚拟桌面偏移，需要转换为真实坐标（与钉图窗口完全一致）
                if hasattr(self, 'virtual_desktop_offset_x'):
                    real_x0 += self.virtual_desktop_offset_x
                    real_y0 += self.virtual_desktop_offset_y
                    print(f"🔧 [长截图] 坐标转换: 虚拟({min(x0, x1)}, {min(y0, y1)}) -> 真实({real_x0}, {real_y0})")
                
                # 创建选区矩形（使用真实坐标）
                from PyQt5.QtCore import QRect
                capture_rect = QRect(real_x0, real_y0, real_width, real_height)
                
                print(f"📐 选中区域（真实坐标）: {capture_rect}")
                
                # 验证目标显示器检测
                target_screen = self.get_screen_for_rect(real_x0, real_y0, real_x0 + real_width, real_y0 + real_height)
                screen_rect = target_screen.geometry().getRect()
                print(f"🎯 [长截图] 检测到目标显示器: x={screen_rect[0]}, y={screen_rect[1]}, w={screen_rect[2]}, h={screen_rect[3]}")
                
                # 导入必要的模块
                from jietuba_scroll import ScrollCaptureWindow
                from jietuba_stitch import stitch_images_vertical
                from PyQt5.QtWidgets import QApplication, QMessageBox
                from PyQt5.QtGui import QImage
                
                # 隐藏当前截图窗口
                self.hide()
                
                # 创建滚动截图窗口
                self.scroll_capture_window = ScrollCaptureWindow(capture_rect, self)
                
                # 连接信号
                self.scroll_capture_window.finished.connect(self._on_long_screenshot_finished)
                self.scroll_capture_window.cancelled.connect(self._on_long_screenshot_cancelled)
                
                # 显示窗口前，确保窗口被正确创建
                print(f"🪟 长截图窗口创建完成，准备显示...")
                print(f"   窗口几何信息: x={self.scroll_capture_window.x()}, y={self.scroll_capture_window.y()}, w={self.scroll_capture_window.width()}, h={self.scroll_capture_window.height()}")
                
                # 显示窗口
                self.scroll_capture_window.show()
                self.scroll_capture_window.raise_()
                self.scroll_capture_window.activateWindow()
                
                print("✅ 滚动截图窗口已显示并激活")
                return
        
        # 如果没有有效选区，显示提示
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(None, "警告", "请先选择一个有效的截图区域！")
    
    def _on_long_screenshot_finished(self):
        """长截图完成"""
        print("📸 长截图完成，开始拼接...")
        
        try:
            from jietuba_smart_stitch import auto_stitch
            from jietuba_stitch import stitch_images_vertical
            from PyQt5.QtWidgets import QApplication, QMessageBox
            from PyQt5.QtGui import QImage, QPixmap
            
            # 获取所有截图
            screenshots = self.scroll_capture_window.get_screenshots()
            
            if not screenshots or len(screenshots) == 0:
                QMessageBox.warning(None, "警告", "スクリーンショットが撮影されませんでした。")
                self._cleanup_long_screenshot()
                return
            
            print(f"🖼️ 共有 {len(screenshots)} 张截图，开始拼接...")
            
            # 使用升级后的智能拼接（ORB特征点匹配）
            used_fallback = False  # 标记是否使用了备用拼接方案
            try:
                print("🤖 使用智能拼接（ORB特征点匹配 + RANSAC + 重复过滤）...")
                result_image = auto_stitch(
                    screenshots,
                    mode='smart',
                    min_confidence=0.5,  # 使用推荐的0.5阈值
                    filter_duplicates=True,  # 启用重复过滤
                    duplicate_high_threshold=0.6,  # 连续两图重复率>60%
                    duplicate_low_threshold=0.2  # 隔一图重复率>20%
                )
                print("✅ 智能拼接完成")
            except Exception as e:
                print(f"⚠️ 智能拼接失败: {e}，使用简单拼接")
                used_fallback = True  # 标记使用了备用方案
                # 使用简单拼接作为最终后备方案
                result_image = stitch_images_vertical(
                    screenshots,
                    align='left',
                    spacing=0,
                    bg_color=(255, 255, 255)
                )
            
            print(f"✅ 拼接完成，图片大小: {result_image.size}")
            
            # 将PIL Image转换为QImage
            if result_image.mode == 'RGB':
                qimage = QImage(
                    result_image.tobytes(),
                    result_image.width,
                    result_image.height,
                    result_image.width * 3,
                    QImage.Format_RGB888
                )
            elif result_image.mode == 'RGBA':
                qimage = QImage(
                    result_image.tobytes(),
                    result_image.width,
                    result_image.height,
                    result_image.width * 4,
                    QImage.Format_RGBA8888
                )
            else:
                result_image = result_image.convert('RGB')
                qimage = QImage(
                    result_image.tobytes(),
                    result_image.width,
                    result_image.height,
                    result_image.width * 3,
                    QImage.Format_RGB888
                )
            
            # 转换为QPixmap
            pixmap = QPixmap.fromImage(qimage)
            
            # 保存到文件（使用与普通截图相同的保存目录）
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"長スクショ_{timestamp}.png"
            filepath = os.path.join(self.screenshot_save_dir, filename)
            
            try:
                # 使用PIL保存，质量更好
                result_image.save(filepath, 'PNG', optimize=True)
                print(f"💾 长截图已保存: {filepath}")
            except Exception as save_error:
                print(f"⚠️ 保存长截图文件失败: {save_error}")
                # 即使保存失败，也继续复制到剪贴板
            
            # 复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(pixmap)
            
            print("✅ 长截图已复制到剪贴板")
            
            # 只在使用备用方案时显示提示消息
            if used_fallback:
                QMessageBox.information(
                    None,
                    "長スクショ完了",
                    f"長スクリーンショットが完了しました。\n{len(screenshots)} 枚の画像を結合\n\n※ スマート結合に失敗したため、シンプル結合を使用しました。\nクリップボードにコピーされました。"
                )
            
        except Exception as e:
            print(f"❌ 拼接长截图失败: {e}")
            import traceback
            traceback.print_exc()
            
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                None,
                "エラー",
                f"長スクリーンショットの結合中にエラーが発生しました:\n{str(e)}"
            )
        
        finally:
            # 清理并关闭
            self._cleanup_long_screenshot()
    
    def _on_long_screenshot_cancelled(self):
        """长截图被取消"""
        print("❌ 长截图被取消")
        self._cleanup_long_screenshot()
    
    def _cleanup_long_screenshot(self):
        """清理长截图资源并关闭截图窗口"""
        try:
            # 清理滚动截图窗口
            if hasattr(self, 'scroll_capture_window'):
                self.scroll_capture_window.close()
                self.scroll_capture_window.deleteLater()
                del self.scroll_capture_window
            
            # 关闭截图窗口
            self.clear_and_hide()
            
        except Exception as e:
            print(f"⚠️ 清理长截图资源时出错: {e}")

    def freeze_img(self):
        # 设置钉图创建标志，防止在关闭绘画工具时意外触发备份
        self._creating_pinned_window = True
        
        # 在进入钉图模式前，关闭所有绘制工具
        print("🎨 钉图前检查：关闭所有绘制工具")
        drawing_tools_active = False
        
        # 检查并关闭所有绘制工具
        for tool_name, is_active in self.painter_tools.items():
            if is_active:
                print(f"🎨 关闭绘制工具: {tool_name}")
                self.painter_tools[tool_name] = 0
                drawing_tools_active = True
        
        # 如果有文字输入框正在显示，先提交或清理
        if hasattr(self, 'text_box') and self.text_box.isVisible():
            print("🎨 检测到文字输入框，进行清理")
            # 如果有文字内容，尝试提交
            if self.text_box.toPlainText().strip():
                print(f"💾 保存正在绘制的文字内容: '{self.text_box.toPlainText().strip()}'")
                self.text_box.paint = True
                
                # 触发文字提交处理 - 改进的保存逻辑
                try:
                    from jietuba_text_drawer import UnifiedTextDrawer
                    
                    # 确保绘画层存在
                    if hasattr(self, 'paintlayer') and self.paintlayer:
                        # 获取绘画层的painter
                        paint_pixmap = self.paintlayer.pixmap()
                        if paint_pixmap:
                            painter = QPainter(paint_pixmap)
                            painter.setRenderHint(QPainter.Antialiasing)
                            
                            # 执行文字绘制
                            success = UnifiedTextDrawer.process_text_drawing(self, painter, self.text_box)
                            painter.end()
                            
                            if success:
                                # 更新绘画层显示
                                self.paintlayer.setPixmap(paint_pixmap)
                                print("✅ 文字已成功保存到绘画层")
                            else:
                                print("⚠️ 文字保存可能失败")
                        else:
                            print("⚠️ 绘画层pixmap无效")
                    else:
                        print("⚠️ 绘画层不存在")
                        
                    # 强制刷新显示
                    self.update()
                    QApplication.processEvents()
                    
                except Exception as e:
                    print(f"🎨 文字提交时出错: {e}")
            else:
                print("🔄 没有文字内容需要保存")
            
            # 隐藏文字输入框
            self.text_box.hide()
            self.text_box.clear()
            self.text_box.paint = False
        
        # 恢复工具按钮的视觉状态
        if drawing_tools_active:
            self.restore_painter_tools_visual_state()
            print("🎨 绘制工具已全部关闭，进入钉图模式")
        
        self.cutpic(save_as=2)
        
        # 获取真实的屏幕坐标（需要考虑虚拟桌面偏移）
        real_x0 = min(self.x0, self.x1)
        real_y0 = min(self.y0, self.y1)
        real_x1 = max(self.x0, self.x1)
        real_y1 = max(self.y0, self.y1)
        
        # 如果有虚拟桌面偏移，需要转换为真实坐标
        if hasattr(self, 'virtual_desktop_offset_x'):
            real_x0 += self.virtual_desktop_offset_x
            real_y0 += self.virtual_desktop_offset_y
            real_x1 += self.virtual_desktop_offset_x
            real_y1 += self.virtual_desktop_offset_y
        
        print(f"截图区域: 虚拟({min(self.x0, self.x1)}, {min(self.y0, self.y1)}) -> 真实({real_x0}, {real_y0})")
        
        # 获取截图区域所在的显示器
        target_screen = self.get_screen_for_rect(real_x0, real_y0, real_x1, real_y1)
        
        # 确保钉图窗口位置在正确的显示器内
        initial_x = real_x0
        initial_y = real_y0
        window_width = self.final_get_img.width()
        window_height = self.final_get_img.height()
        
        # 调整位置确保窗口完全在目标显示器内
        adjusted_x, adjusted_y = self.adjust_position_to_screen(
            initial_x, initial_y, window_width, window_height, target_screen)
        
        print(f"钉图窗口: 初始位置({initial_x}, {initial_y}) -> 调整后({adjusted_x}, {adjusted_y})")
        
        freezer = Freezer(None, self.final_get_img,
                         adjusted_x, adjusted_y,
                         len(self.parent.freeze_imgs), self)
        
        # 保存显示器信息到freezer对象中
        freezer.target_screen = target_screen
        
        # 复制截图时的绘制历史到钉图窗口
        # 计算截图区域坐标（用于从全屏备份中裁剪）
        crop_x = min(self.x0, self.x1)
        crop_y = min(self.y0, self.y1)
        crop_w = max(self.x0, self.x1) - crop_x
        crop_h = max(self.y0, self.y1) - crop_y
        
        print(f"📋 钉图备份: 复制截图历史，裁剪区域: ({crop_x}, {crop_y}, {crop_w}, {crop_h})")
        freezer.copy_screenshot_backup_history(crop_x, crop_y, crop_w, crop_h)
        
        # 在创建钉图窗口时自动保存图片到桌面上的スクショ文件夹
        try:
            timestamp = time.strftime("%Y-%m-%d_%H.%M.%S", time.localtime())
            filename = f"pinned_{timestamp}.png"
            save_path = os.path.join(self.screenshot_save_dir, filename)
            
            # 如果有绘画层内容，需要合并后保存
            if hasattr(self, 'paintlayer') and self.paintlayer and self.paintlayer.pixmap():
                # 创建合并图像
                merged_img = QPixmap(self.final_get_img.size())
                merged_img.fill(Qt.transparent)
                
                painter = QPainter(merged_img)
                painter.setRenderHint(QPainter.Antialiasing)
                # 先绘制原图
                painter.drawPixmap(0, 0, self.final_get_img)
                # 再绘制绘画层
                painter.drawPixmap(0, 0, self.paintlayer.pixmap())
                painter.end()
                
                success = merged_img.save(save_path, "PNG")
            else:
                # 没有绘画层，直接保存原图
                success = self.final_get_img.save(save_path, "PNG")
            
            if success:
                print(f"✅ 钉图窗口已自动保存到: {save_path}")
                # 移除了已保存提示
            else:
                print(f"❌ 钉图窗口保存失败: {save_path}")
                
        except Exception as e:
            print(f"❌ 钉图窗口自动保存出错: {e}")
        
        self.parent.freeze_imgs.append(freezer)
        # 设置标志表示刚刚创建了钉图窗口，main.py中的_on_screenshot_end会检查这个标志
        if hasattr(self.parent, '_just_created_pin_window'):
            self.parent._just_created_pin_window = True
        
        # 清除钉图创建标志
        self._creating_pinned_window = False
        
        # 创建钉图窗口后不再强制显示主窗口，保持托盘状态
        # if not QSettings('Fandes', 'jietuba').value("S_SIMPLE_MODE", False, bool):
        #     self.parent.show()
        self.clear_and_hide()

    # OCR功能已移除
    # def ocr(self):
    #     # 在执行OCR前，先保存当前的绘制状态（如果有正在输入的文字）
    #     print("📝 [OCR] 执行OCR前，保存当前绘制状态")
    #     self._reset_text_box_completely()
    #     
    #     # 移除了正在识别提示
    #     
    #     # 检查是否为钉图模式
    #     if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
    #         # 钉图模式下，直接在钉图窗口中进行OCR
    #         self.current_pinned_window.ocr()
    #     else:
    #         # 正常截图模式，创建新的OCR窗口
    #         self.cutpic(save_as=2)
    #         
    #         # 获取真实的屏幕坐标（需要考虑虚拟桌面偏移）
    #         real_x0 = min(self.x0, self.x1)
    #         real_y0 = min(self.y0, self.y1)
    #         real_x1 = max(self.x0, self.x1)
    #         real_y1 = max(self.y0, self.y1)
    #         
    #         # 如果有虚拟桌面偏移，需要转换为真实坐标
    #         if hasattr(self, 'virtual_desktop_offset_x'):
    #             real_x0 += self.virtual_desktop_offset_x
    #             real_y0 += self.virtual_desktop_offset_y
    #             real_x1 += self.virtual_desktop_offset_x
    #             real_y1 += self.virtual_desktop_offset_y
    #         
    #         print(f"OCR区域: 虚拟({min(self.x0, self.x1)}, {min(self.y0, self.y1)}) -> 真实({real_x0}, {real_y0})")
    #         
    #         # 获取截图区域所在的显示器
    #         target_screen = self.get_screen_for_rect(real_x0, real_y0, real_x1, real_y1)
    #         
    #         # 确保OCR窗口位置在正确的显示器内
    #         initial_x = real_x0
    #         initial_y = real_y0
    #         window_width = self.final_get_img.width()
    #         window_height = self.final_get_img.height()
    #         
    #         # 调整位置确保窗口完全在目标显示器内
    #         adjusted_x, adjusted_y = self.adjust_position_to_screen(
    #             initial_x, initial_y, window_width, window_height, target_screen)
    #         
    #         print(f"OCR窗口: 初始位置({initial_x}, {initial_y}) -> 调整后({adjusted_x}, {adjusted_y})")
    #         
    #         self.ocr_freezer = Freezer(None, self.final_get_img, adjusted_x, adjusted_y,
    #                                    len(self.parent.freeze_imgs), self)
    #         
    #         # 保存显示器信息到freezer对象中
    #         self.ocr_freezer.target_screen = target_screen
    #         
    #         self.ocr_freezer.ocr()
    #     QApplication.processEvents()

    # OCR结果处理方法已移除
    # def ocr_res_signalhandle(self, text):
    #     self.shower.setPlaceholderText("")
    #     self.shower.insertPlainText(text)
    #     # jt = re.sub(r'[^\w]', '', text).replace('_', '')
    #     # n = 0
    #     # for i in text:
    #     #     if self.is_alphabet(i):
    #     #         n += 1
    #     # if n / len(jt) > 0.4:
    #     #     print("is en")
    #     #     self.shower.tra()

    # 翻译功能已移除
    # def open_translate(self):
    #     """打开详细翻译功能"""
    #     # 在执行翻译前，先保存当前的绘制状态（如果有正在输入的文字）
    #     print("🌐 [翻译] 执行翻译前，保存当前绘制状态")
    #     self._reset_text_box_completely()
    #     
    #     # 移除了OCR識別中提示
    #     
    #     if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
    #         # 钉图模式下，直接使用钉图窗口的图像
    #         temp_path = 'j_temp/translate_temp.png'  # 临时文件仍使用j_temp
    #         self.current_pinned_window.showing_imgpix.save(temp_path)
    #     else:
    #         # 正常截图模式
    #         self.cutpic(save_as=2)
    #         temp_path = 'j_temp/translate_temp.png'  # 临时文件仍使用j_temp
    #         self.final_get_img.save(temp_path)
    # 
    #     # 直接进行OCR识别
    #     import cv2
    #     from jampublic import CONFIG_DICT
    #     img = cv2.imread(temp_path)
    #     self.translate_ocrthread = OcrimgThread(img, lang=CONFIG_DICT.get('ocr_lang', 'ch'))
    #     self.translate_ocrthread.result_show_signal.connect(self.translate_ocr_result_handler)
    #     self.translate_ocrthread.start()
    # 
    # def translate_ocr_result_handler(self, text):
    #     """处理OCR识别结果并打开翻译"""
    #     if text and text.strip():
    #         # 对文本进行URL编码
    #         from urllib.parse import quote
    #         encoded_text = quote(text.strip())
    #         
    #         # 构造Google翻译URL
    #         url = 'https://translate.google.com/?sl=auto&tl=ja&text=' + encoded_text + '&op=translate'
    #         
    #         # 打开浏览器
    #         from PyQt5.QtGui import QDesktopServices
    #         from PyQt5.QtCore import QUrl
    #         QDesktopServices.openUrl(QUrl(url))
    #         
    #         # 移除了已打开详细翻译提示
    #         # 截图完成，清理界面
    #         self.clear_and_hide()
    #     else:
    #         # 移除了未识别到文字提示
    #         # 等待2秒后清理界面
    #         QTimer.singleShot(2000, self.clear_and_hide)

    def is_alphabet(self, uchar):
        """判断一个unicode是否是英文字母"""
        if (u'\u0041' <= uchar <= u'\u005a') or (u'\u0061' <= uchar <= u'\u007a'):
            return True
        else:
            return False

    def copy_pinned_image(self):
        """复制钉图窗口的图片（包含绘画内容）"""
        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
            try:
                # 使用钉图窗口的合并图像方法
                if hasattr(self.current_pinned_window, '_create_merged_image'):
                    final_img = self.current_pinned_window._create_merged_image()
                else:
                    # 如果没有合并方法，使用原始图片
                    final_img = self.current_pinned_window.showing_imgpix
                
                # 复制到剪贴板
                clipboard = QApplication.clipboard()
                clipboard.setPixmap(final_img)
                
                # 显示提示
                # 移除了画像をコピーしました提示
                print("✅ 已复制钉图图像到剪贴板")
            except Exception as e:
                print(f"❌ 复制钉图图像失败: {e}")
                # 移除了コピー失敗提示
        else:
            print("❌ 复制失败：当前不在钉图模式")
            # 移除了コピー失敗提示


    def choice(self):  # 选区完毕后显示选择按钮的函数
        self.choicing = True

        # 钉图模式下，不重新定位工具栏，保持在钉图窗口附近的位置
        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
            # 钉图模式：保持工具栏当前位置，不做移动
            self.botton_box.show()
            return

        # 统一从选区所在显示器出发定位工具栏，防止跨屏显示
        selection_left = min(self.x0, self.x1)
        selection_top = min(self.y0, self.y1)
        selection_right = max(self.x0, self.x1)
        selection_bottom = max(self.y0, self.y1)

        offset_x = getattr(self, 'virtual_desktop_offset_x', 0)
        offset_y = getattr(self, 'virtual_desktop_offset_y', 0)

        selection_global_left = selection_left + offset_x
        selection_global_top = selection_top + offset_y
        selection_global_right = selection_right + offset_x
        selection_global_bottom = selection_bottom + offset_y

        target_screen = self.get_screen_for_rect(
            selection_global_left, selection_global_top,
            selection_global_right, selection_global_bottom
        )
        screen_geo = target_screen.geometry()
        screen_x = screen_geo.x()
        screen_y = screen_geo.y()
        screen_right = screen_x + screen_geo.width()
        screen_bottom = screen_y + screen_geo.height()

        toolbar_width = self.botton_box.width()
        toolbar_height = self.botton_box.height()
        spacing = 10

        # 智能布局：根据屏幕边界自动调整工具栏位置
        # 1. 判断垂直位置：优先下方，超出则上方
        if selection_global_bottom + spacing + toolbar_height <= screen_bottom:
            # 下方有足够空间
            toolbar_y = selection_global_bottom + spacing
        else:
            # 下方空间不足，放在上方
            toolbar_y = selection_global_top - toolbar_height - spacing
            # 如果上方也不够，则贴着屏幕底部
            if toolbar_y < screen_y:
                toolbar_y = screen_bottom - toolbar_height - spacing

        # 2. 判断水平位置：优先右对齐，超出则左对齐
        if selection_global_right - toolbar_width >= screen_x:
            # 右对齐不会超出左边界
            toolbar_x = selection_global_right - toolbar_width
        else:
            # 右对齐会超出左边界，改为左对齐
            toolbar_x = selection_global_left
            # 如果左对齐会超出右边界，则贴着屏幕右边
            if toolbar_x + toolbar_width > screen_right:
                toolbar_x = screen_right - toolbar_width

        # 3. 最终边界检查：确保工具栏完全在屏幕内
        toolbar_x = max(screen_x, min(toolbar_x, screen_right - toolbar_width))
        toolbar_y = max(screen_y, min(toolbar_y, screen_bottom - toolbar_height))

        chosen_global = (toolbar_x, toolbar_y)

        local_x = int(round(chosen_global[0] - offset_x))
        local_y = int(round(chosen_global[1] - offset_y))

        # 确保局部坐标仍在截图窗口内部，避免负值或越界
        local_x = max(0, min(local_x, self.width() - toolbar_width))
        local_y = max(0, min(local_y, self.height() - toolbar_height))

        self.botton_box.move(local_x, local_y)
        self.botton_box.show()

    def handle_save_button_click(self):
        """处理保存按钮点击 - 根据当前模式选择不同的保存方式"""
        # 在保存前，先保存当前的绘制状态（如果有正在输入的文字）
        print("💾 [保存] 执行保存前，保存当前绘制状态")
        self._reset_text_box_completely()
        
        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
            # 钉图模式：使用新的合成保存接口
            self.save_pinned_window_with_composite()
        else:
            # 普通截图模式：使用原来的保存方式
            self.cutpic(1)

    def save_pinned_window_with_composite(self):
        """钉图窗口的新保存接口 - 先合成绘画层和图片层，再保存并可选择位置和重命名"""
        try:
            if not hasattr(self, 'current_pinned_window') or not self.current_pinned_window:
                # 移除了无有效的钉图窗口提示
                return
            
            # 1. 创建合成图像 - 合并图片层和绘画层
            composite_image = self.create_composite_image_for_pinned_window()
            if not composite_image or composite_image.isNull():
                # 移除了无法创建合成图像提示
                return
            
            # 2. 弹出保存对话框，允许用户选择位置和重命名
            default_name = f"PinnedWindow_{time.strftime('%Y-%m-%d_%H.%M.%S', time.localtime())}.png"
            file_path, file_type = QFileDialog.getSaveFileName(
                self, 
                "保存钉图窗口", 
                QStandardPaths.writableLocation(QStandardPaths.PicturesLocation) + "/" + default_name,
                "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;BMP Files (*.bmp);;All Files (*.*)"
            )
            
            # 3. 如果用户选择了路径，则保存合成图像
            if file_path:
                success = composite_image.save(file_path)
                if success:
                    # 移除了已保存到提示
                    print(f"✅ 钉图窗口已保存到: {file_path}")
                else:
                    # 移除了保存失败提示
                    print(f"❌ 保存失败: {file_path}")
            else:
                print("用户取消了保存操作")
                
        except Exception as e:
            # 移除了保存出错提示
            print(f"❌ 钉图窗口保存出错: {e}")

    def create_composite_image_for_pinned_window(self):
        """为钉图窗口创建合成图像 - 合并图片层和绘画层"""
        try:
            if not hasattr(self, 'current_pinned_window') or not self.current_pinned_window:
                return QPixmap()
            
            # 获取钉图窗口的基础图像
            base_image = self.current_pinned_window.showing_imgpix
            if not base_image or base_image.isNull():
                print("⚠️ 钉图窗口没有有效的基础图像")
                return QPixmap()
            
            # 创建与钉图窗口尺寸相同的画布（使用原始图像尺寸，不是窗口显示尺寸）
            composite_pixmap = QPixmap(base_image.size())
            composite_pixmap.fill(Qt.transparent)
            
            painter = QPainter(composite_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 1. 绘制基础图像
            painter.drawPixmap(0, 0, base_image)
            
            # 2. 绘制绘画层内容（如果存在）
            if (hasattr(self.current_pinned_window, 'paintlayer') and 
                self.current_pinned_window.paintlayer and 
                hasattr(self.current_pinned_window.paintlayer, 'pixmap')):
                
                paint_content = self.current_pinned_window.paintlayer.pixmap()
                if paint_content and not paint_content.isNull():
                    # 计算缩放比例，将绘画层内容缩放到与基础图像相同的尺寸
                    window_size = self.current_pinned_window.size()
                    base_size = base_image.size()
                    
                    # 如果绘画层和基础图像尺寸不同，需要缩放绘画层
                    if window_size != base_size:
                        # 缩放绘画层内容到基础图像的尺寸
                        scaled_paint_content = paint_content.scaled(
                            base_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                        )
                        painter.drawPixmap(0, 0, scaled_paint_content)
                        print(f"✅ 已缩放并合并绘画层: {window_size} -> {base_size}")
                    else:
                        painter.drawPixmap(0, 0, paint_content)
                        print("✅ 已合并绘画层内容")
                else:
                    print("ℹ️ 绘画层为空")
            else:
                print("ℹ️ 没有绘画层")
            
            painter.end()
            
            print(f"✅ 成功创建合成图像，尺寸: {composite_pixmap.width()}x{composite_pixmap.height()}")
            return composite_pixmap
            
        except Exception as e:
            print(f"❌ 创建合成图像失败: {e}")
            return QPixmap()

    def cutpic(self, save_as=0):  # 裁剪图片
        """裁剪图片,0:正常截图保存模式, 1:另存为模式, 2:内部调用保存图片, 3:内部调用,直接返回图片"""
        # 在截图保存前，先保存正在绘制的文字内容
        if save_as in [0, 1]:  # 只在实际保存时执行，内部调用不需要
            print("📸 [截图保存] 执行保存前，检查并保存正在绘制的内容")
            self._reset_text_box_completely()
        
        self.sshoting = False
        
        # 在钉图模式下，直接使用钉图窗口的内容
        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
            # 钉图模式：获取钉图窗口的完整内容（包括绘画层）
            if hasattr(self.current_pinned_window, 'paintlayer') and self.current_pinned_window.paintlayer:
                # 合成钉图窗口的背景图和绘画层
                base_pixmap = self.current_pinned_window.showing_imgpix
                paint_pixmap = self.current_pinned_window.paintlayer.pixmap()
                
                final_pixmap = QPixmap(base_pixmap.size())
                painter = QPainter(final_pixmap)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.drawPixmap(0, 0, base_pixmap)  # 绘制背景
                if paint_pixmap:
                    painter.drawPixmap(0, 0, paint_pixmap)  # 绘制绘画层
                painter.end()
                
                self.final_get_img = final_pixmap
            else:
                # 没有绘画层，直接使用原始图像
                self.final_get_img = self.current_pinned_window.showing_imgpix
            
            # 钉图模式下的保存处理
            if save_as == 1:
                path, l = QFileDialog.getSaveFileName(self, "保存为", QStandardPaths.writableLocation(
                    QStandardPaths.PicturesLocation), "img Files (*.PNG *.jpg *.JPG *.JPEG *.BMP *.ICO)"
                                                      ";;all files(*.*)")
                if path:
                    print(f"钉图模式保存: {path}")
                    self.final_get_img.save(path)
                    return
                else:
                    return
            elif save_as == 2:
                return
            elif save_as == 3:
                return self.final_get_img
            
            # 钉图模式下的其他处理
            return
        
        # 正常截图模式的处理
        transparentpix = self.pixmap().copy()
        paintlayer = self.paintlayer.pixmap()
        painter = QPainter(transparentpix)
        painter.setRenderHint(QPainter.Antialiasing)
        if paintlayer:  # 添加安全检查
            painter.drawPixmap(0, 0, paintlayer)
        painter.end()  # 一定要end
        if save_as == 3:  # 油漆桶工具
            return transparentpix

        pix = QPixmap(transparentpix.width(), transparentpix.height())
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(0, 0, transparentpix)
        p.end()

        x0 = min(self.x0, self.x1)
        y0 = min(self.y0, self.y1)
        x1 = max(self.x0, self.x1)
        y1 = max(self.y0, self.y1)
        w = x1 - x0
        h = y1 - y0

        # print(x0, y0, x1, y1)
        if (x1 - x0) < 1 or (y1 - y0) < 1:
            # 移除了范围过小<1提示
            return
        self.final_get_img = pix.copy(x0, y0, w, h)

        if save_as:
            if save_as == 1:
                path, l = QFileDialog.getSaveFileName(self, "保存为", QStandardPaths.writableLocation(
                    QStandardPaths.PicturesLocation), "img Files (*.PNG *.jpg *.JPG *.JPEG *.BMP *.ICO)"
                                                      ";;all files(*.*)")
                if path:
                    print(path)
                    self.final_get_img.save(path)  # 保存裁剪后的图像，而不是整个画面
                    self.clear_and_hide()
                else:
                    return
            elif save_as == 2:
                return
        if __name__ == '__main__':  # 当直接运行本文件时直接保存,测试用
            # 使用新的保存目录
            filepath = os.path.join(self.screenshot_save_dir, '{}.png'.format(CONFIG_DICT["last_pic_save_name"]))
            self.final_get_img.save(filepath)
            QApplication.clipboard().setPixmap(self.final_get_img)
            print(f"已复制到剪切板并保存到: {filepath}")
            self.clear_and_hide()
            return
        # 以下为作者软件的保存操作,懒得删了...
        if self.mode == "set_area":
            area = [x0,y0,(x1 - x0 + 1) // 2 * 2,(y1 - y0 + 1) // 2 * 2]
            if area[2] == 0 or area[3] == 0:
                # 移除了选择范围过小提示
                pass
            else:
                self.set_area_result_signal.emit(area)
            if not QSettings('Fandes', 'jietuba').value("S_SIMPLE_MODE", False, bool):
                # 检查主窗口截图前的可见状态，只有原本可见才显示
                if hasattr(self.parent, '_was_visible') and self.parent._was_visible:
                    self.parent.show()
        elif self.mode == "getpix":
            self.getpix_result_signal.emit((x0, y0, w, h),self.final_get_img)
            if not QSettings('Fandes', 'jietuba').value("S_SIMPLE_MODE", False, bool):
                # 检查主窗口截图前的可见状态，只有原本可见才显示
                if hasattr(self.parent, '_was_visible') and self.parent._was_visible:
                    self.parent.show()
        else:
            def save():
                CONFIG_DICT["last_pic_save_name"]="{}".format( str(time.strftime("%Y-%m-%d_%H.%M.%S", time.localtime())))
                # 使用新的保存目录（桌面上的スクショ文件夹）
                filepath = os.path.join(self.screenshot_save_dir, '{}.png'.format(CONFIG_DICT["last_pic_save_name"]))
                self.final_get_img.save(filepath)
                if self.mode == "screenshot":
                    self.screen_shot_result_signal.emit(filepath)
                print(f'截图已保存到: {filepath}')

            self.save_data_thread = Commen_Thread(save)
            self.save_data_thread.start()
            st = time.process_time()
            self.manage_data()
            print('managetime:', time.process_time() - st)
        self.clear_and_hide()

    def manage_data(self):
        """截屏完之后数据处理,不用可自己写"""
        if self.mode == "screenshot":
            if not QSettings('Fandes', 'jietuba').value("S_SIMPLE_MODE", False, bool):
                self.screen_shot_end_show_sinal.emit(self.final_get_img)

            clipboard = QApplication.clipboard()
            try:
                if self.parent.settings.value('screenshot/copy_type_ss', '图像数据', type=str) == '图像数据':
                    clipboard.setPixmap(self.final_get_img)
                    print('sava 图像数据')
                    # 移除了图像数据已复制到剪切板提示
                elif self.parent.settings.value('screenshot/copy_type_ss', '图像数据', type=str) == '图像文件':
                    if hasattr(self, 'save_data_thread'):
                        self.save_data_thread.wait()
                    data = QMimeData()
                    # 使用新的保存路径
                    filepath = os.path.join(self.screenshot_save_dir, '{}.png'.format(CONFIG_DICT["last_pic_save_name"]))
                    url = QUrl.fromLocalFile(filepath)
                    data.setUrls([url])
                    clipboard.setMimeData(data)
                    print('save url {}'.format(url))
                    # 移除了图像文件已复制到剪切板提示
            except:
                clipboard.setPixmap(self.final_get_img)
                # 移除了图像数据已复制到剪切板提示
        elif self.mode == "ocr":
            try:
                if hasattr(self, 'save_data_thread'):
                    self.save_data_thread.wait()
                # 使用新的保存路径
                filepath = os.path.join(self.screenshot_save_dir, '{}.png'.format(CONFIG_DICT["last_pic_save_name"]))
                self.ocr_image_signal.emit(filepath)
            except:
                print(sys.exc_info(), 1822)

        # self.save_data_thread.wait()
        # self.clear()

        # self.close()

    # =====================
    # 已绘制文字区域二次编辑（选中/移动/缩放）辅助方法
    # =====================
    def _hit_test_selection_handle(self, x, y):
        # 兜底确保状态存在
        self._ensure_selection_state()
        if not getattr(self, 'selection_active', False):
            return None
        r = self.selection_rect
        handle = 6
        # 八个手柄区域
        cx = r.x() + r.width() // 2
        cy = r.y() + r.height() // 2
        areas = {
            'tl': QRect(r.left()-handle//2, r.top()-handle//2, handle, handle),
            't':  QRect(cx-handle//2, r.top()-handle//2, handle, handle),
            'tr': QRect(r.right()-handle//2, r.top()-handle//2, handle, handle),
            'l':  QRect(r.left()-handle//2, cy-handle//2, handle, handle),
            'r':  QRect(r.right()-handle//2, cy-handle//2, handle, handle),
            'bl': QRect(r.left()-handle//2, r.bottom()-handle//2, handle, handle),
            'b':  QRect(cx-handle//2, r.bottom()-handle//2, handle, handle),
            'br': QRect(r.right()-handle//2, r.bottom()-handle//2, handle, handle),
        }
        pt = QPoint(x, y)
        for k, a in areas.items():
            if a.contains(pt):
                return k
        if r.contains(pt):
            return 'move'
        return None

    def _begin_selection_at(self, x, y):
        """从绘画层pixmap的alpha通道出发，提取点击处连通区域为选区。"""
        pl_pm = self.paintlayer.pixmap()
        if pl_pm is None or pl_pm.isNull():
            return False
        if not (0 <= x < pl_pm.width() and 0 <= y < pl_pm.height()):
            return False
        img = pl_pm.toImage().convertToFormat(QImage.Format_ARGB32)
        col = QColor(img.pixelColor(x, y))
        if col.alpha() < 10:
            return False  # 点击在透明处，不进入选择

        w, h = img.width(), img.height()
        visited = set()
        q = deque()
        q.append((x, y))
        visited.add((x, y))
        minx = maxx = x
        miny = maxy = y
        # 4邻域泛洪
        while q:
            cx, cy = q.popleft()
            # 更新边界
            if cx < minx: minx = cx
            if cx > maxx: maxx = cx
            if cy < miny: miny = cy
            if cy > maxy: maxy = cy
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                    if QColor(img.pixelColor(nx, ny)).alpha() >= 10:
                        visited.add((nx, ny))
                        q.append((nx, ny))

        # 构造选区矩形（加1，因为像素是包含性的）
        rect = QRect(minx, miny, max(1, (maxx - minx + 1)), max(1, (maxy - miny + 1)))
        if rect.width() <= 0 or rect.height() <= 0:
            return False

        # 生成选区图像（裁剪矩形区域）
        sel_pm = pl_pm.copy(rect)

        # 将选区像素从原绘画层抠掉（置透明）
        mod = img
        for (px, py) in visited:
            mod.setPixelColor(px, py, QColor(0, 0, 0, 0))
        new_pm = QPixmap(w, h)
        new_pm.fill(Qt.transparent)
        painter = QPainter(new_pm)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawImage(0, 0, mod)
        painter.end()
        self.paintlayer.setPixmap(new_pm)

        # 保存状态
        self.selection_active = True
        self.selection_rect = rect
        self.selection_original_rect = QRect(rect)
        self.selection_pixmap = sel_pm
        self.selection_scaled_pixmap = QPixmap(sel_pm)  # 初始未缩放
        # 保存像素mask（相对rect左上）
        self.selection_mask = {(px - rect.left(), py - rect.top()) for (px, py) in visited}
        self.selection_dragging = False
        self.selection_resize_edge = None
        self.selection_press_rect = QRect(rect)
        self.selection_press_pos = QPoint(x, y)
        self.selection_press_offset = QPoint(x - rect.left(), y - rect.top())
        self.paintlayer.update()
        return True

    def _update_selection_preview(self):
        # 预览位图按当前rect尺寸缩放
        if self.selection_pixmap and self.selection_rect.width() > 0 and self.selection_rect.height() > 0:
            self.selection_scaled_pixmap = self.selection_pixmap.scaled(
                self.selection_rect.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self.paintlayer.update()

    def _commit_selection(self):
        if not self.selection_active or self.selection_pixmap is None:
            return
        # 把当前预览（可能缩放后）绘制回绘画层
        base = self.paintlayer.pixmap()
        if base is None or base.isNull():
            base = QPixmap(self.width(), self.height())
            base.fill(Qt.transparent)
        painter = QPainter(base)
        painter.setRenderHint(QPainter.Antialiasing)
        # 如有缩放则使用缩放后的位图
        pm = self.selection_scaled_pixmap if self.selection_scaled_pixmap is not None else self.selection_pixmap
        painter.drawPixmap(self.selection_rect.topLeft(), pm)
        painter.end()
        self.paintlayer.setPixmap(base)
        # 结束选择并纳入撤销
        self.selection_active = False
        self.paintlayer.update()
        self.backup_shortshot()

    def _cancel_selection(self):
        # 取消：将原来的选区位图回填到原位置
        if not self.selection_active or self.selection_pixmap is None:
            self.selection_active = False
            self.paintlayer.update()
            return
        base = self.paintlayer.pixmap()
        if base is None or base.isNull():
            base = QPixmap(self.width(), self.height())
            base.fill(Qt.transparent)
        painter = QPainter(base)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(self.selection_original_rect.topLeft(), self.selection_pixmap)
        painter.end()
        self.paintlayer.setPixmap(base)
        self.selection_active = False
        self.paintlayer.update()

    def mouseDoubleClickEvent(self, e):  # 双击
        if e.button() == Qt.LeftButton:
            print("左键双击")

    # 鼠标点击事件
    def _ensure_text_box_focus(self):
        """确保文字输入框能正确获得焦点"""
        try:
            if hasattr(self, 'text_box') and self.text_box.isVisible():
                self.text_box.raise_()
                self.text_box.activateWindow()
                self.text_box.setFocus(Qt.MouseFocusReason)
                print(f"钉图模式: 重新确保文字框焦点，hasFocus={self.text_box.hasFocus()}")
        except Exception as e:
            print(f"确保文字框焦点时出错: {e}")

    def mousePressEvent(self, event):
        # 如果是钉图模式并且有绘图工具激活，检查事件是否来自钉图窗口的委托
        if hasattr(self, 'mode') and self.mode == "pinned" and 1 in self.painter_tools.values():
            # 检查事件是否是全局坐标（来自钉图窗口的委托）
            if not hasattr(event, '_from_pinned_window'):
                print("主窗口鼠标按下调试: 不是委托事件，直接返回")
                return  # 如果不是委托事件，直接返回
            else:
                print("主窗口鼠标按下调试: 收到钉图窗口委托事件")

        if event.button() == Qt.LeftButton:  # 按下了左键
            # 通用：若当前没有选区，且未在输入文字框时，尝试直接点击已绘制像素进入选区模式
            # 条件：未激活任何绘图工具 或 激活的是文字工具（便于二次调整）
            try:
                no_tool_active = not (1 in self.painter_tools.values())
                text_tool_active = bool(self.painter_tools.get('drawtext_on'))
                text_box_visible = hasattr(self, 'text_box') and self.text_box.isVisible()
                if not self.selection_active and not text_box_visible and (no_tool_active or text_tool_active):
                    if self._begin_selection_at(event.x(), event.y()):
                        self.selection_dragging = False  # 初次只是选中，不立即移动
                        print(f"[选区] 直接点击像素进入选中 rect={self.selection_rect}")
                        return
            except Exception as e:
                print(f"[选区] 快速选中尝试异常: {e}")
            self.left_button_push = True
            print(f"主窗口鼠标按下调试: 设置left_button_push=True")
            
            # 添加调试信息
            if hasattr(self, 'mode') and self.mode == "pinned":
                print(f"钉图鼠标按下调试: 有绘图工具={1 in self.painter_tools.values()}, _from_pinned_window={hasattr(event, '_from_pinned_window')}")
            
            # 若已存在选区，优先处理选区的移动/缩放
            if getattr(self, 'selection_active', False):
                handle = self._hit_test_selection_handle(event.x(), event.y())
                if handle:
                    self.selection_press_rect = QRect(self.selection_rect)
                    self.selection_press_pos = QPoint(event.x(), event.y())
                    if handle == 'move':
                        self.selection_dragging = True
                        self.selection_resize_edge = None
                        self.selection_press_offset = QPoint(event.x() - self.selection_rect.left(),
                                                             event.y() - self.selection_rect.top())
                    else:
                        self.selection_resize_edge = handle
                        self.selection_dragging = False
                    return

            if 1 in self.painter_tools.values():  # 如果有绘图工具打开了,说明正在绘图
                # 处理坐标，区分是否来自钉图窗口委托
                if hasattr(event, '_from_pinned_window') and hasattr(self, 'mode') and self.mode == "pinned":
                    # 来自钉图窗口的委托事件，需要转换为相对于绘画层的坐标
                    press_x = event.x()
                    press_y = event.y()
                    print(f"主窗口鼠标按下调试: 钉图委托坐标 x={press_x}, y={press_y}")
                else:
                    # 正常的截图模式
                    press_x = event.x()
                    press_y = event.y()
                    print(f"主窗口鼠标按下调试: 截图模式坐标 x={press_x}, y={press_y}")
                    
                if self.painter_tools['drawrect_bs_on']:
                    # print("ch",self.drawrect_pointlist)
                    self.drawrect_pointlist = [[press_x, press_y], [-2, -2], 0]
                elif self.painter_tools['drawarrow_on']:
                    self.drawarrow_pointlist = [[press_x, press_y], [-2, -2], 0]
                    # self.drawarrow_pointlist[0] = [event.x(), event.y()]
                elif self.painter_tools['drawcircle_on']:
                    self.drawcircle_pointlist = [[press_x, press_y], [-2, -2], 0]
                    print(f"钉图圆形调试: 设置起始点 [{press_x}, {press_y}]")
                    # self.drawcircle_pointlist[0] = [event.x(), event.y()]
                elif self.painter_tools['drawtext_on']:
                    # 文本工具：点击已绘制像素 -> 进入选区编辑；否则创建输入框
                    # 优先命中现有选区的手柄/移动
                    handle = self._hit_test_selection_handle(press_x, press_y)
                    if handle:
                        self.selection_press_rect = QRect(self.selection_rect)
                        self.selection_press_pos = QPoint(press_x, press_y)
                        if handle == 'move':
                            self.selection_dragging = True
                            self.selection_resize_edge = None
                            self.selection_press_offset = QPoint(press_x - self.selection_rect.left(),
                                                                 press_y - self.selection_rect.top())
                        else:
                            self.selection_resize_edge = handle
                            self.selection_dragging = False
                        return
                    # 未有选区则尝试从绘画层提取点击处的连通像素作为选区
                    if not self.selection_active:
                        if self._begin_selection_at(press_x, press_y):
                            # 初始化拖动
                            self.selection_dragging = True
                            self.selection_press_rect = QRect(self.selection_rect)
                            self.selection_press_pos = QPoint(press_x, press_y)
                            self.selection_press_offset = QPoint(press_x - self.selection_rect.left(),
                                                                 press_y - self.selection_rect.top())
                            return
                    # 检查是否已经有文字输入框在显示
                    if hasattr(self, 'text_box') and self.text_box.isVisible():
                        # 检查输入框中是否有文字内容
                        current_text = self.text_box.toPlainText().strip()
                        
                        if current_text:
                            # 如果有文字内容，触发完成输入
                            print(f"🎯 [文字工具] 有文字内容，触发绘制: '{current_text}'")
                            self.text_box.paint = True
                        else:
                            # 如果没有文字内容，视为取消操作，清理相关状态
                            print(f"🎯 [文字工具] 无文字内容，取消操作并清理状态")
                            self.text_box.paint = False
                            # 清理旧的坐标点，因为用户取消了文字输入
                            if len(self.drawtext_pointlist) > 0:
                                print(f"🧹 [文字工具] 清理取消的坐标点: {self.drawtext_pointlist}")
                                self.drawtext_pointlist.clear()
                        
                        self.text_box.hide()
                        
                        # 在钉图模式下，需要触发钉图窗口的paintlayer更新
                        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
                            if hasattr(self.current_pinned_window, 'paintlayer'):
                                self.current_pinned_window.paintlayer.update()
                                print("钉图模式: 触发paintlayer更新以绘制文字")
                        else:
                            self.update()  # 正常截图模式触发主窗口更新
                        
                        # 注意：不要在这里立即clear()，让绘制逻辑自己处理清理
                        # 文字绘制完成后会自动清理输入框和锚点信息
                        return
                    
                    # 重要：在创建新的文字输入框之前，确保完全重置状态
                    self.text_box.clear()  # 清空内容
                    self.text_box.paint = False  # 重置绘制状态
                    if hasattr(self.text_box, '_anchor_base'):
                        delattr(self.text_box, '_anchor_base')  # 清除锚点信息
                    
                    # 关键修复：清理旧的未使用坐标点，避免在错误位置创建文字框
                    if len(self.drawtext_pointlist) > 0:
                        print(f"🧹 [文字工具] 清理旧的坐标点: {self.drawtext_pointlist}")
                        self.drawtext_pointlist.clear()  # 清空所有旧坐标
                    
                    # 在钉图模式下，需要特殊处理文字输入框的位置
                    if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
                        # 钉图模式：将文字框位置转换为全局坐标
                        global_x = self.current_pinned_window.x() + press_x
                        global_y = self.current_pinned_window.y() + press_y
                        
                        # 重新设置文字框属性和位置（每次都重新设置确保正确）
                        self.text_box.setParent(None)  # 清除父窗口关系
                        self.text_box.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
                        self.text_box.setAttribute(Qt.WA_TranslucentBackground, True)
                        
                        # 关键修复：确保文字颜色可见，背景透明
                        # 不要使用透明文字颜色，应该显示为正常颜色供用户输入
                        color = self.pencolor
                        self.text_box.setStyleSheet(f"""
                            QTextEdit {{
                                background: rgba(255, 255, 255, 180);
                                color: rgb({color.red()}, {color.green()}, {color.blue()});
                                border: 1px solid rgba(128, 128, 128, 100);
                                border-radius: 3px;
                                padding: 2px;
                            }}
                        """)
                        
                        # 位置设置
                        self.text_box.move(global_x, global_y)
                        print(f"🎯 [钉图文字框] 设置全局位置: ({global_x}, {global_y}), 钉图位置: ({self.current_pinned_window.x()}, {self.current_pinned_window.y()})")
                        
                    else:
                        # 正常截图模式
                        self.text_box.move(press_x, press_y)
                        print(f"🎯 [截图文字框] 设置位置: ({press_x}, {press_y})")
                        self.text_box.setParent(self)
                        self.text_box.setWindowFlags(Qt.Widget)
                        
                        # 清除透明背景属性（如果之前设置过）
                        self.text_box.setAttribute(Qt.WA_TranslucentBackground, False)
                        # 截图模式使用完全透明背景，只显示文字
                        color = self.pencolor
                        self.text_box.setStyleSheet(f"""
                            QTextEdit {{
                                background: rgba(0, 0, 0, 0);
                                color: rgb({color.red()}, {color.green()}, {color.blue()});
                                border: none;
                                padding: 2px;
                            }}
                        """)
                    
                    self.drawtext_pointlist.append([press_x, press_y])
                    print(f"🎯 [文字工具] 添加坐标点到drawtext_pointlist: [{press_x}, {press_y}]")
                    self.text_box.setFont(QFont('', self.tool_width))
                    self.text_box.setTextColor(self.pencolor)
                    self.text_box.textAreaChanged()
                    
                    # 关键修复：确保文字框能正确显示和获得焦点
                    print(f"显示文字框: 位置=({self.text_box.x()}, {self.text_box.y()}), isVisible={self.text_box.isVisible()}")
                    self.text_box.show()
                    self.text_box.raise_()  # 提升到顶层
                    self.text_box.activateWindow()  # 激活窗口
                    self.text_box.setFocus(Qt.MouseFocusReason)  # 明确设置焦点原因
                    
                    # 双重检查焦点设置 - 使用弱引用避免对象被删除时的错误
                    import weakref
                    weak_self = weakref.ref(self)
                    def ensure_focus():
                        obj = weak_self()
                        if obj is not None:
                            obj._ensure_text_box_focus()
                    QTimer.singleShot(50, ensure_focus)
                    
                    print(f"文字框焦点设置: hasFocus={self.text_box.hasFocus()}")
                    self.alpha_slider.setValue(255)
                    # 不要清除工具状态，保持文字工具激活
                    # self.change_tools_fun("")
                elif self._is_brush_tool_active():
                    tool_label = "荧光笔" if self.painter_tools['highlight_on'] else "画笔"
                    print(f"主窗口鼠标按下调试: 开始{tool_label}绘制，添加起始点 [{press_x}, {press_y}]")
                    self.pen_pointlist.append([-2, -2])  # 添加分隔符
                    self.pen_pointlist.append([press_x, press_y])  # 添加起始点
                    self.pen_drawn_points_count = 1  # 重置计数器，从1开始（包括起始点）
                    # 记录起始点用于移动检测
                    self.pen_start_point = [press_x, press_y]
                    self.pen_last_point = [press_x, press_y]
            else:  # 否则说明正在选区或移动选区
                r = 0
                x0 = min(self.x0, self.x1)
                x1 = max(self.x0, self.x1)
                y0 = min(self.y0, self.y1)
                y1 = max(self.y0, self.y1)
                my = (y1 + y0) // 2
                mx = (x1 + x0) // 2
                # print(x0, x1, y0, y1, mx, my, event.x(), event.y())
                # 以下为判断点击在哪里
                if not self.finding_rect and (self.x0 - 8 < event.x() < self.x0 + 8) and (
                        my - 8 < event.y() < my + 8 or y0 - 8 < event.y() < y0 + 8 or y1 - 8 < event.y() < y1 + 8):
                    self.move_x0 = True
                    r = 1

                elif not self.finding_rect and (self.x1 - 8 < event.x() < self.x1 + 8) and (
                        my - 8 < event.y() < my + 8 or y0 - 8 < event.y() < y0 + 8 or y1 - 8 < event.y() < y1 + 8):
                    self.move_x1 = True
                    r = 1
                    # print('x1')

                elif not self.finding_rect and (self.y0 - 8 < event.y() < self.y0 + 8) and (
                        mx - 8 < event.x() < mx + 8 or x0 - 8 < event.x() < x0 + 8 or x1 - 8 < event.x() < x1 + 8):
                    self.move_y0 = True
                    print('y0')
                elif not self.finding_rect and self.y1 - 8 < event.y() < self.y1 + 8 and (
                        mx - 8 < event.x() < mx + 8 or x0 - 8 < event.x() < x0 + 8 or x1 - 8 < event.x() < x1 + 8):
                    self.move_y1 = True

                elif (x0 + 8 < event.x() < x1 - 8) and (
                        y0 + 8 < event.y() < y1 - 8) and not self.finding_rect:
                    # if not self.finding_rect:
                    self.move_rect = True
                    self.setCursor(Qt.SizeAllCursor)
                    self.bx = abs(max(self.x1, self.x0) - event.x())
                    self.by = abs(max(self.y1, self.y0) - event.y())
                else:
                    self.NpainterNmoveFlag = True  # 没有绘图没有移动还按下了左键,说明正在选区,标志变量
                    # if self.finding_rect:
                    #     self.rx0 = event.x()
                    #     self.ry0 = event.y()
                    # else:
                    self.rx0 = event.x()  # 记录下点击位置
                    self.ry0 = event.y()
                    if self.x1 == -50:
                        self.x1 = event.x()
                        self.y1 = event.y()

                    # print('re')
                if r:  # 判断是否点击在了对角线上
                    if (self.y0 - 8 < event.y() < self.y0 + 8) and (
                            x0 - 8 < event.x() < x1 + 8):
                        self.move_y0 = True
                        # print('y0')
                    elif self.y1 - 8 < event.y() < self.y1 + 8 and (
                            x0 - 8 < event.x() < x1 + 8):
                        self.move_y1 = True
                        # print('y1')
            if self.finding_rect:
                self.finding_rect = False
                # self.finding_rectde = True
            # 仅在非绘画模式时隐藏工具栏，激活绘画功能时保持工具栏可见
            if not (1 in self.painter_tools.values()):
                self.botton_box.hide()
            self.update()
        # elif event.button() == Qt.RightButton:  # 右键
        #     self.setCursor(Qt.ArrowCursor)
        #     if 1 in self.painter_tools.values():  # 退出绘图工具
        #         if self.painter_tools["selectcolor_on"]:
        #             self.Tipsshower.setText("取消取色器")
        #             self.choice_clor_btn.setStyleSheet(
        #                 'background-color:{0};'.format(self.pencolor.name()))  # 还原choiceclor显示的颜色
        #         if self.painter_tools["perspective_cut_on"] and len(self.perspective_cut_pointlist) > 0:
        #             self.setCursor(QCursor(QPixmap(":/perspective.png").scaled(32, 32, Qt.KeepAspectRatio), 0, 32))
        #             self.perspective_cut_pointlist.pop()
        #             # if not len(self.perspective_cut_pointlist):
        #             #     self.choicing = False
        #             #     self.finding_rect = True
        #         elif self.painter_tools["polygon_ss_on"] and len(self.polygon_ss_pointlist) > 0:
        #             self.setCursor(QCursor(QPixmap(":/polygon_ss.png").scaled(32, 32, Qt.KeepAspectRatio), 0, 32))
        #             self.polygon_ss_pointlist.pop()
        #             # if not len(self.polygon_ss_pointlist):
        #             #     self.choicing = False
        #             #     self.finding_rect = True
        #         else:
        #             self.choicing = False
        #             self.finding_rect = True
        #             self.shower.hide()
        #             self.change_tools_fun("")

        #     elif self.choicing:  # 退出选定的选区
        #         self.botton_box.hide()
        #         self.choicing = False
        #         self.finding_rect = True
        #         self.shower.hide()
        #         self.x0 = self.y0 = self.x1 = self.y1 = -50
        #     else:  # 退出截屏
        #         try:
        #             if not QSettings('Fandes', 'jamtools').value("S_SIMPLE_MODE", False, bool):
        #                 self.parent.show()

        #             self.parent.bdocr = False
        #         except:
        #             print(sys.exc_info(), 2051)
        #         self.clear_and_hide()
            self.update()
            
            # 如果是钉图模式，也需要更新钉图窗口
            if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
                self.current_pinned_window.update()

    # 鼠标释放事件
    def mouseReleaseEvent(self, event):
        # 如果是钉图模式并且有绘图工具激活，检查事件是否来自钉图窗口的委托
        if hasattr(self, 'mode') and self.mode == "pinned" and 1 in self.painter_tools.values():
            # 检查事件是否是全局坐标（来自钉图窗口的委托）
            if not hasattr(event, '_from_pinned_window'):
                return  # 如果不是委托事件，直接返回
        
        if event.button() == Qt.LeftButton:
            # 选区编辑结束 -> 提交
            if getattr(self, 'selection_active', False) and (self.selection_dragging or self.selection_resize_edge):
                self.selection_dragging = False
                self.selection_resize_edge = None
                self._update_selection_preview()
                self._commit_selection()
                return
            self.left_button_push = False
            if 1 in self.painter_tools.values():  # 绘图工具松开
                should_backup = False  # 添加备份控制标志
                
                if self._is_brush_tool_active():
                    self.pen_pointlist.append([-2, -2])
                    # 画笔工具：使用计数器检查是否有实际的绘制
                    tool_label = "荧光笔" if self.painter_tools['highlight_on'] else "画笔"
                    print(f"{tool_label}撤销调试: 绘制了{self.pen_drawn_points_count}个点")
                    if self.pen_drawn_points_count >= 2:
                        # 检查是否有实际的移动（使用记录的起始点和结束点）
                        has_movement = False
                        print(f"{tool_label}移动检测: 检查起始点和结束点...")
                        print(f"  - pen_start_point存在: {hasattr(self, 'pen_start_point')}")
                        print(f"  - pen_last_point存在: {hasattr(self, 'pen_last_point')}")
                        
                        if hasattr(self, 'pen_start_point') and hasattr(self, 'pen_last_point'):
                            start_x, start_y = self.pen_start_point
                            end_x, end_y = self.pen_last_point
                            movement_distance = abs(end_x - start_x) + abs(end_y - start_y)
                            print(f"{tool_label}移动检测: 起始点({start_x}, {start_y}) -> 结束点({end_x}, {end_y}), 距离: {movement_distance}")
                            if movement_distance > 5:  # 总移动距离大于5像素才算有效
                                has_movement = True
                        else:
                            # 如果没有记录的起始点和结束点，尝试从pen_pointlist获取
                            valid_points = [p for p in self.pen_pointlist if p != [-2, -2]]
                            if len(valid_points) >= 2:
                                start_x, start_y = valid_points[0]
                                end_x, end_y = valid_points[-1]
                                movement_distance = abs(end_x - start_x) + abs(end_y - start_y)
                                print(f"{tool_label}移动检测(备用): 起始点({start_x}, {start_y}) -> 结束点({end_x}, {end_y}), 距离: {movement_distance}")
                                if movement_distance > 5:
                                    has_movement = True
                        
                        if has_movement:
                            should_backup = True
                            print(f"{tool_label}撤销调试: 检测到{self.pen_drawn_points_count}个绘制点且有移动，进行备份")
                        else:
                            should_backup = False
                            print(f"{tool_label}撤销调试: 虽有{self.pen_drawn_points_count}个点但无明显移动，不进行备份")
                    else:
                        should_backup = False
                        print(f"{tool_label}撤销调试: 只有{self.pen_drawn_points_count}个点，不进行备份")
                elif self.painter_tools['drawrect_bs_on']:
                    self.drawrect_pointlist[1] = [event.x(), event.y()]
                    self.drawrect_pointlist[2] = 1
                    # 矩形工具：检查起点和终点是否不同
                    start_point = self.drawrect_pointlist[0]
                    end_point = self.drawrect_pointlist[1]
                    if (abs(start_point[0] - end_point[0]) > 5 or 
                        abs(start_point[1] - end_point[1]) > 5):  # 至少移动5像素才算有效绘制
                        should_backup = False  # 不在这里备份，等待paintEvent完成绘制后再备份
                        print(f"矩形撤销调试: 检测到有效绘制，等待paintEvent完成后备份")
                    else:
                        print(f"矩形撤销调试: 移动距离太小，不进行备份")
                elif self.painter_tools['drawarrow_on']:
                    self.drawarrow_pointlist[1] = [event.x(), event.y()]
                    self.drawarrow_pointlist[2] = 1
                    # 箭头工具：检查起点和终点是否不同
                    start_point = self.drawarrow_pointlist[0]
                    end_point = self.drawarrow_pointlist[1]
                    if (abs(start_point[0] - end_point[0]) > 5 or 
                        abs(start_point[1] - end_point[1]) > 5):  # 至少移动5像素才算有效绘制
                        should_backup = False  # 不在这里备份，等待paintEvent完成绘制后再备份
                        print(f"箭头撤销调试: 检测到有效绘制，等待paintEvent完成后备份")
                    else:
                        print(f"箭头撤销调试: 移动距离太小，不进行备份")
                elif self.painter_tools['drawcircle_on']:
                    self.drawcircle_pointlist[1] = [event.x(), event.y()]
                    self.drawcircle_pointlist[2] = 1
                    print(f"钉图圆形调试: 设置终点 [{event.x()}, {event.y()}]，绘制圆形 {self.drawcircle_pointlist}")
                    # 圆形工具：检查起点和终点是否不同
                    start_point = self.drawcircle_pointlist[0]
                    end_point = self.drawcircle_pointlist[1]
                    if (abs(start_point[0] - end_point[0]) > 5 or 
                        abs(start_point[1] - end_point[1]) > 5):  # 至少移动5像素才算有效绘制
                        should_backup = False  # 不在这里备份，等待paintEvent完成绘制后再备份
                        print(f"圆形撤销调试: 检测到有效绘制，等待paintEvent完成后备份")
                    else:
                        print(f"圆形撤销调试: 移动距离太小，不进行备份")
                elif self.painter_tools['drawtext_on']:
                    # 文字工具：这里不进行备份，因为文字还没有确认输入
                    # 文字的备份会在PaintLayer的paintEvent中，确认有文字内容时进行
                    print(f"文字撤销调试: 文字工具点击，等待文字输入确认")
                    should_backup = False
                
                # 只有在确实有绘制内容时才进行备份
                if should_backup:
                    # 检查是否来自钉图窗口
                    if hasattr(event, '_from_pinned_window') and event._from_pinned_window:
                        print(f"🎨 {tool_label}撤销调试: 来自钉图窗口，需要特殊处理备份")
                        
                        # 使用事件中的钉图窗口引用，而不是错误的查找逻辑
                        pinned_window = None
                        if hasattr(event, '_pinned_window_instance') and event._pinned_window_instance:
                            pinned_window = event._pinned_window_instance
                            print(f"🎨 {tool_label}撤销调试: 使用事件中的钉图窗口引用")
                        else:
                            # 旧的查找逻辑作为后备方案（但很容易出错）
                            print(f"🎨 {tool_label}撤销调试: 事件中没有钉图窗口引用，使用查找逻辑")
                            freeze_imgs_list = None
                            
                            # 确定freeze_imgs的位置
                            if hasattr(self, 'parent') and hasattr(self.parent, 'freeze_imgs'):
                                freeze_imgs_list = self.parent.freeze_imgs
                                print(f"🎨 {tool_label}撤销调试: 使用parent.freeze_imgs，列表长度: {len(freeze_imgs_list)}")
                            elif hasattr(self, 'freeze_imgs'):
                                freeze_imgs_list = self.freeze_imgs
                                print(f"🎨 {tool_label}撤销调试: 使用self.freeze_imgs，列表长度: {len(freeze_imgs_list)}")
                            
                            if freeze_imgs_list:
                                for freeze_window in freeze_imgs_list:
                                    if hasattr(freeze_window, 'paintlayer'):
                                        pinned_window = freeze_window
                                        break
                        
                        if pinned_window:
                            # 先合并图层，再备份
                            print(f"🎨 {tool_label}撤销调试: 调用钉图窗口的图层合并和备份 (窗口ID: {getattr(pinned_window, 'listpot', '未知')})")
                            pinned_window._merge_paint_to_base()  # 合并绘画层到底图
                            pinned_window.backup_shortshot()      # 备份钉图窗口状态
                        else:
                            print(f"❌ {tool_label}撤销调试: 未找到对应的钉图窗口")
                    else:
                        # 普通截图窗口备份
                        self.backup_shortshot()
                        print(f"撤销系统: 备份完成，当前步骤: {self.backup_ssid}")
                else:
                    print(f"撤销系统: 跳过备份，无有效绘制内容")
            else:  # 调整选区松开
                self.setCursor(Qt.ArrowCursor)
            self.NpainterNmoveFlag = False  # 选区结束标志置零
            self.move_rect = self.move_y0 = self.move_x0 = self.move_x1 = self.move_y1 = False
            self.choice()
            # self.sure_btn.show()
            
        elif event.button() == Qt.RightButton:  # 右键 - 统一行为：直接退出截图
            # 若有选区则取消并还原
            if getattr(self, 'selection_active', False):
                self._cancel_selection()
                return
            
            # 无论当前处于什么状态，右键都直接退出截图（与ESC行为一致）
            try:
                if not QSettings('Fandes', 'jietuba').value("S_SIMPLE_MODE", False, bool):
                    # 检查主窗口截图前的可见状态，只有原本可见才显示
                    if hasattr(self.parent, '_was_visible') and self.parent._was_visible:
                        self.parent.show()
                    # 如果没有_was_visible属性或值为False，说明原本在托盘中，不显示主窗口

                self.parent.bdocr = False
            except:
                print(sys.exc_info(), 2051)
            self.clear_and_hide()
            self.update()
            
            # 如果是钉图模式，也需要更新钉图窗口
            if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
                self.current_pinned_window.update()
                
    # 鼠标滑轮事件
    def wheelEvent(self, event):
        if self.isVisible():
            angleDelta = event.angleDelta() / 8
            dy = angleDelta.y()
            # print(dy)
            if self.change_alpha:  # 正在调整透明度
                if dy > 0 and self.alpha < 254:
                    self.alpha_slider.setValue(self.alpha_slider.value() + 2)
                elif dy < 0 and self.alpha > 2:
                    self.alpha_slider.setValue(self.alpha_slider.value() - 2)
                self.Tipsshower.setText("透明度值{}".format(self.alpha))

            else:  # 否则是调节画笔大小
                # angleDelta = event.angleDelta() / 8
                # dy = angleDelta.y()
                # print(dy)
                if dy > 0:
                    self.tool_width += 1
                elif self.tool_width > 1:
                    self.tool_width -= 1
                self.size_slider.setValue(self.tool_width)
                self.Tipsshower.setText("大小{}px".format(self.tool_width))

                # if 1 in self.painter_tools.values():

                if self.painter_tools['drawtext_on']:
                    # self.text_box.move(event.x(), event.y())
                    # self.drawtext_pointlist.append([event.x(), event.y()])
                    self.text_box.setFont(QFont('', self.tool_width))
                    # self.text_box.setTextColor(self.pencolor)
                    self.text_box.textAreaChanged()
            self.update()

    # 鼠标移动事件
    def mouseMoveEvent(self, event):
        # print(self.isVisible(), 12121, self.finding_rect, self.smartcursor_on, self.isActiveWindow(), self.isHidden())
        
        # 如果是钉图模式并且有绘图工具激活，检查事件是否来自钉图窗口的委托
        if hasattr(self, 'mode') and self.mode == "pinned" and 1 in self.painter_tools.values():
            # 检查事件是否是全局坐标（来自钉图窗口的委托）
            if not hasattr(event, '_from_pinned_window'):
                return  # 如果不是委托事件，直接返回
        
        # 在钉图模式下，即使主窗口不可见也要处理绘画事件
        process_drawing = (hasattr(self, 'mode') and self.mode == "pinned" and 
                          hasattr(event, '_from_pinned_window')) or self.isVisible()
        
        if process_drawing:
            # 处理选区移动/缩放
            if getattr(self, 'selection_active', False) and self.left_button_push:
                if self.selection_dragging:
                    # 拖动移动
                    new_x = event.x() - self.selection_press_offset.x()
                    new_y = event.y() - self.selection_press_offset.y()
                    self.selection_rect.moveTo(new_x, new_y)
                    self._update_selection_preview()
                    self.paintlayer.update()
                    return
                elif self.selection_resize_edge:
                    # 基于按下时的矩形进行缩放
                    pr = self.selection_press_rect
                    dx = event.x() - self.selection_press_pos.x()
                    dy = event.y() - self.selection_press_pos.y()
                    left, top = pr.left(), pr.top()
                    right, bottom = pr.right(), pr.bottom()
                    edge = self.selection_resize_edge
                    if 'l' in edge:
                        left = pr.left() + dx
                    if 'r' in edge:
                        right = pr.right() + dx
                    if 't' in edge:
                        top = pr.top() + dy
                    if 'b' in edge:
                        bottom = pr.bottom() + dy
                    # 规范化并限制最小尺寸
                    x0 = min(left, right)
                    x1 = max(left, right)
                    y0 = min(top, bottom)
                    y1 = max(top, bottom)
                    if x1 - x0 < 1:
                        x1 = x0 + 1
                    if y1 - y0 < 1:
                        y1 = y0 + 1
                    self.selection_rect = QRect(x0, y0, x1 - x0, y1 - y0)
                    self._update_selection_preview()
                    self.paintlayer.update()
                    return
            self.mouse_posx = event.x()  # 先储存起鼠标位置,用于画笔等的绘图计算
            self.mouse_posy = event.y()
            if self.finding_rect and self.smartcursor_on and self.isVisible():  # 智能选区只在主窗口可见时使用
                # 延迟初始化智能选区，仅在用户真正需要时才进行
                if not self._smart_selection_initialized:
                    self._lazy_init_smart_selection()
                self.x0, self.y0, self.x1, self.y1 = self.finder.find_targetrect((self.mouse_posx, self.mouse_posy))
                self.setCursor(QCursor(QPixmap(":/smartcursor.png").scaled(32, 32, Qt.KeepAspectRatio), 16, 16))
                # print(self.x0, self.y0, self.x1, self.y1 )
                # print("findtime {}".format(time.process_time()-st))
            elif 1 in self.painter_tools.values():  # 如果有绘图工具已经被选择,说明正在绘图
                # 处理坐标，区分是否来自钉图窗口委托
                if hasattr(event, '_from_pinned_window') and hasattr(self, 'mode') and self.mode == "pinned":
                    # 来自钉图窗口的委托事件，需要转换为相对于绘画层的坐标
                    paint_x = event.x()
                    paint_y = event.y()
                else:
                    # 正常的截图模式
                    paint_x = event.x()
                    paint_y = event.y()
                    
                self.paintlayer.px = paint_x
                self.paintlayer.py = paint_y
                
                # # 添加调试信息
                # if hasattr(self, 'mode') and self.mode == "pinned":
                #     print(f"主窗口收到鼠标移动: left_button_push={self.left_button_push}, pen_on={self.painter_tools.get('pen_on', 0)}, paint_x={paint_x}, paint_y={paint_y}")
                
                if self.left_button_push:
                    print(f"主窗口绘画调试: left_button_push=True, 开始绘画处理")
                    if self._is_brush_tool_active():
                        tool_label = "荧光笔" if self.painter_tools['highlight_on'] else "画笔"
                        print(f"添加{tool_label}点: [{paint_x}, {paint_y}]")
                        self.pen_pointlist.append([paint_x, paint_y])
                        self.pen_drawn_points_count += 1  # 增加计数器
                        # 更新最后一个点用于移动检测
                        self.pen_last_point = [paint_x, paint_y]
                        # 在钉图模式下，更新钉图窗口而不是主窗口
                        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
                            self.current_pinned_window.update()
                        else:
                            self.update()  # 立即更新显示
                    elif self.painter_tools['drawrect_bs_on']:
                        self.drawrect_pointlist[1] = [paint_x, paint_y]
                        # 在钉图模式下，更新钉图窗口而不是主窗口
                        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
                            self.current_pinned_window.update()
                        else:
                            self.update()  # 立即更新显示
                    elif self.painter_tools['drawarrow_on']:
                        self.drawarrow_pointlist[1] = [paint_x, paint_y]
                        # 在钉图模式下，更新钉图窗口而不是主窗口
                        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
                            self.current_pinned_window.update()
                        else:
                            self.update()  # 立即更新显示
                    elif self.painter_tools['drawcircle_on']:
                        self.drawcircle_pointlist[1] = [paint_x, paint_y]
                        # 在钉图模式下，更新钉图窗口而不是主窗口
                        if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
                            self.current_pinned_window.update()
                        else:
                            self.update()  # 立即更新显示
                # self.update()
                if self._is_brush_tool_active():
                    self.setCursor(QCursor(QPixmap(":/pen.png").scaled(32, 32, Qt.KeepAspectRatio), 0, 32))
                elif self.painter_tools['drawrect_bs_on']:
                    self.setCursor(Qt.ArrowCursor)  # 明确设置为默认箭头鼠标
                elif self.painter_tools['drawarrow_on']:
                    self.setCursor(QCursor(QPixmap(":/arrowicon.png").scaled(32, 32, Qt.KeepAspectRatio), 0, 32))
                elif self.painter_tools['drawcircle_on']:
                    self.setCursor(Qt.ArrowCursor)  # 明确设置为默认箭头鼠标
                elif self.painter_tools['drawtext_on']:
                    self.setCursor(QCursor(QPixmap(":/texticon.png").scaled(16, 16, Qt.KeepAspectRatio), 0, 0))

            else:  # 不在绘画
                minx = min(self.x0, self.x1)
                maxx = max(self.x0, self.x1)
                miny = min(self.y0, self.y1)
                maxy = max(self.y0, self.y1)  # 以上取选区的最小值和最大值
                my = (maxy + miny) // 2
                mx = (maxx + minx) // 2  # 取中间值
                if ((minx - 8 < event.x() < minx + 8) and (miny - 8 < event.y() < miny + 8)) or \
                        ((maxx - 8 < event.x() < maxx + 8) and (maxy - 8 < event.y() < maxy + 8)):
                    self.setCursor(Qt.SizeFDiagCursor)
                elif ((minx - 8 < event.x() < minx + 8) and (maxy - 8 < event.y() < maxy + 8)) or \
                        ((maxx - 8 < event.x() < maxx + 8) and (miny - 8 < event.y() < miny + 8)):
                    self.setCursor(Qt.SizeBDiagCursor)
                elif (self.x0 - 8 < event.x() < self.x0 + 8) and (
                        my - 8 < event.y() < my + 8 or miny - 8 < event.y() < miny + 8 or maxy - 8 < event.y() < maxy + 8):
                    self.setCursor(Qt.SizeHorCursor)
                elif (self.x1 - 8 < event.x() < self.x1 + 8) and (
                        my - 8 < event.y() < my + 8 or miny - 8 < event.y() < miny + 8 or maxy - 8 < event.y() < maxy + 8):
                    self.setCursor(Qt.SizeHorCursor)
                elif (self.y0 - 8 < event.y() < self.y0 + 8) and (
                        mx - 8 < event.x() < mx + 8 or minx - 8 < event.x() < minx + 8 or maxx - 8 < event.x() < maxx + 8):
                    self.setCursor(Qt.SizeVerCursor)
                elif (self.y1 - 8 < event.y() < self.y1 + 8) and (
                        mx - 8 < event.x() < mx + 8 or minx - 8 < event.x() < minx + 8 or maxx - 8 < event.x() < maxx + 8):
                    self.setCursor(Qt.SizeVerCursor)
                elif (minx + 8 < event.x() < maxx - 8) and (
                        miny + 8 < event.y() < maxy - 8):
                    if self.move_rect:
                        self.setCursor(Qt.SizeAllCursor)
                    # self.setCursor(Qt.SizeAllCursor)
                elif self.move_x1 or self.move_x0 or self.move_y1 or self.move_y0:  # 再次判断防止光标抖动
                    b = (self.x1 - self.x0) * (self.y1 - self.y0) > 0
                    if (self.move_x0 and self.move_y0) or (self.move_x1 and self.move_y1):
                        if b:
                            self.setCursor(Qt.SizeFDiagCursor)
                        else:
                            self.setCursor(Qt.SizeBDiagCursor)
                    elif (self.move_x1 and self.move_y0) or (self.move_x0 and self.move_y1):
                        if b:
                            self.setCursor(Qt.SizeBDiagCursor)
                        else:
                            self.setCursor(Qt.SizeFDiagCursor)
                    elif (self.move_x0 or self.move_x1) and not (self.move_y0 or self.move_y1):
                        self.setCursor(Qt.SizeHorCursor)
                    elif not (self.move_x0 or self.move_x1) and (self.move_y0 or self.move_y1):
                        self.setCursor(Qt.SizeVerCursor)
                    # elif self.move_rect:
                    #     self.setCursor(Qt.SizeAllCursor)
                else:
                    self.setCursor(Qt.ArrowCursor)
                # 以上几个ifelse都是判断鼠标移动的位置和选框的关系然后设定光标形状
                # print(11)
                if self.NpainterNmoveFlag:  # 如果没有在绘图也没在移动(调整)选区,在选区,则不断更新选区的数值
                    # self.sure_btn.hide()
                    # self.roll_ss_btn.hide()
                    self.x1 = event.x()  # 储存当前位置到self.x1下同
                    self.y1 = event.y()
                    self.x0 = self.rx0  # 鼠标按下时记录的坐标,下同
                    self.y0 = self.ry0
                    if self.y1 > self.y0:  # 下面是边界修正,由于选框占用了一个像素,否则有误差
                        self.y1 += 1
                    else:
                        self.y0 += 1
                    if self.x1 > self.x0:
                        self.x1 += 1
                    else:
                        self.x0 += 1
                else:  # 说明在移动或者绘图,不过绘图没有什么处理的,下面是处理移动/拖动选区
                    if self.move_x0:  # 判断拖动标志位,下同
                        self.x0 = event.x()
                    elif self.move_x1:
                        self.x1 = event.x()
                    if self.move_y0:
                        self.y0 = event.y()
                    elif self.move_y1:
                        self.y1 = event.y()
                    elif self.move_rect:  # 拖动选框
                        dx = abs(self.x1 - self.x0)
                        dy = abs(self.y1 - self.y0)
                        if self.x1 > self.x0:
                            self.x1 = event.x() + self.bx
                            self.x0 = self.x1 - dx
                        else:
                            self.x0 = event.x() + self.bx
                            self.x1 = self.x0 - dx

                        if self.y1 > self.y0:
                            self.y1 = event.y() + self.by
                            self.y0 = self.y1 - dy
                        else:
                            self.y0 = event.y() + self.by
                            self.y1 = self.y0 - dy
            # print("movetime{}".format(time.process_time()-st))
            self.update()  # 更新界面
            
            # 如果是钉图模式，也需要更新钉图窗口
            if hasattr(self, 'mode') and self.mode == "pinned" and hasattr(self, 'current_pinned_window'):
                self.current_pinned_window.update()
        # QApplication.processEvents()

    def keyPressEvent(self, e):  # 按键按下,没按一个键触发一次
        super(Slabel, self).keyPressEvent(e)
        # self.pixmap().save(temp_path + '/aslfdhds.png')
        if e.key() == Qt.Key_Escape:  # 退出
            self.clear_and_hide()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter):  # Enter键完成截图
            # 检查是否有任何绘制工具激活，如果有则不响应Enter键
            if hasattr(self, 'painter_tools') and any(self.painter_tools.values()):
                # 有绘制工具激活时，Enter键可能用于文字输入等，不执行完成操作
                print("🎯 [Enter键] 绘制工具激活中，忽略Enter键完成操作")
                return
            
            # 检查文字输入框是否在焦点中
            if hasattr(self, 'text_box') and self.text_box.isVisible() and self.text_box.hasFocus():
                # 文字输入框有焦点时，Enter键用于文字输入，不执行完成操作
                print("📝 [Enter键] 文字输入框激活中，忽略Enter键完成操作")
                return
            
            # 检查是否已选择区域
            if hasattr(self, 'choicing') and self.choicing:
                # 已选择区域，执行完成截图操作
                print("✅ [Enter键] 执行完成截图操作")
                self.handle_sure_btn_click()
            else:
                print("⚠️ [Enter键] 未选择截图区域，忽略Enter键")
        elif e.key() == Qt.Key_Control:  # 按住ctrl,更改透明度标志位置一
            print("cahnge")
            self.change_alpha = True

        elif self.change_alpha:  # 如果已经按下了ctrl
            if e.key() == Qt.Key_S:  # 还按下了s,说明是保存,ctrl+s
                # 在保存前，先保存当前的绘制状态（如果有正在输入的文字）
                print("💾 [Ctrl+S] 执行保存前，保存当前绘制状态")
                self._reset_text_box_completely()
                self.cutpic(1)
            else:
                if e.key() == Qt.Key_Z:  # 前一步
                    self.last_step()
                elif e.key() == Qt.Key_Y:  # 后一步
                    self.next_step()

    def keyReleaseEvent(self, e) -> None:  # 按键松开
        super(Slabel, self).keyReleaseEvent(e)
        if e.key() == Qt.Key_Control:
            self.change_alpha = False

    def clear_and_hide(self):  # 清理退出
        print("clear and hide")
        
        # 在清理退出前，先保存正在绘制的文字内容
        try:
            if hasattr(self, 'text_box') and self.text_box.isVisible() and self.text_box.toPlainText().strip():
                print("⚠️ [退出] 检测到正在绘制的文字，先保存再退出")
                self._reset_text_box_completely()
        except Exception as e:
            print(f"⚠️ 退出前保存文字时出错: {e}")
        
        try:
            # 在清理前先安全地重置撤销系统状态
            if hasattr(self, 'backup_pic_list'):
                print(f"清理前撤销状态: backup_ssid={getattr(self, 'backup_ssid', 'None')}, list_length={len(self.backup_pic_list)}")
                # 确保backup_ssid处于有效范围内
                if hasattr(self, 'backup_ssid') and len(self.backup_pic_list) > 0:
                    self.backup_ssid = min(max(0, self.backup_ssid), len(self.backup_pic_list) - 1)
        except Exception as e:
            print(f"⚠️ 清理前重置撤销状态时出错: {e}")
            
        # 清理绘画相关资源
        try:
            if hasattr(self, 'pixPainter') and self.pixPainter:
                if self.pixPainter.isActive():
                    self.pixPainter.end()
                self.pixPainter = None
        except Exception as e:
            print(f"⚠️ 清理pixPainter时出错: {e}")
            
        try:
            # OCR freezer清理已移除
            # if self.ocr_freezer is not None:
            #     self.ocr_freezer.clear()
            pass
        except Exception as e:
            print(f"⚠️ 清理OCR freezer时出错: {e}")
            
        try:
            if PLATFORM_SYS == "darwin":  # 如果系统为macos
                print("drawin hide")
                self.setWindowOpacity(0)
                self.showNormal()
            self.hide()
        except Exception as e:
            print(f"⚠️ 隐藏窗口时出错: {e}")
            
        try:
            self.clearotherthread = Commen_Thread(self.clear_and_hide_thread)
            self.clearotherthread.start()
        except Exception as e:
            print(f"⚠️ 启动清理线程时出错: {e}")
            # 直接调用清理函数作为fallback
            try:
                self.clear_and_hide_thread()
            except Exception as e2:
                print(f"⚠️ 直接调用清理函数也失败: {e2}")

    def clear_and_hide_thread(self):  # 后台等待线程
        try:
            print("开始清理线程")
            self.close_signal.emit()
            print("发送关闭信号完成")
        except Exception as e:
            print(f"⚠️ 发送关闭信号时出错: {e}")
            
        try:
            if hasattr(self, 'save_data_thread'):
                print("等待保存数据线程完成")
                self.save_data_thread.wait()
                print("保存数据线程等待完成")
        except Exception as e:
            print(f"⚠️ 等待保存数据线程时出错: {e}")
            print(f"详细错误信息: {sys.exc_info()}")
            
        print("清理线程完成")

    def cleanup_resources(self):
        """清理Slabel的所有资源，防止崩溃"""
        try:
            print("🧹 开始清理Slabel资源...")
            
            # 清理撤销系统
            if hasattr(self, 'backup_pic_list'):
                print(f"清理撤销列表，当前长度: {len(self.backup_pic_list)}")
                try:
                    for pixmap in self.backup_pic_list:
                        if pixmap and not pixmap.isNull():
                            del pixmap
                    self.backup_pic_list.clear()
                    self.backup_ssid = 0
                    print("撤销系统资源清理完成")
                except Exception as e:
                    print(f"清理撤销系统时出错: {e}")
            
            # 清理绘画相关资源
            if hasattr(self, 'pixPainter') and self.pixPainter:
                try:
                    if self.pixPainter.isActive():
                        self.pixPainter.end()
                    self.pixPainter = None
                    print("pixPainter清理完成")
                except Exception as e:
                    print(f"清理pixPainter时出错: {e}")
            
            # 清理paintlayer
            if hasattr(self, 'paintlayer') and self.paintlayer:
                try:
                    if hasattr(self.paintlayer, 'cleanup_resources'):
                        self.paintlayer.cleanup_resources()
                    self.paintlayer = None
                    print("paintlayer清理完成")
                except Exception as e:
                    print(f"清理paintlayer时出错: {e}")
            
            # 清理其他绘画数据
            paint_attrs = ['pen_pointlist', 'drawrect_pointlist', 'drawcircle_pointlist', 
                          'drawarrow_pointlist', 'drawtext_pointlist']
            for attr in paint_attrs:
                if hasattr(self, attr):
                    try:
                        setattr(self, attr, [])
                    except:
                        pass
            
            print("🧹 Slabel资源清理完成")
            
        except Exception as e:
            print(f"⚠️ 清理Slabel资源时出错: {e}")

    def paint_on_pinned_window(self, painter, pinned_window):
        """在钉图窗口上绘制绘画内容"""
        # 保存原始画笔状态
        painter.save()
        
        # 设置绘画参数
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制画笔轨迹
        if self.pen_pointlist:
            pen = QPen(self.pencolor, self.tool_width, Qt.SolidLine)
            painter.setPen(pen)
            for i in range(len(self.pen_pointlist) - 1):
                if self.pen_pointlist[i] != [-2, -2] and self.pen_pointlist[i + 1] != [-2, -2]:
                    painter.drawLine(self.pen_pointlist[i][0], self.pen_pointlist[i][1],
                                   self.pen_pointlist[i + 1][0], self.pen_pointlist[i + 1][1])

        # 绘制矩形
        if self.drawrect_pointlist[2] == 1:
            pen = QPen(self.pencolor, self.tool_width, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.drawrect_pointlist[0][0], self.drawrect_pointlist[0][1],
                           self.drawrect_pointlist[1][0] - self.drawrect_pointlist[0][0],
                           self.drawrect_pointlist[1][1] - self.drawrect_pointlist[0][1])

        # 绘制箭头
        if self.drawarrow_pointlist[2] == 1:
            pen = QPen(self.pencolor, self.tool_width, Qt.SolidLine)
            painter.setPen(pen)
            # 绘制箭头的直线部分
            painter.drawLine(self.drawarrow_pointlist[0][0], self.drawarrow_pointlist[0][1],
                           self.drawarrow_pointlist[1][0], self.drawarrow_pointlist[1][1])
            # 可以添加箭头头部的绘制

        # 绘制圆形
        if self.drawcircle_pointlist[2] == 1:
            pen = QPen(self.pencolor, self.tool_width, Qt.SolidLine)
            painter.setPen(pen)
            radius = ((self.drawcircle_pointlist[1][0] - self.drawcircle_pointlist[0][0]) ** 2 +
                     (self.drawcircle_pointlist[1][1] - self.drawcircle_pointlist[0][1]) ** 2) ** 0.5
            painter.drawEllipse(self.drawcircle_pointlist[0][0] - radius, self.drawcircle_pointlist[0][1] - radius,
                              radius * 2, radius * 2)

        # 恢复画笔状态
        painter.restore()

    # 绘制事件
    def paintEvent(self, event):  # 绘图函数,每次调用self.update时触发
        super().paintEvent(event)
        if self.on_init:
            print('oninit return')
            return
        pixPainter = QPainter(self.pixmap())  # 画笔
        pixPainter.end()

    def closeEvent(self, event):
        """Slabel窗口关闭事件，设置closed标记防止QPainter冲突"""
        try:
            self.closed = True
            # 清理paintlayer
            if hasattr(self, 'paintlayer') and self.paintlayer:
                if hasattr(self.paintlayer, 'clear'):
                    self.paintlayer.clear()
            print("🔒 [关闭事件] Slabel窗口关闭，已设置closed标记")
        except Exception as e:
            print(f"⚠️ Slabel关闭事件处理错误: {e}")
        super().closeEvent(event)


if __name__ == '__main__':
    class testwin(QWidget):  # 随便设置的一个ui,
        def __init__(self):
            super(testwin, self).__init__()
            self.freeze_imgs = []  # 储存固定截屏在屏幕上的数组
            btn = QPushButton("截屏", self)
            btn.setGeometry(20, 20, 60, 30)
            btn.setShortcut("Alt+Z")
            btn.clicked.connect(self.ss)
            self.temppos = [500, 100]
            self.s = Slabel(self)
            self.s.close_signal.connect(self.ss_end)  # 截屏结束信号连接
            self.resize(300, 200)

        def ss(self):  # 截屏开始
            self.setWindowOpacity(0)  # 设置透明度而不是hide是因为透明度更快
            self.temppos = [self.x(), self.y()]
            self.move(QApplication.desktop().width(), QApplication.desktop().height())
            self.s.screen_shot()
            # self.hide()

        def ss_end(self):
            del self.s
            self.move(self.temppos[0], self.temppos[1])
            self.show()
            self.setWindowOpacity(1)
            self.raise_()
            gc.collect()
            print(gc.isenabled(), gc.get_count(), gc.get_freeze_count())
            print('cleard')
            self.s = Slabel(self)
            self.s.close_signal.connect(self.ss_end)

        def show(self) -> None:
            super(testwin, self).show()
            print("ss show")


    app = QApplication(sys.argv)
    
    # 设置DPI感知模式以正确处理Windows系统缩放
    try:
        # 设置高DPI缩放策略
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # 设置DPI缩放因子舍入策略
        if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
            if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, 'PassThrough'):
                app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
            else:
                # 如果没有PassThrough，尝试Round或其他策略
                app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Round)
        
        print(f"✅ DPI设置完成: EnableHighDpiScaling={app.testAttribute(Qt.AA_EnableHighDpiScaling)}")
    except Exception as dpi_error:
        print(f"⚠️ DPI设置失败: {dpi_error}")
    
    s = testwin()
    s.show()
    sys.exit(app.exec_())
