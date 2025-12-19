"""
SLabelAdapterPyQt5 - PyQt5兼容的适配器

由于现有程序使用PyQt5,而canvas模块使用PyQt6,
这个适配器提供PyQt5兼容的接口,用于逐步集成。

阶段性策略:
1. 第一阶段: 仅集成撤销/重做功能 (使用backup_pic_list的兼容层)
2. 第二阶段: 逐步迁移到完整的Document架构
"""

from typing import Optional, Tuple, List
from PyQt5.QtCore import QRectF, QPointF
from PyQt5.QtGui import QPixmap, QImage


class SLabelAdapterPyQt5:
    """
    PyQt5兼容的适配器 - 渐进式集成
    
    阶段1: 仅提供撤销/重做的改进实现
    阶段2: 逐步集成完整的Document-View-Command架构
    """
    
    def __init__(self, background: QImage = None):
        """
        初始化适配器
        
        Args:
            background: 截图背景 (可选,后续可通过set_background设置)
        """
        # 背景图像
        self.background = background
        
        # ==================== 旧API兼容字段 ====================
        
        # 选区坐标 (x1,y1,x2,y2) - 保持完全兼容
        self.x1: int = -1
        self.y1: int = -1
        self.x2: int = -1
        self.y2: int = -1
        
        # 历史记录 - 增强版本(支持更多信息)
        self.backup_pic_list: List[dict] = []
        self.backup_ssid: int = -1
        
        # ==================== 新功能标志 ====================
        
        # 是否启用增强的撤销系统
        self._enhanced_undo = True
        
        # 最大历史记录数
        self._max_history = 50
        
        print("✅ [SLabelAdapterPyQt5] 初始化完成 (PyQt5兼容模式)")
    
    # ========================================================================
    #  背景管理
    # ========================================================================
    
    def set_background(self, background: QImage):
        """设置背景图像"""
        self.background = background
        print(f"📐 [适配器] 设置背景: {background.width()}x{background.height()}")
    
    # ========================================================================
    #  选区相关API (完全兼容旧Slabel)
    # ========================================================================
    
    def set_selection(self, x1: int, y1: int, x2: int, y2: int):
        """
        设置选区 (兼容旧API)
        
        Args:
            x1, y1: 左上角坐标
            x2, y2: 右下角坐标
        """
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        print(f"📐 [选区] 设置: ({x1},{y1}) → ({x2},{y2})")
    
    def get_selection(self) -> Tuple[int, int, int, int]:
        """
        获取选区坐标
        
        Returns:
            (x1, y1, x2, y2) 元组
        """
        return (self.x1, self.y1, self.x2, self.y2)
    
    def has_selection(self) -> bool:
        """是否有选区"""
        return self.x1 >= 0 and self.y1 >= 0
    
    def clear_selection(self):
        """清除选区"""
        self.x1 = self.y1 = self.x2 = self.y2 = -1
    
    # ========================================================================
    #  增强的撤销/重做 (兼容旧API,内部优化)
    # ========================================================================
    
    def backup_shortshot(self, state: dict = None):
        """
        备份当前状态 (增强版)
        
        Args:
            state: 状态字典,包含任意需要备份的数据
                   如果为None,则创建空状态(兼容旧用法)
        """
        if state is None:
            state = {}
        
        # 添加时间戳
        import time
        state['timestamp'] = time.time()
        
        # 如果在历史中间位置,清除后续历史
        if self.backup_ssid < len(self.backup_pic_list) - 1:
            self.backup_pic_list = self.backup_pic_list[:self.backup_ssid + 1]
        
        # 添加新状态
        self.backup_pic_list.append(state)
        self.backup_ssid = len(self.backup_pic_list) - 1
        
        # 限制历史数量
        if len(self.backup_pic_list) > self._max_history:
            removed = len(self.backup_pic_list) - self._max_history
            self.backup_pic_list = self.backup_pic_list[removed:]
            self.backup_ssid = len(self.backup_pic_list) - 1
        
        print(f"💾 [备份] 已备份 (历史数:{len(self.backup_pic_list)}, 当前:{self.backup_ssid})")
    
    def last_step(self) -> Optional[dict]:
        """
        撤销 (返回上一个状态)
        
        Returns:
            上一个状态字典,如果不能撤销则返回None
        """
        if self.backup_ssid > 0:
            self.backup_ssid -= 1
            state = self.backup_pic_list[self.backup_ssid]
            print(f"↶ [撤销] 回到状态 {self.backup_ssid}/{len(self.backup_pic_list)-1}")
            return state
        else:
            print("⚠️ [撤销] 已是第一步,无法撤销")
            return None
    
    def next_step(self) -> Optional[dict]:
        """
        重做 (前进到下一个状态)
        
        Returns:
            下一个状态字典,如果不能重做则返回None
        """
        if self.backup_ssid < len(self.backup_pic_list) - 1:
            self.backup_ssid += 1
            state = self.backup_pic_list[self.backup_ssid]
            print(f"↷ [重做] 前进到状态 {self.backup_ssid}/{len(self.backup_pic_list)-1}")
            return state
        else:
            print("⚠️ [重做] 已是最新状态,无法重做")
            return None
    
    def can_undo(self) -> bool:
        """是否可以撤销"""
        return self.backup_ssid > 0
    
    def can_redo(self) -> bool:
        """是否可以重做"""
        return self.backup_ssid < len(self.backup_pic_list) - 1
    
    def get_undo_count(self) -> int:
        """获取可撤销步数"""
        return self.backup_ssid
    
    def get_redo_count(self) -> int:
        """获取可重做步数"""
        return len(self.backup_pic_list) - 1 - self.backup_ssid
    
    # ========================================================================
    #  调试接口
    # ========================================================================
    
    def print_state(self):
        """打印当前状态(调试用)"""
        print("\n" + "="*60)
        print("📊 [SLabelAdapterPyQt5] 当前状态")
        print("="*60)
        print(f"选区: {self.get_selection()}")
        print(f"历史步数: {len(self.backup_pic_list)}")
        print(f"当前位置: {self.backup_ssid}")
        print(f"可撤销: {self.can_undo()} ({self.get_undo_count()}步)")
        print(f"可重做: {self.can_redo()} ({self.get_redo_count()}步)")
        if self.background:
            print(f"背景尺寸: {self.background.width()}x{self.background.height()}")
        print("="*60 + "\n")


# ============================================================================
#  简化的测试代码
# ============================================================================

if __name__ == '__main__':
    """简单测试"""
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QColor
    import sys
    
    app = QApplication(sys.argv)
    
    # 创建背景
    bg = QImage(800, 600, QImage.Format_RGB32)
    bg.fill(QColor(255, 255, 255))
    
    # 创建适配器
    adapter = SLabelAdapterPyQt5(bg)
    
    # 测试选区
    adapter.set_selection(100, 100, 300, 200)
    assert adapter.get_selection() == (100, 100, 300, 200)
    
    # 测试撤销/重做
    adapter.backup_shortshot({'action': 'init'})
    adapter.set_selection(150, 150, 400, 300)
    adapter.backup_shortshot({'action': 'resize'})
    
    # 撤销
    state = adapter.last_step()
    assert state['action'] == 'init'
    
    # 重做
    state = adapter.next_step()
    assert state['action'] == 'resize'
    
    # 打印状态
    adapter.print_state()
    
    print("✅ 所有测试通过!")
