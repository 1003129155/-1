"""
主程序 - 新架构版本
完整截图流程: 截屏 → 选区 → 绘制 → 导出
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QImage, QColor, QUndoStack, QScreen

from canvas.document import Document, LayerStyle
from canvas.canvas_widget import CanvasWidget
from canvas.tools_v2 import ToolContext, ToolController
from canvas.tools_impl import (
    PenTool, RectTool, EllipseTool, ArrowTool,
    TextTool, NumberTool, HighlighterTool, MosaicTool
)
from canvas.selection_tool import SelectionTool
from canvas.export_service import ExportService
from canvas.toolbar_adapter import ToolbarAdapter
from ui.toolbar_full import Toolbar


class ScreenshotApp:
    """
    截图应用 - 新架构完整版
    
    流程:
    1. 截取屏幕
    2. 创建Document
    3. 显示CanvasWidget(全屏)
    4. 用户拖拽选区
    5. 确认选区 → 显示工具栏
    6. 用户绘制
    7. 保存/复制/确认
    """
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        
        # 核心组件
        self.doc = None
        self.canvas = None
        self.undo_stack = None
        self.tool_controller = None
        self.toolbar = None
        self.toolbar_adapter = None
        self.export_service = None
        
        print("=" * 60)
        print("🚀 截图应用启动 - 新架构版本")
        print("=" * 60)
    
    def capture_screen(self) -> QImage:
        """
        截取屏幕
        
        Returns:
            QImage: 屏幕截图
        """
        print("\n📸 正在截取屏幕...")
        
        # 获取主屏幕
        screen = self.app.primaryScreen()
        screenshot = screen.grabWindow(0)
        image = screenshot.toImage()
        
        print(f"✅ 截图成功: {image.width()}x{image.height()}")
        return image
    
    def start(self):
        """启动应用"""
        
        # 1. 截取屏幕
        background = self.capture_screen()
        
        # 2. 创建Document
        print("\n📄 创建Document...")
        self.doc = Document(background)
        
        # 3. 创建撤销栈
        print("📚 创建QUndoStack...")
        self.undo_stack = QUndoStack()
        
        # 4. 创建工具上下文
        print("🔧 创建ToolContext...")
        style = LayerStyle(color=QColor(255, 0, 0), stroke_width=5, opacity=1.0)
        tool_context = ToolContext(
            document=self.doc,
            undo_stack=self.undo_stack,
            style=style
        )
        
        # 5. 创建工具控制器
        print("🛠️ 创建ToolController...")
        self.tool_controller = ToolController(tool_context)
        
        # 注册所有工具
        self.tool_controller.register(SelectionTool())
        self.tool_controller.register(PenTool())
        self.tool_controller.register(RectTool())
        self.tool_controller.register(EllipseTool())
        self.tool_controller.register(ArrowTool())
        self.tool_controller.register(TextTool())
        self.tool_controller.register(NumberTool())
        self.tool_controller.register(HighlighterTool())
        self.tool_controller.register(MosaicTool())
        
        # 6. 创建CanvasWidget
        print("🖼️ 创建CanvasWidget...")
        self.canvas = CanvasWidget(self.doc)
        self.canvas.set_tool_controller(self.tool_controller)
        
        # 7. 创建工具栏
        print("🧰 创建工具栏...")
        self.toolbar = Toolbar()
        
        # 8. 创建工具栏适配器
        print("🔌 创建ToolbarAdapter...")
        self.toolbar_adapter = ToolbarAdapter(
            self.toolbar,
            self.tool_controller,
            self.undo_stack
        )
        
        # 9. 创建导出服务
        print("📦 创建ExportService...")
        self.export_service = ExportService(self.doc)
        
        # 10. 连接信号
        print("🔗 连接信号...")
        self._connect_signals()
        
        # 11. 显示画布(全屏)
        print("\n🎬 显示画布...")
        self.canvas.showFullScreen()
        
        # 12. 初始状态:不激活任何工具,让用户创建选区
        # 选区创建完成后才激活工具
        print("⏳ 等待用户创建选区...")
        
        print("\n" + "=" * 60)
        print("✅ 应用启动完成!")
        print("=" * 60)
        print("\n操作说明:")
        print("1. 🖱️  拖拽鼠标创建选区")
        print("2. ⏎  回车确认选区 → 显示工具栏")
        print("3. ✏️  使用工具栏绘制图形")
        print("4. 💾 点击保存/复制按钮")
        print("5. ❌ ESC退出")
        print("=" * 60)
        
        # 运行应用
        sys.exit(self.app.exec())
    
    def _connect_signals(self):
        """连接信号"""
        
        # 画布信号
        self.canvas.selection_confirmed.connect(self._on_selection_confirmed)
        self.canvas.cancel_requested.connect(self._on_cancel)
        
        # 工具栏信号
        self.toolbar_adapter.save_requested.connect(self._on_save)
        self.toolbar_adapter.copy_requested.connect(self._on_copy)
        self.toolbar_adapter.confirm_requested.connect(self._on_confirm)
    
    # ========================================================================
    #  信号处理
    # ========================================================================
    
    def _on_selection_confirmed(self, selection: QRectF):
        """选区确认 → 显示工具栏"""
        print(f"\n✅ 选区确认: {selection}")
        
        # 激活画笔工具(默认)
        self.tool_controller.activate("pen")
        print("✏️ 激活画笔工具")
        
        # 计算工具栏位置(选区下方)
        toolbar_x = int(selection.left())
        toolbar_y = int(selection.bottom() + 10)
        
        # 检查是否超出屏幕
        screen_height = self.doc.background.height()
        if toolbar_y + self.toolbar.height() > screen_height:
            # 放在选区上方
            toolbar_y = int(selection.top() - self.toolbar.height() - 10)
        
        # 显示工具栏
        self.toolbar_adapter.show_at(toolbar_x, toolbar_y)
        print(f"🧰 工具栏显示: ({toolbar_x}, {toolbar_y})")
    
    def _on_save(self):
        """保存图像"""
        print("\n💾 保存图像...")
        
        # 生成文件名
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"screenshot_{timestamp}.png"
        
        # 导出
        success = self.export_service.export_to_file(filepath, self.doc.selection)
        
        if success:
            print(f"✅ 保存成功: {filepath}")
        else:
            print(f"❌ 保存失败")
    
    def _on_copy(self):
        """复制到剪贴板"""
        print("\n📋 复制到剪贴板...")
        self.export_service.export_to_clipboard(self.doc.selection)
    
    def _on_confirm(self):
        """确认并退出"""
        print("\n✅ 确认并退出...")
        
        # 导出到剪贴板
        self.export_service.export_to_clipboard(self.doc.selection)
        
        # 退出应用
        self.app.quit()
    
    def _on_cancel(self):
        """取消并退出"""
        print("\n❌ 取消截图,退出应用")
        self.app.quit()


def main():
    """主函数"""
    app = ScreenshotApp()
    app.start()


if __name__ == "__main__":
    main()
