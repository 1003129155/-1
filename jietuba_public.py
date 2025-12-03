#!usr/bin/python3
# -*- coding: utf-8 -*-
"""
jietuba_public.py - 公共配置和工具函数模块

提供截图工具的公共配置、工具函数和共享组件。０

主要功能:
- 全局配置管理 (CONFIG_DICT)
- 配置持久化 (ConfigManager)
- 截图保存目录管理
- 公共UI组件 (TipsShower等)
- 通用工具函数

主要类:
- ConfigManager: 配置管理器,使用 QSettings 持久化配置
- TipsShower: 提示信息显示窗口
- Commen_Thread: 通用工作线程
- linelabel: 自定义标签组件

全局变量:
- CONFIG_DICT: 全局配置字典
- PLATFORM_SYS: 系统平台标识



依赖模块:
- PyQt5: GUI框架

使用方法:
    from jietuba_public import CONFIG_DICT, get_screenshot_save_dir
    save_dir = get_screenshot_save_dir()
"""

import os
import sys
import time
from PyQt5.QtCore import QRect, Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt5.QtGui import QColor, QBrush, QPixmap, QPainter, QPen, QFont
from PyQt5.QtWidgets import QApplication, QLabel, QWidget


def resource_path(relative_path):
    """
    获取资源文件的绝对路径
    适用于开发环境和 PyInstaller 打包后的环境
    
    Args:
        relative_path: 资源文件的相对路径，如 "svg/画笔.svg"
    
    Returns:
        资源文件的绝对路径
    """
    try:
        # PyInstaller 打包后会创建临时文件夹，并将路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    except AttributeError:
        # 开发环境中，使用当前文件所在目录的父目录
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, relative_path)


OcrDetector = None
OCR_AVAILABLE = False

APP_ID = QSettings('Fandes', 'jietuba').value('BaiduAI_APPID', '17302981', str)  # 获取的 ID，下同
API_KEY = QSettings('Fandes', 'jietuba').value('BaiduAI_APPKEY', 'wuYjn1T9GxGIXvlNkPa9QWsw', str)
SECRECT_KEY = QSettings('Fandes', 'jietuba').value('BaiduAI_SECRECT_KEY', '89wrg1oEiDzh5r0L63NmWeYNZEWUNqvG', str)
print("platform is", sys.platform)
PLATFORM_SYS = sys.platform
CONFIG_DICT = {
    "last_pic_save_name": "{}".format(str(time.strftime("%Y-%m-%d_%H.%M.%S", time.localtime()))),
    # "ocr_lang": "jp",  # [已废弃] 功能已移除，此配置项不再使用
}

def get_apppath():
    p = sys.path[0].replace("\\", "/").rstrip("/") if os.path.isdir(sys.path[0]) else os.path.split(sys.path[0])[0]
    # print("apppath",p)
    if sys.platform == "darwin" and p.endswith("MacOS"):
        p = os.path.join(p.rstrip("MacOS"), "Resources")
    return p


def get_screenshot_save_dir():
    """获取截图保存目录 - 支持从配置读取自定义路径"""
    try:
        from PyQt5.QtCore import QSettings
        settings = QSettings('Fandes', 'jietuba')
        
        # 从配置读取保存路径
        default_path = os.path.join(os.path.expanduser("~"), "Desktop", "スクショ")
        screenshot_dir = settings.value('screenshot/save_path', default_path, type=str)
        
        # 确保目录存在
        if not os.path.exists(screenshot_dir):
            os.makedirs(screenshot_dir)
            print(f"创建截图保存目录: {screenshot_dir}")
        
        return screenshot_dir
    except Exception as e:
        print(f"创建截图保存目录失败: {e}")
        # 如果失败，使用当前目录
        return "."


apppath = get_apppath()

class TipsShower(QLabel):
    def __init__(self, text, targetarea=(0, 0, 0, 0), parent=None, fontsize=35, timeout=1000):
        super().__init__(parent)
        self.parent = parent
        self.area = list(targetarea)
        self.timeout = timeout
        self.rfont = QFont('', fontsize)
        self.setFont(self.rfont)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.hide)
        self.setText(text)

        self.show()

        self.setStyleSheet("color:white")
    def set_pos(self,x,y):
        self.area[0],self.area[1]=[x,y]
    def setText(self, text, autoclose=True, font: QFont = None, color: QColor = None) -> None:
        super(TipsShower, self).setText(text)
        print("settext")
        self.adjustSize()
        x, y, w, h = self.area
        if x < QApplication.desktop().width() - x - w:
            self.move(x + w + 5, y)
        else:
            self.move(x - self.width() - 5, y)
        self.show()
        if autoclose:
            self.timer.start(self.timeout)
        if font is not None:
            print("更换字体")
            self.setFont(font)
        if font is not None:
            self.setStyleSheet("color:{}".format(color.name()))

    def hide(self) -> None:
        super(TipsShower, self).hide()
        self.timer.stop()
        self.setFont(self.rfont)
        self.setStyleSheet("color:white")

    def textAreaChanged(self, minsize=0):
        self.document.adjustSize()
        newWidth = self.document.size().width() + 25
        newHeight = self.document.size().height() + 15
        if newWidth != self.width():
            if newWidth < minsize:
                self.setFixedWidth(minsize)
            else:
                self.setFixedWidth(newWidth)
        if newHeight != self.height():
            if newHeight < minsize:
                self.setFixedHeight(minsize)
            else:
                self.setFixedHeight(newHeight)



class linelabel(QLabel):
    move_signal = pyqtSignal(int, int)
    def __init__(self, parent=None):
        super(linelabel, self).__init__(parent=parent)
        self.setMouseTracking(True)
        self.moving = False
        # self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("QPushButton{color:black}"
                           "QPushButton:hover{color:green}"
                           "QPushButton:hover{background-color:rgb(200,200,100)}"
                           "QPushButton{background-color:rgb(239,239,239)}"
                           "QScrollBar{width:3px;border:none; background-color:rgb(200,200,200);"
                           "border-radius: 8px;}"
                           )
    def paintEvent(self, e):
        super(linelabel, self).paintEvent(e)
        painter = QPainter(self)
        brush = QBrush(Qt.Dense7Pattern)
        painter.setBrush(brush)
        painter.drawRect(0, 0, self.width(), self.height())
        painter.end()
        
    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if e.button() == Qt.LeftButton:
            self.moving = False
            self.setCursor(Qt.ArrowCursor)
            self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.moving = True
            self.dx = e.x()
            self.dy = e.y()
            self.setCursor(Qt.SizeAllCursor)
            self.update()

    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)
        if self.isVisible():
            if self.moving:
                self.move(e.x() + self.x() - self.dx, e.y() + self.y() - self.dy)
                self.update()
                self.move_signal.emit(self.x(),self.y())

            self.setCursor(Qt.SizeAllCursor)

                
class Transparent_windows(QLabel):
    def __init__(self, x=0, y=0, w=0, h=0, color=Qt.red, havelabel=False):
        super().__init__()
        self.setGeometry(x - 5, y - 5, w + 10, h + 10)
        self.area = (x, y, w, h)
        self.x, self.y, self.w, self.h = x, y, w, h
        self.color = color
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        if havelabel:
            self.label = QLabel(self)
            self.label.setGeometry(self.w - 55, 6 + self.h + 1, 60, 14)
            self.label.setStyleSheet("color: green;border: 2 px;font-weight:bold;")

    def setGeometry(self, x, y, w, h):
        super(Transparent_windows, self).setGeometry(x - 5, y - 5, w + 10, h + 10)
        self.area = (x, y, w, h)

    def paintEvent(self, e):
        super().paintEvent(e)
        x, y, w, h = self.area
        p = QPainter(self)
        p.setPen(QPen(self.color, 2, Qt.SolidLine))
        p.drawRect(QRect(3, 3, w + 4, h + 4))
        p.end()


class Commen_Thread(QThread):
    def __init__(self, action, *args):
        super(QThread, self).__init__()
        self.action = action
        self.args = args

    def run(self):
        print('start_thread params:{}'.format(self.args))
        if self.args:
            print(self.args)
            if len(self.args) == 1:
                self.action(self.args[0])
            elif len(self.args) == 2:
                self.action(self.args[0], self.args[1])
            elif len(self.args) == 3:
                self.action(self.args[0], self.args[1], self.args[2])
            elif len(self.args) == 4:
                self.action(self.args[0], self.args[1], self.args[2], self.args[3])
        else:
            self.action()



if __name__ == '__main__':

    pass  # 保持语法正确性
