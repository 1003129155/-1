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
- OCR_AVAILABLE: OCR功能可用性(已禁用)

注意:
- OCR 功能已移除以减小打包体积
- 网络相关功能已移除
- 语音功能已移除

依赖模块:
- PyQt5: GUI框架
- cv2: OpenCV图像处理

使用方法:
    from jietuba_public import CONFIG_DICT, get_screenshot_save_dir
    save_dir = get_screenshot_save_dir()
"""
# @Time    : 2020/11/13 22:42
# @Author  : Fandes
# @FileName: public.py
# @Software: PyCharm
import hashlib
import http.client
import os
import random
import re
import sys
import time
import cv2
# import requests  # 网络功能已移除，减小打包体积
from PyQt5.QtCore import QRect, Qt, QThread, pyqtSignal, QStandardPaths, QTimer, QSettings, QFileInfo, \
    QUrl, QObject, QSize
from PyQt5.QtCore import QRect, Qt, QThread, pyqtSignal, QSettings, QSizeF, QStandardPaths, QUrl
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor, QBrush, QTextDocument, QTextCursor, QDesktopServices,QPixmap
from PyQt5.QtGui import QPainter, QPen, QIcon, QFont,QImage
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit, QWidget
from urllib.parse import quote
import numpy as np
# from fake_useragent import UserAgent  # UA生成器已移除，减小打包体积

# from jietuba_speak import Speaker  # 语音功能已移除，减小打包体积
# OCR模块已移除 - 如需文字识别功能请手动添加
OcrDetector = None
OCR_AVAILABLE = False

APP_ID = QSettings('Fandes', 'jietuba').value('BaiduAI_APPID', '17302981', str)  # 获取的 ID，下同
API_KEY = QSettings('Fandes', 'jietuba').value('BaiduAI_APPKEY', 'wuYjn1T9GxGIXvlNkPa9QWsw', str)
SECRECT_KEY = QSettings('Fandes', 'jietuba').value('BaiduAI_SECRECT_KEY', '89wrg1oEiDzh5r0L63NmWeYNZEWUNqvG', str)
print("platform is", sys.platform)
PLATFORM_SYS = sys.platform
CONFIG_DICT = {
    "last_pic_save_name": "{}".format(str(time.strftime("%Y-%m-%d_%H.%M.%S", time.localtime()))),
    "ocr_lang": "jp",  # 默认改为日语，可为 'ch'|'en'|'jp'
}

def get_apppath():
    p = sys.path[0].replace("\\", "/").rstrip("/") if os.path.isdir(sys.path[0]) else os.path.split(sys.path[0])[0]
    # print("apppath",p)
    if sys.platform == "darwin" and p.endswith("MacOS"):
        p = os.path.join(p.rstrip("MacOS"), "Resources")
    return p


def get_screenshot_save_dir():
    """获取截图保存目录 - 桌面上的スクショ文件夹"""
    try:
        # 获取用户桌面路径
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        # 创建スクショ文件夹
        screenshot_dir = os.path.join(desktop_path, "スクショ")
        
        # 确保目录存在
        if not os.path.exists(screenshot_dir):
            os.makedirs(screenshot_dir)
            print(f"创建截图保存目录: {screenshot_dir}")
        
        return screenshot_dir
    except Exception as e:
        print(f"创建截图保存目录失败: {e}")
        # 如果失败，回退到当前目录的j_temp（为了兼容性）
        fallback_dir = "j_temp"
        if not os.path.exists(fallback_dir):
            os.makedirs(fallback_dir)
        return fallback_dir


apppath = get_apppath()

# 网络功能已移除 - 减小打包体积
# def get_request_session(url="https://github.com"):
#     # 获取系统的代理设置
#     proxies = requests.utils.get_environ_proxies(url)
#     # 创建一个 session 对象
#     session = requests.session()
#     # 设置代理配置
#     session.proxies = proxies
#     return session

# def get_UserAgent():
#     ua = "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Mobile Safari/537.36 Edg/108.0.1462.54"
#     try:
#         ua_file = os.path.join(apppath,"fake_useragent_0.1.11.json")
#         if os.path.exists(ua_file):
#             ua = UserAgent(path=os.path.join(apppath,"fake_useragent_0.1.11.json"),verify_ssl=False).random
#         else:
#             ua = UserAgent(verify_ssl=False).random
#     except Exception as e:
#         print(e,"get_UserAgent")
#     return ua

# def gethtml(url, times=3):  # 下载一个链接
#     try:
#         ua = get_UserAgent()
#         session = get_request_session(url)
#         response = session.get(url, headers={"User-Agent": ua}, timeout=8, verify=False)
#         response.encoding = 'utf-8'
#         if response.status_code == 200:
#             return response.text
#     except Exception as e:
#         error_msg = "{}".format(sys.exc_info())
#         print(error_msg, '重试中')
#         time.sleep(1)
#         if times > 0:
#             return gethtml(url, times=times - 1)
#         else:
#             return error_msg
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

                


class mutilocr(QThread):
    """多图片文字识别线程"""
    statusbarsignal = pyqtSignal(str)
    ocr_signal = pyqtSignal(str, str)

    def __init__(self, files):
        super(mutilocr, self).__init__()
        self.files = files
        self.threadlist = []
        self.filename = ""

    def run(self) -> None:
        for file in self.files:
            self.statusbarsignal.emit('开始识别图片')
            filename = os.path.basename(file)
            self.filename = filename
            with open(file, 'rb') as f:
                img_bytes = f.read()
                # 从字节数组读取图像
                np_array = np.frombuffer(img_bytes, np.uint8)
                img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
            print("正在识别图片：\t" + filename)
            
            self.statusbarsignal.emit('正在识别: ' + filename)
            self.ocr_signal.emit(self.filename, "\n>>>>识别图片:{}<<<<\n".format(filename))
            # OCR功能已移除，跳过文字识别
            self.statusbarsignal.emit('OCR功能已禁用: ' + filename)
            self.ocr_signal.emit(self.filename, "\n>>>>OCR功能已移除，跳过识别:{}<<<<\n".format(filename))
            # th = OcrimgThread(img)
            # th.result_show_signal.connect(self.mutil_cla_signalhandle)
            # th.start()
            # th.wait()
            # self.threadlist.append(th)

    def mutil_cla_signalhandle(self, text):
        """一个结果回调"""
        self.ocr_signal.emit(self.filename, text)
        print("已识别{}".format(self.filename))


# OCR功能已移除 - OcrimgThread类已禁用
# 如需恢复文字识别功能，请：
# 1. 安装PaddleOCR相关依赖
# 2. 恢复PaddleOCRModel模块
# 3. 取消下方注释

# class OcrimgThread(QThread):
#     """文字识别线程"""
#     # simple_show_signal = pyqtSignal(str)
#     result_show_signal = pyqtSignal(str)
#     statusbar_signal = pyqtSignal(str)
#     det_res_img = pyqtSignal(QPixmap)# 返回文字监测结果
#     boxes_info_signal = pyqtSignal(list)# 返回识别信息结果
#     def __init__(self, image, lang: str = None):
#         super(QThread, self).__init__()
#         self.image = image  # img
#         self.ocr_result = None
#         self.ocr_sys = None
#         self.lang = (lang or CONFIG_DICT.get("ocr_lang", "ch")).lower()
#         # self.simple_show_signal.connect(jamtools.simple_show)
#     def get_match_text(self,match_text_boxes):
#         if self.ocr_sys is not None:
#             return self.ocr_sys.get_format_text(match_text_boxes)
#     def run(self):
#         self.statusbar_signal.emit('正在识别文字...')
#         text = ""  # 初始化text变量
#         try:
#             if OcrDetector is None:
#                 text = "OCR模块不可用，请检查依赖库安装"
#                 self.statusbar_signal.emit('OCR模块不可用！')
#                 self.result_show_signal.emit(text)
#                 print("OCR模块不可用")
#                 return
#                 
#             self.ocr_sys = OcrDetector(self.image, use_dnn=False, version=3, lang=self.lang)  # 支持v2和v3版本的
#             stime = time.time()
#             # 得到检测框
#             dt_boxes = self.ocr_sys.get_boxes()
#             image = self.ocr_sys.draw_boxes(dt_boxes[0],self.image)
#             # cv2.imwrite("testocr.png",image)
#             image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
#             # 创建QImage对象
#             height, width, channel = image.shape
#             bytesPerLine = 3 * width
#             qimage = QImage(image.data, width, height, bytesPerLine, QImage.Format_RGB888)
# 
#             # 创建QPixmap对象
#             qpixmap = QPixmap.fromImage(qimage)
#             self.det_res_img.emit(qpixmap)
#             
#             dettime = time.time()
#             print(len(dt_boxes[0]))
#             if len(dt_boxes[0])==0:
#                 text="<没有识别到文字>"
#             else:
#                 # 识别 results: 单纯的识别结果，results_info: 识别结果+置信度    原图
#                 # 识别模型固定尺寸只能100长度，需要处理可以根据自己场景导出模型 1000
#                 # onnx可以支持动态，不受限
#                 results, results_info = self.ocr_sys.recognition_img(dt_boxes)
#                 # print(f'results :{str(results)}')
#                 print("识别时间:",time.time()-dettime,dettime - stime)
#                 match_text_boxes = self.ocr_sys.get_match_text_boxes(dt_boxes[0],results)
#                 text= self.ocr_sys.get_format_text(match_text_boxes)
#                 self.boxes_info_signal.emit(match_text_boxes)
#             # print(text)
#         except Exception as e:
#             print("Unexpected error:",e, "jampublic l326")
#             text = f"识别出错：{str(e)}"
#             self.statusbar_signal.emit('识别出错！{}'.format(str(e)))
#         # print(text)
#         if text == '':
#             text = '没有识别到文字'
#         self.ocr_result = text
#         self.result_show_signal.emit(text)
#         self.statusbar_signal.emit('识别完成！')
# 
#         print("识别完成")


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
    # 网络功能已移除 - 以下代码已禁用
    # app = QApplication(sys.argv)
    # w = Transparent_windows(20, 20, 500, 200)
    # w.show()
    # import json
    # a = gethtml("https://raw.githubusercontent.com/fandesfyf/JamTools/main/ci_scripts/versions.json")  # 网络功能已移除
    # print(json.loads(a))
    # w.setGeometry()
    # sys.exit(app.exec_())
    pass  # 保持语法正确性
