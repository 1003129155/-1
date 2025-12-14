# -*- coding: utf-8 -*-
"""
jietuba_ocr_text_layer.py - OCR 可交互文字层（钉图专用）

在钉图窗口上叠加一个完全透明的文字选择层，支持：
- 鼠标悬停时显示文本选择光标
- 点击设置光标位置，拖拽选择连续文字（Word 风格）
- 支持钉图缩放时坐标自适应
- 绘画模式时自动禁用

使用：
当钉图生成后，自动异步触发 OCR 识别并创建此透明文字层
"""
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QRect, QPoint, QRectF, pyqtSignal, QEvent
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QCursor, QFont, QFontMetrics
from typing import List, Dict, Optional, Tuple


class OCRTextItem:
    """OCR 识别的单个文字块"""
    
    def __init__(self, text: str, box: List[List[int]], score: float):
        """
        初始化文字块
        
        Args:
            text: 文字内容
            box: 四个角的坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]（相对于原始图像）
            score: 识别置信度
        """
        self.text = text
        self.original_box = box  # 保存原始坐标
        self.score = score
        
        # 计算原始边界矩形（归一化坐标 0-1）
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        self.norm_rect = QRectF(
            min(xs), min(ys),
            max(xs) - min(xs),
            max(ys) - min(ys)
        )
        
        # 用于文字内部字符定位
        self.char_positions: List[Tuple[int, int]] = []  # 每个字符的 x 位置（相对于文字块）
    
    def calculate_char_positions(self, rect: QRect):
        """计算每个字符的位置（均分）"""
        if not self.text:
            return
        
        char_count = len(self.text)
        char_width = rect.width() / char_count if char_count > 0 else 0
        
        self.char_positions.clear()
        for i in range(char_count + 1):  # +1 是为了包含结束位置
            x_pos = rect.x() + int(i * char_width)
            self.char_positions.append(x_pos)
    
    def get_char_index_at_pos(self, x: int, rect: QRect) -> int:
        """根据 x 坐标获取最接近的字符索引"""
        if not self.text or not self.char_positions:
            return 0
        
        # 确保 x 在文字块范围内（扩展检测范围）
        if x < rect.x():
            return 0  # 点击在左侧，返回起始位置
        if x > rect.x() + rect.width():
            return len(self.text)  # 点击在右侧，返回末尾位置
        
        # 找到最接近的字符位置
        for i, char_x in enumerate(self.char_positions):
            if x < char_x:
                # 判断是靠近前一个还是当前字符
                if i > 0:
                    prev_x = self.char_positions[i - 1]
                    mid_x = (prev_x + char_x) / 2
                    if x < mid_x:
                        return i - 1
                return i
        
        return len(self.text)  # 超出范围返回末尾
    
    def get_scaled_rect(self, scale_x: float, scale_y: float, original_width: int, original_height: int) -> QRect:
        """
        获取缩放后的矩形
        
        Args:
            scale_x: X轴缩放比例
            scale_y: Y轴缩放比例
            original_width: 原始图像宽度
            original_height: 原始图像高度
        """
        # 从归一化坐标转换为实际坐标
        x = int(self.norm_rect.x() * scale_x)
        y = int(self.norm_rect.y() * scale_y)
        w = int(self.norm_rect.width() * scale_x)
        h = int(self.norm_rect.height() * scale_y)
        return QRect(x, y, w, h)
    
    def contains(self, point: QPoint, scale_x: float, scale_y: float, original_width: int, original_height: int) -> bool:
        """检查点是否在缩放后的文字块内（扩大检测范围）"""
        rect = self.get_scaled_rect(scale_x, scale_y, original_width, original_height)
        # 扩大检测范围：上下左右各扩展5像素，提高点击容错率
        expanded_rect = rect.adjusted(-5, -5, 5, 5)
        return expanded_rect.contains(point)


class OCRTextLayer(QWidget):
    """OCR 可交互文字层（完全透明，Word 风格文字选择）"""
    
    def __init__(self, parent=None, original_width: int = 100, original_height: int = 100):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 默认透传鼠标，仅在文字区域/选择时拦截
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._event_filter_target = None
        parent_widget = parent if isinstance(parent, QWidget) else None
        if parent_widget:
            parent_widget.installEventFilter(self)
            self._event_filter_target = parent_widget
            try:
                parent_widget.destroyed.connect(self._detach_event_filter)
            except Exception:
                pass
        
        # 原始图像尺寸
        self.original_width = original_width
        self.original_height = original_height
        
        self.text_items: List[OCRTextItem] = []
        self.enabled = True  # 外部启用标志
        self.drawing_mode = False  # 绘图工具是否开启
        
        # Word 风格选择
        self.selection_start: Optional[Tuple[int, int]] = None  # (item_index, char_index)
        self.selection_end: Optional[Tuple[int, int]] = None    # (item_index, char_index)
        self.is_selecting = False
        
        # 双击检测
        self.last_click_time = 0
        self.last_click_pos: Optional[QPoint] = None
        
        # 当前鼠标是否在文字上
        self._mouse_on_text = False
        
        # 动态检查绘图状态的回调函数 (返回 True 表示正在绘图)
        self.is_drawing_callback = None

    def _detach_event_filter(self):
        target = getattr(self, '_event_filter_target', None)
        if target:
            try:
                target.removeEventFilter(self)
            except Exception:
                pass
        self._event_filter_target = None

    def event(self, event):
        # PyQt5中使用QEvent.Type枚举值68表示Destroy事件
        if event.type() == 68:  # QEvent.Destroy
            self._detach_event_filter()
        return super().event(event)

    def _is_active(self) -> bool:
        """是否可用：外部启用且未处于绘图模式"""
        # 优先检查动态回调
        is_drawing = False
        if self.is_drawing_callback:
            try:
                is_drawing = self.is_drawing_callback()
            except Exception:
                pass
        
        # 如果检测到进入绘图模式，清除选择
        if is_drawing and (self.selection_start or self.selection_end):
            self.clear_selection()
                
        return self.enabled and not self.drawing_mode and not is_drawing

    def set_drawing_mode(self, active: bool):
        """设置绘图模式开关，开启时屏蔽文字层交互"""
        self.drawing_mode = bool(active)
        self._apply_effective_enabled()

    def set_draw_tool_active(self, active: bool):
        """供工具栏按钮调用：按钮按下(True)/抬起(False) 即切换文字层。
        注意：这里代表工具处于“绘制工具被选中”的状态，而非实际开始绘制过程。
        """
        self.set_drawing_mode(active)

    def _apply_effective_enabled(self):
        """应用有效的启用状态：只有在启用且有文字块时才显示"""
        if not self._is_active():
            # 禁用时清除选择并透传
            self.clear_selection()
            self.setCursor(Qt.ArrowCursor)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.hide()
        else:
            # 启用时：检查是否有文字块
            if not self.text_items:
                self.hide()
                return
                
            # 有文字块时显示并配置
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.recalculate_char_positions()
            self.raise_()  # 提升到最上层
            self.show()
            
            # 确保事件过滤器已安装
            parent_widget = self.parentWidget()
            if parent_widget and self._event_filter_target != parent_widget:
                if self._event_filter_target:
                    self._event_filter_target.removeEventFilter(self)
                parent_widget.installEventFilter(self)
                self._event_filter_target = parent_widget

    def recalculate_char_positions(self):
        """根据当前尺寸重新计算所有文字块的字符位置，避免缩放后命中范围偏差"""
        if not self.text_items:
            return
        scale_x, scale_y = self.get_scale_factors()
        for item in self.text_items:
            rect = item.get_scaled_rect(scale_x, scale_y, self.original_width, self.original_height)
            item.calculate_char_positions(rect)

    def _is_pos_on_text(self, pos: QPoint) -> bool:
        """给定本地坐标，判断是否在文字块扩展范围内"""
        scale_x, scale_y = self.get_scale_factors()
        for item in self.text_items:
            if item.contains(pos, scale_x, scale_y, self.original_width, self.original_height):
                return True
        return False

    def _sort_items_by_position(self):
        """按 y 再 x 排序，保持与显示一致的顺序，便于跨行选择"""
        if not self.text_items:
            return
        self.text_items.sort(key=lambda it: (it.norm_rect.y(), it.norm_rect.x()))
    
    def set_enabled(self, enabled: bool):
        """设置是否启用（绘画模式时设置为 False）"""
        self.enabled = enabled
        self._apply_effective_enabled()
    
    def load_ocr_result(self, ocr_result: Dict, original_width: int, original_height: int):
        """
        加载 OCR 识别结果
        
        Args:
            ocr_result: OCR 返回的字典格式结果
            original_width: 原始图像宽度
            original_height: 原始图像高度
        """
        self.text_items.clear()
        self.original_width = original_width
        self.original_height = original_height
        
        if ocr_result.get('code') != 100:
            return
        
        data = ocr_result.get('data', [])
        if not data:
            return
        
        for item in data:
            text = item.get('text', '')
            box = item.get('box', [])
            score = item.get('score', 0.0)
            
            # 明确检查 text 和 box 是否有效（避免 numpy 数组的真值判断问题）
            if text and box is not None and len(box) > 0:
                self.text_items.append(OCRTextItem(text, box, score))

        # 按行自上而下排序，确保多行选择顺序正确
        self._sort_items_by_position()
        
        # 预计算字符位置
        self.recalculate_char_positions()
        
        print(f"✅ [OCR文字层] 钉图加载了 {len(self.text_items)} 个文字块")
        
        # 加载完成后，如果已启用则显示文字层
        if self.enabled:
            self._apply_effective_enabled()
    
    def get_scale_factors(self) -> tuple:
        """获取当前缩放比例"""
        if self.original_width == 0 or self.original_height == 0:
            return 1.0, 1.0
        
        scale_x = self.width() / self.original_width
        scale_y = self.height() / self.original_height
        return scale_x, scale_y

    def resizeEvent(self, event):
        """窗口尺寸变化时重新计算字符位置，确保悬停和选择命中准确"""
        super().resizeEvent(event)
        self.recalculate_char_positions()
    
    def paintEvent(self, event):
        """绘制文字层（Word 风格的文字选择高亮）"""
        # 如果不活跃（绘图模式或被禁用），不绘制选中状态
        if not self._is_active() or not self.text_items:
            return
        
        if not self.selection_start or not self.selection_end:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        scale_x, scale_y = self.get_scale_factors()
        
        # 标准化选择范围（确保 start <= end）
        start_item, start_char = self.selection_start
        end_item, end_char = self.selection_end
        
        if start_item > end_item or (start_item == end_item and start_char > end_char):
            start_item, end_item = end_item, start_item
            start_char, end_char = end_char, start_char
        
        # 绘制选中的文字范围（Windows 蓝色高亮）
        for item_idx in range(start_item, end_item + 1):
            if item_idx >= len(self.text_items):
                break
            
            item = self.text_items[item_idx]
            rect = item.get_scaled_rect(scale_x, scale_y, self.original_width, self.original_height)
            
            if not item.char_positions:
                item.calculate_char_positions(rect)
            
            # 确定当前文字块的选择范围
            if item_idx == start_item and item_idx == end_item:
                # 同一个文字块
                char_start = start_char
                char_end = end_char
            elif item_idx == start_item:
                # 起始文字块
                char_start = start_char
                char_end = len(item.text)
            elif item_idx == end_item:
                # 结束文字块
                char_start = 0
                char_end = end_char
            else:
                # 中间的文字块，全选
                char_start = 0
                char_end = len(item.text)
            
            # 绘制选中区域
            if char_start < len(item.char_positions) and char_end < len(item.char_positions):
                x_start = item.char_positions[char_start]
                x_end = item.char_positions[char_end]
                
                highlight_rect = QRect(
                    x_start, rect.y(),
                    x_end - x_start, rect.height()
                )
                
                # Windows 文本选择样式：蓝色背景
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(0, 120, 215, 100)))
                painter.drawRect(highlight_rect)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 只在文字上才拦截"""
        if not self._is_active():
            # 如果不活跃（例如进入绘图模式），停止当前选择
            if self.is_selecting:
                self.is_selecting = False
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.setCursor(Qt.ArrowCursor)
            return
        
        pos = event.pos()
        
        # 拖拽选择模式
        if self.is_selecting:
            # 更新选择终点
            item_idx, char_idx = self._get_char_at_pos(pos)
            if item_idx is not None:
                self.selection_end = (item_idx, char_idx)
                self.update()
            return
        
        on_text = self._is_pos_on_text(pos)
        
        # 动态切换鼠标事件透传模式
        if on_text:
            # 在文字上：拦截鼠标事件，显示文本光标
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            self.setCursor(Qt.IBeamCursor)
            self._mouse_on_text = True
        else:
            # 不在文字上：透传鼠标事件给父窗口
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.setCursor(Qt.ArrowCursor)
            self._mouse_on_text = False
            event.ignore()

    def eventFilter(self, obj, event):
        """全局事件过滤：在透传模式下跟踪鼠标，只有文字/选择时拦截，空白允许拖动"""
        if not self._is_active():
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.setCursor(Qt.ArrowCursor)
            return False

        et = event.type()
        if et in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            # 将父窗口的事件坐标转换为本地坐标
            if hasattr(event, 'pos'):
                global_pos = obj.mapToGlobal(event.pos())
                local_pos = self.mapFromGlobal(global_pos)
            else:
                return False

            on_text = self._is_pos_on_text(local_pos)

            # 拖拽选择过程中始终拦截
            if self.is_selecting:
                self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
                return False  # 让文字层自己的鼠标事件处理

            if et == QEvent.MouseMove:
                if on_text:
                    self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
                    self.setCursor(Qt.IBeamCursor)
                else:
                    self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                    self.setCursor(Qt.ArrowCursor)

            elif et == QEvent.MouseButtonPress:
                if on_text:
                    # 让按下事件进入文字层用于选择
                    self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
                else:
                    # 空白：直接透传；如果有选区，提前清空
                    if self.selection_start or self.selection_end:
                        self.clear_selection()
                    self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            elif et == QEvent.MouseButtonRelease:
                if not self.is_selecting and not on_text:
                    self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        return False  # 不拦截事件，让它继续传递
    
    def mousePressEvent(self, event):
        """鼠标按下事件 - Word 风格点击设置光标"""
        if not self._is_active() or event.button() != Qt.LeftButton:
            # 透传给父窗口
            event.ignore()
            return
        
        pos = event.pos()
        self.setFocus()
        
        # 获取点击位置的字符
        item_idx, char_idx = self._get_char_at_pos(pos)
        
        if item_idx is not None:
            # 点击在文字上
            event.accept()
            
            # 检测双击
            import time
            current_time = time.time()
            is_double_click = False
            
            if self.last_click_pos and self.last_click_time:
                time_diff = current_time - self.last_click_time
                pos_diff = (pos - self.last_click_pos).manhattanLength()
                
                # 双击条件：500ms 内，距离小于 5 像素
                if time_diff < 0.5 and pos_diff < 5:
                    is_double_click = True
            
            self.last_click_time = current_time
            self.last_click_pos = pos
            
            if is_double_click:
                # 双击：选择整个文字块
                self._select_word(item_idx)
            else:
                # 单击：设置光标位置并开始选择
                self.selection_start = (item_idx, char_idx)
                self.selection_end = (item_idx, char_idx)
                self.is_selecting = True
            
            self.update()
        else:
            # 点击空白处：清除选择并透传给父窗口
            if self.selection_start or self.selection_end:
                # 有选择时，第一次点击空白清除选择
                self.clear_selection()
                # 让事件继续传递给父窗口用于拖动
                self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                event.ignore()
            else:
                # 没有选择时，透传给父窗口（允许拖动钉图）
                self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                event.ignore()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if not self._is_active() or event.button() != Qt.LeftButton:
            event.ignore()
            return
        
        if self.is_selecting:
            self.is_selecting = False
            self._copy_selected_text()
            event.accept()
        else:
            # 透传给父窗口
            event.ignore()
        # 释放后回到透传，避免阻塞其他操作
        if not self.is_selecting:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    
    def _get_char_at_pos(self, pos: QPoint) -> Tuple[Optional[int], Optional[int]]:
        """获取指定位置的字符索引，支持跨行拖拽：
        1) 命中文字块：返回该块的字符索引
        2) 不命中时：选取垂直距离最近的文字块，并计算对应字符位置
        """
        scale_x, scale_y = self.get_scale_factors()

        nearest_idx = None
        nearest_dy = None
        nearest_rect = None

        for item_idx, item in enumerate(self.text_items):
            rect = item.get_scaled_rect(scale_x, scale_y, self.original_width, self.original_height)

            # 使用扩展的检测范围
            expanded_rect = rect.adjusted(-5, -5, 5, 5)

            # 计算最近行
            dy = abs(pos.y() - rect.center().y())
            if nearest_dy is None or dy < nearest_dy:
                nearest_dy = dy
                nearest_idx = item_idx
                nearest_rect = rect

            if expanded_rect.contains(pos):
                if not item.char_positions:
                    item.calculate_char_positions(rect)
                char_idx = item.get_char_index_at_pos(pos.x(), rect)
                return (item_idx, char_idx)

        # 未命中任何块时，选择最近行
        if nearest_idx is not None and nearest_rect is not None:
            item = self.text_items[nearest_idx]
            if not item.char_positions:
                item.calculate_char_positions(nearest_rect)

            # x 超出时也要选择：左侧=开头，右侧=末尾
            char_idx = item.get_char_index_at_pos(pos.x(), nearest_rect)
            return (nearest_idx, char_idx)

        return (None, None)
    
    def _select_word(self, item_idx: int):
        """选择整个文字块（双击时）"""
        if item_idx >= len(self.text_items):
            return
        
        item = self.text_items[item_idx]
        self.selection_start = (item_idx, 0)
        self.selection_end = (item_idx, len(item.text))
        self.is_selecting = False
        
        # 立即复制
        self._copy_selected_text()
        print(f"📝 [OCR文字层] 双击选择整个文字块: {item.text}")
    
    def _copy_selected_text(self):
        """复制选中的文字到剪贴板（Word 风格）"""
        if not self.selection_start or not self.selection_end:
            return
        
        # 标准化选择范围
        start_item, start_char = self.selection_start
        end_item, end_char = self.selection_end
        
        if start_item > end_item or (start_item == end_item and start_char > end_char):
            start_item, end_item = end_item, start_item
            start_char, end_char = end_char, start_char
        
        # 提取选中的文字
        selected_text_parts = []
        
        for item_idx in range(start_item, end_item + 1):
            if item_idx >= len(self.text_items):
                break
            
            item = self.text_items[item_idx]
            
            # 确定当前文字块的选择范围
            if item_idx == start_item and item_idx == end_item:
                # 同一个文字块
                selected_text_parts.append(item.text[start_char:end_char])
            elif item_idx == start_item:
                # 起始文字块
                selected_text_parts.append(item.text[start_char:])
            elif item_idx == end_item:
                # 结束文字块
                selected_text_parts.append(item.text[:end_char])
            else:
                # 中间的文字块，全选
                selected_text_parts.append(item.text)
        
        selected_text = ''.join(selected_text_parts)
        
        if selected_text:
            # 复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setText(selected_text)
            print(f"📋 [OCR文字层] 已复制: {selected_text[:50]}{'...' if len(selected_text) > 50 else ''}")
    
    def clear_selection(self):
        """清除选择"""
        self.selection_start = None
        self.selection_end = None
        self.is_selecting = False
        self.update()
    
    def keyPressEvent(self, event):
        """键盘事件"""
        if not self._is_active():
            return
        
        # Ctrl+C: 复制
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_C:
            self._copy_selected_text()
        # Ctrl+A: 全选所有文字
        elif event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_A:
            if self.text_items:
                self.selection_start = (0, 0)
                self.selection_end = (len(self.text_items) - 1, len(self.text_items[-1].text))
                self.update()
                print("📝 [OCR文字层] 全选所有文字")
        # Escape: 清除选择
        elif event.key() == Qt.Key_Escape:
            # 始终放行 ESC，让钉图窗口接管（用于关闭）
            event.ignore()
            return
        else:
            super().keyPressEvent(event)

