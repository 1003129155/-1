"""
jietuba_drawing.py - 统一绘画模块

整合所有绘画相关功能，包括：
- 文字绘制（截图窗口和钉图窗口通用）
- 绘画层（画笔、箭头、矩形、圆形等）
- 遮罩层（选区边框、放大镜）

主要类:
- UnifiedTextDrawer: 统一文字绘制器类
- MaskLayer: 遮罩层，显示截图选区、手柄、放大镜等
- PaintLayer: 绘画层，处理所有绘图操作

主要功能函数:
- get_line_interpolation: 笔迹插值函数，平滑绘制

依赖模块:
- PyQt5: GUI框架和绘图功能
"""

import math
from PyQt5.QtCore import Qt, QRect, QRectF, QPoint
from PyQt5.QtGui import (QPainter, QPen, QColor, QBrush, QPixmap, QFont, 
                         QPolygon, QFontMetrics)
from PyQt5.QtWidgets import QLabel


# ============================================================================
#  工具函数
# ============================================================================

def get_line_interpolation(p1, p0):
    """为两点之间生成插值点，平滑笔迹"""
    if not p1 or not p0:
        return None
    x0, y0 = p0[:2]
    x1, y1 = p1[:2]
    dx = x1 - x0
    dy = y1 - y0
    distance = max(abs(dx), abs(dy))
    if distance <= 1:
        return None
    steps = int(distance)
    if steps <= 1:
        return None
    interpolated = []
    for step in range(1, steps):
        t = step / float(steps)
        interpolated.append([
            int(round(x0 + dx * t)),
            int(round(y0 + dy * t)),
        ])
    return interpolated


# ============================================================================
#  文字绘制器类
# ============================================================================

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
            # 允许空文本：仍显示插入符，避免用户感觉"无反应"

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


# ============================================================================
#  遮罩层类
# ============================================================================

class MaskLayer(QLabel):
    """遮罩层 - 显示截图选区、手柄、放大镜等"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.parent.on_init:
            print('oninit return')
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 正常显示选区
        rect = QRect(min(self.parent.x0, self.parent.x1), min(self.parent.y0, self.parent.y1),
                     abs(self.parent.x1 - self.parent.x0), abs(self.parent.y1 - self.parent.y0))

        painter.setPen(QPen(QColor(64, 224, 208), 2, Qt.SolidLine))
        painter.drawRect(rect)
        painter.drawRect(0, 0, self.width(), self.height())
        painter.setPen(QPen(QColor(48, 200, 192), 8, Qt.SolidLine))
        painter.drawPoint(
            QPoint(self.parent.x0, min(self.parent.y1, self.parent.y0) + abs(self.parent.y1 - self.parent.y0) // 2))
        painter.drawPoint(
            QPoint(min(self.parent.x1, self.parent.x0) + abs(self.parent.x1 - self.parent.x0) // 2, self.parent.y0))
        painter.drawPoint(
            QPoint(self.parent.x1, min(self.parent.y1, self.parent.y0) + abs(self.parent.y1 - self.parent.y0) // 2))
        painter.drawPoint(
            QPoint(min(self.parent.x1, self.parent.x0) + abs(self.parent.x1 - self.parent.x0) // 2, self.parent.y1))
        painter.drawPoint(QPoint(self.parent.x0, self.parent.y0))
        painter.drawPoint(QPoint(self.parent.x0, self.parent.y1))
        painter.drawPoint(QPoint(self.parent.x1, self.parent.y0))
        painter.drawPoint(QPoint(self.parent.x1, self.parent.y1))

        x = y = 100
        if self.parent.x1 > self.parent.x0:
            x = self.parent.x0 + 5
        else:
            x = self.parent.x0 - 72
        if self.parent.y1 > self.parent.y0:
            y = self.parent.y0 + 15
        else:
            y = self.parent.y0 - 5
        painter.setPen(QPen(QColor(32, 178, 170), 2, Qt.SolidLine))
        painter.drawText(x, y,
                         '{}x{}'.format(abs(self.parent.x1 - self.parent.x0), abs(self.parent.y1 - self.parent.y0)))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawRect(0, 0, self.width(), min(self.parent.y1, self.parent.y0))
        painter.drawRect(0, min(self.parent.y1, self.parent.y0), min(self.parent.x1, self.parent.x0),
                         self.height() - min(self.parent.y1, self.parent.y0))
        painter.drawRect(max(self.parent.x1, self.parent.x0), min(self.parent.y1, self.parent.y0),
                         self.width() - max(self.parent.x1, self.parent.x0),
                         self.height() - min(self.parent.y1, self.parent.y0))
        painter.drawRect(min(self.parent.x1, self.parent.x0), max(self.parent.y1, self.parent.y0),
                         max(self.parent.x1, self.parent.x0) - min(self.parent.x1, self.parent.x0),
                         self.height() - max(self.parent.y1, self.parent.y0))
        
        # 以下为鼠标放大镜
        if not (self.parent.painter_tools['drawcircle_on'] or
                self.parent.painter_tools['drawrect_bs_on'] or
                self.parent.painter_tools['drawarrow_on'] or
                self.parent.painter_tools['pen_on'] or
                self.parent.painter_tools['highlight_on'] or
                self.parent.painter_tools['drawtext_on'] or
                self.parent.move_rect):

            # 鼠标放大镜功能
            if self.parent.mouse_posx > self.width() - 140:
                enlarge_box_x = self.parent.mouse_posx - 140
            else:
                enlarge_box_x = self.parent.mouse_posx + 20
            if self.parent.mouse_posy > self.height() - 140:
                enlarge_box_y = self.parent.mouse_posy - 120
            else:
                enlarge_box_y = self.parent.mouse_posy + 20
            enlarge_rect = QRect(enlarge_box_x, enlarge_box_y, 120, 120)
            painter.setPen(QPen(QColor(64, 224, 208), 1, Qt.SolidLine))
            painter.drawRect(enlarge_rect)
            painter.setBrush(QBrush(QColor(80, 80, 80, 180)))
            painter.drawRect(QRect(enlarge_box_x, enlarge_box_y - 60, 160, 60))
            painter.setBrush(Qt.NoBrush)

            # 安全获取像素颜色
            color = QColor(255, 255, 255)
            mouse_x = self.parent.mouse_posx
            mouse_y = self.parent.mouse_posy

            if hasattr(self.parent, 'qimg') and self.parent.qimg:
                img = self.parent.qimg
                if 0 <= mouse_x < img.width() and 0 <= mouse_y < img.height():
                    color = QColor(img.pixelColor(mouse_x, mouse_y))
            else:
                pixmap = self.parent.pixmap()
                if pixmap and not pixmap.isNull():
                    img = pixmap.toImage()
                    if 0 <= mouse_x < img.width() and 0 <= mouse_y < img.height():
                        color = QColor(img.pixelColor(mouse_x, mouse_y))

            RGB_color = [color.red(), color.green(), color.blue()]
            # 使用 QColor 的内置方法获取 HSV 值（不需要 cv2）
            h, s, v, _ = color.getHsv()
            HSV_color = [h, s, v]

            painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.SolidLine))
            painter.drawText(enlarge_box_x, enlarge_box_y - 8,
                             ' POS:({},{}) '.format(self.parent.mouse_posx, self.parent.mouse_posy))
            painter.drawText(enlarge_box_x, enlarge_box_y - 24,
                             " HSV:({},{},{})".format(HSV_color[0], HSV_color[1], HSV_color[2]))
            painter.drawText(enlarge_box_x, enlarge_box_y - 40,
                             " RGB:({},{},{})".format(RGB_color[0], RGB_color[1], RGB_color[2]))

            try:
                painter.setCompositionMode(QPainter.CompositionMode_Source)
                rpix = QPixmap(self.width() + 120, self.height() + 120)
                rpix.fill(QColor(0, 0, 0))
                rpixpainter = QPainter(rpix)
                rpixpainter.drawPixmap(60, 60, self.parent.pixmap())
                rpixpainter.end()
                larger_pix = rpix.copy(self.parent.mouse_posx, self.parent.mouse_posy, 120, 120).scaled(
                    120 + self.parent.tool_width * 10, 120 + self.parent.tool_width * 10)
                pix = larger_pix.copy(larger_pix.width() // 2 - 60, larger_pix.height() // 2 - 60, 120, 120)
                painter.drawPixmap(enlarge_box_x, enlarge_box_y, pix)
                painter.setPen(QPen(QColor(64, 224, 208), 1, Qt.SolidLine))
                painter.drawLine(enlarge_box_x, enlarge_box_y + 60, enlarge_box_x + 120, enlarge_box_y + 60)
                painter.drawLine(enlarge_box_x + 60, enlarge_box_y, enlarge_box_x + 60, enlarge_box_y + 120)
            except:
                print('draw_enlarge_box fail')

        painter.end()


# ============================================================================
#  绘画层类
# ============================================================================

class PaintLayer(QLabel):
    """绘画层 - 处理所有绘图操作"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.px = self.py = -50
        self.pixPainter = None
        self._pixpainter_started_in_event = False

    def _begin_pix_painter(self):
        """确保 self.pixPainter 指向一个已 begin 的 QPainter"""
        if self.pixPainter and isinstance(self.pixPainter, QPainter):
            try:
                if self.pixPainter.isActive():
                    return True
            except Exception:
                self.pixPainter = None
        pm = self.pixmap()
        if not pm or pm.isNull():
            return False
        self.pixPainter = QPainter()
        if not self.pixPainter.begin(pm):
            self.pixPainter = None
            return False
        self.pixPainter.setRenderHint(QPainter.Antialiasing)
        self._pixpainter_started_in_event = True
        return True

    def _draw_optimized_arrow(self, painter, pointlist, color, width):
        """绘制箭头（尖细尾巴+渐变箭杆+后弯曲箭头）"""
        try:
            start_point = pointlist[0]
            end_point = pointlist[1]
            
            # 计算箭头的方向和长度
            dx = end_point[0] - start_point[0]
            dy = end_point[1] - start_point[1]
            length = math.sqrt(dx * dx + dy * dy)
            
            if length < 5:
                return
            
            # 单位向量和垂直向量
            unit_x = dx / length
            unit_y = dy / length
            perp_x = -unit_y
            perp_y = unit_x
            
            # === 参数设计 ===
            base_width = width
            
            # 箭头三角形参数
            arrow_head_length = min(length * 0.25, max(20, base_width * 4.5))
            arrow_head_width = max(base_width * 1.8, 7)  # 箭头要宽一些
            
            # 箭杆与箭头连接处的宽度（要比箭头窄）
            neck_width = arrow_head_width * 0.85  # 颈部细窄
            
            # === 第一部分：绘制箭杆（从尖细尾巴到颈部） ===
            # 箭杆结束点（箭头颈部位置）
            neck_x = end_point[0] - arrow_head_length * unit_x
            neck_y = end_point[1] - arrow_head_length * unit_y
            
            # 尾巴起点宽度（非常尖细）
            tail_width = base_width * 0.15

            # 箭杆中段宽度（最粗的部分，在70%位置）
            mid_point = 0.7
            mid_x = start_point[0] + dx * mid_point
            mid_y = start_point[1] + dy * mid_point
            mid_width = base_width * 0.9
            
            # 使用多个点绘制平滑渐变的箭杆
            from PyQt5.QtGui import QPainterPath
            from PyQt5.QtCore import QPointF
            
            path = QPainterPath()
            
            # 构建箭杆轮廓（上半部分）
            path.moveTo(QPointF(start_point[0] + perp_x * tail_width / 2,
                               start_point[1] + perp_y * tail_width / 2))
            
            # 添加中间粗的部分
            path.lineTo(QPointF(mid_x + perp_x * mid_width / 2,
                               mid_y + perp_y * mid_width / 2))
            
            # 连接到颈部（变细）
            path.lineTo(QPointF(neck_x + perp_x * neck_width / 2,
                               neck_y + perp_y * neck_width / 2))
            
            # 下半部分（镜像）
            path.lineTo(QPointF(neck_x - perp_x * neck_width / 2,
                               neck_y - perp_y * neck_width / 2))
            
            path.lineTo(QPointF(mid_x - perp_x * mid_width / 2,
                               mid_y - perp_y * mid_width / 2))
            
            path.lineTo(QPointF(start_point[0] - perp_x * tail_width / 2,
                               start_point[1] - perp_y * tail_width / 2))
            
            path.closeSubpath()
            
            # 绘制箭杆
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawPath(path)
            
            # === 第二部分：绘制带后弯曲的箭头三角形 ===
            # 箭头尖端
            tip_x = end_point[0]
            tip_y = end_point[1]
            
            # 箭头底部两翼（宽度大于颈部）
            wing_left_x = neck_x + perp_x * arrow_head_width
            wing_left_y = neck_y + perp_y * arrow_head_width
            
            wing_right_x = neck_x - perp_x * arrow_head_width
            wing_right_y = neck_y - perp_y * arrow_head_width
            
            # 添加后弯曲效果：在箭头底部中心向后凹陷
            # 凹陷点位置（向后退一点）
            notch_depth = arrow_head_length * 0.2  # 凹陷深度
            notch_x = neck_x - unit_x * notch_depth
            notch_y = neck_y - unit_y * notch_depth
            
            # 使用Path绘制带凹陷的箭头
            arrow_path = QPainterPath()
            arrow_path.moveTo(QPointF(tip_x, tip_y))
            arrow_path.lineTo(QPointF(wing_left_x, wing_left_y))
            
            # 绘制后弯曲的底边（使用二次贝塞尔曲线）
            # 控制点在凹陷处
            arrow_path.quadTo(
                QPointF(notch_x, notch_y),  # 控制点（凹陷点）
                QPointF(wing_right_x, wing_right_y)  # 终点
            )
            
            arrow_path.lineTo(QPointF(tip_x, tip_y))
            arrow_path.closeSubpath()
            
            # 绘制箭头
            painter.drawPath(arrow_path)
            
            # 恢复画笔设置
            painter.setBrush(Qt.NoBrush)
            
        except Exception as e:
            print(f"绘制优化箭头错误: {e}")

    def paintEvent(self, e):
        super().paintEvent(e)
        
        # 检查父窗口是否正在关闭
        if not self.parent or getattr(self.parent, 'closed', False):
            return
            
        if self.parent.on_init:
            print('oninit return')
            return
            
        # 画鼠标圆圈（工具激活时）
        if 1 in self.parent.painter_tools.values():
            painter = QPainter(self)
            color = QColor(self.parent.pencolor)
            color.setAlpha(255)
            width = self.parent.tool_width
            painter.setPen(QPen(color, 1, Qt.SolidLine))
            rect = QRectF(self.px - width // 2, self.py - width // 2, width, width)
            painter.drawEllipse(rect)
            painter.end()
            
        # 初始化pixPainter
        try:
            if hasattr(self, 'pixPainter') and self.pixPainter:
                try:
                    if self.pixPainter.isActive():
                        self.pixPainter.end()
                except:
                    pass
                self.pixPainter = None
            
            if self.pixmap() and not self.pixmap().isNull():
                self.pixPainter = QPainter()
                if not self.pixPainter.begin(self.pixmap()):
                    print('QPainter begin failed')
                    return
                self.pixPainter.setRenderHint(QPainter.Antialiasing)
            else:
                print('pixmap invalid, skip painting')
                return
        except Exception as e:
            print(f'pixpainter init fail: {e}')
            return

        def get_ture_pen_alpha_color():
            color = QColor(self.parent.pencolor)
            if color.alpha() != 255:
                al = self.parent.pencolor.alpha() / (self.parent.tool_width / 2)
                if al > 1:
                    color.setAlpha(al)
                else:
                    color.setAlpha(1)
            return color

        # 荧光笔特殊处理 - 使用正片叠底模式
        base_painter = None
        if self.parent.painter_tools.get('highlight_on'):
            base_pixmap = self.parent.pixmap()
            if base_pixmap and not base_pixmap.isNull():
                base_painter = QPainter(base_pixmap)
                base_painter.setRenderHint(QPainter.Antialiasing)
                base_painter.setCompositionMode(QPainter.CompositionMode_Multiply)

        # 画笔工具
        while len(self.parent.pen_pointlist):
            color = get_ture_pen_alpha_color()
            pen_painter = base_painter if base_painter else self.pixPainter
            pen_painter.setBrush(color)
            pen_painter.setPen(Qt.NoPen)
            pen_painter.setRenderHint(QPainter.Antialiasing)
            new_pen_point = self.parent.pen_pointlist.pop(0)
            if self.parent.old_pen is None:
                self.parent.old_pen = new_pen_point
                continue
            if self.parent.old_pen[0] != -2 and new_pen_point[0] != -2:
                # 荧光笔使用正方形笔刷，普通画笔使用圆形笔刷
                if self.parent.painter_tools.get('highlight_on'):
                    pen_painter.drawRect(new_pen_point[0] - self.parent.tool_width / 2,
                                         new_pen_point[1] - self.parent.tool_width / 2,
                                         self.parent.tool_width, self.parent.tool_width)
                else:
                    pen_painter.drawEllipse(new_pen_point[0] - self.parent.tool_width / 2,
                                            new_pen_point[1] - self.parent.tool_width / 2,
                                            self.parent.tool_width, self.parent.tool_width)
                if abs(new_pen_point[0] - self.parent.old_pen[0]) > 1 or abs(
                        new_pen_point[1] - self.parent.old_pen[1]) > 1:
                    interpolateposs = get_line_interpolation(new_pen_point[:], self.parent.old_pen[:])
                    if interpolateposs is not None:
                        for pos in interpolateposs:
                            x, y = pos
                            if self.parent.painter_tools.get('highlight_on'):
                                pen_painter.drawRect(x - self.parent.tool_width / 2,
                                                     y - self.parent.tool_width / 2,
                                                     self.parent.tool_width, self.parent.tool_width)
                            else:
                                pen_painter.drawEllipse(x - self.parent.tool_width / 2,
                                                        y - self.parent.tool_width / 2,
                                                        self.parent.tool_width, self.parent.tool_width)
            self.parent.old_pen = new_pen_point
            
        if base_painter:
            base_painter.end()
            if hasattr(self.parent, 'showing_imgpix') and self.parent.pixmap():
                try:
                    self.parent.showing_imgpix = self.parent.pixmap().copy()
                except Exception as sync_err:
                    print(f"⚠️ 正片叠底同步失败: {sync_err}")
            if hasattr(self.parent, 'qimg'):
                try:
                    self.parent.qimg = self.parent.pixmap().toImage()
                except Exception as image_sync_err:
                    print(f"⚠️ 正片叠底图像同步失败: {image_sync_err}")
            self.parent.update()
            
        # 画矩形工具
        if self.parent.drawrect_pointlist[0][0] != -2 and self.parent.drawrect_pointlist[1][0] != -2:
            try:
                temppainter = QPainter(self)
                temppainter.setPen(QPen(self.parent.pencolor, self.parent.tool_width, Qt.SolidLine))
                poitlist = self.parent.drawrect_pointlist
                temppainter.drawRect(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                     abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                temppainter.end()
            except Exception as e:
                print(f"画矩形临时QPainter错误: {e}")
                
            if self.parent.drawrect_pointlist[2] == 1:
                try:
                    self.pixPainter.setPen(QPen(self.parent.pencolor, self.parent.tool_width, Qt.SolidLine))
                    self.pixPainter.drawRect(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                             abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                    self.parent.drawrect_pointlist = [[-2, -2], [-2, -2], 0]
                    print(f"矩形撤销调试: paintEvent中绘制完成，创建备份")
                    self.parent.backup_shortshot()
                except Exception as e:
                    print(f"画矩形pixPainter错误: {e}")

        # 画圆工具
        if self.parent.drawcircle_pointlist[0][0] != -2 and self.parent.drawcircle_pointlist[1][0] != -2:
            try:
                temppainter = QPainter(self)
                temppainter.setPen(QPen(self.parent.pencolor, self.parent.tool_width, Qt.SolidLine))
                poitlist = self.parent.drawcircle_pointlist
                temppainter.drawEllipse(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                        abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                temppainter.end()
            except Exception as e:
                print(f"画圆临时QPainter错误: {e}")
                
            if self.parent.drawcircle_pointlist[2] == 1:
                try:
                    self.pixPainter.setPen(QPen(self.parent.pencolor, self.parent.tool_width, Qt.SolidLine))
                    self.pixPainter.drawEllipse(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                                abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                    self.parent.drawcircle_pointlist = [[-2, -2], [-2, -2], 0]
                    print(f"圆形撤销调试: paintEvent中绘制完成，创建备份")
                    self.parent.backup_shortshot()
                except Exception as e:
                    print(f"画圆pixPainter错误: {e}")

        # 画箭头工具（优化版：渐变箭身+锐利箭头）
        if self.parent.drawarrow_pointlist[0][0] != -2 and self.parent.drawarrow_pointlist[1][0] != -2:
            try:
                temppainter = QPainter(self)
                poitlist = self.parent.drawarrow_pointlist
                
                # 使用优化的箭头绘制函数
                self._draw_optimized_arrow(temppainter, poitlist, self.parent.pencolor, self.parent.tool_width)
                temppainter.end()
            except Exception as e:
                print(f"画箭头临时QPainter错误: {e}")
                
            if self.parent.drawarrow_pointlist[2] == 1:
                try:
                    if not self._begin_pix_painter():
                        raise RuntimeError('pixPainter 初始化失败，无法提交箭头')
                    
                    # 使用优化的箭头绘制函数
                    self._draw_optimized_arrow(self.pixPainter, poitlist, self.parent.pencolor, self.parent.tool_width)
                    
                    self.parent.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
                    print(f"箭头撤销调试: paintEvent中绘制完成，创建备份")
                    self.parent.backup_shortshot()
                except Exception as e:
                    print(f"画箭头pixPainter错误: {e}")

        # 文字提交阶段
        if len(self.parent.drawtext_pointlist) > 1 or self.parent.text_box.paint:
            if self.parent.text_box.paint:
                try:
                    UnifiedTextDrawer.process_text_drawing(self.parent, self.pixPainter, self.parent.text_box)
                except Exception as e:
                    print(f"统一文字提交错误: {e}")
            else:
                try:
                    text = self.parent.text_box.toPlainText()
                    self.parent.text_box.clear()
                    pos = self.parent.drawtext_pointlist.pop(0)
                    if text and text.strip():
                        self.pixPainter.setFont(QFont('', self.parent.tool_width))
                        self.pixPainter.setPen(QPen(self.parent.pencolor, 3, Qt.SolidLine))
                        lines = text.split('\n')
                        line_height = self.parent.tool_width * 2.0
                        base_x = pos[0] + self.parent.text_box.document.size().height() / 8 - 3
                        base_y = pos[1] + self.parent.text_box.document.size().height() * 32 / 41 - 2
                        for i, line in enumerate(lines):
                            if line.strip():
                                self.pixPainter.drawText(base_x, base_y + i * line_height, line)
                        self.parent.backup_shortshot()
                        self.parent.setFocus()
                    else:
                        print("文字撤销调试: 空文本提交跳过")
                except Exception as e:
                    print(f"旧文字提交兼容错误: {e}")

        # 实时文字预览
        try:
            if (hasattr(self.parent, 'text_box') and
                hasattr(self.parent, 'drawtext_pointlist') and
                len(self.parent.drawtext_pointlist) > 0 and
                not self.parent.text_box.paint):
                UnifiedTextDrawer.render_live_preview(self, self.parent, self.parent.text_box)
        except Exception as e:
            print(f"截图实时文字预览错误: {e}")
            
        # 清理pixPainter
        try:
            if hasattr(self, 'pixPainter') and self.pixPainter:
                if self.pixPainter.isActive():
                    self.pixPainter.end()
                self.pixPainter = None
        except Exception as e:
            print(f"pixpainter end error: {e}")
            self.pixPainter = None

        # 选区预览与手柄绘制
        try:
            if hasattr(self.parent, 'selection_active') and self.parent.selection_active:
                overlay = QPainter(self)
                overlay.setRenderHint(QPainter.Antialiasing)
                if getattr(self.parent, 'selection_scaled_pixmap', None) is not None:
                    overlay.drawPixmap(self.parent.selection_rect.topLeft(), self.parent.selection_scaled_pixmap)
                pen = QPen(QColor(0, 120, 215), 1, Qt.DashLine)
                overlay.setPen(pen)
                overlay.setBrush(Qt.NoBrush)
                overlay.drawRect(self.parent.selection_rect)
                
                handle_size = 6
                r = self.parent.selection_rect
                cx = r.x() + r.width() // 2
                cy = r.y() + r.height() // 2
                handles = [
                    QRect(r.left()-handle_size//2, r.top()-handle_size//2, handle_size, handle_size),
                    QRect(cx-handle_size//2, r.top()-handle_size//2, handle_size, handle_size),
                    QRect(r.right()-handle_size//2, r.top()-handle_size//2, handle_size, handle_size),
                    QRect(r.left()-handle_size//2, cy-handle_size//2, handle_size, handle_size),
                    QRect(r.right()-handle_size//2, cy-handle_size//2, handle_size, handle_size),
                    QRect(r.left()-handle_size//2, r.bottom()-handle_size//2, handle_size, handle_size),
                    QRect(cx-handle_size//2, r.bottom()-handle_size//2, handle_size, handle_size),
                    QRect(r.right()-handle_size//2, r.bottom()-handle_size//2, handle_size, handle_size),
                ]
                overlay.setBrush(QBrush(QColor(0, 120, 215)))
                for h in handles:
                    overlay.drawRect(h)
                overlay.end()
        except Exception as e:
            print(f"selection overlay draw error: {e}")

    def clear(self):
        """清理PaintLayer的绘画数据和QPainter"""
        try:
            if hasattr(self, 'pixPainter') and self.pixPainter:
                try:
                    if self.pixPainter.isActive():
                        self.pixPainter.end()
                except:
                    pass
                self.pixPainter = None
            
            empty_pix = QPixmap(1, 1)
            empty_pix.fill(Qt.transparent)
            self.setPixmap(empty_pix)
            self.parent = None
            print("🧹 [内存清理] PaintLayer清理完成")
        except Exception as e:
            print(f"⚠️ PaintLayer清理时出错: {e}")

    def __del__(self):
        """析构函数，确保QPainter被正确清理"""
        try:
            if hasattr(self, 'pixPainter') and self.pixPainter:
                try:
                    if self.pixPainter.isActive():
                        self.pixPainter.end()
                except:
                    pass
                self.pixPainter = None
        except:
            pass


# ============================================================================
#  设计说明
# ============================================================================
# 
# 文字绘制设计:
# 1. 实时预览与最终提交使用完全相同的坐标/行高/字体/颜色计算，保证所见即所得。
# 2. 预览阶段不弹出 drawtext_pointlist 中的坐标点；提交阶段在 process_text_drawing 中才真正 pop。
# 3. text_box.paint == True 视为提交状态：
#       - process_text_drawing 负责: 从 pointlist 取点 -> 绘制到底层 pixmap -> 备份 -> 清理输入框
#       - render_live_preview 只在 paint == False 且有文字且点存在时执行。
# 4. 多窗口适配：截图主窗口 paintlayer 与 钉图窗口 PinnedPaintLayer 均调用 render_live_preview。
# 5. 安全性：预览绘制使用前景 QPainter(target_widget)，不会破坏底层像素图，可随文本动态刷新。
#
