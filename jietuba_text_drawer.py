"""
jietuba_text_drawer.py - 统一文字绘制组件模块

提供截图窗口和钉图窗口通用的文字绘制功能,
实现文字工具的统一处理逻辑。

主要功能:
- 文字绘制到 pixmap
- 实时文字预览渲染
- 支持多行文字输入
- 自动换行和文字框调整

主要类:
- UnifiedTextDrawer: 统一文字绘制器类

特点:
- 统一的文字绘制接口
- 支持实时预览(不修改底层 pixmap)
- 支持提交绘制(写入 pixmap)
- 自适应文字大小和颜色

依赖模块:
- PyQt5: GUI框架和绘图功能

使用方法:
    # 实时预览
    UnifiedTextDrawer.render_live_preview(painter, parent, text_box)
    
    # 提交绘制
    UnifiedTextDrawer.process_text_drawing(parent, painter, text_box)
"""

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import math
from collections import deque


class UnifiedTextDrawer:from collections import deque


class UnifiedTextDrawer:
    """统一的文字绘制器，提供通用的文字绘制功能"""
    
    def __init__(self):
        pass
    
    @staticmethod
    def draw_text_to_pixmap(pixmap, text, pos, font_size, color, document_size=None):
        """
        在pixmap上绘制文字
        
        Args:
            pixmap: 目标QPixmap
            text: 要绘制的文字
            pos: 绘制位置 (x, y)
            font_size: 字体大小
            color: 字体颜色
            document_size: 文字框的文档大小，用于位置调整
        
        Returns:
            bool: 绘制是否成功
        """
        if not pixmap or pixmap.isNull() or not text or not text.strip():
            return False
            
        try:
            painter = QPainter(pixmap)
            painter.setFont(QFont('', font_size))
            painter.setPen(QPen(color, 3, Qt.SolidLine))
            
            # 处理多行文字
            lines = text.split('\n')
            line_height = font_size * 2.0  # 行高 = 字体大小 * 2倍
            
            # 计算基础位置（与原始实现保持一致）
            if document_size:
                base_x = pos[0] + document_size.height() / 8 - 3
                base_y = pos[1] + document_size.height() * 32 / 41 - 2
            else:
                base_x = pos[0]
                base_y = pos[1]
            
            # 绘制每一行
            for i, line in enumerate(lines):
                if line.strip():  # 只绘制非空行
                    final_x = base_x
                    final_y = base_y + i * line_height
                    painter.drawText(final_x, final_y, line)
            
            painter.end()
            return True
            
        except Exception as e:
            print(f"统一文字绘制器错误: {e}")
            return False
    
    @staticmethod
    def process_text_drawing(parent, pixmap_painter, text_box):
        """
        处理文字绘制流程（统一截图窗口和钉图窗口的逻辑）
        
        Args:
            parent: 父窗口对象
            pixmap_painter: 用于绘制的QPainter对象
            text_box: 文字输入框对象
        
        Returns:
            bool: 是否成功绘制了文字
        """
        try:
            # 检查输入参数的有效性
            if not pixmap_painter:
                print("统一文字绘制: pixmap_painter为空")
                return False
                
            if not pixmap_painter.isActive():
                print("统一文字绘制: pixmap_painter未激活")
                return False
            
            # 检查是否需要绘制文字
            if not (hasattr(parent, 'text_box') and text_box.paint) and \
               not (hasattr(parent, 'drawtext_pointlist') and 
                    len(parent.drawtext_pointlist) > 0 and 
                    getattr(text_box, 'paint', False)):
                return False
            
            # 进入文本绘制流程
            text_box.paint = False
            text = text_box.toPlainText()
            pos = None
            
            if len(parent.drawtext_pointlist) > 0:
                # 仅在有有效文字时再弹出坐标，避免丢失
                pos = parent.drawtext_pointlist[0]
            
            if text and text.strip() and pos is not None:
                # 弹出使用的坐标点
                parent.drawtext_pointlist.pop(0)
                
                # 设置字体与画笔
                try:
                    pixmap_painter.setFont(QFont('', parent.tool_width))
                    pixmap_painter.setPen(QPen(parent.pencolor, 3, Qt.SolidLine))
                except Exception as font_error:
                    print(f"统一文字绘制: 设置字体时出错: {font_error}")
                    return False
                
                # 多行处理
                lines = text.split('\n')
                line_height = parent.tool_width * 2.0
                # 使用锚定基准，避免随 document.height() 变化导致首行跳动
                if not hasattr(text_box, '_anchor_base'):  # 兼容旧状态
                    h = text_box.document.size().height()
                    text_box._anchor_base = (
                        pos[0] + h / 8 - 3,
                        pos[1] + h * 32 / 41 - 2
                    )
                base_x, base_y = text_box._anchor_base
                
                # 计算文字区域边界
                max_line_width = 0
                total_height = len(lines) * line_height
                
                # 估算每行的宽度（简单估算）
                for line in lines:
                    if line.strip():
                        estimated_width = len(line) * parent.tool_width * 0.6  # 粗略估算
                        max_line_width = max(max_line_width, estimated_width)
                
                # 创建文字区域矩形
                text_rect = QRect(int(base_x), int(base_y - parent.tool_width), 
                                int(max_line_width), int(total_height))
                
                # 绘制文字
                try:
                    for i, line in enumerate(lines):
                        if line.strip():
                            pixmap_painter.drawText(base_x, base_y + i * line_height, line)
                except Exception as draw_error:
                    print(f"统一文字绘制: 绘制文字时出错: {draw_error}")
                    return False
                
                # 注意：不在这里结束painter，让调用方处理painter的生命周期
                # 这样可以避免 "QPaintDevice: Cannot destroy paint device that is being painted" 错误
                
                # 创建撤销备份 - 特殊处理钉图窗口
                if hasattr(parent, 'backup_shortshot'):
                    try:
                        # 检查是否在钉图窗口环境中
                        is_pinned_window = False
                        pinned_window = None
                        
                        # 优先检查parent是否直接在钉图模式下
                        if hasattr(parent, 'mode') and parent.mode == "pinned" and hasattr(parent, 'current_pinned_window'):
                            pinned_window = parent.current_pinned_window
                            is_pinned_window = True
                            print(f"🎨 文字撤销调试: 通过mode属性检测到钉图模式")
                        else:
                            # 回退到原有的检查逻辑
                            # 检查parent是否有freeze_imgs属性且有钉图窗口
                            if hasattr(parent, 'parent') and hasattr(parent.parent, 'freeze_imgs'):
                                freeze_imgs_list = parent.parent.freeze_imgs
                                if freeze_imgs_list:
                                    for freeze_window in freeze_imgs_list:
                                        if hasattr(freeze_window, 'paintlayer'):
                                            pinned_window = freeze_window
                                            is_pinned_window = True
                                            break
                            elif hasattr(parent, 'freeze_imgs'):
                                freeze_imgs_list = parent.freeze_imgs
                                if freeze_imgs_list:
                                    for freeze_window in freeze_imgs_list:
                                        if hasattr(freeze_window, 'paintlayer'):
                                            pinned_window = freeze_window
                                            is_pinned_window = True
                                            break
                        
                        if is_pinned_window and pinned_window:
                            # 钉图窗口：确保备份系统已初始化，然后先合并图层，再备份
                            print(f"🎨 文字撤销调试: 钉图窗口文字绘制完成，调用图层合并和备份")
                            
                            # 确保钉图窗口备份系统已初始化
                            if not hasattr(pinned_window, 'backup_pic_list') or not pinned_window.backup_pic_list:
                                print(f"🎨 文字撤销调试: 钉图窗口备份系统未初始化，进行初始化")
                                # 这种情况不应该发生，因为copy_screenshot_backup_history应该已经初始化了
                                # 但如果确实发生了，我们需要确保有正确的初始状态
                                pinned_window.backup_pic_list = [pinned_window.showing_imgpix.copy()]
                                pinned_window.backup_ssid = 0
                                if not hasattr(pinned_window, '_original_backup_list'):
                                    pinned_window._original_backup_list = [pinned_window.showing_imgpix.copy()]
                                print(f"🎨 文字撤销调试: 应急初始化完成，backup_ssid={pinned_window.backup_ssid}")
                            
                            # 检查当前备份状态
                            print(f"🎨 文字撤销调试: 绘制前状态 - backup_ssid={pinned_window.backup_ssid}, 列表长度={len(pinned_window.backup_pic_list)}")
                            
                            pinned_window._merge_paint_to_base()  # 合并绘画层到底图
                            pinned_window.backup_shortshot()      # 备份钉图窗口状态
                            
                            # 检查备份后状态
                            print(f"🎨 文字撤销调试: 绘制后状态 - backup_ssid={pinned_window.backup_ssid}, 列表长度={len(pinned_window.backup_pic_list)}")
                        else:
                            # 普通截图窗口：直接备份
                            parent.backup_shortshot()
                        
                        print(f"统一文字绘制: 绘制文字'{text.strip()}'完成，进行备份")
                    except Exception as backup_error:
                        print(f"统一文字绘制: 备份时出错: {backup_error}")
                
                # 清空输入框内容，避免下一次新建输入框出现上一次文本
                try:
                    text_box.clear()
                    # 清除锚点信息，确保下次新建输入框时重新计算位置
                    if hasattr(text_box, '_anchor_base'):
                        delattr(text_box, '_anchor_base')
                except Exception:
                    pass
                
                # 还原焦点
                if hasattr(parent, 'setFocus'):
                    try:
                        parent.setFocus()
                    except Exception:
                        pass
                
                return True
            else:
                # 空文本：清理坐标点和输入框状态，因为没有内容需要绘制
                print("统一文字绘制: 无文字内容或仅空白，清理坐标点和输入框状态")
                
                # 清理对应的坐标点，因为这个点不会被使用
                if len(parent.drawtext_pointlist) > 0:
                    unused_coord = parent.drawtext_pointlist.pop(0)
                    print(f"统一文字绘制: 清理未使用的坐标点: {unused_coord}")
                
                text_box.clear()
                # 清除锚点信息，确保下次新建输入框时重新计算位置
                if hasattr(text_box, '_anchor_base'):
                    delattr(text_box, '_anchor_base')
                return False
                
        except Exception as e:
            print(f"统一文字绘制流程错误: {e}")
            return False

    # ===================== 实时预览支持 =====================
    @staticmethod
    def render_live_preview(target_widget, parent, text_box):
        """在目标widget上实时绘制正在输入的文字预览(不落盘、不修改pointlist)。

        Args:
            target_widget: QWidget (通常是绘制图层: paintlayer / PinnedPaintLayer)
            parent: 主窗口对象(含颜色/字号/坐标列表)
            text_box: 当前文字输入框
        """
        try:
            if (not hasattr(parent, 'drawtext_pointlist') or
                len(parent.drawtext_pointlist) == 0 or
                not hasattr(parent, 'text_box') or
                not text_box.isVisible() or
                getattr(text_box, 'paint', False)):  # 已进入提交阶段不再预览
                return

            text = text_box.toPlainText()
            # 允许空文本：仍显示插入符，避免用户感觉“无反应”

            pos = parent.drawtext_pointlist[0]  # 仅取坐标，不弹出
            painter = QPainter(target_widget)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 创建字体并设置给painter
            font = QFont('', parent.tool_width)
            painter.setFont(font)
            painter.setPen(QPen(parent.pencolor, 3, Qt.SolidLine))
            
            # 创建字体度量对象用于精确测量文字宽度（使用相同的字体）
            font_metrics = QFontMetrics(font)

            lines = text.split('\n')
            line_height = parent.tool_width * 2.0
            # 初始化锚定基准（只在首次或 anchor 缺失时计算一次）
            if not hasattr(text_box, '_anchor_base'):
                h = text_box.document.size().height()
                text_box._anchor_base = (
                    pos[0] + h / 8 - 3,
                    pos[1] + h * 32 / 41 - 2
                )
            base_x, base_y = text_box._anchor_base

            # 获取文字输入框的实际光标位置
            cursor_position = text_box.textCursor().position()
            
            # 计算光标所在的行和列
            text_before_cursor = text[:cursor_position] if cursor_position <= len(text) else text
            lines_before_cursor = text_before_cursor.split('\n')
            cursor_line = len(lines_before_cursor) - 1
            cursor_column = len(lines_before_cursor[-1]) if lines_before_cursor else 0
            
            # 绘制文字并记录光标位置
            cursor_x = base_x
            cursor_y = base_y
            
            for i, line in enumerate(lines):
                y = base_y + i * line_height
                if line.strip():
                    painter.drawText(base_x, y, line)
                
                # 如果这是光标所在的行，使用精确的文字宽度计算光标位置
                if i == cursor_line:
                    # 计算光标前的文字部分的实际宽度
                    text_before_cursor_in_line = line[:cursor_column] if cursor_column <= len(line) else line
                    # 使用兼容的宽度测量方法
                    try:
                        # PyQt5 5.11+ 支持 horizontalAdvance
                        text_width = font_metrics.horizontalAdvance(text_before_cursor_in_line)
                    except AttributeError:
                        # 较老版本使用 width 方法
                        text_width = font_metrics.width(text_before_cursor_in_line)
                    cursor_x = base_x + text_width
                    cursor_y = y

            # 绘制插入符（光标），需要 text_box 维护 _cursor_visible
            if hasattr(text_box, '_cursor_visible') and text_box._cursor_visible:
                cursor_height = parent.tool_width * 1.8
                painter.setPen(QPen(parent.pencolor, max(1, parent.tool_width//6)))
                painter.drawLine(int(cursor_x+2), int(cursor_y - cursor_height*0.8),
                                  int(cursor_x+2), int(cursor_y + cursor_height*0.2))

            painter.end()
        except Exception as e:
            print(f"实时文字预览错误: {e}")

# 设计说明:
# 1. 实时预览与最终提交使用完全相同的坐标/行高/字体/颜色计算，保证所见即所得。
# 2. 预览阶段不弹出 drawtext_pointlist 中的坐标点；提交阶段在 process_text_drawing 中才真正 pop。
# 3. text_box.paint == True 视为提交状态：
#       - process_text_drawing 负责: 从 pointlist 取点 -> 绘制到底层 pixmap -> 备份 -> 清理输入框
#       - render_live_preview 只在 paint == False 且有文字且点存在时执行。
# 4. 多窗口适配：截图主窗口 paintlayer 与 钉图窗口 PinnedPaintLayer 均调用 render_live_preview。
# 5. 安全性：预览绘制使用前景 QPainter(target_widget)，不会破坏底层像素图，可随文本动态刷新。
