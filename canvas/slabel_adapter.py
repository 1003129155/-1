"""
SLabelAdapter - Slabel 到 Document-View-Command 架构的适配器

目的:
1. 对外保持 Slabel 原有API兼容性
2. 对内使用新的 Document-View-Command 架构
3. 渐进式迁移,降低风险

架构:
    旧API (Slabel)
         ↓
    SLabelAdapter (适配层)
         ↓
    Document + CanvasWidget + QUndoStack (新架构)
"""

from typing import Optional, Tuple
from PyQt6.QtCore import QRectF, QPointF, QSize
from PyQt6.QtGui import QPixmap, QImage, QColor, QUndoStack
from PyQt6.QtWidgets import QWidget

from .document import Document, Layer
from .canvas_widget import CanvasWidget
from .commands import SetSelectionCommand, AddLayerCommand


class SLabelAdapter:
    """
    Slabel 适配器
    
    提供兼容旧Slabel的API,内部使用新架构实现
    
    旧API示例:
        self.x1, self.y1, self.x2, self.y2  # 选区坐标
        self.backup_pic_list                # 历史记录
        self.set_selection(x1, y1, x2, y2)  # 设置选区
        
    新架构:
        self.document                       # 数据模型
        self.canvas_view                    # 视图渲染
        self.undo_stack                     # 撤销栈
    """
    
    def __init__(self, background: QImage):
        """
        初始化适配器
        
        Args:
            background: 截图背景图像
        """
        # ==================== 新架构组件 ====================
        
        # 1. 数据模型 (Document)
        self.document = Document(background)
        
        # 2. 视图渲染 (CanvasWidget) - 延迟创建,在需要时初始化
        self.canvas_view: Optional[CanvasWidget] = None
        
        # 3. 撤销栈 (QUndoStack)
        self.undo_stack = QUndoStack()
        
        # ==================== 旧API兼容字段 ====================
        
        # 选区坐标 (x1,y1,x2,y2) - 兼容旧代码
        self.x1: int = -1
        self.y1: int = -1
        self.x2: int = -1
        self.y2: int = -1
        
        # 历史记录列表 - 兼容旧代码
        self.backup_pic_list = []
        self.backup_ssid = -1
        
        # ==================== 内部状态 ====================
        
        # 是否启用新架构(渐进式迁移标志)
        self._use_new_architecture = True
        
        print("✅ [SLabelAdapter] 初始化完成")
        print(f"   - Document: {self.document.rect}")
        print(f"   - 背景尺寸: {background.width()}x{background.height()}")
    
    # ========================================================================
    #  选区相关API (兼容旧Slabel)
    # ========================================================================
    
    def set_selection(self, x1: int, y1: int, x2: int, y2: int):
        """
        设置选区 (旧API)
        
        内部会转换为新架构的 SetSelectionCommand
        
        Args:
            x1, y1: 左上角坐标
            x2, y2: 右下角坐标
        """
        if self._use_new_architecture:
            # 新架构: 使用命令模式
            # 保存旧选区(用于撤销)
            old_rect = self.document.selection
            
            rect = QRectF(
                min(x1, x2), 
                min(y1, y2),
                abs(x2 - x1),
                abs(y2 - y1)
            )
            cmd = SetSelectionCommand(self.document, rect, old_rect)
            self.undo_stack.push(cmd)
        
        # 同步旧字段(兼容性)
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        
        print(f"📐 [选区] 设置: ({x1},{y1}) → ({x2},{y2})")
    
    def get_selection(self) -> Tuple[int, int, int, int]:
        """
        获取选区坐标 (旧API)
        
        Returns:
            (x1, y1, x2, y2) 元组
        """
        if self._use_new_architecture and self.document.selection:
            rect = self.document.selection
            self.x1 = int(rect.x())
            self.y1 = int(rect.y())
            self.x2 = int(rect.x() + rect.width())
            self.y2 = int(rect.y() + rect.height())
        
        return (self.x1, self.y1, self.x2, self.y2)
    
    def has_selection(self) -> bool:
        """是否有选区"""
        if self._use_new_architecture:
            return self.document.has_selection()
        return self.x1 >= 0 and self.y1 >= 0
    
    def clear_selection(self):
        """清除选区"""
        if self._use_new_architecture:
            self.document.set_selection(None)
        self.x1 = self.y1 = self.x2 = self.y2 = -1
    
    # ========================================================================
    #  图层相关API (兼容旧Slabel)
    # ========================================================================
    
    def add_layer(self, layer: Layer):
        """
        添加图层 (新API,推荐使用)
        
        Args:
            layer: Layer实例
        """
        if self._use_new_architecture:
            cmd = AddLayerCommand(self.document, layer)
            self.undo_stack.push(cmd)
        else:
            # 降级: 直接添加
            self.document.add_layer(layer)
    
    def remove_layer(self, layer_id: int):
        """
        删除图层
        
        Args:
            layer_id: 图层ID
        """
        # TODO: 实现 RemoveLayerCommand
        self.document.remove_layer(layer_id)
    
    def get_layer_count(self) -> int:
        """获取图层数量"""
        return len(self.document.layers)
    
    # ========================================================================
    #  撤销/重做 (兼容旧Slabel)
    # ========================================================================
    
    def record_state(self, snapshot: dict):
        """
        记录当前状态到撤销栈 (新方法)
        
        Args:
            snapshot: 从_capture_backup_snapshot()获取的状态快照
        """
        if self._use_new_architecture:
            # 将快照保存到backup_pic_list(兼容性)
            self.backup_pic_list.append(snapshot)
            self.backup_ssid = len(self.backup_pic_list) - 1
            
            # 限制历史数量
            max_history = 50
            if len(self.backup_pic_list) > max_history:
                self.backup_pic_list = self.backup_pic_list[-max_history:]
                self.backup_ssid = len(self.backup_pic_list) - 1
            
            print(f"💾 [撤销栈] 状态已记录 - 总步数: {len(self.backup_pic_list)}, 当前: {self.backup_ssid}")
    
    def can_undo(self) -> bool:
        """是否可以撤销"""
        if self._use_new_architecture:
            return self.backup_ssid > 0 and len(self.backup_pic_list) > 0
        return self.undo_stack.canUndo()
    
    def can_redo(self) -> bool:
        """是否可以重做"""
        if self._use_new_architecture:
            return self.backup_ssid < len(self.backup_pic_list) - 1
        return self.undo_stack.canRedo()
    
    def undo(self):
        """执行撤销"""
        if self._use_new_architecture:
            if self.can_undo():
                self.backup_ssid -= 1
                print(f"↶ [撤销] 撤销到步骤 {self.backup_ssid}")
            else:
                print("⚠️ [撤销] 无法撤销")
        else:
            if self.undo_stack.canUndo():
                self.undo_stack.undo()
    
    def redo(self):
        """执行重做"""
        if self._use_new_architecture:
            if self.can_redo():
                self.backup_ssid += 1
                print(f"↷ [重做] 重做到步骤 {self.backup_ssid}")
            else:
                print("⚠️ [重做] 无法重做")
        else:
            if self.undo_stack.canRedo():
                self.undo_stack.redo()
    
    def get_current_state(self) -> Optional[dict]:
        """
        获取当前状态快照
        
        Returns:
            当前状态的字典,如果没有状态则返回None
        """
        if self._use_new_architecture:
            if 0 <= self.backup_ssid < len(self.backup_pic_list):
                return self.backup_pic_list[self.backup_ssid]
        return None
    
    def backup_shortshot(self):
        """
        备份当前状态 (旧API)
        
        内部会同步到 undo_stack
        """
        if self._use_new_architecture:
            # 新架构: 自动由命令处理,无需手动备份
            # 但为了兼容旧代码,这里同步 backup_pic_list
            state = self._export_state()
            self.backup_pic_list.append(state)
            self.backup_ssid = len(self.backup_pic_list) - 1
            
            # 限制历史数量(防止内存爆炸)
            max_history = 50
            if len(self.backup_pic_list) > max_history:
                self.backup_pic_list = self.backup_pic_list[-max_history:]
                self.backup_ssid = len(self.backup_pic_list) - 1
        
        print(f"💾 [备份] 当前状态 (历史数: {len(self.backup_pic_list)})")
    
    def last_step(self):
        """撤销 (旧API)"""
        if self._use_new_architecture:
            if self.undo_stack.canUndo():
                self.undo_stack.undo()
                print("↶ [撤销] 执行撤销")
            else:
                print("⚠️ [撤销] 无法撤销")
        else:
            # 降级: 使用旧方式
            if self.backup_ssid > 0:
                self.backup_ssid -= 1
                self._restore_state(self.backup_pic_list[self.backup_ssid])
    
    def next_step(self):
        """重做 (旧API)"""
        if self._use_new_architecture:
            if self.undo_stack.canRedo():
                self.undo_stack.redo()
                print("↷ [重做] 执行重做")
            else:
                print("⚠️ [重做] 无法重做")
        else:
            # 降级: 使用旧方式
            if self.backup_ssid < len(self.backup_pic_list) - 1:
                self.backup_ssid += 1
                self._restore_state(self.backup_pic_list[self.backup_ssid])
    
    # ========================================================================
    #  渲染相关 (兼容旧Slabel)
    # ========================================================================
    
    def render_to_pixmap(self) -> QPixmap:
        """
        渲染当前画布为 QPixmap
        
        用于兼容旧代码中使用 pixmap() 的地方
        
        Returns:
            包含背景+图层的完整图像
        """
        if self._use_new_architecture:
            # 使用 CanvasWidget 渲染
            if not self.canvas_view:
                self.canvas_view = CanvasWidget(self.document)
            
            # 从 QWidget 抓取像素图
            return self.canvas_view.grab()
        else:
            # 降级: 从 Document 手动渲染
            from PyQt6.QtGui import QPainter
            
            bg = self.document.background
            pixmap = QPixmap.fromImage(bg)
            painter = QPainter(pixmap)
            
            # 绘制所有图层
            for layer in self.document.layers:
                # TODO: 实现简单的图层渲染
                pass
            
            painter.end()
            return pixmap
    
    # ========================================================================
    #  内部辅助方法
    # ========================================================================
    
    def _export_state(self) -> dict:
        """
        导出当前状态 (用于备份)
        
        Returns:
            包含选区、图层等信息的字典
        """
        return {
            'selection': self.document.selection,
            'layers': [layer.clone() for layer in self.document.layers],
            'active_layer_id': self.document.active_layer_id,
        }
    
    def _restore_state(self, state: dict):
        """
        恢复状态 (用于撤销/重做)
        
        Args:
            state: _export_state() 导出的状态
        """
        self.document.set_selection(state.get('selection'))
        self.document.layers = state.get('layers', [])
        self.document.active_layer_id = state.get('active_layer_id')
        self.document.layer_updated.emit(-1)
    
    # ========================================================================
    #  调试接口
    # ========================================================================
    
    def print_state(self):
        """打印当前状态(调试用)"""
        print("\n" + "="*60)
        print("📊 [SLabelAdapter] 当前状态")
        print("="*60)
        print(f"选区: {self.get_selection()}")
        print(f"图层数: {self.get_layer_count()}")
        print(f"历史步数: {len(self.backup_pic_list)}")
        print(f"可撤销: {self.undo_stack.canUndo()}")
        print(f"可重做: {self.undo_stack.canRedo()}")
        print("="*60 + "\n")
