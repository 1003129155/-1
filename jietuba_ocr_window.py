# -*- coding: utf-8 -*-
"""
jietuba_ocr_window.py - OCR 结果显示窗口

显示 OCR 识别结果的窗口。
支持文本显示、复制、编辑等功能。

主要类:
- OCRResultWindow: OCR 结果显示窗口
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QLabel, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon


class OCRResultWindow(QWidget):
    """OCR 结果显示窗口"""
    
    closed = pyqtSignal()  # 窗口关闭信号
    toggle_boxes_requested = pyqtSignal()  # 切换边框显示
    toggle_text_requested = pyqtSignal()  # 切换文字显示
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OCR 识别结果")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.resize(550, 450)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 标题标签
        title_label = QLabel("📖 识别结果")
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        layout.addWidget(title_label)
        
        # 文本编辑区域
        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont("Microsoft YaHei", 10))
        self.text_edit.setPlaceholderText("识别结果将显示在这里...")
        layout.addWidget(self.text_edit)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 复制按钮
        self.copy_btn = QPushButton("📋 复制")
        self.copy_btn.setToolTip("复制识别结果到剪贴板")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(self.copy_btn)
        
        # 清空按钮
        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.setToolTip("清空识别结果")
        self.clear_btn.clicked.connect(self.clear_text)
        button_layout.addWidget(self.clear_btn)
        
        # 切换边框按钮
        self.toggle_boxes_btn = QPushButton("📦 边框")
        self.toggle_boxes_btn.setToolTip("切换文字边框显示")
        self.toggle_boxes_btn.setCheckable(True)
        self.toggle_boxes_btn.setChecked(True)
        self.toggle_boxes_btn.clicked.connect(self.toggle_boxes_requested.emit)
        button_layout.addWidget(self.toggle_boxes_btn)
        
        # 弹簧
        button_layout.addStretch()
        
        # 关闭按钮
        self.close_btn = QPushButton("✖ 关闭")
        self.close_btn.setToolTip("关闭窗口")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
        # 设置样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QLabel {
                color: #333;
            }
        """)
    
    def set_text(self, text: str):
        """设置显示文本"""
        self.text_edit.setPlainText(text)
    
    def get_text(self) -> str:
        """获取当前文本"""
        return self.text_edit.toPlainText()
    
    def copy_to_clipboard(self):
        """复制文本到剪贴板"""
        text = self.get_text()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            
            # 临时改变按钮文本以提示用户
            original_text = self.copy_btn.text()
            self.copy_btn.setText("✅ 已复制")
            
            # 1秒后恢复按钮文本
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(1000, lambda: self.copy_btn.setText(original_text))
    
    def clear_text(self):
        """清空文本"""
        self.text_edit.clear()
    
    def append_text(self, text: str):
        """追加文本"""
        current_text = self.get_text()
        if current_text:
            self.set_text(current_text + "\n\n" + text)
        else:
            self.set_text(text)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self.closed.emit()
        super().closeEvent(event)
    
    def show_with_text(self, text: str):
        """显示窗口并设置文本"""
        self.set_text(text)
        self.show()
        self.activateWindow()
        self.raise_()


# 测试代码
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    
    window = OCRResultWindow()
    window.set_text("这是一个测试文本\n用于测试 OCR 结果显示窗口\n支持多行显示")
    window.show()
    
    sys.exit(app.exec_())
