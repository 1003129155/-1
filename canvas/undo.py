"""
快照撤销系统
基于图像快照列表+指针的撤销/重做
"""

from PyQt6.QtGui import QImage, QPainter


class SnapshotUndoStack:
    """
    快照撤销栈(使用列表+指针实现)
    
    工作原理:
    - backup_list: [初始, 操作1, 操作2, ...]
    - backup_index: 当前位置指针
    - 撤销: index--, 恢复list[index]
    - 重做: index++, 恢复list[index]
    """
    
    def __init__(self, max_depth: int = 50):
        """
        Args:
            max_depth: 最大撤销深度
        """
        self.max_depth = max_depth
        self._backup_list = []  # 快照列表
        self._backup_index = 0  # 当前位置指针
        self._initialized = False
    
    def init_with_image(self, img: QImage):
        """
        初始化撤销系统(创建初始状态)
        
        Args:
            img: 初始图像
        """
        self._backup_list = [img.copy()]
        self._backup_index = 0
        self._initialized = True
        print(f"🔄 [撤销] 初始化: index={self._backup_index}, list_length={len(self._backup_list)}")
    
    def push_snapshot(self, img: QImage):
        """
        推入新快照（操作完成后调用）
        
        Args:
            img: 当前图像快照
        """
        if not self._initialized:
            # 如果未初始化,当作初始化
            self.init_with_image(img)
            return
        
        # 如果当前不在列表末尾(之前有撤销操作),删除后面的所有状态
        if self._backup_index < len(self._backup_list) - 1:
            self._backup_list = self._backup_list[:self._backup_index + 1]
        
        # 添加新快照
        self._backup_list.append(img.copy())
        
        # 限制列表长度
        if len(self._backup_list) > self.max_depth:
            self._backup_list.pop(0)
        else:
            self._backup_index += 1
        
        print(f"🔄 [撤销] 推入快照: index={self._backup_index}, list_length={len(self._backup_list)}")
    
    def can_undo(self) -> bool:
        """是否可以撤销"""
        return self._backup_index > 0
    
    def can_redo(self) -> bool:
        """是否可以重做"""
        return self._backup_index < len(self._backup_list) - 1
    
    def undo(self, overlay_item):
        """
        撤销操作
        
        Args:
            overlay_item: OverlayPixmapItem 实例
        """
        if not self.can_undo():
            print("⚠️ [撤销] 无法撤销")
            return
        
        # 指针后退
        self._backup_index -= 1
        
        # 恢复快照(直接替换内部图像)
        snapshot = self._backup_list[self._backup_index]
        img = overlay_item.image()
        painter = QPainter(img)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(0, 0, snapshot)
        painter.end()
        
        # 标记更新
        overlay_item.mark_dirty()
        
        print(f"↩️ [撤销] 成功: index={self._backup_index}, list_length={len(self._backup_list)}")
    
    def redo(self, overlay_item):
        """
        重做操作
        
        Args:
            overlay_item: OverlayPixmapItem 实例
        """
        if not self.can_redo():
            print("⚠️ [重做] 无法重做")
            return
        
        # 指针前进
        self._backup_index += 1
        
        # 恢复快照(直接替换内部图像)
        snapshot = self._backup_list[self._backup_index]
        img = overlay_item.image()
        painter = QPainter(img)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(0, 0, snapshot)
        painter.end()
        
        # 标记更新
        overlay_item.mark_dirty()
        
        print(f"↪️ [重做] 成功: index={self._backup_index}, list_length={len(self._backup_list)}")
        
        print(f"↪️ [重做] 成功: index={self._backup_index}, list_length={len(self._backup_list)}")
    
    def clear(self):
        """清空撤销/重做栈"""
        self._backup_list.clear()
        self._backup_index = 0
        self._initialized = False
        print("🧹 [撤销] 清空栈")
