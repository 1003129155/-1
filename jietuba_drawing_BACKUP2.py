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
from typing import Optional
from PyQt5.QtCore import Qt, QRect, QRectF, QPoint, QPointF
from PyQt5.QtGui import (QPainter, QPen, QColor, QBrush, QPixmap, QFont, 
                         QPolygon, QFontMetrics)
from PyQt5.QtWidgets import QLabel
from jietuba_layer_system import StrokeStampRenderer


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

            lines = text.split('\n')
            line_height = font_size * 2.0
            if document_size:
                base_x = pos[0] + document_size.height() / 8 - 3
                base_y = pos[1] + document_size.height() * 32 / 41 - 2
            else:
                base_x = pos[0]
                base_y = pos[1]

            for i, line in enumerate(lines):
                if line.strip():
                    painter.drawText(base_x, base_y + i * line_height, line)

            painter.end()
            return True

        except Exception as e:
            print(f"统一文字绘制器错误: {e}")
            return False

    @staticmethod
    def process_text_drawing(parent, pixmap_painter, text_box, *, vector_target=None, force_raster=False):
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
            if not pixmap_painter:
                print("统一文字绘制: pixmap_painter为空")
                return False

            if not pixmap_painter.isActive():
                print("统一文字绘制: pixmap_painter未激活")
                return False

            if not (hasattr(parent, 'text_box') and text_box.paint) and \
               not (hasattr(parent, 'drawtext_pointlist') and
                    len(parent.drawtext_pointlist) > 0 and
                    getattr(text_box, 'paint', False)):
                return False

            text_box.paint = False
            text = text_box.toPlainText()
            pos = None
            if len(parent.drawtext_pointlist) > 0:
                pos = parent.drawtext_pointlist[0]

            if text and text.strip() and pos is not None:
                parent.drawtext_pointlist.pop(0)
                try:
                    pixmap_painter.setFont(QFont('', parent.tool_width))
                    pixmap_painter.setPen(QPen(parent.pencolor, 3, Qt.SolidLine))
                except Exception as font_error:
                    print(f"统一文字绘制: 设置字体时出错: {font_error}")
                    return False

                lines = text.split('\n')
                line_height = parent.tool_width * 2.0
                if not hasattr(text_box, '_anchor_base'):
                    h = text_box.document.size().height()
                    text_box._anchor_base = (
                        pos[0] + h / 8 - 3,
                        pos[1] + h * 32 / 41 - 2
                    )
                base_x, base_y = text_box._anchor_base

                max_line_width = 0
                total_height = len(lines) * line_height
                for line in lines:
                    if line.strip():
                        estimated_width = len(line) * parent.tool_width * 0.6
                        max_line_width = max(max_line_width, estimated_width)

                text_rect = QRect(int(base_x), int(base_y - parent.tool_width),
                                  int(max_line_width), int(total_height))

                handled_by_vector = False
                font_family = ""
                font_weight = None
                font_italic = False
                font_obj = None
                try:
                    font_obj = QFont(text_box.currentFont()) if hasattr(text_box, 'currentFont') else QFont(text_box.font())
                except Exception:
                    font_obj = QFont()
                font_obj.setPointSize(max(1, parent.tool_width))
                font_family = font_obj.family()
                font_weight = font_obj.weight()
                font_italic = font_obj.italic()

                vector_owner = vector_target or parent
                if vector_owner and hasattr(vector_owner, 'record_text_command'):
                    try:
                        handled_by_vector = bool(
                            vector_owner.record_text_command(
                                anchor_point=(base_x, base_y),
                                text=text,
                                color=parent.pencolor,
                                font_size=parent.tool_width,
                                line_ratio=(line_height / max(1.0, float(parent.tool_width))),
                                font_family=font_family,
                                font_weight=font_weight,
                                font_italic=font_italic,
                            )
                        )
                    except Exception as vector_error:
                        handled_by_vector = False
                        print(f"统一文字绘制: 矢量文字记录失败，回退到栅格绘制: {vector_error}")

                if force_raster:
                    handled_by_vector = False

                if not handled_by_vector:
                    try:
                        if font_obj:
                            pixmap_painter.setFont(font_obj)
                        for i, line in enumerate(lines):
                            if line.strip():
                                pixmap_painter.drawText(base_x, base_y + i * line_height, line)
                    except Exception as draw_error:
                        print(f"统一文字绘制: 绘制文字时出错: {draw_error}")
                        return False

                if not handled_by_vector and hasattr(parent, 'backup_shortshot'):
                    try:
                        parent.backup_shortshot()
                    except Exception as backup_error:
                        print(f"统一文字绘制: 备份时出错: {backup_error}")

                try:
                    text_box.clear()
                    if hasattr(text_box, '_anchor_base'):
                        delattr(text_box, '_anchor_base')
                except Exception:
                    pass

                if hasattr(parent, 'setFocus'):
                    try:
                        parent.setFocus()
                    except Exception:
                        pass

                try:
                    parent._last_tool_commit = 'text'
                except Exception:
                    pass
                return True
            else:
                print("统一文字绘制: 无文字内容或仅空白，清理坐标点和输入框状态")
                if len(parent.drawtext_pointlist) > 0:
                    unused_coord = parent.drawtext_pointlist.pop(0)
                    print(f"统一文字绘制: 清理未使用的坐标点: {unused_coord}")

                text_box.clear()
                if hasattr(text_box, '_anchor_base'):
                    delattr(text_box, '_anchor_base')
                try:
                    if getattr(parent, '_last_tool_commit', None) == 'text':
                        parent._last_tool_commit = None
                except Exception:
                    pass
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
            if (not hasattr(parent, 'text_box') or
                not text_box.isVisible() or
                getattr(text_box, 'paint', False)):
                return

            # 兼容 drawtext_pointlist 在输入过程中被意外清理的情况，必要时根据
            # 文本框的真实位置反推绘制锚点，避免导致实时预览缺失。
            anchor_point = None
            if hasattr(parent, 'drawtext_pointlist') and parent.drawtext_pointlist:
                anchor_point = parent.drawtext_pointlist[0]
            if not anchor_point:
                try:
                    widget_top_left = text_box.mapToGlobal(QPoint(0, 0))
                    mapped = target_widget.mapFromGlobal(widget_top_left)
                    anchor_point = [mapped.x(), mapped.y()]
                except Exception:
                    anchor_point = [text_box.x(), text_box.y()]

            # 将预编辑文本插入到实时预览内容中，确保可见拼音/假名
            if hasattr(text_box, 'compose_preview_text'):
                text, caret_index, preedit_start, preedit_text = text_box.compose_preview_text()
            else:
                text = text_box.toPlainText()
                caret_index = text_box.textCursor().position()
                preedit_start = -1
                preedit_text = ''
            pos = anchor_point  # 仅取坐标，不弹出
            painter = QPainter(target_widget)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 创建字体并设置给painter
            try:
                font = QFont(text_box.currentFont()) if hasattr(text_box, 'currentFont') else QFont(text_box.font())
            except Exception:
                font = QFont()
            font.setPointSize(max(1, parent.tool_width))
            painter.setFont(font)
            base_pen = QPen(parent.pencolor, 3, Qt.SolidLine)
            painter.setPen(base_pen)
            
            # 创建字体度量对象用于精确测量文字宽度（使用相同的字体）
            font_metrics = QFontMetrics(font)

            def _text_width_local(content: str) -> int:
                try:
                    return font_metrics.horizontalAdvance(content)
                except AttributeError:
                    return font_metrics.width(content)

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

            # 计算光标所在的行和列（包含预编辑字符）
            caret_index = max(0, min(len(text), caret_index))
            cursor_line = 0
            cursor_column = 0
            scanning_offset = 0
            for i, line in enumerate(lines):
                line_len = len(line)
                if caret_index <= scanning_offset + line_len:
                    cursor_line = i
                    cursor_column = caret_index - scanning_offset
                    break
                scanning_offset += line_len + 1
            else:
                cursor_line = max(0, len(lines) - 1)
                cursor_column = len(lines[cursor_line]) if lines else 0

            cursor_x = base_x
            cursor_y = base_y + cursor_line * line_height

            preedit_end = preedit_start + len(preedit_text) if preedit_start >= 0 else -1
            line_offset = 0
            for i, line in enumerate(lines):
                y = base_y + i * line_height
                painter.setPen(base_pen)
                painter.drawText(base_x, y, line)

                # 预编辑文本使用虚线下划线高亮，帮助用户区分候选状态
                if preedit_text and preedit_start >= 0:
                    line_start = line_offset
                    line_end = line_start + len(line)
                    overlap_start = max(preedit_start, line_start)
                    overlap_end = min(preedit_end, line_end)
                    if overlap_start < overlap_end:
                        prefix = line[:overlap_start - line_start]
                        highlight = line[overlap_start - line_start: overlap_end - line_start]
                        prefix_width = _text_width_local(prefix)
                        highlight_width = _text_width_local(highlight)
                        underline_y = y + font_metrics.descent() + 2
                        highlight_pen = QPen(QColor(parent.pencolor).lighter(140), max(1, parent.tool_width // 6))
                        highlight_pen.setStyle(Qt.DashLine)
                        painter.setPen(highlight_pen)
                        painter.drawLine(int(base_x + prefix_width), int(underline_y),
                                         int(base_x + prefix_width + highlight_width), int(underline_y))
                        painter.setPen(base_pen)

                if i == cursor_line:
                    text_before_cursor_in_line = line[:cursor_column] if cursor_column <= len(line) else line
                    cursor_x = base_x + _text_width_local(text_before_cursor_in_line)
                    cursor_y = y

                line_offset += len(line) + 1

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

        # 绘制边框 - 加粗到4像素
        painter.setPen(QPen(QColor(64, 224, 208), 4, Qt.SolidLine))
        painter.drawRect(rect)
        painter.drawRect(0, 0, self.width(), self.height())
        
        # 绘制尺寸文字
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

        # 绘制阴影遮罩
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
        
        # 绘制阴影后再绘制控制点（确保控制点在最上层）
        handle_size = 10
        handle_positions = [
            QPoint(self.parent.x0, min(self.parent.y1, self.parent.y0) + abs(self.parent.y1 - self.parent.y0) // 2),
            QPoint(min(self.parent.x1, self.parent.x0) + abs(self.parent.x1 - self.parent.x0) // 2, self.parent.y0),
            QPoint(self.parent.x1, min(self.parent.y1, self.parent.y0) + abs(self.parent.y1 - self.parent.y0) // 2),
            QPoint(min(self.parent.x1, self.parent.x0) + abs(self.parent.x1 - self.parent.x0) // 2, self.parent.y1),
            QPoint(self.parent.x0, self.parent.y0),
            QPoint(self.parent.x0, self.parent.y1),
            QPoint(self.parent.x1, self.parent.y0),
            QPoint(self.parent.x1, self.parent.y1),
        ]
        
        for pos in handle_positions:
            painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.SolidLine))
            painter.setBrush(QColor(48, 200, 192))
            painter.drawEllipse(pos, handle_size // 2 + 1, handle_size // 2 + 1)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(48, 200, 192))
            painter.drawEllipse(pos, handle_size // 2, handle_size // 2)
        
        # 以下为鼠标放大镜
        if not (self.parent.painter_tools['drawcircle_on'] or
                self.parent.painter_tools['drawrect_bs_on'] or
                self.parent.painter_tools['drawarrow_on'] or
                self.parent.painter_tools['drawnumber_on'] or
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
            painter.setPen(QPen(QColor(64, 224, 208), 2, Qt.SolidLine))
            painter.drawRect(enlarge_rect)
            
            # 优化：绘制更美观的信息背景框
            info_box_height = 75  # 增加高度以容纳更大字体
            info_box_width = 150  # 增加宽度
            painter.setPen(QPen(QColor(64, 224, 208), 2, Qt.SolidLine))  # 加边框
            painter.setBrush(QBrush(QColor(40, 40, 45, 220)))  # 更深的背景，更高透明度
            painter.drawRoundedRect(QRect(enlarge_box_x, enlarge_box_y - info_box_height, 
                                         info_box_width, info_box_height), 5, 5)  # 圆角矩形
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

            # 优化：使用更大的字体和更好的布局
            font = QFont('Microsoft YaHei', 10, QFont.Bold)  # 微软雅黑，10号，加粗
            painter.setFont(font)
            
            # 使用渐变色文字效果
            painter.setPen(QPen(QColor(100, 240, 220), 2, Qt.SolidLine))  # 青色文字
            painter.drawText(enlarge_box_x + 8, enlarge_box_y - info_box_height + 20,
                             'POS: ({}, {})'.format(self.parent.mouse_posx, self.parent.mouse_posy))
            
            painter.setPen(QPen(QColor(255, 200, 100), 2, Qt.SolidLine))  # 橙黄色文字
            painter.drawText(enlarge_box_x + 8, enlarge_box_y - info_box_height + 42,
                             'RGB: ({}, {}, {})'.format(RGB_color[0], RGB_color[1], RGB_color[2]))
            
            painter.setPen(QPen(QColor(200, 150, 255), 2, Qt.SolidLine))  # 紫色文字
            painter.drawText(enlarge_box_x + 8, enlarge_box_y - info_box_height + 64,
                             'HSV: ({}, {}, {})'.format(HSV_color[0], HSV_color[1], HSV_color[2]))

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
        self._active_stroke = []
        self._pending_vectors = []
        self._current_stroke_meta = None

    @property
    def document(self):
        """获取关联的矢量文档"""
        if self.parent and hasattr(self.parent, '_ensure_vector_document'):
            return self.parent._ensure_vector_document()
        return None

    def _vector_capture_color(self, effective_color: QColor, is_highlight: bool) -> QColor:
        """选择写入矢量命令的颜色。

        荧光笔实时绘制会为了笔迹效果调整 alpha，但矢量还原需要保留用户设定
        的透明度，否则撤销/重做后会显得过淡。普通画笔仍沿用实时颜色。"""

        try:
            if is_highlight and hasattr(self.parent, 'pencolor'):
                return QColor(self.parent.pencolor)
        except Exception:
            pass
        return QColor(effective_color)

    def _current_pen_color(self, is_highlight: bool) -> QColor:
        color = QColor(self.parent.pencolor)
        if not is_highlight and color.alpha() != 255:
            denom = max(1.0, float(self.parent.tool_width) / 2.0)
            al = self.parent.pencolor.alpha() / denom
            color.setAlpha(int(al) if al > 1 else 1)
        return color

    def _render_live_brush_segment(
        self,
        painter: QPainter,
        start_point,
        end_point,
        color: QColor,
        brush_kind: str,
        raw_alpha: Optional[int],
    ) -> None:
        if not painter or not end_point:
            return
        points = []
        if start_point and start_point[0] != -2:
            points.append(QPointF(start_point[0], start_point[1]))
        points.append(QPointF(end_point[0], end_point[1]))
        StrokeStampRenderer.render(
            painter,
            points,
            self.parent.tool_width,
            QColor(color),
            brush_kind,
            raw_alpha,
        )

    def force_flush_pen_points(self):
        """强制处理待绘制的画笔点，生成矢量命令
        
        在备份前调用此方法，确保所有画笔点都被转换为矢量命令。
        这是一个同步方法，会立即处理 pen_pointlist 中的所有点。
        """
        if not self.parent or not hasattr(self.parent, 'pen_pointlist'):
            return
        
        if not self.parent.pen_pointlist:
            return
        
        # 初始化 pixPainter（如果需要）
        if not self._begin_pix_painter():
            return
        
        try:
            while len(self.parent.pen_pointlist):
                new_pen_point = self.parent.pen_pointlist.pop(0)

                if new_pen_point[0] == -2:
                    self._finalize_vector_stroke()
                    self.parent.old_pen = new_pen_point
                    continue

                is_highlight = bool(self.parent.painter_tools.get('highlight_on'))
                color = self._current_pen_color(is_highlight)
                raw_alpha = int(self.parent.pencolor.alpha()) if is_highlight else None
                brush_kind = "square" if is_highlight else "round"
                pen_painter = self.pixPainter
                if pen_painter:
                    pen_painter.setRenderHint(QPainter.Antialiasing)

                if self.parent.old_pen is None:
                    self.parent.old_pen = new_pen_point
                    self._current_stroke_meta = (
                        self._vector_capture_color(color, is_highlight),
                        self.parent.tool_width,
                        is_highlight,
                        raw_alpha,
                    )
                    self._active_stroke.append([new_pen_point[0], new_pen_point[1]])
                    continue

                if not self._active_stroke:
                    self._current_stroke_meta = (
                        self._vector_capture_color(color, is_highlight),
                        self.parent.tool_width,
                        is_highlight,
                        raw_alpha,
                    )

                self._active_stroke.append([new_pen_point[0], new_pen_point[1]])

                if self.parent.old_pen[0] != -2 and new_pen_point[0] != -2:
                    self._render_live_brush_segment(
                        pen_painter,
                        self.parent.old_pen,
                        new_pen_point,
                        color,
                        brush_kind,
                        raw_alpha,
                    )

                self.parent.old_pen = new_pen_point
            
            # 处理完成后，将 _pending_vectors 传递给父窗口
            if self._pending_vectors and hasattr(self.parent, 'ingest_vector_commands'):
                payload = list(self._pending_vectors)
                self._pending_vectors.clear()
                try:
                    self.parent.ingest_vector_commands(payload)
                except Exception as e:
                    print(f"⚠️ 矢量笔迹记录失败: {e}")
            
        finally:
            if self.pixPainter and self.pixPainter.isActive():
                self.pixPainter.end()
            self.pixPainter = None

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
            
        # 画鼠标圆圈（工具激活时，但排除文字工具）
        if 1 in self.parent.painter_tools.values() and not self.parent.painter_tools.get('drawtext_on'):
            painter = QPainter(self)
            color = QColor(self.parent.pencolor)
            color.setAlpha(255)
            
            # 针对序号工具使用特殊的大小计算
            if self.parent.painter_tools.get('drawnumber_on'):
                # 序号工具的圆圈大小应该与实际绘制的标号圆形一致
                circle_radius = max(10, self.parent.tool_width * 1.5)
                width = circle_radius * 2  # 直径 = 半径 * 2
            else:
                width = self.parent.tool_width
            
            painter.setPen(QPen(color, 1, Qt.SolidLine))
            rect = QRectF(self.px - width / 2, self.py - width / 2, width, width)
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
            new_pen_point = self.parent.pen_pointlist.pop(0)
            if new_pen_point[0] == -2:
                self._finalize_vector_stroke()
                self.parent.old_pen = new_pen_point
                continue

            is_highlight = bool(self.parent.painter_tools.get('highlight_on'))
            color = self._current_pen_color(is_highlight)
            raw_alpha = int(self.parent.pencolor.alpha()) if is_highlight else None
            brush_kind = "square" if is_highlight else "round"
            pen_painter = base_painter if is_highlight and base_painter else self.pixPainter
            if pen_painter:
                pen_painter.setRenderHint(QPainter.Antialiasing)

            if self.parent.old_pen is None:
                self.parent.old_pen = new_pen_point
                self._current_stroke_meta = (
                    self._vector_capture_color(color, is_highlight),
                    self.parent.tool_width,
                    is_highlight,
                    raw_alpha,
                )
                self._active_stroke.append([new_pen_point[0], new_pen_point[1]])
                continue

            if not self._active_stroke:
                self._current_stroke_meta = (
                    self._vector_capture_color(color, is_highlight),
                    self.parent.tool_width,
                    is_highlight,
                    raw_alpha,
                )

            self._active_stroke.append([new_pen_point[0], new_pen_point[1]])
            if self.parent.old_pen[0] != -2 and new_pen_point[0] != -2:
                self._render_live_brush_segment(
                    pen_painter,
                    self.parent.old_pen,
                    new_pen_point,
                    color,
                    brush_kind,
                    raw_alpha,
                )
            self.parent.old_pen = new_pen_point
        if self._pending_vectors and hasattr(self.parent, 'ingest_vector_commands'):
            payload = list(self._pending_vectors)
            self._pending_vectors.clear()
            try:
                self.parent.ingest_vector_commands(payload)
            except Exception as e:
                print(f"⚠️ 矢量笔迹记录失败: {e}")
            
        if base_painter:
            base_painter.end()
            # 矢量系统会自动管理图像数据，不需要手动同步 showing_imgpix
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
                    if hasattr(self.parent, 'record_rectangle_command'):
                        self.parent.record_rectangle_command(
                            poitlist[0][:],
                            poitlist[1][:],
                            self.parent.pencolor,
                            self.parent.tool_width,
                        )
                    print(f"矩形撤销调试: paintEvent中绘制完成，创建备份")
                    self.parent.backup_shortshot()
                    
                    # 自动选中刚绘制的矩形
                    if hasattr(self.parent, 'paintlayer') and hasattr(self.parent.paintlayer, 'document'):
                        last_index = len(self.parent.paintlayer.document.commands) - 1
                        if last_index >= 0:
                            self.parent.selected_command_index = last_index
                            print(f"🎯 [自动选中] 矩形绘制完成，自动选中对象 {last_index}")
                            # 强制重绘以显示选中框
                            self.update()
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
                    
                    # 🔧 在记录矢量命令之前先清空预览，避免闪烁
                    self.parent.drawcircle_pointlist = [[-2, -2], [-2, -2], 0]
                    
                    if hasattr(self.parent, 'record_circle_command'):
                        self.parent.record_circle_command(
                            poitlist[0][:],
                            poitlist[1][:],
                            self.parent.pencolor,
                            self.parent.tool_width,
                        )
                    print(f"圆形撤销调试: paintEvent中绘制完成，创建备份")
                    self.parent.backup_shortshot()
                    
                    # 自动选中刚绘制的圆形
                    if hasattr(self.parent, 'paintlayer') and hasattr(self.parent.paintlayer, 'document'):
                        last_index = len(self.parent.paintlayer.document.commands) - 1
                        if last_index >= 0:
                            self.parent.selected_command_index = last_index
                            print(f"🎯 [自动选中] 圆形绘制完成，自动选中对象 {last_index}")
                            # 强制重绘以显示选中框
                            self.update()
                except Exception as e:
                    print(f"画圆pixPainter错误: {e}")

        # 画箭头工具（优化版：渐变箭身+锐利箭头）
        if self.parent.drawarrow_pointlist[0][0] != -2 and self.parent.drawarrow_pointlist[1][0] != -2:
            try:
                temppainter = QPainter(self)
                poitlist = self.parent.drawarrow_pointlist
                pen_color = QColor(self.parent.pencolor)
                
                # 使用优化的箭头绘制函数
                self._draw_optimized_arrow(temppainter, poitlist, pen_color, self.parent.tool_width)
                temppainter.end()
            except Exception as e:
                print(f"画箭头临时QPainter错误: {e}")
                
            if self.parent.drawarrow_pointlist[2] == 1:
                try:
                    if not self._begin_pix_painter():
                        raise RuntimeError('pixPainter 初始化失败，无法提交箭头')
                    
                    # 使用优化的箭头绘制函数
                    self._draw_optimized_arrow(self.pixPainter, poitlist, pen_color, self.parent.tool_width)
                    if hasattr(self.parent, 'record_arrow_command'):
                        self.parent.record_arrow_command(
                            poitlist[0][:],
                            poitlist[1][:],
                            pen_color,
                            self.parent.tool_width,
                        )
                    self.parent.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
                    print(f"箭头撤销调试: paintEvent中绘制完成，创建备份")
                    self.parent.backup_shortshot()
                    
                    # 自动选中刚绘制的箭头
                    if hasattr(self.parent, 'paintlayer') and hasattr(self.parent.paintlayer, 'document'):
                        last_index = len(self.parent.paintlayer.document.commands) - 1
                        if last_index >= 0:
                            self.parent.selected_command_index = last_index
                            print(f"🎯 [自动选中] 箭头绘制完成，自动选中对象 {last_index}")
                            # 强制重绘以显示选中框
                            self.update()
                except Exception as e:
                    print(f"画箭头pixPainter错误: {e}")

        # 画序号标注工具
        if hasattr(self.parent, 'drawnumber_pointlist') and len(self.parent.drawnumber_pointlist) >= 2:
            if self.parent.drawnumber_pointlist[0][0] != -2:
                # 临时预览
                try:
                    temppainter = QPainter(self)
                    center_x, center_y = self.parent.drawnumber_pointlist[0]
                    number = self.parent.drawnumber_counter
                    pen_color = QColor(self.parent.pencolor)
                    circle_radius = max(10, self.parent.tool_width * 1.5)
                    
                    # 绘制圆形背景（使用当前透明度设置）
                    temppainter.setPen(Qt.NoPen)
                    bg_color = QColor(pen_color)
                    bg_color.setAlpha(self.parent.alpha)  # 使用透明度滑块的值
                    temppainter.setBrush(bg_color)
                    from PyQt5.QtCore import QPointF
                    temppainter.drawEllipse(QPointF(center_x, center_y), circle_radius, circle_radius)
                    
                    # 绘制数字
                    font = QFont("Arial", int(circle_radius * 0.8), QFont.Bold)
                    temppainter.setFont(font)
                    temppainter.setPen(QPen(QColor(255, 255, 255)))
                    
                    text = str(number)
                    metrics = temppainter.fontMetrics()
                    text_width = metrics.horizontalAdvance(text)
                    text_height = metrics.height()
                    text_x = center_x - text_width / 2
                    text_y = center_y + text_height / 3
                    
                    temppainter.drawText(int(text_x), int(text_y), text)
                    temppainter.end()
                except Exception as e:
                    print(f"画序号临时QPainter错误: {e}")
                
                # 提交到pixmap
                if self.parent.drawnumber_pointlist[1] == 1:
                    try:
                        if not self._begin_pix_painter():
                            raise RuntimeError('pixPainter 初始化失败，无法提交序号')
                        
                        center_x, center_y = self.parent.drawnumber_pointlist[0]
                        number = self.parent.drawnumber_counter
                        pen_color = QColor(self.parent.pencolor)
                        circle_radius = max(10, self.parent.tool_width * 1.5)
                        
                        # 绘制圆形背景（使用当前透明度设置）
                        self.pixPainter.setPen(Qt.NoPen)
                        bg_color = QColor(pen_color)
                        bg_color.setAlpha(self.parent.alpha)  # 使用透明度滑块的值
                        self.pixPainter.setBrush(bg_color)
                        from PyQt5.QtCore import QPointF
                        self.pixPainter.drawEllipse(QPointF(center_x, center_y), circle_radius, circle_radius)
                        
                        # 绘制数字
                        font = QFont("Arial", int(circle_radius * 0.8), QFont.Bold)
                        self.pixPainter.setFont(font)
                        self.pixPainter.setPen(QPen(QColor(255, 255, 255)))
                        
                        text = str(number)
                        metrics = self.pixPainter.fontMetrics()
                        text_width = metrics.horizontalAdvance(text)
                        text_height = metrics.height()
                        text_x = center_x - text_width / 2
                        text_y = center_y + text_height / 3
                        
                        self.pixPainter.drawText(int(text_x), int(text_y), text)
                        
                        # 记录矢量命令
                        if hasattr(self.parent, 'record_number_command'):
                            self.parent.record_number_command(
                                (center_x, center_y),
                                number,
                                QColor(255, 255, 255),  # 文字颜色（白色）
                                pen_color,  # 背景颜色
                                circle_radius,
                            )
                        
                        # 序号自增
                        self.parent.drawnumber_counter += 1
                        # 重置状态
                        self.parent.drawnumber_pointlist = [[-2, -2], 0]
                        print(f"序号撤销调试: paintEvent中绘制完成，创建备份，下一个序号为 {self.parent.drawnumber_counter}")
                        self.parent.backup_shortshot()
                    except Exception as e:
                        print(f"画序号pixPainter错误: {e}")

        # 文字提交阶段
        if len(self.parent.drawtext_pointlist) > 1 or self.parent.text_box.paint:
            if self.parent.text_box.paint:
                try:
                    UnifiedTextDrawer.process_text_drawing(
                        self.parent,
                        self.pixPainter,
                        self.parent.text_box,
                        force_raster=True,
                    )
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

        # 选区预览与手柄绘制
        self._draw_selection_overlay()
            
        # 清理pixPainter
        try:
            if hasattr(self, 'pixPainter') and self.pixPainter:
                if self.pixPainter.isActive():
                    self.pixPainter.end()
                self.pixPainter = None
        except Exception as e:
            print(f"pixpainter end error: {e}")
            self.pixPainter = None

    def _finalize_vector_stroke(self):
        if not self._active_stroke or not self._current_stroke_meta:
            self._active_stroke = []
            self._current_stroke_meta = None
            return
        if len(self._current_stroke_meta) == 4:
            color, width, is_highlight, raw_alpha = self._current_stroke_meta
        else:
            # 兼容老版本，仅包含颜色/宽度/高亮标记
            color, width, is_highlight = self._current_stroke_meta
            raw_alpha = int(color.alpha())
        self._pending_vectors.append(
            {
                "type": "stroke",
                "points": [tuple(pt) for pt in self._active_stroke],
                "color": QColor(color),
                "width": width,
                "is_highlight": is_highlight,
                "raw_alpha": raw_alpha,
            }
        )
        self._active_stroke = []
        self._current_stroke_meta = None

    def _draw_selection_overlay(self):
        parent = self.parent
        if not parent or getattr(parent, 'closed', False):
            return
            
        # 1. 绘制截图选区边框（原逻辑）
        if getattr(parent, 'selection_active', False):
            rect = getattr(parent, 'selection_rect', None)
            if rect and rect.width() > 0 and rect.height() > 0:
                pixmap = getattr(parent, 'selection_scaled_pixmap', None)
                if pixmap is None:
                    pixmap = getattr(parent, 'selection_pixmap', None)
                if pixmap and not pixmap.isNull():
                    try:
                        overlay = QPainter(self)
                        overlay.setRenderHint(QPainter.Antialiasing)
                        overlay.drawPixmap(rect.topLeft(), pixmap)
                        pen = QPen(QColor(0, 120, 215), 1, Qt.DashLine)
                        overlay.setPen(pen)
                        overlay.setBrush(Qt.NoBrush)
                        overlay.drawRect(rect)

                        handle_size = 6
                        cx = rect.x() + rect.width() // 2
                        cy = rect.y() + rect.height() // 2
                        handles = [
                            QRect(rect.left()-handle_size//2, rect.top()-handle_size//2, handle_size, handle_size),
                            QRect(cx-handle_size//2, rect.top()-handle_size//2, handle_size, handle_size),
                            QRect(rect.right()-handle_size//2, rect.top()-handle_size//2, handle_size, handle_size),
                            QRect(rect.left()-handle_size//2, cy-handle_size//2, handle_size, handle_size),
                            QRect(rect.right()-handle_size//2, cy-handle_size//2, handle_size, handle_size),
                            QRect(rect.left()-handle_size//2, rect.bottom()-handle_size//2, handle_size, handle_size),
                            QRect(cx-handle_size//2, rect.bottom()-handle_size//2, handle_size, handle_size),
                            QRect(rect.right()-handle_size//2, rect.bottom()-handle_size//2, handle_size, handle_size),
                        ]
                        overlay.setBrush(QBrush(QColor(0, 120, 215)))
                        for handle in handles:
                            overlay.drawRect(handle)
                        overlay.end()
                    except Exception as e:
                        print(f"selection overlay draw error: {e}")

        # 2. 绘制选中对象的边框（新逻辑）
        if hasattr(parent, 'selected_command_index') and parent.selected_command_index is not None:
            try:
                # 获取选中对象的包围盒
                if hasattr(parent, 'paintlayer') and hasattr(parent.paintlayer, 'document'):
                    doc = parent.paintlayer.document
                    rect_norm = doc.get_command_rect(parent.selected_command_index)
                    if rect_norm:
                        # get_command_rect 返回的是基于 base_size 的坐标
                        # 如果当前显示尺寸与 base_size 不同，需要缩放
                        # 但通常 paintlayer 的大小就是 base_size (或者 document 内部处理了)
                        # 实际上 get_command_rect 已经返回了像素坐标 (基于 base_size)
                        # 我们只需要确保绘制坐标系正确
                        
                        painter = QPainter(self)
                        painter.setRenderHint(QPainter.Antialiasing)
                        
                        # 绘制橙色虚线框
                        pen = QPen(QColor(255, 165, 0), 2, Qt.DashLine)
                        painter.setPen(pen)
                        painter.setBrush(Qt.NoBrush)
                        painter.drawRect(rect_norm)
                        
                        # 绘制手柄
                        handle_size = 8
                        rect = rect_norm
                        cx = rect.x() + rect.width() / 2
                        cy = rect.y() + rect.height() / 2
                        
                        # 8个手柄
                        handles = [
                            QRectF(rect.left()-handle_size/2, rect.top()-handle_size/2, handle_size, handle_size),
                            QRectF(cx-handle_size/2, rect.top()-handle_size/2, handle_size, handle_size),
                            QRectF(rect.right()-handle_size/2, rect.top()-handle_size/2, handle_size, handle_size),
                            QRectF(rect.left()-handle_size/2, cy-handle_size/2, handle_size, handle_size),
                            QRectF(rect.right()-handle_size/2, cy-handle_size/2, handle_size, handle_size),
                            QRectF(rect.left()-handle_size/2, rect.bottom()-handle_size/2, handle_size, handle_size),
                            QRectF(cx-handle_size/2, rect.bottom()-handle_size/2, handle_size, handle_size),
                            QRectF(rect.right()-handle_size/2, rect.bottom()-handle_size/2, handle_size, handle_size),
                        ]
                        
                        painter.setPen(QPen(QColor(255, 165, 0), 1, Qt.SolidLine))
                        painter.setBrush(QBrush(QColor(255, 255, 255)))
                        for handle in handles:
                            painter.drawRect(handle)
                            
                        painter.end()
            except Exception as e:
                print(f"object selection overlay draw error: {e}")



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
