# -*- coding: utf-8 -*-
"""
jietuba_widgets.py - 自定义控件模块

提供截图工具使用的各种自定义 UI 控件和组件。

主要类:
- FramelessEnterSendQTextEdit: 无边框回车发送文本框
- Freezer: 钉图窗口类,支持图片置顶显示和编辑

特点:
支持拖拽、快捷键、透明度调整、绘图编辑、历史记录等

依赖模块:
jietuba_public, jietuba_resource, jietuba_text_drawer
"""
import os
import re
import numpy as np
import cv2
import jietuba_resource
from PyQt5.QtCore import Qt, pyqtSignal, QStandardPaths, QUrl, QTimer, QSize, QPoint, QRectF
from PyQt5.QtGui import QTextCursor, QDesktopServices, QMouseEvent, QTextOption, QCursor, QKeyEvent
from PyQt5.QtGui import QPainter, QPen, QIcon, QFont, QImage, QPixmap, QColor, QLinearGradient, QMovie, QPolygon, QBrush
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QMenu
from jietuba_public import linelabel,TipsShower, get_screenshot_save_dir
# OcrimgThread已移除 - 如需OCR功能请手动添加

class FramelessEnterSendQTextEdit(QTextEdit):
    """重写的OCR文字识别结果显示窗口 - 更简单高效"""
    clear_signal = pyqtSignal()
    showm_signal = pyqtSignal(str)
    del_myself_signal = pyqtSignal(int)

    def __init__(self, parent=None, enter_tra=False, autoresetid=0):
        super().__init__(parent)
        self._parent_widget = parent  # 避免覆盖parent()方法
        self.action = self.show
        self.moving = False
        self.autoreset = autoresetid
        self.enter_tra = enter_tra  # 保存参数为实例变量
        
        # 历史记录设置
        self.hsp = os.path.join(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation),
                                "JietubaSimpleModehistory.txt")
        if os.path.exists(self.hsp):
            with open(self.hsp, "r", encoding="utf-8") as f:
                self.history = f.read().split("<\n\n<<>>\n\n>")
        else:
            self.history = []
        self.setMouseTracking(True)
        
        # 字体设置 - 优化按钮和文本的字体大小比例
        text_font = QFont('Microsoft YaHei', 11)  # 文本字体稍小
        text_font.setStyleHint(QFont.SansSerif)
        self.setFont(text_font)
        self.setPlaceholderText('OCR認識結果...')
        
        # 文本设置
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(15)

        text_style = """
            FramelessEnterSendQTextEdit {
                background-color: rgba(255, 255, 255, 0.98);
                border: 2px solid #3498db;
                border-radius: 12px;
                padding: 15px;
                font-family: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif;
                font-size: 11pt;
                color: #2c3e50;
                selection-background-color: #3498db;
                line-height: 1.4;
            }
        """
        self.setStyleSheet(text_style)
        
        # 初始大小 - 明显更大
        self.setMinimumSize(300, 150)
        self.resize(400, 200)

        # 定位到屏幕中央
        screen_center = QApplication.desktop().screen().rect().center()
        self.move(screen_center.x() - 200, screen_center.y() - 100)
        
        # 连接文本变化信号
        self.document().contentsChanged.connect(self.auto_resize)
        
        # 创建工具栏
        self._create_toolbar()
        
        # 信号连接
        self.clear_signal.connect(self.clear)
        
        print("✅ 新文本输入框初始化完成")

    def _set_initial_position(self):
        """智能设置初始位置，支持多显示器环境"""
        try:
            # 初始化时，截图区域坐标可能还未设置，所以只做基础定位
            # 主要的智能定位会在_smart_reposition_before_show中进行
            
            # 使用鼠标当前位置确定显示器
            cursor_pos = QCursor.pos()
            parent_center_x = cursor_pos.x()
            parent_center_y = cursor_pos.y()
            print(f"📍 初始化时使用鼠标位置: ({parent_center_x}, {parent_center_y})")
            
            # 找到包含该点的显示器
            target_screen = None
            for screen in QApplication.screens():
                screen_rect = screen.geometry()
                if screen_rect.contains(parent_center_x, parent_center_y):
                    target_screen = screen
                    break
            
            if target_screen is None:
                target_screen = QApplication.primaryScreen()
            
            # 在目标显示器中设置一个临时位置，真正的智能定位在显示时进行
            screen_rect = target_screen.availableGeometry()
            initial_x = screen_rect.x() + screen_rect.width() // 3
            initial_y = screen_rect.y() + screen_rect.height() // 3
            
            self.setGeometry(initial_x, initial_y, 100, 100)
            print(f"📍 OCR窗口临时位置: 显示器{target_screen.name()} ({initial_x}, {initial_y})")
            
        except Exception as e:
            print(f"⚠️ 设置初始位置失败，使用默认位置: {e}")
            # 出错时使用主显示器中心
            desktop = QApplication.desktop()
            self.setGeometry(desktop.width()//2, desktop.height()//2, 100, 100)

    def _smart_reposition_before_show(self):
        """在显示前智能重新定位窗口"""
        try:
            # 尝试从父窗口获取当前截图区域的显示器信息
            target_screen = None
            
            if self._parent_widget:
                # 如果有父窗口，尝试获取截图区域信息
                if hasattr(self._parent_widget, 'x0') and hasattr(self._parent_widget, 'y0'):
                    # 获取截图区域的中心点
                    center_x = (self._parent_widget.x0 + self._parent_widget.x1) // 2
                    center_y = (self._parent_widget.y0 + self._parent_widget.y1) // 2
                    
                    # 找到包含截图区域的显示器
                    for screen in QApplication.screens():
                        screen_rect = screen.geometry()
                        if screen_rect.contains(center_x, center_y):
                            target_screen = screen
                            break
            
            if target_screen is None:
                # 使用鼠标当前位置确定显示器
                cursor_pos = QCursor.pos()
                for screen in QApplication.screens():
                    screen_rect = screen.geometry()
                    if screen_rect.contains(cursor_pos):
                        target_screen = screen
                        break
            
            if target_screen is None:
                target_screen = QApplication.primaryScreen()
            
            # 获取目标显示器的可用区域
            screen_rect = target_screen.availableGeometry()  # 使用availableGeometry排除任务栏等
            screen_x, screen_y, screen_w, screen_h = screen_rect.getRect()
            
            # 检查当前位置是否在目标显示器内
            current_right = self.x() + self.width()
            current_bottom = self.y() + self.height()
            
            if not (screen_x <= self.x() < screen_x + screen_w and 
                   screen_y <= self.y() < screen_y + screen_h and
                   current_right <= screen_x + screen_w and
                   current_bottom <= screen_y + screen_h):
                
                # 窗口不在目标显示器内，重新定位
                # 优先显示在截图区域附近，但确保在屏幕边界内
                if (self._parent_widget and 
                    hasattr(self._parent_widget, 'x0') and 
                    hasattr(self._parent_widget, 'y0') and
                    self._parent_widget.x0 > 0 and self._parent_widget.y0 > 0):  # 检查坐标是否有效
                    
                    # 尝试在截图区域右下角显示
                    preferred_x = max(self._parent_widget.x0, self._parent_widget.x1) + 10
                    preferred_y = max(self._parent_widget.y0, self._parent_widget.y1) + 10
                    
                    # 确保在屏幕边界内
                    if preferred_x + self.width() > screen_x + screen_w:
                        preferred_x = screen_x + screen_w - self.width() - 20
                    if preferred_y + self.height() > screen_y + screen_h:
                        preferred_y = screen_y + screen_h - self.height() - 20
                    
                    # 确保不小于屏幕起始位置
                    preferred_x = max(preferred_x, screen_x + 10)
                    preferred_y = max(preferred_y, screen_y + 10)
                    
                    print(f"📍 基于有效截图区域重新定位: ({preferred_x}, {preferred_y})")
                    
                else:
                    # 截图区域坐标无效或不存在，使用屏幕中心偏右下
                    preferred_x = screen_x + screen_w * 2 // 3
                    preferred_y = screen_y + screen_h * 2 // 3
                    print(f"📍 使用默认重新定位: ({preferred_x}, {preferred_y})")
                
                print(f"📍 重新定位OCR窗口到显示器{target_screen.name()}: ({preferred_x}, {preferred_y})")
                self.move(preferred_x, preferred_y)
            else:
                print(f"📍 OCR窗口已在正确显示器内，无需重新定位")
                
        except Exception as e:
            print(f"⚠️ 智能重新定位失败: {e}")

    def _create_toolbar(self):
        """创建工具栏"""
        self.toolbar = QWidget()
        self.toolbar.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        
        # 设置工具栏背景样式
        toolbar_bg_style = """
            QWidget {
                background-color: rgba(248, 249, 250, 0.98);
                border: 2px solid #3498db;
                border-radius: 12px;
            }
        """
        self.toolbar.setStyleSheet(toolbar_bg_style)
        
        # 创建布局 - 增加间距，确保按钮不挤在一起
        layout = QHBoxLayout(self.toolbar)
        layout.setContentsMargins(20, 12, 20, 12)  # 增加边距
        layout.setSpacing(15)  # 增加按钮间距
        
        # 统一按钮样式 - 更加合适的尺寸和字体
        btn_base_style = """
            QPushButton {
                background-color: rgba(52, 152, 219, 0.95);
                color: white;
                border: 1px solid #2980b9;
                border-radius: 6px;
                font-weight: bold;
                font-size: 10pt;
                font-family: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif;
                padding: 8px 14px;
                min-width: 65px;
                max-width: 85px;
                min-height: 34px;
                max-height: 38px;
            }
            QPushButton:hover {
                background-color: rgba(41, 128, 185, 0.95);
                border: 1px solid #1f5f85;
            }
            QPushButton:pressed {
                background-color: rgba(31, 95, 133, 0.95);
            }
        """
        
        # 创建按钮 - 使用短小精悍的日语文本
        # 复制按钮
        self.copy_btn = QPushButton("コピー")
        self.copy_btn.setStyleSheet(btn_base_style)
        self.copy_btn.clicked.connect(self.copy_text)
        self.copy_btn.setToolTip('テキストをクリップボードにコピー')
        
        # 清空按钮
        self.clear_btn = QPushButton("クリア")
        self.clear_btn.setStyleSheet(btn_base_style)
        self.clear_btn.clicked.connect(self.clear)
        self.clear_btn.setToolTip('テキスト内容をクリア')
        
        # 关闭按钮 - 特殊颜色和稍微大一点的字体
        self.close_btn = QPushButton("閉じる")
        close_btn_style = """
            QPushButton {
                background-color: rgba(220, 53, 69, 0.95);
                color: white;
                border: 1px solid #c82333;
                border-radius: 6px;
                font-weight: bold;
                font-size: 10pt;
                font-family: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif;
                padding: 8px 14px;
                min-width: 65px;
                max-width: 85px;
                min-height: 34px;
                max-height: 38px;
            }
            QPushButton:hover {
                background-color: rgba(200, 35, 51, 0.95);
                border: 1px solid #a71e2a;
            }
            QPushButton:pressed {
                background-color: rgba(167, 30, 42, 0.95);
            }
        """
        self.close_btn.setStyleSheet(close_btn_style)
        self.close_btn.clicked.connect(self.close_completely)
        self.close_btn.setToolTip('OCR識別ウィンドウを閉じる')
        
        # 添加按钮到布局
        layout.addWidget(self.copy_btn)
        layout.addWidget(self.clear_btn)
        layout.addWidget(self.close_btn)
        
        # 设置工具栏大小 - 适应更大的按钮和间距
        self.toolbar.setFixedSize(320, 62)

    def auto_resize(self):
        """自动调整大小 - 简化版本"""
        text = self.toPlainText()
        
        # 获取文档尺寸
        doc = self.document()
        doc.adjustSize()
        doc_size = doc.size()
        
        # 计算新尺寸
        padding = 50  # 内边距
        min_width, min_height = 300, 150
        max_width, max_height = 800, 600
        
        new_width = max(min_width, min(max_width, int(doc_size.width()) + padding))
        
        if text.strip():
            # 有文本：使用2.5倍高度确保足够空间
            calculated_height = int(doc_size.height() * 2.5) + padding
            new_height = max(min_height, min(max_height, calculated_height))
        else:
            # 空文本：使用最小高度
            new_height = min_height
        
        # 应用新尺寸
        old_size = self.size()
        self.setFixedSize(new_width, new_height)
        
        print(f"� 文本框自动调整: {old_size.width()}x{old_size.height()} → {new_width}x{new_height}")
        print(f"   文本长度: {len(text)}, 文档尺寸: {doc_size.width()}x{doc_size.height()}")
        
        # 保持在屏幕内
        self._keep_in_screen()
        
        # 更新工具栏位置
        self._update_toolbar_position()
        
        # 强制更新
        self.update()
        QApplication.processEvents()

    def _keep_in_screen(self):
        """保持窗口在屏幕范围内"""
        screen = QApplication.desktop().screenGeometry()
        x, y = self.x(), self.y()
        w, h = self.width(), self.height()
        
        if x + w > screen.width():
            x = screen.width() - w - 20
        if y + h > screen.height():
            y = screen.height() - h - 20
        if x < 10:
            x = 10
        if y < 10:
            y = 10
            
        self.move(x, y)

    def _update_toolbar_position(self):
        """更新工具栏位置"""
        if hasattr(self, 'toolbar') and self.isVisible():
            # 工具栏放在文本框下方中央
            toolbar_x = self.x() + (self.width() - self.toolbar.width()) // 2
            toolbar_y = self.y() + self.height() + 10
            
            # 确保工具栏在屏幕内
            screen = QApplication.desktop().screenGeometry()
            if toolbar_x + self.toolbar.width() > screen.width():
                toolbar_x = screen.width() - self.toolbar.width() - 10
            if toolbar_y + self.toolbar.height() > screen.height():
                toolbar_y = self.y() - self.toolbar.height() - 10
                
            self.toolbar.move(toolbar_x, toolbar_y)

    def copy_text(self):
        """复制文本到剪贴板"""
        text = self.toPlainText().strip()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            # 显示复制成功提示 - 适配按钮字体大小
            original_placeholder = self.placeholderText()
            self.setPlaceholderText("✓ クリップボードにコピーしました")
            
            # 临时调整提示文字样式
            temp_style = """
                FramelessEnterSendQTextEdit {
                    background-color: rgba(255, 255, 255, 0.98);
                    border: 2px solid #28a745;
                    border-radius: 12px;
                    padding: 15px;
                    font-family: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif;
                    font-size: 11pt;
                    color: #28a745;
                    selection-background-color: #3498db;
                    line-height: 1.4;
                }
            """
            self.setStyleSheet(temp_style)
            
            # 2秒后恢复
            import weakref
            weak_self = weakref.ref(self)
            def restore_style():
                obj = weak_self()
                if obj is not None:
                    obj.setPlaceholderText(original_placeholder)
                    obj.setStyleSheet("""
                        FramelessEnterSendQTextEdit {
                            background-color: rgba(255, 255, 255, 0.98);
                            border: 2px solid #3498db;
                            border-radius: 12px;
                            padding: 15px;
                            font-family: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif;
                            font-size: 11pt;
                            color: #2c3e50;
                            selection-background-color: #3498db;
                            line-height: 1.4;
                        }
                    """)
            QTimer.singleShot(2000, restore_style)
            print(f"✅ 文本已复制到剪贴板: {len(text)} 字符")
        else:
            self.setPlaceholderText("コピーするテキストがありません")
            # 使用弱引用避免对象被删除时的错误
            import weakref
            weak_self = weakref.ref(self)
            def reset_placeholder():
                obj = weak_self()
                if obj is not None:
                    obj.setPlaceholderText("OCR認識結果...")
            QTimer.singleShot(2000, reset_placeholder)

    def close_completely(self):
        """完全关闭"""
        if self._parent_widget and hasattr(self._parent_widget, 'cleanup_ocr_state'):
            self._parent_widget.cleanup_ocr_state()
        self.hide()

    def show(self):
        """显示窗口"""
        super().show()
        if hasattr(self, 'toolbar'):
            self.toolbar.show()
            self._update_toolbar_position()
        self.activateWindow()
        self.raise_()
        self.setFocus()

    def hide(self):
        """隐藏窗口"""
        if hasattr(self, 'toolbar'):
            self.toolbar.hide()
        super().hide()

    def move(self, x, y):
        """移动窗口"""
        super().move(x, y)
        self._update_toolbar_position()

    def insertPlainText(self, text):
        """插入文本"""
        super().insertPlainText(text)
        self.show()

    def keyPressEvent(self, e):
        """键盘事件"""
        if e.key() == Qt.Key_Return or e.key() == Qt.Key_Enter:
            if e.modifiers() & Qt.ControlModifier:
                # Ctrl+Enter: 完成输入
                self.action()
                return
            else:
                # Enter: 换行
                super().keyPressEvent(e)
                return
        
        super().keyPressEvent(e)
        
        # 历史记录快捷键
        if e.key() == Qt.Key_Left and e.modifiers() == Qt.ControlModifier:
            self.last_history()
        elif e.key() == Qt.Key_Right and e.modifiers() == Qt.ControlModifier:
            self.next_history()
        elif e.key() == Qt.Key_S and e.modifiers() == Qt.ControlModifier:
            self.addhistory()

    def closeEvent(self, e):
        """关闭事件"""
        if hasattr(self, 'toolbar'):
            self.toolbar.close()
        super().closeEvent(e)

    # 历史记录方法
    def addhistory(self):
        text = self.toPlainText()
        if text not in self.history and len(text.replace(" ", "").replace("\n", "")):
            self.history.append(text)
            mode = "r+" if os.path.exists(self.hsp) else "w+"
            with open(self.hsp, mode, encoding="utf-8") as f:
                hislist = f.read().split("<\n\n<<>>\n\n>")
                hislist.append(text)
                if len(hislist) > 20:
                    hislist = hislist[-20:]
                    self.history = self.history[-20:]
                newhis = "<\n\n<<>>\n\n>".join(hislist)
                f.seek(0)
                f.truncate()
                f.write(newhis)
            self.history_pos = len(self.history)

    def keyenter_connect(self, action):
        self.action = action

    def next_history(self):
        if self.history_pos < len(self.history) - 1:
            hp = self.history_pos
            self.clear()
            self.history_pos = hp + 1
            self.setText(self.history[self.history_pos])

    def last_history(self):
        hp = self.history_pos
        self.addhistory()
        self.history_pos = hp
        if self.history_pos > 0:
            hp = self.history_pos
            self.clear()
            self.history_pos = hp - 1
            self.setText(self.history[self.history_pos])

    def clear(self, notsave=False):
        save = not notsave
        if save:
            self.addhistory()
        self.history_pos = len(self.history)
        super().clear()
        # 设置现代化样式
        self.setStyleSheet("""
            FramelessEnterSendQTextEdit {
                background-color: rgba(255, 255, 255, 0.95);
                border: 2px solid #e1e5e9;
                border-radius: 12px;
                padding: 12px;
                font-family: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif;
                font-size: 11pt;
                color: #2c3e50;
                selection-background-color: #3498db;
            }
            QPushButton {
                background-color: rgba(248, 249, 250, 0.9);
                border: 1px solid #dee2e6;
                border-radius: 8px;
                color: #495057;
                font-weight: 500;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: rgba(233, 236, 239, 0.9);
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: rgba(222, 226, 230, 0.9);
            }
        """)
        
        # 智能初始位置设置 - 支持多显示器环境
        self._set_initial_position()
        self.menu_size = 32
        self.button_spacing = 4
        
        # 创建工具栏容器
        self.toolbar = QWidget()
        self.toolbar.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.toolbar.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.95);
                border: 1px solid #e1e5e9;
                border-radius: 8px;
            }
        """)
        
        # 创建按钮
        self._create_buttons()
        
        # 布局工具栏
        self._layout_toolbar()
        
        # 设置工具提示
        self.setToolTip('OCR文字認識結果、編集可能\nEnterキーで改行、Ctrl+Enterで入力完了')
        self.clear_signal.connect(self.clear)
        self.textAreaChanged()
        self.activateWindow()
        self.setFocus()

        # 处理enter_tra参数（保持向后兼容）
        if self.enter_tra:
            self.action = self.show  # 新版本不再支持翻译功能

    def _create_buttons(self):
        """创建按钮"""
        # 关闭按钮 - 真正结束OCR功能
        self.close_button = QPushButton('✕', self.toolbar)
        self.close_button.setToolTip('OCR認識を終了して閉じる')
        self.close_button.setFixedSize(self.menu_size, self.menu_size)
        self.close_button.clicked.connect(self.close_ocr_completely)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(220, 53, 69, 0.9);
                color: white;
                border: 1px solid #dc3545;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: rgba(200, 35, 51, 0.9);
            }
        """)

        # 复制按钮
        self.copy_button = QPushButton('📋', self.toolbar)
        self.copy_button.setToolTip('テキストをクリップボードにコピー')
        self.copy_button.setFixedSize(self.menu_size, self.menu_size)
        self.copy_button.clicked.connect(self.copy_text)
        self.copy_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 167, 69, 0.9);
                color: white;
                border: 1px solid #28a745;
                border-radius: 6px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: rgba(34, 134, 58, 0.9);
            }
        """)

        # 清空按钮
        self.clear_button = QPushButton('🗑', self.toolbar)
        self.clear_button.setToolTip('テキスト内容をクリア')
        self.clear_button.setFixedSize(self.menu_size, self.menu_size)
        self.clear_button.clicked.connect(self.clear)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 193, 7, 0.9);
                color: #212529;
                border: 1px solid #ffc107;
                border-radius: 6px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: rgba(255, 176, 6, 0.9);
            }
        """)

        # 历史按钮
        self.history_prev_button = QPushButton('◀', self.toolbar)
        self.history_prev_button.setToolTip('前の履歴記録 (Ctrl+←)')
        self.history_prev_button.setFixedSize(self.menu_size//2 + 2, self.menu_size//2 + 2)
        self.history_prev_button.clicked.connect(self.last_history)
        
        self.history_next_button = QPushButton('▶', self.toolbar)
        self.history_next_button.setToolTip('次の履歴記録 (Ctrl+→)')
        self.history_next_button.setFixedSize(self.menu_size//2 + 2, self.menu_size//2 + 2)
        self.history_next_button.clicked.connect(self.next_history)
        
        # 历史按钮样式
        history_style = """
            QPushButton {
                background-color: rgba(108, 117, 125, 0.9);
                color: white;
                border: 1px solid #6c757d;
                border-radius: 4px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: rgba(90, 98, 104, 0.9);
            }
        """
        self.history_prev_button.setStyleSheet(history_style)
        self.history_next_button.setStyleSheet(history_style)

    def _layout_toolbar(self):
        """布局工具栏"""
        from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout
        
        # 创建主要按钮布局
        main_layout = QHBoxLayout(self.toolbar)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(self.button_spacing)
        
        main_layout.addWidget(self.close_button)
        main_layout.addWidget(self.copy_button)
        main_layout.addWidget(self.clear_button)
        
        # 历史按钮垂直布局
        history_layout = QVBoxLayout()
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.setSpacing(2)
        history_layout.addWidget(self.history_prev_button)
        history_layout.addWidget(self.history_next_button)
        
        main_layout.addLayout(history_layout)
        
        # 计算工具栏大小
        toolbar_width = (self.menu_size * 3 + self.menu_size//2 + 2 + 
                        self.button_spacing * 3 + 16)
        toolbar_height = self.menu_size + 12
        self.toolbar.setFixedSize(toolbar_width, toolbar_height)

    def close_ocr_completely(self):
        """完全关闭OCR功能"""
        # 发送信号通知父级清理OCR状态
        if self._parent_widget and hasattr(self._parent_widget, 'cleanup_ocr_state'):
            self._parent_widget.cleanup_ocr_state()
        
        # 隐藏工具栏和文本框
        self.toolbar.hide()
        self.hide()

    def move(self, x, y, active=False):
        """移动时同时移动工具栏，智能避免遮挡"""
        super().move(x, y)
        if hasattr(self, 'toolbar'):
            self._position_toolbar_smartly()

    def _position_toolbar_smartly(self):
        """智能定位工具栏，避免与文字窗口遮挡"""
        if not hasattr(self, 'toolbar'):
            return
            
        # 获取当前屏幕信息
        screens = QApplication.screens()
        current_screen = QApplication.primaryScreen()
        
        # 找到文字窗口所在的屏幕
        text_center_x = self.x() + self.width() // 2
        text_center_y = self.y() + self.height() // 2
        
        for screen in screens:
            geometry = screen.geometry()
            if (text_center_x >= geometry.x() and text_center_x < geometry.x() + geometry.width() and
                text_center_y >= geometry.y() and text_center_y < geometry.y() + geometry.height()):
                current_screen = screen
                break
        
        screen_rect = current_screen.geometry()
        toolbar_width = self.toolbar.width()
        toolbar_height = self.toolbar.height()
        
        # 文字窗口的边界
        text_left = self.x()
        text_right = self.x() + self.width()
        text_top = self.y()
        text_bottom = self.y() + self.height()
        
        # 尝试不同的工具栏位置（优先级从高到低）
        positions = [
            # 1. 右上角（文字窗口右侧，上方对齐）
            (text_right + 12, text_top - 5),
            # 2. 左上角（文字窗口左侧，上方对齐）
            (text_left - toolbar_width - 12, text_top - 5),
            # 3. 上方中央（文字窗口上方）
            (text_left + (self.width() - toolbar_width) // 2, text_top - toolbar_height - 10),
            # 4. 右下角（文字窗口右侧，下方对齐）
            (text_right + 12, text_bottom - toolbar_height + 5),
            # 5. 左下角（文字窗口左侧，下方对齐）
            (text_left - toolbar_width - 12, text_bottom - toolbar_height + 5),
            # 6. 下方中央（文字窗口下方）
            (text_left + (self.width() - toolbar_width) // 2, text_bottom + 10),
        ]
        
        # 选择第一个在屏幕范围内且不与钉图窗口重叠的位置
        for toolbar_x, toolbar_y in positions:
            # 检查是否在屏幕范围内
            if (toolbar_x >= screen_rect.x() + 5 and 
                toolbar_y >= screen_rect.y() + 5 and
                toolbar_x + toolbar_width <= screen_rect.x() + screen_rect.width() - 5 and
                toolbar_y + toolbar_height <= screen_rect.y() + screen_rect.height() - 5):
                
                # 检查是否与钉图窗口重叠
                overlaps_with_pinned = False
                for widget in QApplication.allWidgets():
                    if isinstance(widget, Freezer) and widget.isVisible():
                        if (toolbar_x < widget.x() + widget.width() and
                            toolbar_x + toolbar_width > widget.x() and
                            toolbar_y < widget.y() + widget.height() and
                            toolbar_y + toolbar_height > widget.y()):
                            overlaps_with_pinned = True
                            break
                
                if not overlaps_with_pinned:
                    self.toolbar.move(toolbar_x, toolbar_y)
                    return
        
        # 如果所有位置都不合适，使用默认位置（右侧，但调整到屏幕范围内）
        default_x = min(text_right + 12, screen_rect.x() + screen_rect.width() - toolbar_width - 5)
        default_y = max(screen_rect.y() + 5, min(text_top, screen_rect.y() + screen_rect.height() - toolbar_height - 5))
        
        # 最后检查默认位置是否与钉图窗口重叠，如果重叠则放到屏幕右上角
        overlaps_default = False
        for widget in QApplication.allWidgets():
            if isinstance(widget, Freezer) and widget.isVisible():
                if (default_x < widget.x() + widget.width() and
                    default_x + toolbar_width > widget.x() and
                    default_y < widget.y() + widget.height() and
                    default_y + toolbar_height > widget.y()):
                    overlaps_default = True
                    break
        
        if overlaps_default:
            # 放到屏幕右上角
            default_x = screen_rect.x() + screen_rect.width() - toolbar_width - 10
            default_y = screen_rect.y() + 10
        
        self.toolbar.move(default_x, default_y)

    def show(self):
        """显示时同时显示工具栏，并智能定位到合适的显示器"""
        # 在显示前重新定位窗口到合适的位置
        self._smart_reposition_before_show()
        
        super().show()
        if hasattr(self, 'toolbar'):
            self.toolbar.show()
            self.move(self.x(), self.y())  # 更新工具栏位置

    def hide(self):
        """隐藏时同时隐藏工具栏"""
        if hasattr(self, 'toolbar'):
            self.toolbar.hide()
        super().hide()
    def move_signal_callback(self, x, y):
        """工具栏移动回调（保留兼容性）"""
        if hasattr(self, 'toolbar'):
            new_x = x - self.width() - 8
            if self.x() != new_x or self.y() != y:
                self.move(new_x, y)
    def copy_text(self):
        """复制文本到剪贴板"""
        text = self.toPlainText().strip()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            # 显示复制成功提示
            self.setPlaceholderText("クリップボードにコピーしました ✓")
            # 使用弱引用避免对象被删除时的错误
            import weakref
            weak_self = weakref.ref(self)
            def reset_placeholder():
                obj = weak_self()
                if obj is not None:
                    obj.setPlaceholderText("OCR認識結果...")
            QTimer.singleShot(2000, reset_placeholder)

    def textAreaChanged(self, minsize=200, recheck=True, border=40):
        """根据文本内容自动调整窗口大小（修正版）"""
        print(f"🚨🚨🚨 textAreaChanged 被调用了！！！ border={border}, recheck={recheck} 🚨🚨🚨")
        self.document().adjustSize()

        # ===== 1. 基础内容高度 =====
        newWidth = self.document().size().width() + border
        original_doc_height = self.document().size().height()
        newHeight = original_doc_height * 2.0 + border // 2  # 改为2倍，效果更明显

        # ===== 2. 修正：额外计算 padding 和 margin =====
        fm = self.fontMetrics()
        line_height = fm.lineSpacing()         # 单行高度
        padding = 12                           # 来自 QSS: padding:12px
        margin = int(self.document().documentMargin())  # 文档边距
        extra = padding * 2 + margin * 2

        # 如果文本为空，至少给一行的高度，但仍应用1.2倍系数
        text_content = self.toPlainText()
        if not text_content.strip():
            # 空文本时，取较大值：要么是1.2倍计算结果，要么是最小行高
            min_empty_height = line_height + extra
            calculated_height = newHeight + extra
            newHeight = max(min_empty_height, calculated_height)
            if recheck:
                print(f"   🔤 空文本处理: min_empty={min_empty_height}, calculated={calculated_height}, 选择={newHeight}")
        else:
            newHeight = newHeight + extra
            if recheck:
                print(f"   🔤 有文本处理: 原始={original_doc_height * 1.2 + border // 2}, 加extra后={newHeight}")
            
        # 调试信息
        if recheck:  # 只在第一次调用时打印，避免重复
            print(f"🔍 高度计算调试:")
            print(f"   原始文档高度: {original_doc_height}")
            print(f"   1.2倍: {original_doc_height * 1.2}")
            print(f"   border//2: {border // 2}")
            print(f"   初步newHeight: {original_doc_height * 1.2 + border // 2}")
            print(f"   extra补偿: {extra}")
            print(f"   最终newHeight: {newHeight}")
            print(f"   文本内容: '{text_content}' (长度: {len(text_content)})")
            print(f"   当前窗口高度: {self.height()}")
            print(f"   minsize: {minsize}, min_height将是: {max(minsize // 4, 50)}")

        # ===== 3. 获取屏幕信息 =====
        current_screen = None
        screens = QApplication.screens()
        for screen in screens:
            screen_rect = screen.geometry().getRect()
            screen_x, screen_y, screen_w, screen_h = screen_rect
            window_center_x = self.x() + self.width() // 2
            window_center_y = self.y() + self.height() // 2
            if (screen_x <= window_center_x < screen_x + screen_w and
                screen_y <= window_center_y < screen_y + screen_h):
                current_screen = screen
                break

        if current_screen is None:
            current_screen = QApplication.primaryScreen()

        screen_rect = current_screen.geometry().getRect()
        screen_x, screen_y, screen_w, screen_h = screen_rect

        # ===== 4. 限制范围 =====
        min_width = max(minsize, 150)
        min_height = max(minsize // 4, 100)  # 最小高度从50增加到100

        # 宽度调整
        if newWidth < min_width:
            self.setFixedWidth(min_width)
        elif newWidth > screen_w // 2:
            self.setFixedWidth(screen_w // 2 + border)
        else:
            self.setFixedWidth(newWidth)

        # 高度调整
        if recheck:  # 调试信息
            print(f"   📏 高度调整前: newHeight={newHeight}, min_height={min_height}")
        
        if newHeight < min_height:
            if recheck:
                print(f"   ⚠️  高度被限制到最小值: {newHeight} -> {min_height}")
            self.setFixedHeight(min_height)
            if recheck:
                print(f"   🔧 setFixedHeight({min_height}) 调用完成，当前实际高度: {self.height()}")
        elif newHeight > screen_h * 2 // 3:
            max_height = screen_h * 2 // 3 + 15
            if recheck:
                print(f"   ⚠️  高度被限制到最大值: {newHeight} -> {max_height}")
            self.setFixedHeight(max_height)
            if recheck:
                print(f"   🔧 setFixedHeight({max_height}) 调用完成，当前实际高度: {self.height()}")
        else:
            if recheck:
                print(f"   ✅ 设置高度为: {newHeight}")
            self.setFixedHeight(int(newHeight))
            if recheck:
                print(f"   🔧 setFixedHeight({int(newHeight)}) 调用完成，当前实际高度: {self.height()}")
                print(f"   🔧 窗口几何: x={self.x()}, y={self.y()}, w={self.width()}, h={self.height()}")
                print(f"   🔧 是否可见: {self.isVisible()}")
                # 如果窗口不可见，强制显示
                if not self.isVisible():
                    print(f"   🔧 窗口不可见，强制显示...")
                    self.show()
                    print(f"   🔧 强制显示后是否可见: {self.isVisible()}")
                # 强制刷新界面
                self.update()
                self.repaint()
                QApplication.processEvents()

        # ===== 5. 智能边界检查 - 支持多显示器环境 =====
        self._adjust_position_for_multi_screen(screen_x, screen_y, screen_w, screen_h, border)

        # ===== 6. 再次校准 =====
        if recheck:
            self.textAreaChanged(recheck=False)

        self.adjustBotton()

    def _adjust_position_for_multi_screen(self, current_screen_x, current_screen_y, current_screen_w, current_screen_h, border):
        """智能调整窗口位置，支持多显示器环境"""
        window_right = self.x() + self.width()
        window_bottom = self.y() + self.height()
        
        # 检查窗口是否完全在某个显示器内
        is_in_any_screen = False
        for screen in QApplication.screens():
            screen_rect = screen.geometry()
            screen_x, screen_y, screen_w, screen_h = screen_rect.getRect()
            
            # 如果窗口完全在这个显示器内，则不需要调整
            if (self.x() >= screen_x and 
                self.y() >= screen_y and 
                window_right <= screen_x + screen_w and 
                window_bottom <= screen_y + screen_h):
                is_in_any_screen = True
                print(f"📍 OCR窗口完全在显示器{screen.name()}内，无需调整位置")
                break
        
        if not is_in_any_screen:
            # 窗口不在任何显示器内或跨越多个显示器，需要调整
            # 优先调整到当前显示器（通常是截图所在的显示器）
            new_x = self.x()
            new_y = self.y()
            
            # 水平位置调整
            if window_right > current_screen_x + current_screen_w:
                new_x = current_screen_x + current_screen_w - border - self.width()
            elif self.x() < current_screen_x:
                new_x = current_screen_x + border
                
            # 垂直位置调整
            if window_bottom > current_screen_y + current_screen_h:
                new_y = current_screen_y + current_screen_h - border - self.height()
            elif self.y() < current_screen_y:
                new_y = current_screen_y + border
            
            # 确保调整后的位置是有效的
            if new_x != self.x() or new_y != self.y():
                print(f"📍 调整OCR窗口位置: ({self.x()}, {self.y()}) -> ({new_x}, {new_y})")
                self.move(new_x, new_y)

    def adjustBotton(self):
        """调整工具栏位置（兼容旧版本）"""
        if hasattr(self, 'toolbar'):
            # 新版本使用独立工具栏，无需调整
            pass

    def insertPlainText(self, text):
        """插入文本并显示窗口"""
        super(FramelessEnterSendQTextEdit, self).insertPlainText(text)
        self.show()

    

    def wheelEvent(self, e) -> None:
        super(FramelessEnterSendQTextEdit, self).wheelEvent(e)
        angle = e.angleDelta() / 8
        angle = angle.y()
        if QApplication.keyboardModifiers() == Qt.ControlModifier:
            if angle > 0 and self.windowOpacity() < 1:
                self.setWindowOpacity(self.windowOpacity() + 0.1 if angle > 0 else -0.1)
            elif angle < 0 and self.windowOpacity() > 0.2:
                self.setWindowOpacity(self.windowOpacity() - 0.1)

    
            

    def keyPressEvent(self, e):
        """处理键盘事件"""
        # 标记父窗口正在编辑（如果父窗口是Freezer）
        parent_widget = super().parent()  # 使用正确的parent()方法
        if hasattr(parent_widget, '_is_editing'):
            parent_widget._is_editing = True
        
        # 处理换行：允许 Enter 键换行，只有 Ctrl+Enter 才结束输入
        if e.key() == Qt.Key_Return or e.key() == Qt.Key_Enter:
            if e.modifiers() & Qt.ControlModifier:
                # Ctrl+Enter: 结束输入，执行动作
                if hasattr(parent_widget, '_is_editing'):
                    parent_widget._is_editing = False
                self.action()
                return
            else:
                # 普通Enter: 插入换行符
                super(FramelessEnterSendQTextEdit, self).keyPressEvent(e)
                return
        
        # 处理其他按键
        super(FramelessEnterSendQTextEdit, self).keyPressEvent(e)
        
        # 历史记录快捷键
        if e.key() == Qt.Key_Left and QApplication.keyboardModifiers() == Qt.ControlModifier:
            self.last_history()
        elif e.key() == Qt.Key_Right and QApplication.keyboardModifiers() == Qt.ControlModifier:
            self.next_history()
        # 保存快捷键
        elif e.key() == Qt.Key_S and QApplication.keyboardModifiers() == Qt.ControlModifier:
            print("save")
            self.addhistory()
        elif QApplication.keyboardModifiers() not in (Qt.ShiftModifier, Qt.ControlModifier, Qt.AltModifier):
            self.history_pos = len(self.history)
        elif QApplication.keyboardModifiers() == Qt.ControlModifier and e.key() == Qt.Key_Left:
            self.last_history()
        elif QApplication.keyboardModifiers() == Qt.ControlModifier and e.key() == Qt.Key_Right:
            self.next_history()


    def addhistory(self):
        text = self.toPlainText()
        if text not in self.history and len(text.replace(" ", "").replace("\n", "")):
            self.history.append(text)
            mode = "r+"
            if not os.path.exists(self.hsp):
                mode = "w+"
            with open(self.hsp, mode, encoding="utf-8")as f:
                hislist = f.read().split("<\n\n<<>>\n\n>")
                hislist.append(text)
                if len(hislist) > 20:
                    hislist = hislist[-20:]
                    self.history = self.history[-20:]
                newhis = "<\n\n<<>>\n\n>".join(hislist)
                f.seek(0)
                f.truncate()
                f.write(newhis)
            self.history_pos = len(self.history)

    def keyenter_connect(self, action):
        self.action = action

    def next_history(self):
        if self.history_pos < len(self.history) - 1:
            hp = self.history_pos
            self.clear()
            self.history_pos = hp + 1
            self.setText(self.history[self.history_pos])
        # print("next h", self.history_pos, len(self.history))

    def last_history(self):
        hp = self.history_pos
        self.addhistory()
        self.history_pos = hp
        if self.history_pos > 0:
            hp = self.history_pos
            self.clear()
            self.history_pos = hp - 1
            self.setText(self.history[self.history_pos])
        # print("last h", self.history_pos, len(self.history))
    def showEvent(self, e):
        """显示事件"""
        super().showEvent(e)
        if hasattr(self, 'toolbar'):
            self.toolbar.show()
            
    def hide(self) -> None:
        """隐藏时同时隐藏工具栏"""
        self.addhistory()
        super(FramelessEnterSendQTextEdit, self).hide()
        if hasattr(self, 'toolbar'):
            self.toolbar.hide()
        if self.autoreset:
            print('删除', self.autoreset - 1)
            self.del_myself_signal.emit(self.autoreset - 1)
            if hasattr(self, 'toolbar'):
                self.toolbar.close()
            self.close()

    def closeEvent(self, e) -> None:
        """关闭事件"""
        print(f"🔒 [关闭事件] OCR文本窗口关闭事件触发 (autoreset={self.autoreset})")
        
        # 清理toolbar
        if hasattr(self, 'toolbar'):
            self.toolbar.close()
            self.toolbar = None
            
        # 清理历史记录等资源 - 彻底清理
        if hasattr(self, 'history'):
            if isinstance(self.history, list):
                self.history.clear()
            self.history = None
        
        # 清理其他可能的缓存
        if hasattr(self, 'history_pos'):
            self.history_pos = 0
        
        super(FramelessEnterSendQTextEdit, self).closeEvent(e)
        
        # 延迟删除Qt对象
        QTimer.singleShot(50, self.deleteLater)
        
        print(f"🔒 [关闭事件] OCR文本窗口已标记为删除")
    def clear(self, notsave=False):
        save = not notsave
        if save:
            self.addhistory()
        self.history_pos = len(self.history)
        super(FramelessEnterSendQTextEdit, self).clear()
class Hung_widget(QLabel):
    button_signal = pyqtSignal(str)
    def __init__(self,parent=None,funcs = []):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setMouseTracking(True)
        size = 30
        self.buttonsize = size
        self.buttons = []
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: rgba(255, 255, 255, 0); border-radius: 6px;")  # 设置背景色和边框
        for i,func in enumerate(funcs):
            if str(func).endswith(("png","jpg")):
                botton = QPushButton(QIcon(func), '', self)
            else:
                botton = QPushButton(str(func), self)
            botton.clicked.connect(lambda checked, index=func: self.button_signal.emit(index))
            botton.setGeometry(0,i*size,size,size)
            botton.setStyleSheet("""QPushButton {
            border: 2px solid #8f8f91;
            background-color: qradialgradient(
                cx: -0.3, cy: 0.4,
                fx: -0.3, fy: 0.4,
                radius: 1.35,
                stop: 0 #fff,
                stop: 1 #888
            );
            color: white;
            font-size: 16px;
            padding: 6px;
        }

        QPushButton:hover {
            background-color: qradialgradient(
                cx: -0.3, cy: 0.4,
                fx: -0.3, fy: 0.4,
                radius: 1.35,
                stop: 0 #fff,
                stop: 1 #bbb
            );
        }""")
            self.buttons.append(botton)
        self.resize(size,size*len(funcs))

        
    def set_ontop(self,on_top=True):
        if on_top:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.setWindowFlag(Qt.Tool, False)
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.setWindowFlag(Qt.Tool, True)
    def clear(self):
        self.clearMask()
        self.hide()
        super().clear()

    def closeEvent(self, e):
        self.clear()
        super().closeEvent(e)
        
class Loading_label(QLabel):
    def __init__(self, parent=None,size = 100,text=None):
        super().__init__(parent)
        self.giflabel = QLabel(parent = self,text=text if text is not None else "")
        self.giflabel.resize(size, size)
        self.giflabel.setAlignment(Qt.AlignCenter)
        self.gif = QMovie(':./load.gif')
        self.gif.setScaledSize(QSize(size, size))
        self.giflabel.setMovie(self.gif)
    def resizeEvent(self, a0) -> None:
        
        size = min(self.width(),self.height())//3 
        if size < 50:
            size = min(self.width(),self.height())-5
            
        self.gif.setScaledSize(QSize(size, size))
        self.giflabel.resize(size, size)
        self.giflabel.move(self.width()//2-self.giflabel.width()//2,self.height()//2-self.giflabel.height()//2)
        return super().resizeEvent(a0)
    
    def start(self):
        self.gif.start()
        self.show()
    def stop(self):
        self.gif.stop()
        self.hide()

class PinnedPaintLayer(QLabel):
    """钉图窗口的绘画层，完全照搬截图窗口的paintlayer逻辑"""
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self._parent_widget = parent  # 避免覆盖parent()方法
        self.main_window = main_window
        self.px, self.py = 0, 0
        self.setStyleSheet("background-color:rgba(255,255,255,0);")
        pix = QPixmap(parent.width(), parent.height())
        pix.fill(Qt.transparent)
        self.setPixmap(pix)
        self.pixPainter = None
        # 设置鼠标追踪，让paintlayer接收所有鼠标事件，然后透传给父窗口
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        """将鼠标按下事件直接转发给主窗口进行绘画处理"""
        # print(f"PaintLayer鼠标按下调试: 转发给主窗口，坐标=({event.x()}, {event.y()})")
        
        # 检查是否有绘画工具激活
        if (self.main_window and hasattr(self.main_window, 'painter_tools') and 
            1 in self.main_window.painter_tools.values()):
            
            # 创建标记的事件对象
            main_event = QMouseEvent(event.type(), event.pos(), 
                                   event.globalPos(), event.button(), event.buttons(), event.modifiers())
            main_event._from_pinned_window = True
            main_event._pinned_window_instance = self._parent_widget  # 添加当前钉图窗口引用
            
            # print(f"PaintLayer委托调试: 调用主窗口mousePressEvent")
            self.main_window.mousePressEvent(main_event)
        else:
            # 没有绘画工具激活时，转发给父窗口（Freezer）处理
            # print(f"PaintLayer鼠标按下调试: 无绘画工具，转发给父窗口")
            if self._parent_widget:
                self._parent_widget.mousePressEvent(event)
            
    def mouseReleaseEvent(self, event):
        """将鼠标释放事件直接转发给主窗口进行绘画处理"""
        # print(f"PaintLayer鼠标释放调试: 转发给主窗口")
        
        # 检查是否有绘画工具激活
        if (self.main_window and hasattr(self.main_window, 'painter_tools') and 
            1 in self.main_window.painter_tools.values()):
            
            # 创建标记的事件对象
            main_event = QMouseEvent(event.type(), event.pos(), 
                                   event.globalPos(), event.button(), event.buttons(), event.modifiers())
            main_event._from_pinned_window = True
            main_event._pinned_window_instance = self._parent_widget  # 添加当前钉图窗口引用
            
            # print(f"PaintLayer委托调试: 调用主窗口mouseReleaseEvent")
            self.main_window.mouseReleaseEvent(main_event)
        else:
            # 没有绘画工具激活时，转发给父窗口（Freezer）处理
            # print(f"PaintLayer鼠标释放调试: 无绘画工具，转发给父窗口")
            if self._parent_widget:
                self._parent_widget.mouseReleaseEvent(event)
            
    def mouseMoveEvent(self, event):
        """将鼠标移动事件直接转发给主窗口，同时更新鼠标位置"""
        # 更新鼠标位置用于绘制鼠标圆圈
        self.px, self.py = event.x(), event.y()
        self.update()  # 触发重绘以显示鼠标圆圈
        
        # 检查是否有绘画工具激活
        if (self.main_window and hasattr(self.main_window, 'painter_tools') and 
            1 in self.main_window.painter_tools.values()):
            
            # 创建标记的事件对象
            main_event = QMouseEvent(event.type(), event.pos(), 
                                   event.globalPos(), event.button(), event.buttons(), event.modifiers())
            main_event._from_pinned_window = True
            main_event._pinned_window_instance = self._parent_widget  # 添加当前钉图窗口引用
            
            self.main_window.mouseMoveEvent(main_event)
        else:
            # 没有绘画工具激活时，转发给父窗口（Freezer）处理
            if self._parent_widget:
                self._parent_widget.mouseMoveEvent(event)

    def paintEvent(self, e):
        super().paintEvent(e)
        
        # 检查父窗口或主窗口是否正在关闭
        if (not self.main_window or 
            getattr(self.main_window, 'closed', False) or 
            getattr(self._parent_widget, 'closed', False)):
            return
            
        if not self.main_window or self.main_window.on_init:
            print('oninit return')
            return
        if 1 in self.main_window.painter_tools.values():  # 如果有画笔工具打开
            painter = QPainter(self)
            color = QColor(self.main_window.pencolor)
            color.setAlpha(255)

            width = self.main_window.tool_width
            painter.setPen(QPen(color, 1, Qt.SolidLine))
            rect = QRectF(self.px - width // 2, self.py - width // 2,
                          width, width)
            painter.drawEllipse(rect)  # 画鼠标圆
            painter.end()
        
        try:
            self.pixPainter = QPainter(self.pixmap())
            self.pixPainter.setRenderHint(QPainter.Antialiasing)
        except Exception:
            print('pixpainter fail!')
            self.pixPainter = None

        def get_ture_pen_alpha_color():
            color = QColor(self.main_window.pencolor)
            if color.alpha() != 255:
                al = self.main_window.pencolor.alpha() / (self.main_window.tool_width / 2)
                if al > 1:
                    color.setAlpha(al)
                else:
                    color.setAlpha(1)
            return color

        base_painter = None
        base_pixmap = None
        target_label = getattr(self, '_parent_widget', None)
        if (self.main_window.painter_tools.get('highlight_on') and target_label and
                hasattr(target_label, 'pixmap')):
            base_pixmap = target_label.pixmap()
            if base_pixmap and not base_pixmap.isNull():
                base_painter = QPainter(base_pixmap)
                base_painter.setRenderHint(QPainter.Antialiasing)
                base_painter.setCompositionMode(QPainter.CompositionMode_Multiply)

        while len(self.main_window.pen_pointlist):  # 画笔工具
            color = get_ture_pen_alpha_color()
            pen_painter = base_painter if base_painter else self.pixPainter
            if not pen_painter:
                break
            pen_painter.setBrush(color)
            pen_painter.setPen(Qt.NoPen)
            pen_painter.setRenderHint(QPainter.Antialiasing)
            new_pen_point = self.main_window.pen_pointlist.pop(0)
            if self.main_window.old_pen is None:
                self.main_window.old_pen = new_pen_point
                continue
            if self.main_window.old_pen[0] != -2 and new_pen_point[0] != -2:
                # 荧光笔使用正方形笔刷，普通画笔使用圆形笔刷
                if self.main_window.painter_tools.get('highlight_on'):
                    pen_painter.drawRect(new_pen_point[0] - self.main_window.tool_width / 2,
                                         new_pen_point[1] - self.main_window.tool_width / 2,
                                         self.main_window.tool_width, self.main_window.tool_width)
                else:
                    pen_painter.drawEllipse(new_pen_point[0] - self.main_window.tool_width / 2,
                                            new_pen_point[1] - self.main_window.tool_width / 2,
                                            self.main_window.tool_width, self.main_window.tool_width)
                if abs(new_pen_point[0] - self.main_window.old_pen[0]) > 1 or abs(
                        new_pen_point[1] - self.main_window.old_pen[1]) > 1:
                    # 这里需要导入get_line_interpolation函数
                    from jietuba_screenshot import get_line_interpolation
                    interpolateposs = get_line_interpolation(new_pen_point[:], self.main_window.old_pen[:])
                    if interpolateposs is not None:
                        for pos in interpolateposs:
                            x, y = pos
                            # 荧光笔使用正方形笔刷，普通画笔使用圆形笔刷
                            if self.main_window.painter_tools.get('highlight_on'):
                                pen_painter.drawRect(x - self.main_window.tool_width / 2,
                                                     y - self.main_window.tool_width / 2,
                                                     self.main_window.tool_width, self.main_window.tool_width)
                            else:
                                pen_painter.drawEllipse(x - self.main_window.tool_width / 2,
                                                        y - self.main_window.tool_width / 2,
                                                        self.main_window.tool_width, self.main_window.tool_width)

            self.main_window.old_pen = new_pen_point

        if base_painter:
            base_painter.end()
            if base_pixmap:
                try:
                    target_label.setPixmap(base_pixmap)
                    if hasattr(target_label, 'showing_imgpix'):
                        target_label.showing_imgpix = base_pixmap.copy()
                    target_label.update()
                except Exception as sync_err:
                    print(f"⚠️ 钉图荧光笔同步失败: {sync_err}")

        # 处理矩形工具
        if self.main_window.drawrect_pointlist[0][0] != -2 and self.main_window.drawrect_pointlist[1][0] != -2:
            try:
                temppainter = QPainter(self)
                temppainter.setPen(QPen(self.main_window.pencolor, self.main_window.tool_width, Qt.SolidLine))
                poitlist = self.main_window.drawrect_pointlist
                temppainter.drawRect(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                     abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                temppainter.end()
            except Exception as e:
                print(f"钉图画矩形临时QPainter错误: {e}")
                
            if self.main_window.drawrect_pointlist[2] == 1:
                try:
                    self.pixPainter.setPen(QPen(self.main_window.pencolor, self.main_window.tool_width, Qt.SolidLine))
                    self.pixPainter.drawRect(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                             abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                    self.main_window.drawrect_pointlist = [[-2, -2], [-2, -2], 0]
                    
                    # 钉图矩形绘制完成后，合并到底图并创建备份
                    print(f"钉图矩形撤销调试: paintEvent中绘制完成，合并到底图")
                    print(f"钉图矩形撤销调试: _parent_widget类型: {type(self._parent_widget)}")
                    if hasattr(self._parent_widget, '_merge_paint_to_base'):
                        print(f"钉图矩形撤销调试: 调用_merge_paint_to_base()")
                        self._parent_widget._merge_paint_to_base()
                    else:
                        print(f"钉图矩形撤销调试: _merge_paint_to_base方法不存在")
                    if hasattr(self._parent_widget, 'backup_shortshot'):
                        print(f"钉图矩形撤销调试: 调用backup_shortshot()")
                        self._parent_widget.backup_shortshot()
                    else:
                        print(f"钉图矩形撤销调试: backup_shortshot方法不存在")
                except Exception as e:
                    print(f"钉图画矩形pixPainter错误: {e}")

        # 处理圆形工具
        if self.main_window.drawcircle_pointlist[0][0] != -2 and self.main_window.drawcircle_pointlist[1][0] != -2:
            try:
                temppainter = QPainter(self)
                temppainter.setPen(QPen(self.main_window.pencolor, self.main_window.tool_width, Qt.SolidLine))
                poitlist = self.main_window.drawcircle_pointlist
                temppainter.drawEllipse(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                        abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                temppainter.end()
            except Exception as e:
                print(f"钉图画圆临时QPainter错误: {e}")
                
            if self.main_window.drawcircle_pointlist[2] == 1:
                try:
                    self.pixPainter.setPen(QPen(self.main_window.pencolor, self.main_window.tool_width, Qt.SolidLine))
                    self.pixPainter.drawEllipse(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                                abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                    self.main_window.drawcircle_pointlist = [[-2, -2], [-2, -2], 0]
                    
                    # 钉图圆形绘制完成后，合并到底图并创建备份
                    print(f"钉图圆形撤销调试: paintEvent中绘制完成，合并到底图")
                    print(f"钉图圆形撤销调试: _parent_widget类型: {type(self._parent_widget)}")
                    if hasattr(self._parent_widget, '_merge_paint_to_base'):
                        print(f"钉图圆形撤销调试: 调用_merge_paint_to_base()")
                        self._parent_widget._merge_paint_to_base()
                    else:
                        print(f"钉图圆形撤销调试: _merge_paint_to_base方法不存在")
                    if hasattr(self._parent_widget, 'backup_shortshot'):
                        print(f"钉图圆形撤销调试: 调用backup_shortshot()")
                        self._parent_widget.backup_shortshot()
                    else:
                        print(f"钉图圆形撤销调试: backup_shortshot方法不存在")
                except Exception as e:
                    print(f"钉图画圆pixPainter错误: {e}")

        # 处理箭头工具
        if self.main_window.drawarrow_pointlist[0][0] != -2 and self.main_window.drawarrow_pointlist[1][0] != -2:
            try:
                temppainter = QPainter(self)
                # 设置画笔颜色和粗细，支持透明度
                pen_color = QColor(self.main_window.pencolor)
                if hasattr(self.main_window, 'tool_alpha'):
                    pen_color.setAlpha(self.main_window.tool_alpha)
                temppainter.setPen(QPen(pen_color, self.main_window.tool_width, Qt.SolidLine))
                
                # 绘制箭头
                self.draw_arrow(temppainter, self.main_window.drawarrow_pointlist)
                temppainter.end()
            except Exception as e:
                print(f"钉图画箭头临时QPainter错误: {e}")
                
            if self.main_window.drawarrow_pointlist[2] == 1:
                try:
                    # 设置画笔颜色和粗细，支持透明度
                    pen_color = QColor(self.main_window.pencolor)
                    if hasattr(self.main_window, 'tool_alpha'):
                        pen_color.setAlpha(self.main_window.tool_alpha)
                    self.pixPainter.setPen(QPen(pen_color, self.main_window.tool_width, Qt.SolidLine))
                    
                    # 绘制箭头到像素图
                    self.draw_arrow(self.pixPainter, self.main_window.drawarrow_pointlist)
                    self.main_window.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
                    
                    # 钉图箭头绘制完成后，合并到底图并创建备份
                    print(f"钉图箭头撤销调试: paintEvent中绘制完成，合并到底图")
                    print(f"钉图箭头撤销调试: _parent_widget类型: {type(self._parent_widget)}")
                    if hasattr(self._parent_widget, '_merge_paint_to_base'):
                        print(f"钉图箭头撤销调试: 调用_merge_paint_to_base()")
                        self._parent_widget._merge_paint_to_base()
                    else:
                        print(f"钉图箭头撤销调试: _merge_paint_to_base方法不存在")
                    if hasattr(self._parent_widget, 'backup_shortshot'):
                        print(f"钉图箭头撤销调试: 调用backup_shortshot()")
                        self._parent_widget.backup_shortshot()
                    else:
                        print(f"钉图箭头撤销调试: backup_shortshot方法不存在")
                except Exception as e:
                    print(f"钉图画箭头pixPainter错误: {e}")

        # 处理文字工具（钉图模式下的文字绘制）- 使用统一的文字绘制组件
        try:
            from jietuba_text_drawer import UnifiedTextDrawer
            
            if len(self.main_window.drawtext_pointlist) > 0 and hasattr(self.main_window, 'text_box') and self.main_window.text_box.paint:
                print("钉图模式: 开始处理文字绘制")
                
                # 使用统一的文字绘制处理
                success = UnifiedTextDrawer.process_text_drawing(self.main_window, self.pixPainter, self.main_window.text_box)
                
                if success:
                    print("钉图模式: 文字绘制完成")
                    self.update()
                else:
                    print("钉图模式: 文字内容为空，不绘制")
                    
        except Exception as e:
            print(f"钉图统一文字绘制流程错误: {e}")

        # ---- 实时文字预览: 在未提交状态下绘制输入中的文字 (不修改底层pixmap) ----
        try:
            from jietuba_text_drawer import UnifiedTextDrawer
            if (hasattr(self.main_window, 'text_box') and
                hasattr(self.main_window, 'drawtext_pointlist') and
                len(self.main_window.drawtext_pointlist) > 0 and
                not self.main_window.text_box.paint):  # 尚未提交
                UnifiedTextDrawer.render_live_preview(self, self.main_window, self.main_window.text_box)
        except Exception as e:
            print(f"钉图实时文字预览错误: {e}")

        try:
            self.pixPainter.end()
        except:
            pass
    
    def draw_arrow(self, painter, pointlist):
        """绘制箭头的通用函数"""
        try:
            import math
            start_point = pointlist[0]
            end_point = pointlist[1]
            
            # 计算箭头的方向和长度
            dx = end_point[0] - start_point[0]
            dy = end_point[1] - start_point[1]
            length = math.sqrt(dx * dx + dy * dy)
            
            if length < 5:  # 太短的线段不绘制箭头
                return
                
            # 箭头头部的长度和宽度（根据工具宽度调整）
            arrow_head_length = max(10, self.main_window.tool_width * 3)
            arrow_head_width = max(6, self.main_window.tool_width * 2)
            
            # 单位向量
            unit_x = dx / length
            unit_y = dy / length
            
            # 绘制箭头主体线条
            painter.drawLine(start_point[0], start_point[1], end_point[0], end_point[1])
            
            # 计算箭头头部的三个点
            # 箭头尖端就是终点
            tip_x = end_point[0]
            tip_y = end_point[1]
            
            # 箭头底部中心点
            base_x = tip_x - arrow_head_length * unit_x
            base_y = tip_y - arrow_head_length * unit_y
            
            # 箭头底部的两个角点（垂直于箭头方向）
            perp_x = -unit_y  # 垂直向量
            perp_y = unit_x
            
            left_x = base_x + arrow_head_width * perp_x
            left_y = base_y + arrow_head_width * perp_y
            
            right_x = base_x - arrow_head_width * perp_x
            right_y = base_y - arrow_head_width * perp_y
            
            # 绘制箭头头部（三角形）
            from PyQt5.QtGui import QPolygon, QBrush
            from PyQt5.QtCore import QPoint
            
            triangle = QPolygon([
                QPoint(int(tip_x), int(tip_y)),
                QPoint(int(left_x), int(left_y)),
                QPoint(int(right_x), int(right_y))
            ])
            
            # 设置填充颜色（与画笔颜色相同）
            brush = QBrush(painter.pen().color())
            painter.setBrush(brush)
            painter.drawPolygon(triangle)
            
        except Exception as e:
            print(f"钉图绘制箭头错误: {e}")

    def clear(self):
        """清理PinnedPaintLayer的绘画数据"""
        try:
            # 停止并清理painter
            if hasattr(self, 'pixPainter') and self.pixPainter:
                try:
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
            self.main_window = None
            
            # 调用父类清理
            super().clear()
            
        except Exception as e:
            print(f"⚠️ PinnedPaintLayer清理时出错: {e}")

class Freezer(QLabel):
    def __init__(self, parent=None, img=None, x=0, y=0, listpot=0, main_window=None):
        super().__init__()
        self.main_window = main_window  # 保存主截图窗口的引用
        
        # 初始化安全状态标记
        self._is_closed = False  # 标记窗口是否已关闭
        self._should_cleanup = False  # 标记是否应该被清理
        self._is_editing = False  # 标记是否正在编辑
        self.closed = False  # QPainter安全标记
        
        # 删除原来的侧边工具栏
        # self.hung_widget = Hung_widget(funcs =[":/exit.png",":/ontop.png",":/OCR.png",":/copy.png",":/saveicon.png"])
        
        self.tips_shower = TipsShower(" ",(QApplication.desktop().width()//2,50,120,50))
        self.tips_shower.hide()
        self.text_shower = FramelessEnterSendQTextEdit(self, enter_tra=True)
        self.text_shower.hide()
        self.origin_imgpix = img
        self.showing_imgpix = self.origin_imgpix
        self.ocr_res_imgpix = None
        self.listpot = listpot
        
        # 检查图像是否有效
        if self.showing_imgpix:
            self.setPixmap(self.showing_imgpix)
        else:
            print("⚠️ 钉图窗口: 初始化时图像为空")
            # 创建一个默认的空图像以防止后续错误
            self.showing_imgpix = QPixmap(100, 100)
            self.showing_imgpix.fill(Qt.white)
            self.setPixmap(self.showing_imgpix)
        self.settingOpacity = False
        self.setWindowOpacity(1.0)  # 设置为完全不透明
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        # 关闭时自动删除，避免悬挂对象
        try:
            self.setAttribute(Qt.WA_DeleteOnClose, True)
        except Exception:
            pass
        self.setMouseTracking(True)
        self.drawRect = True
        # self.setContextMenuPolicy(Qt.CustomContextMenu)
        if hasattr(self, 'showing_imgpix') and self.showing_imgpix:
            self.setGeometry(x, y, self.showing_imgpix.width(), self.showing_imgpix.height())
        
        # 初始化DPI记录
        self.initialize_dpi_tracking()
        
        # === 创建绘画层，完全照搬截图窗口的逻辑 ===
        self.paintlayer = PinnedPaintLayer(self, self.main_window)
        if hasattr(self, 'showing_imgpix') and self.showing_imgpix:
            self.paintlayer.setGeometry(0, 0, self.showing_imgpix.width(), self.showing_imgpix.height())
        self.paintlayer.show()
        
        # 创建右上角的关闭按钮
        self.close_button = QPushButton('×', self)
        self.close_button.setFixedSize(20, 20)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 0, 0, 180);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 220);
            }
            QPushButton:pressed {
                background-color: rgba(200, 0, 0, 220);
            }
        """)
        self.close_button.setToolTip("关闭钉图窗口 (ESC)")
        self.close_button.clicked.connect(self.close_window_with_esc)
        self.close_button.hide()  # 初始隐藏，鼠标悬停时显示
        
        # 更新关闭按钮位置
        self.update_close_button_position()
        
        self.show()
        self.drag = self.resize_the_window = False
        self.is_drawing_drag = False  # 添加绘画拖拽标志
        self.on_top = True
        self.p_x = self.p_y = 0
        self.setToolTip("Ctrl+ホイールで透明度調整")
        # self.setMaximumSize(QApplication.desktop().size())
        self.timer = QTimer(self)  # 创建一个定时器
        self.timer.setInterval(200)  # 设置定时器的时间间隔为200ms
        self.timer.timeout.connect(self.check_mouse_leave)  # 定时器超时时触发check_mouse_leave函数
        
        # 创建延迟隐藏工具栏的定时器
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)  # 只触发一次
        self.hide_timer.setInterval(500)  # 0.5秒延迟
        self.hide_timer.timeout.connect(self._hide_toolbar_delayed)
        
        # 删除原来的侧边工具栏信号连接
        # self.hung_widget.button_signal.connect(self.hw_signalcallback)
        # self.hung_widget.show()
        
        self.move(x, y)
        self.ocr_status = "waiting"
        self.ocr_res_info = []
        
        # 添加右键菜单状态标志，防止菜单显示时触发工具栏重新布局
        self._context_menu_active = False
        
        # 初始化备份系统
        self.backup_pic_list = []
        self.backup_ssid = 0
        self._original_backup_list = []  # 添加原始备份列表初始化
        # 创建初始备份状态
        if hasattr(self, 'showing_imgpix') and self.showing_imgpix and not self.showing_imgpix.isNull():
            initial_backup = self.showing_imgpix.copy()
            self.backup_pic_list.append(initial_backup)
            self._original_backup_list.append(initial_backup.copy())  # 同时初始化原始备份列表
            print(f"📋 钉图初始化: 创建初始备份状态，总数: {len(self.backup_pic_list)}, 原始备份: {len(self._original_backup_list)}")
        else:
            print("⚠️ 钉图初始化: showing_imgpix无效，将在copy_screenshot_backup_history中处理")
    
    def _merge_paint_to_base(self):
        """将绘画层内容合并到底图，然后清空绘画层"""
        try:
            # 检查底图是否存在
            print(f"🔍 钉图合并调试: showing_imgpix属性存在={hasattr(self, 'showing_imgpix')}")
            if hasattr(self, 'showing_imgpix'):
                print(f"🔍 钉图合并调试: showing_imgpix值={self.showing_imgpix}")
                print(f"🔍 钉图合并调试: showing_imgpix是否为None={self.showing_imgpix is None}")
                if self.showing_imgpix:
                    print(f"🔍 钉图合并调试: showing_imgpix是否为null={self.showing_imgpix.isNull()}")
            
            # 确保showing_imgpix有效
            if not self._ensure_showing_imgpix_valid():
                print("❌ 钉图合并: showing_imgpix无效且无法恢复，中止合并")
                return
            
            print(f"📋 钉图合并调试: paintlayer存在={hasattr(self, 'paintlayer')}")
            if hasattr(self, 'paintlayer'):
                print(f"📋 钉图合并调试: paintlayer不为空={self.paintlayer is not None}")
                if self.paintlayer:
                    paintlayer_pixmap = self.paintlayer.pixmap()
                    print(f"📋 钉图合并调试: paintlayer.pixmap()存在={paintlayer_pixmap is not None}")
                    if paintlayer_pixmap:
                        print(f"📋 钉图合并调试: pixmap不为null={not paintlayer_pixmap.isNull()}")
                        print(f"📋 钉图合并调试: pixmap尺寸={paintlayer_pixmap.size()}")
            
            if hasattr(self, 'paintlayer') and self.paintlayer and self.paintlayer.pixmap():
                paint_pixmap = self.paintlayer.pixmap()
                if paint_pixmap and not paint_pixmap.isNull():
                    print(f"📋 钉图合并调试: 开始合并，底图尺寸={self.showing_imgpix.size()}，绘画层尺寸={paint_pixmap.size()}")
                    
                    # 创建新的底图，合并绘画层内容
                    new_base = QPixmap(self.showing_imgpix.size())
                    painter = QPainter(new_base)
                    painter.setRenderHint(QPainter.Antialiasing)
                    
                    # 绘制原底图
                    painter.drawPixmap(0, 0, self.showing_imgpix)
                    
                    # 绘制绘画层内容
                    painter.drawPixmap(0, 0, paint_pixmap)
                    painter.end()
                    
                    # 更新底图
                    self.showing_imgpix = new_base
                    self.setPixmap(self.showing_imgpix)
                    
                    # 清空绘画层
                    paint_pixmap.fill(Qt.transparent)
                    self.paintlayer.update()
                    
                    print("📋 钉图合并: 绘画层内容已合并到底图")
                else:
                    print("📋 钉图合并: 绘画层pixmap为空或null，无需合并")
            else:
                print("📋 钉图合并: 没有有效的绘画层，无需合并")
                
        except Exception as e:
            print(f"❌ 钉图合并: 合并失败: {e}")
    
    def _ensure_showing_imgpix_valid(self):
        """确保showing_imgpix始终有效，如果无效则从origin_imgpix恢复"""
        if not hasattr(self, 'showing_imgpix') or not self.showing_imgpix or (self.showing_imgpix and self.showing_imgpix.isNull()):
            if hasattr(self, 'origin_imgpix') and self.origin_imgpix and not self.origin_imgpix.isNull():
                print("🔧 钉图修复: showing_imgpix无效，从origin_imgpix恢复")
                self.showing_imgpix = self.origin_imgpix.copy()
                self.setPixmap(self.showing_imgpix)
                return True
            else:
                print("❌ 钉图修复: origin_imgpix也无效，无法恢复")
                return False
        return True
    
    def _update_for_resize(self, new_width, new_height):
        """缩放时更新底图和备份历史"""
        try:
            print(f"🔄 钉图缩放: 开始更新到 {new_width}x{new_height}")
            
            # 确保showing_imgpix有效
            if not self._ensure_showing_imgpix_valid():
                print("❌ 钉图缩放: showing_imgpix无效且无法恢复，中止缩放更新")
                return
            
            # 1. 更新showing_imgpix到新尺寸 - 基于原始图像缩放
            if hasattr(self, 'origin_imgpix') and self.origin_imgpix:
                # 保存当前的backup_ssid，用于确定应该显示哪个备份状态
                current_backup_id = getattr(self, 'backup_ssid', 0)
                
                # 更新当前显示的图像
                if hasattr(self, 'backup_pic_list') and self.backup_pic_list and current_backup_id < len(self.backup_pic_list):
                    # 获取原始备份状态的图像
                    if hasattr(self, '_original_backup_list') and current_backup_id < len(self._original_backup_list):
                        original_image = self._original_backup_list[current_backup_id]
                        print(f"🔄 钉图缩放: 使用原始备份 {current_backup_id} 进行缩放")
                    else:
                        original_image = self.origin_imgpix
                        print(f"🔄 钉图缩放: 使用origin_imgpix进行缩放")
                else:
                    original_image = self.origin_imgpix
                    print(f"🔄 钉图缩放: 使用origin_imgpix进行缩放")
                
                # 缩放并更新显示
                self.showing_imgpix = original_image.scaled(
                    new_width, new_height,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.setPixmap(self.showing_imgpix)
                print(f"🔄 钉图缩放: showing_imgpix已更新并设置到 {new_width}x{new_height}")
            
            # 2. 更新备份历史中的所有图像到新尺寸
            if hasattr(self, 'backup_pic_list') and self.backup_pic_list:
                print(f"🔄 钉图缩放: 开始更新 {len(self.backup_pic_list)} 个备份图像")
                
                # 保存原始图像列表的引用
                if not hasattr(self, '_original_backup_list'):
                    # 首次缩放，保存原始尺寸的备份
                    self._original_backup_list = [backup.copy() for backup in self.backup_pic_list]
                    print(f"🔄 钉图缩放: 保存了 {len(self._original_backup_list)} 个原始备份")
                
                # 将所有备份缩放到新尺寸
                for i in range(len(self.backup_pic_list)):
                    if i < len(self._original_backup_list) and self._original_backup_list[i]:
                        try:
                            scaled_backup = self._original_backup_list[i].scaled(
                                new_width, new_height,
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation
                            )
                            self.backup_pic_list[i] = scaled_backup
                            print(f"🔄 钉图缩放: 备份 {i} 已从原始尺寸缩放到 {new_width}x{new_height}")
                        except Exception as e:
                            print(f"❌ 钉图缩放: 备份 {i} 缩放失败: {e}")
                
                print(f"✅ 钉图缩放: 所有备份已更新完成")
            
        except Exception as e:
            print(f"❌ 钉图缩放: 更新失败: {e}")
            import traceback
            traceback.print_exc()
    
    def update_close_button_position(self):
        """更新关闭按钮的位置到右上角"""
        if hasattr(self, 'close_button'):
            button_size = 20
            margin = 5
            x = self.width() - button_size - margin
            y = margin
            self.close_button.move(x, y)
            self.close_button.raise_()  # 确保按钮在最上层
    
    def close_window_with_esc(self):
        """模拟ESC键关闭窗口"""
        try:
            # 创建ESC键事件
            esc_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
            # 发送ESC事件到窗口
            self.keyPressEvent(esc_event)
        except Exception as e:
            print(f"模拟ESC关闭失败: {e}")
            # 如果模拟ESC失败，直接调用关闭方法
            self.close()
    
    # ========================= 尺寸/缩放同步工具 =========================
    def _sync_paintlayer_on_resize(self, new_w: int, new_h: int):
        """窗口尺寸变化时，同步绘画层几何与已绘制内容的缩放，避免错位。"""
        try:
            if not hasattr(self, 'paintlayer') or self.paintlayer is None:
                return
            pl = self.paintlayer
            # 当前内容
            try:
                cur_pix = pl.pixmap()
            except Exception:
                cur_pix = None

            # 同步几何
            try:
                pl.setGeometry(0, 0, int(new_w), int(new_h))
            except Exception:
                pass

            # 同步内容
            if cur_pix is not None and (not cur_pix.isNull()):
                if cur_pix.width() != int(new_w) or cur_pix.height() != int(new_h):
                    try:
                        scaled = cur_pix.scaled(int(new_w), int(new_h), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                        pl.setPixmap(scaled)
                    except Exception as e:
                        print(f"⚠️ 绘画层内容缩放失败: {e}")
            else:
                # 确保存在透明底
                try:
                    empty = QPixmap(max(1, int(new_w)), max(1, int(new_h)))
                    empty.fill(Qt.transparent)
                    pl.setPixmap(empty)
                except Exception as e:
                    print(f"⚠️ 创建空绘画层失败: {e}")
        except Exception as e:
            print(f"❌ 同步绘画层失败: {e}")
    
    def copy_screenshot_backup_history(self, crop_x, crop_y, crop_w, crop_h):
        """
        复制截图窗口的绘制历史到钉图窗口，并进行坐标转换和区域裁剪
        
        Args:
            crop_x, crop_y: 截图区域的左上角坐标（在全屏坐标系中）
            crop_w, crop_h: 截图区域的宽度和高度
        """
        try:
            # 检查钉图窗口是否已经有自己的备份历史（表示已经进行过绘画操作）
            has_own_history = (hasattr(self, 'backup_pic_list') and 
                             len(self.backup_pic_list) > 1)
            
            if has_own_history:
                print(f"📋 钉图备份: 钉图窗口已有 {len(self.backup_pic_list)} 个备份，跳过历史复制，保持current_ssid={self.backup_ssid}")
                return
            
            if not hasattr(self.main_window, 'backup_pic_list') or not self.main_window.backup_pic_list:
                print("📋 钉图备份: 主窗口没有绘制历史，创建初始备份状态")
                # 确保备份列表存在并创建初始状态
                if not hasattr(self, 'backup_pic_list'):
                    self.backup_pic_list = []
                if not self.backup_pic_list:
                    # 创建初始备份状态：确保有一个"空白"状态可以撤回
                    initial_backup = self.showing_imgpix.copy()
                    self.backup_pic_list = [initial_backup]
                    self.backup_ssid = 0
                    # 同步更新原始备份列表
                    if not hasattr(self, '_original_backup_list'):
                        self._original_backup_list = []
                    self._original_backup_list = [initial_backup.copy()]
                    print(f"📋 钉图备份: 创建初始备份状态，backup_ssid={self.backup_ssid}")
                return
            
            print(f"📋 钉图备份: 开始复制主窗口的 {len(self.main_window.backup_pic_list)} 个历史状态")
            
            # 初始化钉图的备份系统
            self.backup_pic_list = []
            
            # ===== 关键修复：确保钉图窗口总是有正确的撤回状态 =====
            # 重要：钉图窗口的showing_imgpix是当前最新状态（包含绘制内容）
            # 我们需要构建正确的历史序列：[旧状态, ..., 当前状态]
            
            # 从主窗口复制所有历史状态到钉图窗口
            for i, full_backup in enumerate(self.main_window.backup_pic_list):
                if full_backup and not full_backup.isNull():
                    # 从全屏备份中裁剪出截图区域
                    cropped_backup = full_backup.copy(crop_x, crop_y, crop_w, crop_h)
                    
                    if not cropped_backup.isNull():
                        self.backup_pic_list.append(cropped_backup)
                        print(f"📋 钉图备份: 复制历史状态 {i}, 尺寸: {cropped_backup.width()}x{cropped_backup.height()}")
                    else:
                        print(f"⚠️ 钉图备份: 状态 {i} 裁剪失败")
                else:
                    print(f"⚠️ 钉图备份: 状态 {i} 无效")
            
            # 确保当前显示的图像也在备份列表中（作为最新状态）
            # 检查最后一个备份是否与当前showing_imgpix相同
            current_state_exists = False
            if len(self.backup_pic_list) > 0:
                last_backup = self.backup_pic_list[-1]
                # 使用更严格的比较：尺寸和像素数据都要匹配
                if (last_backup.size() == self.showing_imgpix.size()):
                    # 转换为QImage进行像素级比较
                    last_image = last_backup.toImage()
                    current_image = self.showing_imgpix.toImage()
                    
                    # 如果尺寸相同，再比较像素数据
                    if last_image.size() == current_image.size():
                        # 使用更可靠的比较方法：比较图像的哈希值或像素数据
                        try:
                            # 简单的像素数据比较
                            last_bytes = last_image.bits().asstring(last_image.byteCount())
                            current_bytes = current_image.bits().asstring(current_image.byteCount())
                            if last_bytes == current_bytes:
                                current_state_exists = True
                                print("📋 钉图备份: 当前状态已存在于历史中（像素级匹配）")
                            else:
                                print("📋 钉图备份: 当前状态与最后备份不同（像素级差异）")
                        except Exception as e:
                            print(f"⚠️ 钉图备份: 像素比较失败，使用QImage比较: {e}")
                            # 回退到QImage直接比较
                            if last_image == current_image:
                                current_state_exists = True
                                print("📋 钉图备份: 当前状态已存在于历史中（QImage匹配）")
                    else:
                        print(f"📋 钉图备份: 尺寸不匹配 - 最后备份:{last_image.size()}, 当前:{current_image.size()}")
                else:
                    print(f"📋 钉图备份: QPixmap尺寸不匹配 - 最后备份:{last_backup.size()}, 当前:{self.showing_imgpix.size()}")
            
            # 如果当前状态不在历史中，添加它
            if not current_state_exists:
                self.backup_pic_list.append(self.showing_imgpix.copy())
                print("📋 钉图备份: 添加当前状态到历史末尾")
            else:
                print("📋 钉图备份: 跳过添加当前状态（已存在）")
            
            # 确保至少有一个状态
            if len(self.backup_pic_list) == 0:
                print("⚠️ 钉图备份: 没有有效状态，创建默认状态")
                self.backup_pic_list = [self.showing_imgpix.copy()]
            
            # 设置当前位置：指向最后一个状态（即当前显示的状态）
            self.backup_ssid = len(self.backup_pic_list) - 1
            
            # 同步更新原始备份列表
            if not hasattr(self, '_original_backup_list'):
                self._original_backup_list = []
            self._original_backup_list = [backup.copy() for backup in self.backup_pic_list]
            
            print(f"✅ 钉图备份: 历史复制完成，共 {len(self.backup_pic_list)} 个状态，当前位置: {self.backup_ssid}")
            print(f"📋 钉图备份: 可撤回状态数: {self.backup_ssid}")
            
            # 添加详细的状态调试信息
            print(f"🔍 钉图备份调试: 当前显示状态与backup_pic_list[{self.backup_ssid}]应该匹配")
            if len(self.backup_pic_list) > 1:
                print(f"🔍 钉图备份调试: 撤回将显示backup_pic_list[{self.backup_ssid-1}]（上一个状态）")
            else:
                print(f"🔍 钉图备份调试: 只有一个状态，无法撤回")
            
        except Exception as e:
            print(f"❌ 钉图备份: 复制历史失败: {e}")
            # 失败时创建基础备份，确保有撤回能力
            if not hasattr(self, 'backup_pic_list') or not self.backup_pic_list:
                self.backup_pic_list = [self.showing_imgpix.copy()]
                self.backup_ssid = 0
                if not hasattr(self, '_original_backup_list'):
                    self._original_backup_list = [self.showing_imgpix.copy()]
                print(f"📋 钉图备份: 创建应急备份状态")
    
    def backup_shortshot(self):
        """钉图窗口的备份方法 - 备份当前底图（绘画层内容应该已经合并）"""
        try:
            # 检查底图是否存在
            print(f"🔍 钉图备份调试: showing_imgpix属性存在={hasattr(self, 'showing_imgpix')}")
            if hasattr(self, 'showing_imgpix'):
                print(f"🔍 钉图备份调试: showing_imgpix值={self.showing_imgpix}")
                print(f"🔍 钉图备份调试: showing_imgpix是否为None={self.showing_imgpix is None}")
                if self.showing_imgpix:
                    print(f"🔍 钉图备份调试: showing_imgpix是否为null={self.showing_imgpix.isNull()}")
            
            # 确保showing_imgpix有效
            if not self._ensure_showing_imgpix_valid():
                print("❌ 钉图备份: showing_imgpix无效且无法恢复，中止备份")
                return
            
            # 直接备份底图（绘画层内容已经通过_merge_paint_to_base合并）
            backup_pixmap = self.showing_imgpix.copy()
            
            # 确保备份列表存在
            if not hasattr(self, 'backup_pic_list'):
                self.backup_pic_list = []
                self.backup_ssid = 0  # 修复：初始化为0而不是-1
            
            # 如果当前不在最新位置，清除后续历史
            if self.backup_ssid < len(self.backup_pic_list) - 1:
                self.backup_pic_list = self.backup_pic_list[:self.backup_ssid + 1]
                # 同步清理原始备份列表
                if hasattr(self, '_original_backup_list') and self._original_backup_list:
                    self._original_backup_list = self._original_backup_list[:self.backup_ssid + 1]
            
            # 添加新的备份状态
            self.backup_pic_list.append(backup_pixmap)
            self.backup_ssid = len(self.backup_pic_list) - 1
            
            # 同时更新原始备份列表（用于缩放）
            if hasattr(self, '_original_backup_list'):
                self._original_backup_list.append(backup_pixmap.copy())
                # 保持列表长度同步
                while len(self._original_backup_list) > len(self.backup_pic_list):
                    self._original_backup_list.pop(0)
            else:
                self._original_backup_list = [backup.copy() for backup in self.backup_pic_list]
            
            # 限制历史长度
            while len(self.backup_pic_list) > 10:
                self.backup_pic_list.pop(0)
                if hasattr(self, '_original_backup_list') and self._original_backup_list:
                    self._original_backup_list.pop(0)
                if self.backup_ssid > 0:
                    self.backup_ssid -= 1
            
            print(f"📋 钉图备份: 创建新备份，当前位置: {self.backup_ssid}, 总数: {len(self.backup_pic_list)}")
            print(f"📋 钉图备份: 最终验证 - backup_ssid={self.backup_ssid}, 列表长度={len(self.backup_pic_list)}")
            
        except Exception as e:
            print(f"❌ 钉图备份: 创建备份失败: {e}")
            import traceback
            traceback.print_exc()
    
    def last_step(self):
        """钉图窗口的撤销方法"""
        try:
            print(f"🔍 钉图撤销调试: 开始撤销")
            print(f"🔍 钉图撤销调试: backup_pic_list存在={hasattr(self, 'backup_pic_list')}")
            print(f"🔍 钉图撤销调试: backup_pic_list长度={len(self.backup_pic_list) if hasattr(self, 'backup_pic_list') and self.backup_pic_list else 0}")
            print(f"🔍 钉图撤销调试: backup_ssid={getattr(self, 'backup_ssid', '未定义')}")
            
            if not hasattr(self, 'backup_pic_list') or not self.backup_pic_list:
                print("📋 钉图撤销: 没有备份历史")
                return
            
            # 安全边界检查：确保backup_ssid在有效范围内
            if not hasattr(self, 'backup_ssid'):
                self.backup_ssid = len(self.backup_pic_list) - 1
                print(f"📋 钉图撤销: 初始化backup_ssid为 {self.backup_ssid}")
            
            # 边界保护
            if self.backup_ssid < 0:
                self.backup_ssid = 0
                print(f"📋 钉图撤销: 修正负数backup_ssid为 0")
            elif self.backup_ssid >= len(self.backup_pic_list):
                self.backup_ssid = len(self.backup_pic_list) - 1
                print(f"📋 钉图撤销: 修正超界backup_ssid为 {self.backup_ssid}")
                
            if self.backup_ssid > 0:
                self.backup_ssid -= 1
                backup_image = self.backup_pic_list[self.backup_ssid]
                
                # 更新显示图像 - 确保图像适配当前窗口尺寸
                self.showing_imgpix = backup_image.copy()
                
                # 如果窗口已缩放，需要适配显示
                if backup_image.size() != QSize(self.width(), self.height()):
                    display_image = backup_image.scaled(
                        self.width(), self.height(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.setPixmap(display_image)
                    print(f"📋 钉图撤销: 图像已缩放适配窗口 {self.width()}x{self.height()}")
                else:
                    self.setPixmap(self.showing_imgpix)
                    print(f"📋 钉图撤销: 图像尺寸匹配，直接显示")
                
                # 清空绘画层
                if hasattr(self, 'paintlayer') and self.paintlayer:
                    if self.paintlayer.pixmap():
                        self.paintlayer.pixmap().fill(Qt.transparent)
                    self.paintlayer.update()
                
                self.update()
                print(f"📋 钉图撤销: 撤销到位置 {self.backup_ssid}")
            else:
                print(f"📋 钉图撤销: 已经是第一步，不能再撤销 (backup_ssid={self.backup_ssid})")
                
        except Exception as e:
            print(f"❌ 钉图撤销: 撤销失败: {e}")
            import traceback
            traceback.print_exc()
    
    def next_step(self):
        """钉图窗口的前进方法"""
        try:
            if not hasattr(self, 'backup_pic_list') or not self.backup_pic_list:
                print("📋 钉图前进: 没有备份历史")
                return
            
            # 安全边界检查：确保backup_ssid在有效范围内
            if not hasattr(self, 'backup_ssid'):
                self.backup_ssid = len(self.backup_pic_list) - 1
                print(f"📋 钉图前进: 初始化backup_ssid为 {self.backup_ssid}")
            
            # 边界保护
            if self.backup_ssid < 0:
                self.backup_ssid = 0
                print(f"📋 钉图前进: 修正负数backup_ssid为 0")
            elif self.backup_ssid >= len(self.backup_pic_list):
                self.backup_ssid = len(self.backup_pic_list) - 1
                print(f"📋 钉图前进: 修正超界backup_ssid为 {self.backup_ssid}")
                
            if self.backup_ssid < len(self.backup_pic_list) - 1:
                self.backup_ssid += 1
                backup_image = self.backup_pic_list[self.backup_ssid]
                
                # 更新显示图像 - 确保图像适配当前窗口尺寸
                self.showing_imgpix = backup_image.copy()
                
                # 如果窗口已缩放，需要适配显示
                if backup_image.size() != QSize(self.width(), self.height()):
                    display_image = backup_image.scaled(
                        self.width(), self.height(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.setPixmap(display_image)
                    print(f"📋 钉图前进: 图像已缩放适配窗口 {self.width()}x{self.height()}")
                else:
                    self.setPixmap(self.showing_imgpix)
                    print(f"📋 钉图前进: 图像尺寸匹配，直接显示")
                
                # 清空绘画层
                if hasattr(self, 'paintlayer') and self.paintlayer:
                    if self.paintlayer.pixmap():
                        self.paintlayer.pixmap().fill(Qt.transparent)
                    self.paintlayer.update()
                
                self.update()
                print(f"📋 钉图前进: 前进到位置 {self.backup_ssid}")
            else:
                print(f"📋 钉图前进: 已经是最新步骤，不能再前进 (backup_ssid={self.backup_ssid})")
                
        except Exception as e:
            print(f"❌ 钉图前进: 前进失败: {e}")
            import traceback
            traceback.print_exc()

    def initialize_dpi_tracking(self):
        """初始化DPI跟踪"""
        try:
            # 获取当前显示器
            screens = QApplication.screens()
            current_screen = None
            g = self.geometry()
            window_center_x = g.x() + g.width() // 2
            window_center_y = g.y() + g.height() // 2
            # 调试：输出用于判定的中心点
            # print(f"[DPI调试] center={window_center_x},{window_center_y} geo=({g.x()},{g.y()},{g.width()}x{g.height()})")
            
            for screen in screens:
                geometry = screen.geometry()
                if (window_center_x >= geometry.x() and window_center_x < geometry.x() + geometry.width() and
                    window_center_y >= geometry.y() and window_center_y < geometry.y() + geometry.height()):
                    current_screen = screen
                    break
            
            if current_screen:
                self._last_dpi = current_screen.devicePixelRatio()
                print(f"钉图窗口初始DPI: {self._last_dpi}")
            else:
                self._last_dpi = 1.0
                print("钉图窗口: 无法确定初始DPI，使用默认值1.0")
                
        except Exception as e:
            print(f"DPI初始化失败: {e}")
            self._last_dpi = 1.0

    def cleanup_ocr_state(self):
        """清理OCR状态和识别框"""
        print("开始清理OCR状态...")
        
        # 重置OCR状态
        self.ocr_status = "waiting"
        
        # 停止加载动画
        if hasattr(self, 'Loading_label'):
            self.Loading_label.stop()
        
        # 隐藏文本显示框及其工具栏
        if hasattr(self, 'text_shower'):
            self.text_shower.hide()
            if hasattr(self.text_shower, 'toolbar'):
                self.text_shower.toolbar.hide()
        
        # 恢复原始图像（清除识别框）
        self.showing_imgpix = self.origin_imgpix
        self.setPixmap(self.showing_imgpix.scaled(self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
        # 清空OCR结果信息
        self.ocr_res_info = []
        self.ocr_res_imgpix = None
        
        # 显示提示
        if hasattr(self, 'tips_shower'):
            # 移除了已结束OCR识别提示
            pass
        
        print("OCR状态清理完成")
        
    def ocr(self):
        # OCR功能已移除
        print("⚠️ OCR機能は現在利用できません。")
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(None, "OCR機能", "OCR機能は現在利用できません。by李")
        return
        
        # 原OCR实现已注释 - 如需恢复请取消注释并安装依赖
        # if self.ocr_status == "ocr":
        #     # 移除了認識をキャンセル提示
        #     self.ocr_status = "abort"
        #     self.Loading_label.stop()
        #     self.text_shower.hide()
        #     self.showing_imgpix = self.origin_imgpix
        #     self.setPixmap(self.showing_imgpix.scaled(self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        #     
        #     return
        # elif self.ocr_status == "show":#正在展示结果,取消展示
        #     # 移除了文字認識を終了提示
        #     self.ocr_status = "waiting"
        #     self.Loading_label.stop()
        #     self.text_shower.hide()
        #     self.showing_imgpix = self.origin_imgpix
        #     self.setPixmap(self.showing_imgpix.scaled(self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        #     return
        # self.ocr_status = "ocr"
        # if not os.path.exists("j_temp"):
        #     os.mkdir("j_temp")
        # self.pixmap().save("j_temp/tempocr.png", "PNG")
        # cv_image = cv2.imread("j_temp/tempocr.png")
        # from jampublic import CONFIG_DICT
        # self.ocrthread = OcrimgThread(cv_image, lang=CONFIG_DICT.get('ocr_lang', 'ch'))
        # self.ocrthread.result_show_signal.connect(self.ocr_res_signalhandle)
        # self.ocrthread.boxes_info_signal.connect(self.orc_boxes_info_callback)
        # self.ocrthread.det_res_img.connect(self.det_res_img_callback)
        # self.ocrthread.start()
        # self.Loading_label = Loading_label(self)
        # self.Loading_label.setGeometry(0, 0, self.width(), self.height())
        # self.Loading_label.start()
        # 
        # self.text_shower.setPlaceholderText("認識中、お待ちください...")
        # self.text_shower.move(self.x(), self.y()+self.height()+10)  # 向下移动10像素
        # self.text_shower.show()
        # self.text_shower.clear()
        # QApplication.processEvents()
    def orc_boxes_info_callback(self,text_boxes):
        if self.ocr_status == "ocr":
            for tb in text_boxes:
                tb["select"]=False
            self.ocr_res_info = text_boxes
            print("rec orc_boxes_info_callback")

    def det_res_img_callback(self,piximg):
        if self.ocr_status == "ocr":
            print("rec det_res_img_callback")
            self.showing_imgpix = piximg
            self.ocr_res_imgpix = piximg
            self.setPixmap(piximg.scaled(self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
    def ocr_res_signalhandle(self,text):
        if self.ocr_status == "ocr":
            self.text_shower.setPlaceholderText("")
            self.text_shower.insertPlainText(text)
            self.Loading_label.stop()
            self.ocr_status = "show"
    def contextMenuEvent(self, event):
        # 标记右键菜单正在显示，防止其他事件干扰
        self._context_menu_active = True
        # 停止计时器，防止菜单显示时触发工具栏隐藏
        if hasattr(self, 'timer') and self.timer is not None:
            try:
                self.timer.stop()
            except Exception as e:
                print(f"⚠️ [定时器警告] 右键菜单停止定时器失败: {e}")
        
        menu = QMenu(self)
        quitAction = menu.addAction("終了")
        saveaction = menu.addAction('名前を付けて保存')
        copyaction = menu.addAction('コピー')
        # ocrAction = menu.addAction('文字認識')  # OCR功能已删除，注释掉此按钮
        topaction = menu.addAction('(キャンセル)最前面表示')
        rectaction = menu.addAction('(キャンセル)枠線')

        action = menu.exec_(self.mapToGlobal(event.pos()))
        
        # 标记右键菜单已结束
        self._context_menu_active = False
        
        # 如果用户没有选择退出，重新启动计时器以恢复正常的工具栏隐藏逻辑
        if action != quitAction and action is not None:
            if (hasattr(self, 'timer') and self.timer is not None and 
                not getattr(self, 'closed', False) and 
                not getattr(self, '_is_closed', False)):
                try:
                    self.timer.start()
                except Exception as e:
                    print(f"⚠️ [定时器警告] 右键菜单后启动定时器失败: {e}")
        elif action is None:
            # 用户取消了菜单（点击空白区域），重新启动计时器
            if (hasattr(self, 'timer') and self.timer is not None and 
                not getattr(self, 'closed', False) and 
                not getattr(self, '_is_closed', False)):
                try:
                    self.timer.start()
                except Exception as e:
                    print(f"⚠️ [定时器警告] 取消菜单后启动定时器失败: {e}")
        
        if action == quitAction:
            # 延迟执行清理操作，避免立即刷新界面导致菜单消失
            QTimer.singleShot(100, self.clear)
        elif action == saveaction:
            print("🔍 [调试] 开始处理钉图窗口保存操作")
            
            # 设置保存状态标志，防止意外关闭
            self._is_saving = True
            # 同时设置一个全局标志，防止任何清理操作
            self._prevent_clear = True
            
            if hasattr(self, 'showing_imgpix') and self.showing_imgpix:
                try:
                    # 停止所有可能导致清理的定时器
                    if hasattr(self, 'timer') and self.timer:
                        self.timer.stop()
                    if hasattr(self, 'hide_timer') and self.hide_timer:
                        self.hide_timer.stop()
                    
                    # 合并原图和绘画内容创建最终图像
                    final_img = self._create_merged_image()
                    print("🔍 [调试] 准备打开保存对话框")
                    
                    # 获取当前窗口位置和状态，保存对话框关闭后恢复
                    current_pos = self.pos()
                    current_visible = self.isVisible()
                    
                    path, l = QFileDialog.getSaveFileName(self, "另存为", QStandardPaths.writableLocation(
                        QStandardPaths.PicturesLocation), "png Files (*.png);;"
                                                          "jpg file(*.jpg);;jpeg file(*.JPEG);; bmp file(*.BMP );;ico file(*.ICO);;"
                                                          ";;all files(*.*)")
                    
                    print(f"🔍 [调试] 保存对话框返回结果: path='{path}', type='{l}'")
                    
                    # 确保窗口状态正确恢复
                    if current_visible and not self.isVisible():
                        print("🔍 [调试] 恢复窗口显示状态")
                        self.show()
                        self.move(current_pos)
                        self.raise_()
                    
                    if path:
                        print(f"🔍 [调试] 开始保存图像到: {path}")
                        final_img.save(path)
                        self.tips_shower.set_pos(self.x(),self.y())
                        # 移除了画像を保存しました提示
                        print(f"✅ 钉图窗口已保存到: {path}")
                        print("🔍 [调试] 保存完成，应该保持窗口开启状态")
                        # 注意：保存后不关闭窗口，保持钉图状态
                    else:
                        print("🔍 [调试] 用户取消了保存操作")
                        
                except Exception as e:
                    print(f"❌ [调试] 保存过程中出错: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    # 恢复定时器
                    if (hasattr(self, 'timer') and self.timer and not self.closed and 
                        not getattr(self, '_is_closed', False)):
                        try:
                            self.timer.start()
                        except:
                            pass
                    
                    # 清除所有保存状态标志
                    self._is_saving = False
                    self._prevent_clear = False
                    print("🔍 [调试] 保存操作完全结束，恢复正常状态")
            else:
                self._is_saving = False
                self._prevent_clear = False
                print("❌ [调试] 没有可保存的图像数据")
        elif action == copyaction:
            clipboard = QApplication.clipboard()
            try:
                if hasattr(self, 'showing_imgpix') and self.showing_imgpix:
                    # 合并原图和绘画内容创建最终图像
                    final_img = self._create_merged_image()
                    clipboard.setPixmap(final_img)
                    self.tips_shower.set_pos(self.x(),self.y())
                    # 移除了画像をコピーしました提示
                    print("✅ 已复制包含绘画内容的完整图像到剪贴板")
                else:
                    print('画像が存在しません')
            except Exception as e:
                print(f'コピー失敗: {e}')
        # elif action == ocrAction:  # OCR功能已删除，注释掉相关处理逻辑
        #     self.tips_shower.set_pos(self.x(),self.y())
        #     # 移除了文字识别中提示
        #     self.ocr()
        elif action == topaction:
            self.change_ontop()
        elif action == rectaction:
            self.drawRect = not self.drawRect
            self.update()
            
    def _create_merged_image(self):
        """创建包含绘画内容的完整图像"""
        try:
            # 以当前显示的图像为基础
            if not hasattr(self, 'showing_imgpix') or not self.showing_imgpix:
                print("⚠️ 没有可用的基础图像")
                return QPixmap()
            
            # 创建与当前钉图窗口尺寸相同的画布
            merged_img = QPixmap(self.width(), self.height())
            merged_img.fill(Qt.transparent)
            
            painter = QPainter(merged_img)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 1. 先绘制底层的原图（缩放到当前窗口尺寸）
            scaled_base = self.showing_imgpix.scaled(
                self.width(), self.height(), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            painter.drawPixmap(0, 0, scaled_base)
            
            # 2. 然后绘制绘画层的内容
            if hasattr(self, 'paintlayer') and self.paintlayer and hasattr(self.paintlayer, 'pixmap'):
                try:
                    paint_content = self.paintlayer.pixmap()
                    if paint_content and not paint_content.isNull():
                        painter.drawPixmap(0, 0, paint_content)
                        print("✅ 已合并绘画层内容")
                    else:
                        print("ℹ️ 绘画层为空或无效")
                except Exception as e:
                    print(f"⚠️ 合并绘画层时出错: {e}")
            else:
                print("ℹ️ 没有绘画层或绘画层无效")
            
            painter.end()
            print(f"✅ 成功创建合并图像，尺寸: {merged_img.width()}x{merged_img.height()}")
            return merged_img
            
        except Exception as e:
            print(f"❌ 创建合并图像失败: {e}")
            # 出错时返回原图
            return self.showing_imgpix if hasattr(self, 'showing_imgpix') and self.showing_imgpix else QPixmap()
            
    def change_ontop(self):
        if self.on_top:
            self.on_top = False
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.setWindowFlag(Qt.Tool, False)
            self.show()
        else:
            self.on_top = True
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.setWindowFlag(Qt.Tool, True)
            self.show()
    def setWindowOpacity(self,opacity):
        super().setWindowOpacity(opacity)
        
    def wheelEvent(self, e):
        if self.isVisible():
            angleDelta = e.angleDelta() / 8
            dy = angleDelta.y()
            if self.settingOpacity:
                if dy > 0:
                    if (self.windowOpacity() + 0.1) <= 1:
                        self.setWindowOpacity(self.windowOpacity() + 0.1)
                    else:
                        self.setWindowOpacity(1)
                elif dy < 0 and (self.windowOpacity() - 0.1) >= 0.11:
                    self.setWindowOpacity(self.windowOpacity() - 0.1)
            else:
                # 检查是否有绘画工具激活且主窗口存在
                if (self.main_window and hasattr(self.main_window, 'painter_tools') and 
                    hasattr(self.main_window, 'tool_width') and 1 in self.main_window.painter_tools.values()):
                    
                    # 调整画笔/文字大小（复制截图窗口的逻辑）
                    if dy > 0:
                        self.main_window.tool_width += 1
                    elif self.main_window.tool_width > 1:
                        self.main_window.tool_width -= 1
                    
                    # 如果有size_slider，同步更新
                    if hasattr(self.main_window, 'size_slider'):
                        self.main_window.size_slider.setValue(self.main_window.tool_width)
                    
                    # 如果有Tipsshower，显示提示
                    if hasattr(self.main_window, 'Tipsshower'):
                        # 移除了大小提示
                        pass
                    
                    # 如果文字工具激活，更新文字框字体（复制截图窗口的逻辑）
                    if (hasattr(self.main_window, 'painter_tools') and 
                        self.main_window.painter_tools.get('drawtext_on', 0) and 
                        hasattr(self.main_window, 'text_box')):
                        self.main_window.text_box.setFont(QFont('', self.main_window.tool_width))
                        self.main_window.text_box.textAreaChanged()
                    
                    print(f"🎨 [钉图滚轮] 画笔大小调整为: {self.main_window.tool_width}px")
                    
                elif 2 * QApplication.desktop().width() >= self.width() >= 50:
                    # 原来的缩放逻辑
                    # 获取鼠标所在位置相对于窗口的坐标
                    old_pos = e.pos()
                    old_width = self.width()
                    old_height = self.height()
                    w = self.width() + dy * 5
                    if w < 50: w = 50
                    if w > 2 * QApplication.desktop().width(): w = 2 * QApplication.desktop().width()
                    
                    if hasattr(self, 'showing_imgpix') and self.showing_imgpix:
                        scale = self.showing_imgpix.height() / self.showing_imgpix.width()
                        h = w * scale
                        s = self.width() / w  # 缩放比例
                        self.setPixmap(self.showing_imgpix.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        self.resize(w, h)
                        # 同步绘画层（几何与内容）
                        self._sync_paintlayer_on_resize(int(w), int(h))
                        delta_x = -(w - old_width)*old_pos.x()/old_width
                        delta_y = -(h - old_height)*old_pos.y()/old_height
                        self.move(self.x() + delta_x, self.y() + delta_y)
                    QApplication.processEvents()

            self.update()
    def move(self,x,y):
        super().move(x,y)
        
        # 避免在DPI调整过程中的递归调用
        if getattr(self, '_adjusting_dpi', False):
            return
        
        # 检测DPI变化并调整窗口大小
        self.check_and_adjust_for_dpi_change()
        
        # 智能定位OCR文字窗口，避免遮挡
        if hasattr(self, 'text_shower'):
            self._position_text_shower_smartly()
        
        # 如果有主窗口工具栏，更新其位置
        if self.main_window and hasattr(self.main_window, 'position_toolbar_for_pinned_window'):
            # 检查是否有保存的显示器信息，如果没有则重新获取
            if not hasattr(self, 'target_screen'):
                if hasattr(self.main_window, 'get_screen_for_point'):
                    self.target_screen = self.main_window.get_screen_for_point(
                        self.x() + self.width() // 2, self.y() + self.height() // 2)
            
            # 如果钉图窗口移动到了其他显示器，更新工具栏位置
            if hasattr(self, 'target_screen'):
                current_screen = self.main_window.get_screen_for_point(
                    self.x() + self.width() // 2, self.y() + self.height() // 2)
                if current_screen != self.target_screen:
                    self.target_screen = current_screen
                    print(f"钉图窗口移动到新显示器: {current_screen.geometry().getRect()}")
            
            self.main_window.position_toolbar_for_pinned_window(self)

    def _position_text_shower_smartly(self):
        """智能定位OCR文字窗口，避免遮挡"""
        # 安全检查：确保text_shower存在且有效
        if not hasattr(self, 'text_shower') or self.text_shower is None:
            return
            
        # 获取当前屏幕信息
        screens = QApplication.screens()
        current_screen = QApplication.primaryScreen()
        
        # 找到钉图窗口所在的屏幕
        window_center_x = self.x() + self.width() // 2
        window_center_y = self.y() + self.height() // 2
        
        for screen in screens:
            geometry = screen.geometry()
            if (window_center_x >= geometry.x() and window_center_x < geometry.x() + geometry.width() and
                window_center_y >= geometry.y() and window_center_y < geometry.y() + geometry.height()):
                current_screen = screen
                break
        
        screen_rect = current_screen.geometry()
        
        # 安全地获取文字窗口的预期大小
        try:
            text_width = self.text_shower.width() if self.text_shower.width() > 0 else 300
            text_height = self.text_shower.height() if self.text_shower.height() > 0 else 200
        except AttributeError:
            # 如果text_shower已被清理，直接返回
            return
        
        # 钉图窗口的边界
        img_left = self.x()
        img_right = self.x() + self.width()
        img_top = self.y()
        img_bottom = self.y() + self.height()
        
        # 尝试不同的文字窗口位置（优先级从高到低）
        positions = [
            # 1. 下方中央（钉图窗口正下方）
            (img_left + (self.width() - text_width) // 2, img_bottom + 15),
            # 2. 右下角（钉图窗口右下方）
            (img_right + 15, img_bottom - text_height + 20),
            # 3. 左下角（钉图窗口左下方）
            (img_left - text_width - 15, img_bottom - text_height + 20),
            # 4. 上方中央（钉图窗口正上方）
            (img_left + (self.width() - text_width) // 2, img_top - text_height - 15),
            # 5. 右上角（钉图窗口右上方）
            (img_right + 15, img_top - 20),
            # 6. 左上角（钉图窗口左上方）
            (img_left - text_width - 15, img_top - 20),
        ]
        
        # 选择第一个在屏幕范围内的位置
        for text_x, text_y in positions:
            # 检查是否在屏幕范围内
            if (text_x >= screen_rect.x() + 10 and 
                text_y >= screen_rect.y() + 10 and
                text_x + text_width <= screen_rect.x() + screen_rect.width() - 10 and
                text_y + text_height <= screen_rect.y() + screen_rect.height() - 10):
                
                self.text_shower.move(text_x, text_y)
                return
        
        # 如果所有位置都不合适，使用调整后的默认位置
        default_x = max(screen_rect.x() + 10, min(img_left, screen_rect.x() + screen_rect.width() - text_width - 10))
        default_y = max(screen_rect.y() + 10, min(img_bottom + 15, screen_rect.y() + screen_rect.height() - text_height - 10))
        self.text_shower.move(default_x, default_y)

    def _force_post_switch_resize(self, scale_changed: bool, new_scale: float):
        """显示器切换后模拟一次滚轮缩放，强制刷新钉图窗口尺寸。"""
        try:
            if not hasattr(self, 'showing_imgpix') or not self.showing_imgpix:
                return
            base_w = self.width()
            base_h = self.height()
            img_ratio = self.showing_imgpix.height() / max(1, self.showing_imgpix.width())
            if scale_changed:
                # 与基础缩放比较（如果有）
                base_scale = getattr(self, '_base_scale', new_scale)
                # 高->低 缩小一点，低->高 放大一点
                factor = 0.94 if new_scale < base_scale else 1.06
            else:
                factor = 1.0  # 不改变尺寸，仅刷新
            new_w = int(base_w * factor)
            if new_w < 50: new_w = 50
            if new_w > 2 * QApplication.desktop().width():
                new_w = 2 * QApplication.desktop().width()
            new_h = int(new_w * img_ratio)
            # 仅在需要时调整尺寸，不输出调试
            scaled = self.showing_imgpix.scaled(new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled)
            self.resize(new_w, new_h)
            self._sync_paintlayer_on_resize(new_w, new_h)
            QApplication.processEvents()
        except Exception as e:
            print(f"⚠️ 模拟滚轮调整失败: {e}")
    
    def check_and_adjust_for_dpi_change(self):
        """检测DPI变化并调整窗口大小 - 防止重复触发版本"""
        try:
            # 如果正在调整中，避免重复触发
            if getattr(self, '_adjusting_dpi', False):
                return
                
            # 获取当前显示器
            screens = QApplication.screens()
            current_screen = None
            window_center_x = self.x() + self.width() // 2
            window_center_y = self.y() + self.height() // 2
            
            for screen in screens:
                geometry = screen.geometry()
                if (window_center_x >= geometry.x() and window_center_x < geometry.x() + geometry.width() and
                    window_center_y >= geometry.y() and window_center_y < geometry.y() + geometry.height()):
                    current_screen = screen
                    break
            
            if current_screen is None:
                return
            
            # 获取当前显示器的DPI和缩放信息
            current_dpi = current_screen.devicePixelRatio()
            logical_dpi = current_screen.logicalDotsPerInch()
            physical_dpi = current_screen.physicalDotsPerInch()
            
            # 计算Windows系统缩放比例
            system_scale = logical_dpi / 96.0  # Windows基准DPI是96
            screen_geometry_rect = current_screen.geometry().getRect()
            
            # 检查是否有保存的缩放信息
            if not hasattr(self, '_last_scale_info'):
                self._last_scale_info = {
                    'dpi': current_dpi,
                    'logical_dpi': logical_dpi,
                    'system_scale': system_scale,
                    'screen_geometry': screen_geometry_rect
                }
                # 保存原始图像信息作为基准
                if hasattr(self, 'showing_imgpix') and self.showing_imgpix and not self.showing_imgpix.isNull():
                    # 使用图像的原始尺寸，不受当前显示缩放影响
                    self._base_img_size = (self.showing_imgpix.width(), self.showing_imgpix.height())
                    # 记录初始显示尺寸和对应的缩放
                    self._base_display_size = (self.width(), self.height())
                    self._base_scale = system_scale
                else:
                    self._base_img_size = (800, 600)
                    self._base_display_size = (self.width(), self.height())
                    self._base_scale = system_scale
                    
                # 初次建立基准信息，不再冗余输出
                return
            
            # 检查是否发生了显示器切换（重要：只有屏幕几何变化才调整）
            last_screen = self._last_scale_info.get('screen_geometry')
            last_scale = self._last_scale_info.get('system_scale', 1.0)
            
            screen_changed = screen_geometry_rect != last_screen
            # 缩放变化阈值放宽到 0.05，提高灵敏度
            scale_changed = abs(system_scale - last_scale) > 0.05

            # 只要屏幕几何变了就视为切换；缩放是否变化决定是否重算尺寸
            if screen_changed:
                # 显示器切换，后续自动调整
                
                if hasattr(self, 'showing_imgpix') and self.showing_imgpix and not self.showing_imgpix.isNull():
                    try:
                        # 设置调整标志，防止递归
                        self._adjusting_dpi = True
                        
                        # 基于原始图像尺寸和目标缩放计算理想显示尺寸
                        base_img_width, base_img_height = self._base_img_size
                        base_scale = self._base_scale
                        
                        # 计算在新显示器上应该显示的尺寸
                        # 保持相同的视觉大小：相对于基准缩放的比例
                        scale_ratio = base_scale / system_scale
                        
                        target_width = int(self._base_display_size[0] * scale_ratio)
                        target_height = int(self._base_display_size[1] * scale_ratio)
                        
                        # 获取显示器安全区域
                        screen_geometry = current_screen.geometry()
                        safe_margin = int(100 * system_scale)
                        max_width = screen_geometry.width() - safe_margin
                        max_height = screen_geometry.height() - safe_margin
                        min_size = int(150 * system_scale)
                        
                        # 限制尺寸在安全范围内
                        target_width = max(min_size, min(target_width, max_width))
                        target_height = max(min_size, min(target_height, max_height))
                        
                        current_width = self.width()
                        current_height = self.height()
                        
                        # 计算目标尺寸（调试输出已移除）
                        
                        # 一次性调整到目标尺寸
                        try:
                            # 创建调整后的图像
                            scaled_pixmap = self.showing_imgpix.scaled(
                                target_width, target_height,
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation
                            )
                            
                            # 更新显示和尺寸
                            self.setPixmap(scaled_pixmap)
                            self.resize(target_width, target_height)
                            # 同步绘画层（几何与内容）
                            self._sync_paintlayer_on_resize(int(target_width), int(target_height))
                            
                            # 检查位置是否需要调整
                            current_pos = self.pos()
                            new_x = current_pos.x()
                            new_y = current_pos.y()
                            
                            if current_pos.x() + target_width > screen_geometry.right():
                                new_x = screen_geometry.right() - target_width
                            if current_pos.y() + target_height > screen_geometry.bottom():
                                new_y = screen_geometry.bottom() - target_height
                            if new_x < screen_geometry.left():
                                new_x = screen_geometry.left()
                            if new_y < screen_geometry.top():
                                new_y = screen_geometry.top()
                            
                            if new_x != current_pos.x() or new_y != current_pos.y():
                                self.move(new_x, new_y)
                            
                            # 切换完成
                            # 触发一次模拟滚轮以强制执行与用户滚轮一致的缩放修正, 解决偶发未刷新
                            self._force_post_switch_resize(scale_changed, system_scale)
                            
                            # 钉图窗口调整完成后，重新生成工具栏以匹配新的DPI
                            if self.main_window and hasattr(self.main_window, 'relayout_toolbar_for_pinned_mode'):
                                # 重新生成工具栏以匹配新DPI
                                self.main_window.relayout_toolbar_for_pinned_mode()
                            
                        except Exception:
                            pass
                        
                    except Exception:
                        pass
                    finally:
                        # 更新保存的缩放信息（重要：防止重复触发）
                        self._last_scale_info = {
                            'dpi': current_dpi,
                            'logical_dpi': logical_dpi,
                            'system_scale': system_scale,
                            'screen_geometry': screen_geometry_rect
                        }
                        # 重新启用moveEvent
                        self._adjusting_dpi = False
                
                # 更新工具栏位置
                if self.main_window and hasattr(self.main_window, 'position_toolbar_for_pinned_window'):
                    self.main_window.position_toolbar_for_pinned_window(self)
            
            # 移动但未跨屏时不需要处理
            elif not screen_changed:
                pass
                
        except Exception as e:
            print(f"❌ DPI调整失败: {e}")
            import traceback
            traceback.print_exc()
        
    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        if hasattr(self,"Loading_label"):
            self.Loading_label.setGeometry(0, 0, self.width(), self.height())
        
        # 确保showing_imgpix有效
        self._ensure_showing_imgpix_valid()
        
        # 缩放时更新底图和备份历史
        self._update_for_resize(self.width(), self.height())
        
        # 任意方式触发的尺寸变化，都同步绘画层
        self._sync_paintlayer_on_resize(self.width(), self.height())
        
        # 更新关闭按钮位置
        self.update_close_button_position()
        
        # 如果钉图窗口大小改变，检查是否需要重新生成工具栏
        if (self.main_window and hasattr(self.main_window, 'relayout_toolbar_for_pinned_mode') and 
            hasattr(self.main_window, 'mode') and self.main_window.mode == "pinned"):
            print(f"📏 钉图窗口尺寸变化: {self.width()}x{self.height()}, 重新生成工具栏")
            self.main_window.relayout_toolbar_for_pinned_mode()
            # 重新定位工具栏
            if hasattr(self.main_window, 'position_toolbar_for_pinned_window'):
                self.main_window.position_toolbar_for_pinned_window(self)
    def draw_ocr_select_result(self,ids = []):
        qpixmap = self.ocr_res_imgpix.copy()
        painter = QPainter(qpixmap)
        
        for i,text_box in enumerate(self.ocr_res_info):
            if i in ids:
                pen = QPen(QColor(64, 224, 208))
            else:
                pen = QPen(Qt.red)
            pen.setWidth(2) 
            painter.setPen(pen)
            contour = text_box["box"]
            points = []
            for point in contour:
                x, y = point
                points.append(QPoint(x, y))
            polygon = QPolygon(points + [points[0]])
            painter.drawPolyline(polygon)
        painter.end()
        return qpixmap
    def check_select_ocr_box(self,x,y):
        select_ids = []
        change = False
        for i,text_box in enumerate(self.ocr_res_info):
            contour = text_box["box"]
            dist = cv2.pointPolygonTest(contour, (x,y), False)
            if dist >= 0:
                text_box["select"] = ~text_box["select"]
                change = True
            if text_box["select"]:
                select_ids.append(i)
            
        return select_ids,change
    def update_ocr_text(self,ids):
        match_text_box = []
        for i,text_box in enumerate(self.ocr_res_info):
            if i in ids:
                match_text_box.append(text_box)
        if hasattr(self,"ocrthread"):
            res = self.ocrthread.get_match_text(match_text_box)
            if res is not None:
                return res
        return None
    def update_ocr_select_result(self,x,y):
        select_ids,changed = self.check_select_ocr_box(x,y)
        if changed:
            pix = self.draw_ocr_select_result(ids = select_ids)
            self.showing_imgpix = pix
            self.setPixmap(pix.scaled(self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            update_res = self.update_ocr_text(select_ids)
            if update_res is not None:
                # 更新结果
                self.text_shower.move(self.x(), self.y()+self.height()+10)  # 向下移动10像素
                self.text_shower.show()
                self.text_shower.clear()
                self.text_shower.insertPlainText(update_res)
        return changed
        
    def mousePressEvent(self, event):
        # print(f"钉图鼠标按下调试: 按钮={event.button()}")
        
        # 检查是否有主窗口工具栏显示且有绘画工具激活
        has_main_window = self.main_window is not None
        has_mode = hasattr(self.main_window, 'mode') if has_main_window else False
        is_pinned_mode = self.main_window.mode == "pinned" if has_mode else False
        has_painter_tools = hasattr(self.main_window, 'painter_tools') if has_main_window else False
        # 检查文字工具、画笔工具等是否激活
        has_active_tools = False
        if has_painter_tools:
            tools = self.main_window.painter_tools
            has_active_tools = (tools.get('drawtext_on', 0) == 1 or 
                              tools.get('pen_on', 0) == 1 or 
                              tools.get('eraser_on', 0) == 1 or
                              tools.get('arrow_on', 0) == 1 or
                              tools.get('rect_on', 0) == 1 or
                              tools.get('ellipse_on', 0) == 1 or
                              tools.get('line_on', 0) == 1)
        
        # print(f"钉图鼠标按下调试: 主窗口={has_main_window}, 模式={is_pinned_mode}, 绘图工具={has_active_tools}")
        # if has_painter_tools:
        #     print(f"绘图工具状态: {self.main_window.painter_tools}")
        
        if (has_main_window and has_mode and is_pinned_mode and has_painter_tools and has_active_tools):
            # print("钉图鼠标按下调试: 条件满足，开始委托事件")
            # 有绘画工具激活时，将事件传递给主窗口处理
            # 在钉图模式下，直接使用钉图窗口的本地坐标
            # print(f"🎯 [钉图委托] 原始点击坐标: ({event.x()}, {event.y()})")
            main_event = QMouseEvent(event.type(), event.pos(), 
                                   event.globalPos(), event.button(), event.buttons(), event.modifiers())
            # 添加标记表示这是来自钉图窗口的委托事件
            main_event._from_pinned_window = True
            main_event._pinned_window_instance = self  # 添加当前钉图窗口引用
            # print(f"钉图委托调试: 调用主窗口mousePressEvent，坐标=({event.x()}, {event.y()})")
            self.main_window.mousePressEvent(main_event)
            # 设置标志表示我们正在处理绘画拖拽
            self.is_drawing_drag = True
            # print(f"钉图鼠标按下调试: 设置is_drawing_drag=True")
            # 调用父类方法以确保Qt正确跟踪鼠标状态
            super().mousePressEvent(event)
            return
            
        # print("钉图鼠标按下调试: 条件不满足，使用默认处理")
        # 重置绘画拖拽标志
        self.is_drawing_drag = False
        if event.button() == Qt.LeftButton:
            if self.ocr_status=="show":
                sx,sy = self.origin_imgpix.width()/self.width(),self.origin_imgpix.height()/self.height()
                realx,realy = event.x()*sx,event.y()*sy
                changed = self.update_ocr_select_result(realx,realy)
                if changed:
                    return
            if event.x() > self.width() - 20 and event.y() > self.height() - 20:
                self.resize_the_window = True
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.SizeAllCursor)
                self.drag = True
                self.p_x, self.p_y = event.x(), event.y()
            # self.resize(self.width()/2,self.height()/2)
            # self.setPixmap(self.pixmap().scaled(self.pixmap().width()/2,self.pixmap().height()/2))

    def mouseReleaseEvent(self, event):
        # 检查是否有主窗口工具栏显示且有绘画工具激活，或者正在进行绘画拖拽
        has_active_tools = False
        if (self.main_window and hasattr(self.main_window, 'painter_tools')):
            tools = self.main_window.painter_tools
            has_active_tools = (tools.get('drawtext_on', 0) == 1 or 
                              tools.get('pen_on', 0) == 1 or 
                              tools.get('eraser_on', 0) == 1 or
                              tools.get('arrow_on', 0) == 1 or
                              tools.get('rect_on', 0) == 1 or
                              tools.get('ellipse_on', 0) == 1 or
                              tools.get('line_on', 0) == 1)
        
        if ((self.main_window and hasattr(self.main_window, 'mode') and 
            self.main_window.mode == "pinned" and has_active_tools) or 
            getattr(self, 'is_drawing_drag', False)):
            # 有绘画工具激活时，将事件传递给主窗口处理
            # 在钉图模式下，直接使用钉图窗口的本地坐标
            main_event = QMouseEvent(event.type(), event.pos(), 
                                   event.globalPos(), event.button(), event.buttons(), event.modifiers())
            # 添加标记表示这是来自钉图窗口的委托事件
            main_event._from_pinned_window = True
            main_event._pinned_window_instance = self  # 添加当前钉图窗口引用
            print(f"钉图委托调试: 调用主窗口mouseReleaseEvent，坐标=({event.x()}, {event.y()})")
            self.main_window.mouseReleaseEvent(main_event)
            # 重置绘画拖拽标志
            self.is_drawing_drag = False
            return
            
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ArrowCursor)
            self.drag = self.resize_the_window = False
            self.drag = self.resize_the_window = False
    def underMouse(self) -> bool:
        return super().underMouse()
    def mouseMoveEvent(self, event):
        # 显示关闭按钮（当鼠标在窗口内时）
        if hasattr(self, 'close_button'):
            self.close_button.show()
        
        # 解析按钮状态
        left_pressed = event.buttons() & Qt.LeftButton
        
        # 检查是否有主窗口工具栏显示且有绘画工具激活，或者正在进行绘画拖拽
        has_active_tools = False
        if (self.main_window and hasattr(self.main_window, 'painter_tools')):
            tools = self.main_window.painter_tools
            has_active_tools = (tools.get('drawtext_on', 0) == 1 or 
                              tools.get('pen_on', 0) == 1 or 
                              tools.get('eraser_on', 0) == 1 or
                              tools.get('arrow_on', 0) == 1 or
                              tools.get('rect_on', 0) == 1 or
                              tools.get('ellipse_on', 0) == 1 or
                              tools.get('line_on', 0) == 1)
        
        if ((self.main_window and hasattr(self.main_window, 'mode') and 
            self.main_window.mode == "pinned" and has_active_tools) or 
            getattr(self, 'is_drawing_drag', False)):
            # 有绘画工具激活时，将事件传递给主窗口处理
            # 在钉图模式下，直接使用钉图窗口的本地坐标
            main_event = QMouseEvent(event.type(), event.pos(), 
                                   event.globalPos(), event.button(), event.buttons(), event.modifiers())
            # 添加标记表示这是来自钉图窗口的委托事件
            main_event._from_pinned_window = True
            main_event._pinned_window_instance = self  # 添加当前钉图窗口引用
            print(f"钉图委托调试: 调用主窗口mouseMoveEvent，坐标=({event.x()}, {event.y()})")
            self.main_window.mouseMoveEvent(main_event)
            return
            
        if self.isVisible():
            if self.drag:
                self.move(event.x() + self.x() - self.p_x, event.y() + self.y() - self.p_y)
                # 拖拽移动时检查DPI变化
                self.check_and_adjust_for_dpi_change()
            elif self.resize_the_window:
                if event.x() > 10 and event.y() > 10:
                    w = event.x()
                    scale = self.showing_imgpix.height() / self.showing_imgpix.width()
                    h = w * scale
                    self.resize(w, h)
                    self.setPixmap(self.showing_imgpix.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    # 同步绘画层（几何与内容）
                    self._sync_paintlayer_on_resize(int(w), int(h))
            elif event.x() > self.width() - 20 and event.y() > self.height() - 20:
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
    def enterEvent(self,e):
        super().enterEvent(e)
        if hasattr(self, 'timer') and self.timer and not self.closed:
            self.timer.stop()
        # 停止延迟隐藏定时器（如果正在运行）
        if hasattr(self, 'hide_timer') and self.hide_timer is not None:
            if self.hide_timer.isActive():
                print("🕐 鼠标重新进入，停止延迟隐藏定时器")
                self.hide_timer.stop()
        # 如果右键菜单正在显示，不触发工具栏重新布局
        if getattr(self, '_context_menu_active', False):
            return
            
        # 只有在工具栏未显示时才显示工具栏，避免重复初始化导致二级菜单被隐藏
        if self.main_window and hasattr(self.main_window, 'show_toolbar_for_pinned_window'):
            # 检查工具栏是否已经显示
            if (hasattr(self.main_window, 'botton_box') and 
                not self.main_window.botton_box.isVisible()):
                print("🔧 工具栏未显示，重新显示工具栏")
                self.main_window.show_toolbar_for_pinned_window(self)
            else:
                # 工具栏已经显示，只需要确保它是可见的，不要重新初始化
                if hasattr(self.main_window, 'botton_box'):
                    self.main_window.botton_box.show()
                    self.main_window.botton_box.raise_()
                    print("🔧 工具栏已存在，仅确保可见性")
            
    def leaveEvent(self,e):
        super().leaveEvent(e)
        
        # 隐藏关闭按钮（当鼠标离开窗口时）
        if hasattr(self, 'close_button'):
            self.close_button.hide()
        
        # 如果右键菜单正在显示，不启动计时器
        if not getattr(self, '_context_menu_active', False):
            # 检查timer是否还存在且有效，且窗口未关闭
            if (hasattr(self, 'timer') and self.timer is not None and 
                not getattr(self, 'closed', False) and 
                not getattr(self, '_is_closed', False)):
                try:
                    self.timer.start()
                except Exception as e:
                    print(f"⚠️ [定时器警告] 启动定时器失败: {e}")
            else:
                print("⚠️ [定时器警告] timer不可用，跳过启动")
        self.settingOpacity = False
        
    def _hide_toolbar_delayed(self):
        """延迟隐藏工具栏的方法"""
        # 再次检查鼠标位置，确保仍然不在窗口或工具栏上
        if not self.underMouse():
            if self.main_window and hasattr(self.main_window, 'is_toolbar_under_mouse'):
                if not self.main_window.is_toolbar_under_mouse():
                    # 检查是否有绘画工具激活，如果有则不隐藏工具栏
                    if (hasattr(self.main_window, 'painter_tools') and 
                        1 in self.main_window.painter_tools.values()):
                        print("绘画工具激活中，不隐藏工具栏")
                        return
                    
                    # 检查是否有二级菜单正在显示且处于活跃状态
                    if (hasattr(self.main_window, 'paint_tools_menu') and 
                        self.main_window.paint_tools_menu.isVisible()):
                        # 检查二级菜单是否有焦点或者鼠标刚刚在其上
                        print("二级菜单正在显示，暂不隐藏工具栏")
                        return
                    
                    # 检查是否刚刚点击了绘画工具按钮（给用户一些反应时间）
                    current_time = QTimer().remainingTime() if hasattr(QTimer(), 'remainingTime') else 0
                    
                    # 执行隐藏工具栏
                    if hasattr(self.main_window, 'hide_toolbar_for_pinned_window'):
                        print("🔒 0.5秒延迟后隐藏钉图工具栏")
                        self.main_window.hide_toolbar_for_pinned_window()

    def check_mouse_leave(self):
        # 如果右键菜单正在显示，不执行隐藏操作
        if getattr(self, '_context_menu_active', False):
            return
            
        # 检查是否离开钉图窗口和主工具栏
        if not self.underMouse():
            if self.main_window and hasattr(self.main_window, 'is_toolbar_under_mouse'):
                if not self.main_window.is_toolbar_under_mouse():
                    # 检查是否有绘画工具激活，如果有则应该更谨慎地处理隐藏逻辑
                    if (hasattr(self.main_window, 'painter_tools') and 
                        1 in self.main_window.painter_tools.values()):
                        print("绘画工具激活中，检查是否真的需要隐藏工具栏")
                        
                        # 当绘画工具激活时，只有在鼠标明确远离工作区域时才隐藏工具栏
                        # 检查鼠标是否在钉图窗口的合理范围内（包括一定的缓冲区）
                        cursor_pos = QCursor.pos()
                        window_rect = self.geometry()
                        # 扩大检测范围，给用户更多的操作空间
                        buffer_zone = 50
                        from PyQt5.QtCore import QRect
                        extended_rect = QRect(
                            window_rect.x() - buffer_zone,
                            window_rect.y() - buffer_zone,
                            window_rect.width() + 2 * buffer_zone,
                            window_rect.height() + 2 * buffer_zone
                        )
                        
                        if extended_rect.contains(cursor_pos):
                            print("鼠标仍在工作区域附近，保持工具栏显示")
                            return
                        
                        # 即使要隐藏，也给更长的延迟时间
                        if hasattr(self, 'hide_timer') and self.hide_timer is not None:
                            print("🕐 绘画工具激活时延长隐藏延迟到2秒")
                            self.hide_timer.setInterval(2000)  # 延长到2秒
                            self.hide_timer.start()
                        
                        if (hasattr(self, 'timer') and self.timer is not None and 
                            not getattr(self, 'closed', False) and 
                            not getattr(self, '_is_closed', False)):
                            try:
                                self.timer.stop()
                            except Exception as e:
                                print(f"⚠️ [定时器警告] 绘画工具激活时停止定时器失败: {e}")
                        return
                    
                    # 检查是否有右键菜单正在显示（通过检查当前活动窗口）
                    active_window = QApplication.activeWindow()
                    if active_window and "QMenu" in str(type(active_window)):
                        print("右键菜单正在显示，延迟隐藏工具栏")
                        QTimer.singleShot(500, self.check_mouse_leave)  # 500ms后再次检查
                        return
                    
                    # 普通情况下启动0.5秒延迟隐藏定时器
                    if hasattr(self, 'hide_timer') and self.hide_timer is not None:
                        print("🕐 启动0.5秒延迟隐藏工具栏定时器")
                        self.hide_timer.setInterval(500)  # 重置为默认的0.5秒
                        self.hide_timer.start()
                    
                    # 安全停止检查定时器
                    if hasattr(self, 'timer') and self.timer is not None:
                        try:
                            self.timer.stop()
                        except Exception as e:
                            print(f"⚠️ [定时器警告] 停止定时器失败: {e}")
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.clear()
        elif e.key() == Qt.Key_Control:
            self.settingOpacity = True
        elif self.settingOpacity:  # 如果已经按下了ctrl
            if e.key() == Qt.Key_Z:  # Ctrl+Z 撤回
                print("🔄 [钉图窗口] 检测到 Ctrl+Z，执行撤回")
                self.last_step()
            elif e.key() == Qt.Key_Y:  # Ctrl+Y 重做
                print("🔄 [钉图窗口] 检测到 Ctrl+Y，执行重做")
                self.next_step()

    def keyReleaseEvent(self, e) -> None:
        if e.key() == Qt.Key_Control:
            self.settingOpacity = False

    def paintEvent(self, event):
        super().paintEvent(event)
        
        # 钉图窗口只负责绘制边框，绘画内容由paintlayer处理
        if self.drawRect:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(64, 224, 208), 1, Qt.SolidLine))
            painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
            painter.end()

    def clear(self):
        print(f"🧹 [内存清理] 开始清理钉图窗口 (listpot={self.listpot})")
        
        # 添加调用栈追踪，找出是谁调用了clear()
        import traceback
        stack_trace = traceback.format_stack()
        print("🔍 [调用栈] clear() 被调用的完整路径：")
        for i, frame in enumerate(stack_trace[-5:]):  # 只显示最后5个调用栈
            print(f"   {i}: {frame.strip()}")
        
        # 检查是否正在保存，如果是则拒绝清理
        if hasattr(self, '_is_saving') and self._is_saving:
            print("🚫 [内存清理] 正在保存中，拒绝执行清理操作")
            return
            
        # 检查是否有防清理标志
        if hasattr(self, '_prevent_clear') and self._prevent_clear:
            print("🚫 [内存清理] 检测到防清理标志，拒绝执行清理操作")
            return
        
        # 立即标记为已关闭，防止后续绘画操作
        self.closed = True
        
        # 立即停止所有绘画工具，防止QPainter冲突
        if self.main_window:
            try:
                # 停止所有绘画工具激活状态
                if hasattr(self.main_window, 'painter_tools'):
                    for key in self.main_window.painter_tools:
                        self.main_window.painter_tools[key] = 0
                
                # 清空所有绘画点列表
                if hasattr(self.main_window, 'pen_pointlist'):
                    self.main_window.pen_pointlist.clear()
                if hasattr(self.main_window, 'drawrect_pointlist'):
                    self.main_window.drawrect_pointlist = [[-2, -2], [-2, -2], 0]
                if hasattr(self.main_window, 'drawcircle_pointlist'):
                    self.main_window.drawcircle_pointlist = [[-2, -2], [-2, -2], 0]
                if hasattr(self.main_window, 'drawarrow_pointlist'):
                    self.main_window.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
                if hasattr(self.main_window, 'drawtext_pointlist'):
                    self.main_window.drawtext_pointlist.clear()
                    
                print(f"🧹 [内存清理] 已停止所有绘画操作")
            except Exception as e:
                print(f"⚠️ 停止绘画操作时出错: {e}")
        
        # 记录清理前的内存使用
        try:
            import importlib, os
            psutil = importlib.import_module("psutil")
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            print(f"📊 [内存监控] 清理前内存: {memory_before:.1f} MB")
        except Exception:
            memory_before = None
        
        # 标记为已关闭，防止后续操作
        self._is_closed = True
        self._is_editing = False
        
        # 停止所有定时器
        if hasattr(self, 'timer') and self.timer:
            self.timer.stop()
            self.timer.deleteLater()
            self.timer = None
            print(f"🧹 [内存清理] 定时器已停止并删除")
        
        # 停止延迟隐藏定时器
        if hasattr(self, 'hide_timer') and self.hide_timer:
            self.hide_timer.stop()
            self.hide_timer.deleteLater()
            self.hide_timer = None
            print(f"🧹 [内存清理] 延迟隐藏定时器已停止并删除")
        
        # 清理图像数据 - 这是内存的大头，优先清理
        if hasattr(self, 'origin_imgpix') and self.origin_imgpix:
            self.origin_imgpix = None
            print(f"🧹 [内存清理] origin_imgpix已清理")
            
        if hasattr(self, 'showing_imgpix') and self.showing_imgpix:
            self.showing_imgpix = None
            print(f"🧹 [内存清理] showing_imgpix已清理")
            
        if hasattr(self, 'ocr_res_imgpix') and self.ocr_res_imgpix:
            self.ocr_res_imgpix = None
            print(f"🧹 [内存清理] ocr_res_imgpix已清理")
        
        # 清理QPixmap相关属性
        if hasattr(self, '_cached_pixmap'):
            self._cached_pixmap = None
        if hasattr(self, '_scaled_pixmap'):
            self._scaled_pixmap = None
        
        # 清理工具栏 - 解决ESC后工具栏残留的问题
        if hasattr(self, 'toolbar') and self.toolbar:
            try:
                self.toolbar.hide()
                self.toolbar.deleteLater()
                self.toolbar = None
                print(f"🧹 [内存清理] 工具栏已清理")
            except Exception as e:
                print(f"⚠️ 清理工具栏时出错: {e}")
            
        self.clearMask()
        self.hide()
        
        # 停止并清理 OCR 线程，避免线程持有引用导致泄露
        if hasattr(self, 'ocrthread') and self.ocrthread:
            try:
                try:
                    # 断开信号连接
                    self.ocrthread.result_show_signal.disconnect()
                except Exception:
                    pass
                try:
                    self.ocrthread.boxes_info_signal.disconnect()
                except Exception:
                    pass
                try:
                    self.ocrthread.det_res_img.disconnect()
                except Exception:
                    pass
                # 请求线程退出
                try:
                    self.ocrthread.requestInterruption()
                except Exception:
                    pass
                try:
                    self.ocrthread.quit()
                except Exception:
                    pass
                try:
                    # 等待短时间确保退出
                    self.ocrthread.wait(500)
                except Exception:
                    pass
                try:
                    self.ocrthread.deleteLater()
                except Exception:
                    pass
            except Exception as e:
                print(f"⚠️ 清理OCR线程时出错: {e}")
            finally:
                self.ocrthread = None

        # 清理Loading_label
        if hasattr(self,"Loading_label") and self.Loading_label:
            try:
                self.Loading_label.stop()
                self.Loading_label.deleteLater()
                self.Loading_label = None
                print(f"🧹 [内存清理] Loading_label已清理")
            except Exception as e:
                print(f"⚠️ 清理Loading_label时出错: {e}")
        
        # 清理text_shower
        if hasattr(self, 'text_shower') and self.text_shower:
            try:
                self.text_shower.clear()
                self.text_shower.hide()
                self.text_shower.deleteLater()
                self.text_shower = None
                print(f"🧹 [内存清理] text_shower已清理")
            except Exception as e:
                print(f"⚠️ 清理text_shower时出错: {e}")
        
        # 清理tips_shower
        if hasattr(self, 'tips_shower') and self.tips_shower:
            try:
                self.tips_shower.hide()
                self.tips_shower.deleteLater()
                self.tips_shower = None
                print(f"🧹 [内存清理] tips_shower已清理")
            except Exception as e:
                print(f"⚠️ 清理tips_shower时出错: {e}")
        
        # 清理paintlayer
        if hasattr(self, 'paintlayer') and self.paintlayer:
            try:
                # 调用paintlayer的clear方法进行安全清理
                if hasattr(self.paintlayer, 'clear'):
                    self.paintlayer.clear()
                else:
                    # 备用清理方法
                    self.paintlayer.hide()
                    self.paintlayer.clear()
                
                self.paintlayer.deleteLater()
                self.paintlayer = None
                print(f"🧹 [内存清理] paintlayer已清理")
            except Exception as e:
                print(f"⚠️ 清理paintlayer时出错: {e}")
        
        # 清理所有可能的子控件
        for child in self.findChildren(QWidget):
            try:
                child.deleteLater()
            except Exception:
                pass
        
        # 清理主窗口的文字输入框（如果被独立出来了）
        if self.main_window and hasattr(self.main_window, 'text_box'):
            try:
                self.main_window.text_box.hide()
                self.main_window.text_box.clear()
                # 如果文字框处于独立窗口状态，将其恢复为主窗口的子组件
                self.main_window.text_box.setParent(self.main_window)
                self.main_window.text_box.setWindowFlags(Qt.Widget)
                print(f"🧹 [内存清理] 主窗口文字框已重置")
            except Exception as e:
                print(f"⚠️ 清理主窗口文字框时出错: {e}")
        
        # 清理主窗口的绘画数据列表 - 防止累积
        if self.main_window:
            try:
                # 清理绘画点列表
                if hasattr(self.main_window, 'pen_pointlist'):
                    self.main_window.pen_pointlist.clear()
                if hasattr(self.main_window, 'drawrect_pointlist'):
                    self.main_window.drawrect_pointlist = [[-2, -2], [-2, -2], 0]
                if hasattr(self.main_window, 'drawcircle_pointlist'):
                    self.main_window.drawcircle_pointlist = [[-2, -2], [-2, -2], 0]
                if hasattr(self.main_window, 'drawarrow_pointlist'):
                    self.main_window.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
                if hasattr(self.main_window, 'drawtext_pointlist'):
                    self.main_window.drawtext_pointlist.clear()
                    
                print(f"🧹 [内存清理] 主窗口绘画数据已清理")
            except Exception as e:
                print(f"⚠️ 清理主窗口绘画数据时出错: {e}")
        
        # 清理QLabel的pixmap内容
        self.setPixmap(QPixmap())
        super().clear()
        
        # 断开所有引用，避免循环引用
        self.main_window = None
        self.parent = None
        
        # 立即强制垃圾回收，不等待系统调度
        import gc
        
        # 多次垃圾回收确保彻底清理
        for i in range(3):
            collected = gc.collect()
            if collected > 0:
                print(f"🧹 [强制回收] 第{i+1}次垃圾回收释放了 {collected} 个对象")
        
        # 强制处理Qt事件队列，确保deleteLater生效
        try:
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
            # 再次垃圾回收
            collected = gc.collect()
            if collected > 0:
                print(f"🧹 [Qt事件后] 额外回收了 {collected} 个对象")
        except Exception:
            pass
        
        print(f"🧹 [内存清理] 钉图窗口清理完成")

    def closeEvent(self, e):
        """窗口关闭事件 - 激进的内存回收"""
        print(f"🔒 [关闭事件] 钉图窗口关闭事件触发 (listpot={self.listpot})")
        
        # 检查是否正在保存，如果是则阻止关闭
        if hasattr(self, '_is_saving') and self._is_saving:
            print("🚫 [关闭事件] 正在保存中，阻止窗口关闭")
            e.ignore()
            return
        
        # 防止重复关闭
        if hasattr(self, '_is_closed') and self._is_closed:
            super().closeEvent(e)
            return
        
        # 立即从主窗口的列表中移除自己
        if self.main_window and hasattr(self.main_window, 'freeze_imgs'):
            try:
                if self in self.main_window.freeze_imgs:
                    self.main_window.freeze_imgs.remove(self)
                    print(f"✅ [关闭事件] 已从主窗口列表中移除钉图窗口 (剩余: {len(self.main_window.freeze_imgs)})")
                    
                    # 立即强制垃圾回收
                    import gc
                    gc.collect()
                    
                    # 如果这是最后一个窗口，执行深度清理
                    if len(self.main_window.freeze_imgs) == 0:
                        print("🧹 [最后窗口] 执行深度内存清理...")
                        # 多次垃圾回收确保彻底清理
                        for _ in range(3):
                            gc.collect()
                        try:
                            from PyQt5.QtCore import QCoreApplication
                            QCoreApplication.processEvents()
                        except:
                            pass
                        print("🧹 [最后窗口] 深度内存清理完成")
                        
            except (ValueError, AttributeError) as ex:
                print(f"⚠️ 从列表移除时出错: {ex}")
        
        # 立即执行清理，不等待
        try:
            self.clear()
        except Exception as ex:
            print(f"⚠️ 清理过程中出错: {ex}")
        
        # 立即隐藏和断开连接
        self.hide()
        self.setParent(None)
        
        # 调用父类的closeEvent
        super().closeEvent(e)
        
        # 立即删除，不等待定时器
        self.deleteLater()
        
        # 立即强制处理删除事件
        try:
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
        except:
            pass
        
        print(f"🔒 [关闭事件] 钉图窗口已立即删除")


