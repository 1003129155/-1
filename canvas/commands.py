"""
撤销系统 - QUndoStack + QUndoCommand
专业软件标准做法
"""

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QUndoCommand
from typing import Optional

from .document import Document, Layer


# ============================================================================
#  选区命令
# ============================================================================

class SetSelectionCommand(QUndoCommand):
    """设置选区命令"""
    
    def __init__(self, doc: Document, new_rect: QRectF, old_rect: Optional[QRectF]):
        super().__init__("设置选区")
        self.doc = doc
        self.new_rect = new_rect
        self.old_rect = old_rect
    
    def redo(self):
        self.doc.set_selection(self.new_rect)
    
    def undo(self):
        if self.old_rect:
            self.doc.set_selection(self.old_rect)
        else:
            self.doc.clear_selection()


# ============================================================================
#  图层命令
# ============================================================================

class AddLayerCommand(QUndoCommand):
    """添加图层命令"""
    
    def __init__(self, doc: Document, layer: Layer, index: int = -1):
        super().__init__(f"添加{layer.__class__.__name__}")
        self.doc = doc
        self.layer = layer
        self.index = index
    
    def redo(self):
        self.doc.add_layer(self.layer, self.index)
    
    def undo(self):
        self.doc.remove_layer(self.layer.id)


class RemoveLayerCommand(QUndoCommand):
    """删除图层命令"""
    
    def __init__(self, doc: Document, layer: Layer, index: int):
        super().__init__(f"删除{layer.__class__.__name__}")
        self.doc = doc
        self.layer = layer
        self.index = index
    
    def redo(self):
        self.doc.remove_layer(self.layer.id)
    
    def undo(self):
        # 恢复到原位置
        self.doc.add_layer(self.layer, self.index)


class UpdateLayerCommand(QUndoCommand):
    """
    更新图层命令
    存储图层的前后状态
    """
    
    def __init__(self, doc: Document, layer_id: int, old_layer: Layer, new_layer: Layer):
        super().__init__("修改图层")
        self.doc = doc
        self.layer_id = layer_id
        self.old_layer = old_layer.clone()  # 旧状态快照
        self.new_layer = new_layer.clone()  # 新状态快照
    
    def redo(self):
        # 用新状态替换图层
        for i, layer in enumerate(self.doc.layers):
            if layer.id == self.layer_id:
                self.doc.layers[i] = self.new_layer.clone()
                self.doc.update_layer(self.layer_id)
                return
    
    def undo(self):
        # 用旧状态替换图层
        for i, layer in enumerate(self.doc.layers):
            if layer.id == self.layer_id:
                self.doc.layers[i] = self.old_layer.clone()
                self.doc.update_layer(self.layer_id)
                return


class MoveLayerCommand(QUndoCommand):
    """移动图层命令(改变图层顺序)"""
    
    def __init__(self, doc: Document, layer_id: int, old_index: int, new_index: int):
        super().__init__("移动图层")
        self.doc = doc
        self.layer_id = layer_id
        self.old_index = old_index
        self.new_index = new_index
    
    def redo(self):
        layer = self.doc.layers.pop(self.old_index)
        self.doc.layers.insert(self.new_index, layer)
        self.doc.update_layer(self.layer_id)
    
    def undo(self):
        layer = self.doc.layers.pop(self.new_index)
        self.doc.layers.insert(self.old_index, layer)
        self.doc.update_layer(self.layer_id)


# ============================================================================
#  复合命令示例
# ============================================================================

class BatchLayerCommand(QUndoCommand):
    """
    批量图层命令
    可以合并多个子命令
    """
    
    def __init__(self, description: str = "批量操作"):
        super().__init__(description)
        # 子命令会自动被QUndoStack管理


class DrawStrokeCommand(QUndoCommand):
    """
    绘制画笔命令(完整示例)
    
    专业做法:
    - 拖拽过程中不推命令,只做临时预览
    - 鼠标松开时,创建图层并推入命令
    """
    
    def __init__(self, doc: Document, layer):
        super().__init__("画笔")
        self.doc = doc
        self.layer = layer
    
    def redo(self):
        self.doc.add_layer(self.layer)
    
    def undo(self):
        self.doc.remove_layer(self.layer.id)
    
    def id(self):
        """返回命令ID,用于合并连续命令"""
        return 1
    
    def mergeWith(self, other):
        """
        合并连续命令(可选优化)
        
        例如:连续画多笔,可以合并成一个撤销步骤
        """
        if other.id() != self.id():
            return False
        
        # 合并逻辑...
        return True
