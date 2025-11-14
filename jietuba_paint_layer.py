"""
jietuba_paint_layer.py - 绘画层模块

包含截图工具的绘画相关类：
- MaskLayer: 遮罩层，显示选区边框和放大镜
- PaintLayer: 绘画层，处理所有绘图操作（画笔、箭头、矩形、圆形、文字等）
- get_line_interpolation: 笔迹插值函数

 
"""
import math
import cv2
from numpy import array, uint8
from PyQt5.QtCore import Qt, QRect, QRectF, QPoint
from PyQt5.QtGui import (QPainter, QPen, QColor, QBrush, QPixmap, QFont, 
                         QPolygon, QPainterPath)
from PyQt5.QtWidgets import QLabel


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
            HSV_color = cv2.cvtColor(array([[RGB_color]], dtype=uint8), cv2.COLOR_RGB2HSV).tolist()[0][0]

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

        # 画箭头工具
        if self.parent.drawarrow_pointlist[0][0] != -2 and self.parent.drawarrow_pointlist[1][0] != -2:
            try:
                temppainter = QPainter(self)
                temppainter.setPen(QPen(self.parent.pencolor, self.parent.tool_width, Qt.SolidLine))
                temppainter.setBrush(QBrush(self.parent.pencolor))
                poitlist = self.parent.drawarrow_pointlist
                
                start_x, start_y = poitlist[0][0], poitlist[0][1]
                end_x, end_y = poitlist[1][0], poitlist[1][1]
                temppainter.drawLine(start_x, start_y, end_x, end_y)
                
                angle = math.atan2(end_y - start_y, end_x - start_x)
                arrow_length = max(self.parent.tool_width * 2, 15)
                arrow_p1_x = end_x - arrow_length * math.cos(angle - math.pi / 6)
                arrow_p1_y = end_y - arrow_length * math.sin(angle - math.pi / 6)
                arrow_p2_x = end_x - arrow_length * math.cos(angle + math.pi / 6)
                arrow_p2_y = end_y - arrow_length * math.sin(angle + math.pi / 6)
                
                arrow_head = QPolygon([
                    QPoint(int(end_x), int(end_y)),
                    QPoint(int(arrow_p1_x), int(arrow_p1_y)),
                    QPoint(int(arrow_p2_x), int(arrow_p2_y))
                ])
                temppainter.drawPolygon(arrow_head)
                temppainter.end()
            except Exception as e:
                print(f"画箭头临时QPainter错误: {e}")
                
            if self.parent.drawarrow_pointlist[2] == 1:
                try:
                    if not self._begin_pix_painter():
                        raise RuntimeError('pixPainter 初始化失败，无法提交箭头')
                    self.pixPainter.setPen(QPen(self.parent.pencolor, self.parent.tool_width, Qt.SolidLine))
                    self.pixPainter.setBrush(QBrush(self.parent.pencolor))
                    
                    start_x, start_y = poitlist[0][0], poitlist[0][1]
                    end_x, end_y = poitlist[1][0], poitlist[1][1]
                    self.pixPainter.drawLine(start_x, start_y, end_x, end_y)
                    
                    angle = math.atan2(end_y - start_y, end_x - start_x)
                    arrow_length = max(self.parent.tool_width * 2, 15)
                    arrow_p1_x = end_x - arrow_length * math.cos(angle - math.pi / 6)
                    arrow_p1_y = end_y - arrow_length * math.sin(angle - math.pi / 6)
                    arrow_p2_x = end_x - arrow_length * math.cos(angle + math.pi / 6)
                    arrow_p2_y = end_y - arrow_length * math.sin(angle + math.pi / 6)
                    
                    arrow_head = QPolygon([
                        QPoint(int(end_x), int(end_y)),
                        QPoint(int(arrow_p1_x), int(arrow_p1_y)),
                        QPoint(int(arrow_p2_x), int(arrow_p2_y))
                    ])
                    self.pixPainter.drawPolygon(arrow_head)
                    self.parent.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
                    print(f"箭头撤销调试: paintEvent中绘制完成，创建备份")
                    self.parent.backup_shortshot()
                except Exception as e:
                    print(f"画箭头pixPainter错误: {e}")

        # 文字提交阶段
        if len(self.parent.drawtext_pointlist) > 1 or self.parent.text_box.paint:
            from jietuba_text_drawer import UnifiedTextDrawer
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
            from jietuba_text_drawer import UnifiedTextDrawer
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
