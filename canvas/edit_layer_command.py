"""
图层编辑命令 - 支持撤销/重做
"""
from typing import Any, Dict
from PyQt6.QtGui import QUndoCommand
from canvas.document import Document, Layer


class EditLayerHandleCommand(QUndoCommand):
    """编辑图层控制点的命令"""
    
    def __init__(self, document: Document, layer_index: int, 
                 old_state: Dict[str, Any], new_state: Dict[str, Any]):
        """
        Args:
            document: 文档对象
            layer_index: 图层索引
            old_state: 旧状态字典(key=属性名, value=值)
            new_state: 新状态字典
        """
        super().__init__("编辑图层")
        self.document = document
        self.layer_index = layer_index
        self.old_state = old_state
        self.new_state = new_state
        
    def redo(self):
        """执行/重做:应用新状态"""
        layer = self.document.layers[self.layer_index]
        self._apply_state(layer, self.new_state)
        self.document.layer_updated.emit(self.layer_index)
        
    def undo(self):
        """撤销:恢复旧状态"""
        layer = self.document.layers[self.layer_index]
        self._apply_state(layer, self.old_state)
        self.document.layer_updated.emit(self.layer_index)
        
    def id(self) -> int:
        """返回命令ID用于合并"""
        return 1  # EditLayerHandleCommand的ID
        
    def mergeWith(self, other: QUndoCommand) -> bool:
        """合并命令(QUndoCommand标准接口)"""
        if not isinstance(other, EditLayerHandleCommand):
            return False
        # 同一图层的连续编辑可以合并
        if (self.document is other.document and 
            self.layer_index == other.layer_index):
            # 保留第一个命令的旧状态,更新为最后一个命令的新状态
            self.new_state = other.new_state
            return True
        return False
            
    def _apply_state(self, layer: Layer, state: Dict[str, Any]):
        """应用状态到图层"""
        from PyQt6.QtCore import QPointF, QRectF
        
        for key, value in state.items():
            if hasattr(layer, key):
                # 深拷贝 QPointF/QRectF 对象
                if isinstance(value, QPointF):
                    setattr(layer, key, QPointF(value))
                elif isinstance(value, QRectF):
                    setattr(layer, key, QRectF(value))
                else:
                    setattr(layer, key, value)


class EditTextLayerCommand(QUndoCommand):
    """编辑文字图层的命令"""
    
    def __init__(self, document: Document, layer_index: int, 
                 old_text: str, new_text: str):
        """
        Args:
            document: 文档对象
            layer_index: 图层索引
            old_text: 旧文字
            new_text: 新文字
        """
        super().__init__("编辑文字")
        self.document = document
        self.layer_index = layer_index
        self.old_text = old_text
        self.new_text = new_text
        
    def redo(self):
        """执行/重做:应用新文字"""
        layer = self.document.layers[self.layer_index]
        layer.text = self.new_text
        self.document.layer_updated.emit(self.layer_index)
        
    def undo(self):
        """撤销:恢复旧文字"""
        layer = self.document.layers[self.layer_index]
        layer.text = self.old_text
        self.document.layer_updated.emit(self.layer_index)
