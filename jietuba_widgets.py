# -*- coding: utf-8 -*-
"""
jietuba_widgets.py - 自定义控件模块

提供截图工具使用的各种自定义 UI 控件和组件。

主要类:
- Freezer: 钉图窗口类,支持图片置顶显示和编辑

特点:
支持拖拽、快捷键、透明度调整、绘图编辑、历史记录等

依赖模块:
jietuba_public, jietuba_resource, jietuba_text_drawer
"""
import os
import time
from typing import Dict, List, Tuple, Sequence, Optional
import jietuba_resource
from PyQt5.QtCore import Qt, pyqtSignal, QStandardPaths, QUrl, QTimer, QSize, QPoint, QRect, QRectF
from PyQt5.QtGui import QTextCursor, QMouseEvent, QCursor, QKeyEvent
from PyQt5.QtGui import QPainter, QPen, QIcon, QFont, QImage, QPixmap, QColor, QMovie, QPolygon, QBrush
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QMenu
from jietuba_public import linelabel,TipsShower, get_screenshot_save_dir
from jietuba_layer_system import VectorLayerDocument

class Hung_widget(QLabel):
    button_signal = pyqtSignal(str)
    def __init__(self,parent=None,funcs = []):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setMouseTracking(True)
        size = 30
        self.buttonsize = size
        self.buttons = []
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: rgba(255, 255, 255, 0); border-radius: 6px;")  # 设置背景色和边框
        for i,func in enumerate(funcs):
            if str(func).endswith(("png","jpg")):
                botton = QPushButton(QIcon(func), '', self)
            else:
                botton = QPushButton(str(func), self)
            botton.clicked.connect(lambda checked, index=func: self.button_signal.emit(index))
            botton.setGeometry(0,i*size,size,size)
            botton.setStyleSheet("""QPushButton {
            border: 2px solid #8f8f91;
            background-color: qradialgradient(
                cx: -0.3, cy: 0.4,
                fx: -0.3, fy: 0.4,
                radius: 1.35,
                stop: 0 #fff,
                stop: 1 #888
            );
            color: white;
            font-size: 16px;
            padding: 6px;
        }

        QPushButton:hover {
            background-color: qradialgradient(
                cx: -0.3, cy: 0.4,
                fx: -0.3, fy: 0.4,
                radius: 1.35,
                stop: 0 #fff,
                stop: 1 #bbb
            );
        }""")
            self.buttons.append(botton)
        self.resize(size,size*len(funcs))

        
    def set_ontop(self,on_top=True):
        if on_top:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.setWindowFlag(Qt.Tool, False)
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.setWindowFlag(Qt.Tool, True)
    def clear(self):
        self.clearMask()
        self.hide()
        super().clear()

    def closeEvent(self, e):
        self.clear()
        super().closeEvent(e)
        
class Loading_label(QLabel):
    def __init__(self, parent=None,size = 100,text=None):
        super().__init__(parent)
        self.giflabel = QLabel(parent = self,text=text if text is not None else "")
        self.giflabel.resize(size, size)
        self.giflabel.setAlignment(Qt.AlignCenter)
        self.gif = QMovie(':./load.gif')
        self.gif.setScaledSize(QSize(size, size))
        self.giflabel.setMovie(self.gif)
    def resizeEvent(self, a0) -> None:
        
        size = min(self.width(),self.height())//3 
        if size < 50:
            size = min(self.width(),self.height())-5
            
        self.gif.setScaledSize(QSize(size, size))
        self.giflabel.resize(size, size)
        self.giflabel.move(self.width()//2-self.giflabel.width()//2,self.height()//2-self.giflabel.height()//2)
        return super().resizeEvent(a0)
    
    def start(self):
        self.gif.start()
        self.show()
    def stop(self):
        self.gif.stop()
        self.hide()

class PinnedPaintLayer(QLabel):
    """钉图窗口的绘画层，完全照搬截图窗口的paintlayer逻辑"""
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self._parent_widget = parent  # 避免覆盖parent()方法
        self.main_window = main_window
        self.px, self.py = 0, 0
        self.setStyleSheet("background-color:rgba(255,255,255,0);")
        pix = QPixmap(parent.width(), parent.height())
        pix.fill(Qt.transparent)
        self.setPixmap(pix)
        self.pixPainter = None
        self._active_stroke: List[List[int]] = []
        self._pending_vectors: List[Dict] = []
        self._current_stroke_meta = None
        # 设置鼠标追踪，让paintlayer接收所有鼠标事件，然后透传给父窗口
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        """将鼠标按下事件直接转发给主窗口进行绘画处理"""
        # print(f"PaintLayer鼠标按下调试: 转发给主窗口，坐标=({event.x()}, {event.y()})")
        
        # 检查是否有绘画工具激活
        has_drawing_tool = (self.main_window and hasattr(self.main_window, 'painter_tools') and 
            1 in self.main_window.painter_tools.values())
        
        # OCR 文字层的状态现在通过回调动态检查，不再需要在此处手动设置
        # 避免在事件处理过程中修改控件状态导致的问题
        
        if has_drawing_tool:
            
            # 创建标记的事件对象
            main_event = QMouseEvent(event.type(), event.pos(), 
                                   event.globalPos(), event.button(), event.buttons(), event.modifiers())
            main_event._from_pinned_window = True
            main_event._pinned_window_instance = self._parent_widget  # 添加当前钉图窗口引用
            
            # print(f"PaintLayer委托调试: 调用主窗口mousePressEvent")
            self.main_window.mousePressEvent(main_event)
        else:
            # 没有绘画工具激活时，转发给父窗口（Freezer）处理
            # print(f"PaintLayer鼠标按下调试: 无绘画工具，转发给父窗口")
            if self._parent_widget:
                self._parent_widget.mousePressEvent(event)
            
    def mouseReleaseEvent(self, event):
        """将鼠标释放事件直接转发给主窗口进行绘画处理"""
        # print(f"PaintLayer鼠标释放调试: 转发给主窗口")
        
        # 检查是否有绘画工具激活
        if (self.main_window and hasattr(self.main_window, 'painter_tools') and 
            1 in self.main_window.painter_tools.values()):
            
            # 创建标记的事件对象
            main_event = QMouseEvent(event.type(), event.pos(), 
                                   event.globalPos(), event.button(), event.buttons(), event.modifiers())
            main_event._from_pinned_window = True
            main_event._pinned_window_instance = self._parent_widget  # 添加当前钉图窗口引用
            
            # print(f"PaintLayer委托调试: 调用主窗口mouseReleaseEvent")
            self.main_window.mouseReleaseEvent(main_event)
        else:
            # 没有绘画工具激活时，转发给父窗口（Freezer）处理
            # print(f"PaintLayer鼠标释放调试: 无绘画工具，转发给父窗口")
            if self._parent_widget:
                self._parent_widget.mouseReleaseEvent(event)
            
    def mouseMoveEvent(self, event):
        """将鼠标移动事件直接转发给主窗口，同时更新鼠标位置"""
        # 更新鼠标位置用于绘制鼠标圆圈
        self.px, self.py = event.x(), event.y()
        self.update()  # 触发重绘以显示鼠标圆圈
        
        # 检查是否有绘画工具激活
        if (self.main_window and hasattr(self.main_window, 'painter_tools') and 
            1 in self.main_window.painter_tools.values()):
            
            # 创建标记的事件对象
            main_event = QMouseEvent(event.type(), event.pos(), 
                                   event.globalPos(), event.button(), event.buttons(), event.modifiers())
            main_event._from_pinned_window = True
            main_event._pinned_window_instance = self._parent_widget  # 添加当前钉图窗口引用
            
            self.main_window.mouseMoveEvent(main_event)
        else:
            # 没有绘画工具激活时，转发给父窗口（Freezer）处理
            if self._parent_widget:
                self._parent_widget.mouseMoveEvent(event)

    def paintEvent(self, e):
        super().paintEvent(e)
        
        # 检查父窗口或主窗口是否正在关闭
        if (not self.main_window or 
            getattr(self.main_window, 'closed', False) or 
            getattr(self._parent_widget, 'closed', False)):
            return
            
        if not self.main_window or self.main_window.on_init:
            print('oninit return')
            return
        if 1 in self.main_window.painter_tools.values() and not self.main_window.painter_tools.get('drawtext_on'):  # 如果有画笔工具打开（排除文字工具）
            painter = QPainter(self)
            color = QColor(self.main_window.pencolor)
            color.setAlpha(255)

            # 针对序号工具使用特殊的大小计算（与截图窗口一致）
            if self.main_window.painter_tools.get('drawnumber_on'):
                # 序号工具的圆圈大小应该与实际绘制的标号圆形一致
                circle_radius = max(10, self.main_window.tool_width * 1.5)
                width = circle_radius * 2  # 直径 = 半径 * 2
            else:
                width = self.main_window.tool_width
            
            painter.setPen(QPen(color, 1, Qt.SolidLine))
            rect = QRectF(self.px - width / 2, self.py - width / 2, width, width)
            painter.drawEllipse(rect)  # 画鼠标圆
            painter.end()
        
        try:
            self.pixPainter = QPainter(self.pixmap())
            self.pixPainter.setRenderHint(QPainter.Antialiasing)
        except Exception:
            print('pixpainter fail!')
            self.pixPainter = None

        def get_ture_pen_alpha_color():
            color = QColor(self.main_window.pencolor)
            if color.alpha() != 255:
                al = self.main_window.pencolor.alpha() / (self.main_window.tool_width / 2)
                if al > 1:
                    color.setAlpha(al)
                else:
                    color.setAlpha(1)
            return color

        while len(self.main_window.pen_pointlist):
            color = get_ture_pen_alpha_color()
            pen_width = self.main_window.tool_width
            is_highlight = bool(self.main_window.painter_tools.get('highlight_on'))
            
            # 荧光笔模式：创建base_painter并设置正片叠底混合模式（与截图窗口一致）
            base_painter = None
            if is_highlight:
                base_pixmap = self._parent_widget.pixmap()
                if base_pixmap and not base_pixmap.isNull():
                    base_painter = QPainter(base_pixmap)
                    base_painter.setCompositionMode(QPainter.CompositionMode_Multiply)
            
            pen_painter = base_painter if base_painter else self.pixPainter
            if not pen_painter:
                break
            pen_painter.setBrush(color)
            pen_painter.setPen(Qt.NoPen)
            pen_painter.setRenderHint(QPainter.Antialiasing)
            new_pen_point = self.main_window.pen_pointlist.pop(0)
            if new_pen_point[0] == -2:
                self._finalize_vector_stroke()
                self.main_window.old_pen = new_pen_point
                continue

            if not self._active_stroke:
                self._current_stroke_meta = (QColor(color), pen_width, is_highlight)
            self._active_stroke.append([new_pen_point[0], new_pen_point[1]])

            if self.main_window.old_pen is None or self.main_window.old_pen[0] == -2:
                self.main_window.old_pen = new_pen_point
                if is_highlight:
                    pen_painter.drawRect(new_pen_point[0] - pen_width / 2,
                                         new_pen_point[1] - pen_width / 2,
                                         pen_width, pen_width)
                else:
                    pen_painter.drawEllipse(new_pen_point[0] - pen_width / 2,
                                            new_pen_point[1] - pen_width / 2,
                                            pen_width, pen_width)
                continue

            if self.main_window.old_pen[0] != -2:
                if is_highlight:
                    pen_painter.drawRect(new_pen_point[0] - pen_width / 2,
                                         new_pen_point[1] - pen_width / 2,
                                         pen_width, pen_width)
                else:
                    pen_painter.drawEllipse(new_pen_point[0] - pen_width / 2,
                                            new_pen_point[1] - pen_width / 2,
                                            pen_width, pen_width)
                if abs(new_pen_point[0] - self.main_window.old_pen[0]) > 1 or abs(
                        new_pen_point[1] - self.main_window.old_pen[1]) > 1:
                    from jietuba_screenshot import get_line_interpolation
                    interpolateposs = get_line_interpolation(new_pen_point[:], self.main_window.old_pen[:])
                    if interpolateposs is not None:
                        for pos in interpolateposs:
                            x, y = pos
                            if is_highlight:
                                pen_painter.drawRect(x - pen_width / 2,
                                                     y - pen_width / 2,
                                                     pen_width, pen_width)
                            else:
                                pen_painter.drawEllipse(x - pen_width / 2,
                                                        y - pen_width / 2,
                                                        pen_width, pen_width)

            self.main_window.old_pen = new_pen_point
        
        # 清理 base_painter（如果创建了的话）
        if 'base_painter' in locals() and base_painter is not None:
            base_painter.end()

        if self._pending_vectors and hasattr(self._parent_widget, 'ingest_vector_commands'):
            payload = list(self._pending_vectors)
            self._pending_vectors.clear()
            self._parent_widget.ingest_vector_commands(payload)

        # 处理矩形工具
        if self.main_window.drawrect_pointlist[0][0] != -2 and self.main_window.drawrect_pointlist[1][0] != -2:
            try:
                temppainter = QPainter(self)
                temppainter.setPen(QPen(self.main_window.pencolor, self.main_window.tool_width, Qt.SolidLine))
                poitlist = self.main_window.drawrect_pointlist
                temppainter.drawRect(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                     abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                temppainter.end()
            except Exception as e:
                print(f"钉图画矩形临时QPainter错误: {e}")
                
            if self.main_window.drawrect_pointlist[2] == 1:
                try:
                    start_pt = poitlist[0][:]
                    end_pt = poitlist[1][:]
                    self.pixPainter.setPen(QPen(self.main_window.pencolor, self.main_window.tool_width, Qt.SolidLine))
                    self.pixPainter.drawRect(min(start_pt[0], end_pt[0]), min(start_pt[1], end_pt[1]),
                                             abs(start_pt[0] - end_pt[0]), abs(start_pt[1] - end_pt[1]))
                    self.main_window.drawrect_pointlist = [[-2, -2], [-2, -2], 0]
                    if hasattr(self._parent_widget, 'record_rectangle_command'):
                        self._parent_widget.record_rectangle_command(start_pt, end_pt,
                                                                    self.main_window.pencolor,
                                                                    self.main_window.tool_width)
                except Exception as e:
                    print(f"钉图画矩形pixPainter错误: {e}")

        # 处理圆形工具
        if self.main_window.drawcircle_pointlist[0][0] != -2 and self.main_window.drawcircle_pointlist[1][0] != -2:
            try:
                temppainter = QPainter(self)
                temppainter.setPen(QPen(self.main_window.pencolor, self.main_window.tool_width, Qt.SolidLine))
                poitlist = self.main_window.drawcircle_pointlist
                temppainter.drawEllipse(min(poitlist[0][0], poitlist[1][0]), min(poitlist[0][1], poitlist[1][1]),
                                        abs(poitlist[0][0] - poitlist[1][0]), abs(poitlist[0][1] - poitlist[1][1]))
                temppainter.end()
            except Exception as e:
                print(f"钉图画圆临时QPainter错误: {e}")
                
            if self.main_window.drawcircle_pointlist[2] == 1:
                try:
                    start_pt = poitlist[0][:]
                    end_pt = poitlist[1][:]
                    self.pixPainter.setPen(QPen(self.main_window.pencolor, self.main_window.tool_width, Qt.SolidLine))
                    self.pixPainter.drawEllipse(min(start_pt[0], end_pt[0]), min(start_pt[1], end_pt[1]),
                                                abs(start_pt[0] - end_pt[0]), abs(start_pt[1] - end_pt[1]))
                    self.main_window.drawcircle_pointlist = [[-2, -2], [-2, -2], 0]
                    if hasattr(self._parent_widget, 'record_circle_command'):
                        self._parent_widget.record_circle_command(start_pt, end_pt,
                                                                  self.main_window.pencolor,
                                                                  self.main_window.tool_width)
                except Exception as e:
                    print(f"钉图画圆pixPainter错误: {e}")

        # 处理箭头工具
        if self.main_window.drawarrow_pointlist[0][0] != -2 and self.main_window.drawarrow_pointlist[1][0] != -2:
            try:
                temppainter = QPainter(self)
                # 设置画笔颜色和粗细，支持透明度
                pen_color = QColor(self.main_window.pencolor)
                if hasattr(self.main_window, 'tool_alpha'):
                    pen_color.setAlpha(self.main_window.tool_alpha)
                temppainter.setPen(QPen(pen_color, self.main_window.tool_width, Qt.SolidLine))
                
                # 绘制箭头
                self.draw_arrow(temppainter, self.main_window.drawarrow_pointlist)
                temppainter.end()
            except Exception as e:
                print(f"钉图画箭头临时QPainter错误: {e}")
                
            if self.main_window.drawarrow_pointlist[2] == 1:
                try:
                    # 设置画笔颜色和粗细，支持透明度
                    pen_color = QColor(self.main_window.pencolor)
                    if hasattr(self.main_window, 'tool_alpha'):
                        pen_color.setAlpha(self.main_window.tool_alpha)
                    self.pixPainter.setPen(QPen(pen_color, self.main_window.tool_width, Qt.SolidLine))
                    
                    # 绘制箭头到像素图
                    self.draw_arrow(self.pixPainter, self.main_window.drawarrow_pointlist)
                    start_pt = self.main_window.drawarrow_pointlist[0][:]
                    end_pt = self.main_window.drawarrow_pointlist[1][:]
                    self.main_window.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
                    if hasattr(self._parent_widget, 'record_arrow_command'):
                        self._parent_widget.record_arrow_command(start_pt, end_pt,
                                                                 pen_color,
                                                                 self.main_window.tool_width)
                except Exception as e:
                    print(f"钉图画箭头pixPainter错误: {e}")

        # 处理序号工具
        if hasattr(self.main_window, 'drawnumber_pointlist') and len(self.main_window.drawnumber_pointlist) >= 2:
            if self.main_window.drawnumber_pointlist[0][0] != -2:
                # 临时预览
                try:
                    temppainter = QPainter(self)
                    center_x, center_y = self.main_window.drawnumber_pointlist[0]
                    number = self.main_window.drawnumber_counter
                    pen_color = QColor(self.main_window.pencolor)
                    circle_radius = max(10, self.main_window.tool_width * 1.5)
                    
                    # 绘制圆形背景（使用当前透明度设置）
                    temppainter.setPen(Qt.NoPen)
                    bg_color = QColor(pen_color)
                    bg_color.setAlpha(self.main_window.alpha)  # 使用透明度滑块的值
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
                    print(f"钉图画序号临时QPainter错误: {e}")
                
                # 提交到pixmap
                if self.main_window.drawnumber_pointlist[1] == 1:
                    try:
                        center_x, center_y = self.main_window.drawnumber_pointlist[0]
                        number = self.main_window.drawnumber_counter
                        pen_color = QColor(self.main_window.pencolor)
                        circle_radius = max(10, self.main_window.tool_width * 1.5)
                        
                        # 绘制圆形背景（使用当前透明度设置）
                        self.pixPainter.setPen(Qt.NoPen)
                        bg_color = QColor(pen_color)
                        bg_color.setAlpha(self.main_window.alpha)  # 使用透明度滑块的值
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
                        if hasattr(self._parent_widget, 'record_number_command'):
                            self._parent_widget.record_number_command(
                                (center_x, center_y),
                                number,
                                QColor(255, 255, 255),  # 文字颜色（白色）
                                pen_color,  # 背景颜色
                                circle_radius,
                            )
                        
                        # 序号自增
                        self.main_window.drawnumber_counter += 1
                        # 重置状态
                        self.main_window.drawnumber_pointlist = [[-2, -2], 0]
                        print(f"钉图序号调试: 绘制完成，下一个序号为 {self.main_window.drawnumber_counter}")
                    except Exception as e:
                        print(f"钉图画序号pixPainter错误: {e}")

        # 处理文字工具（钉图模式下的文字绘制）- 使用统一的文字绘制组件
        try:
            from jietuba_drawing import UnifiedTextDrawer
			
            if len(self.main_window.drawtext_pointlist) > 0 and hasattr(self.main_window, 'text_box') and self.main_window.text_box.paint:
                print("钉图模式: 开始处理文字绘制")
				
                # 使用统一的文字绘制处理
                success = UnifiedTextDrawer.process_text_drawing(
                    self.main_window,
                    self.pixPainter,
                    self.main_window.text_box,
                    vector_target=self._parent_widget,
                )
				
                if success:
                    print("钉图模式: 文字绘制完成")
                    self.update()
                else:
                    print("钉图模式: 文字内容为空，不绘制")
					
        except Exception as e:
            print(f"钉图统一文字绘制流程错误: {e}")

        # ---- 实时文字预览: 在未提交状态下绘制输入中的文字 (不修改底层pixmap) ----
        try:
            from jietuba_drawing import UnifiedTextDrawer
            if (hasattr(self.main_window, 'text_box') and
                hasattr(self.main_window, 'drawtext_pointlist') and
                len(self.main_window.drawtext_pointlist) > 0 and
                not self.main_window.text_box.paint):  # 尚未提交
                UnifiedTextDrawer.render_live_preview(self, self.main_window, self.main_window.text_box)
        except Exception as e:
            print(f"钉图实时文字预览错误: {e}")

        try:
            self.pixPainter.end()
        except:
            pass
    
    def draw_arrow(self, painter, pointlist):
        """绘制箭头 - 复用 PaintLayer 的优化箭头实现"""
        try:
            # 直接调用 jietuba_drawing.py 中的优化箭头函数，避免代码重复
            from jietuba_drawing import PaintLayer
            
            # 创建一个临时的 PaintLayer 实例来调用其箭头绘制方法
            # 注意：这里只是借用其绘制方法，不需要完整初始化
            temp_layer = PaintLayer.__new__(PaintLayer)
            temp_layer._draw_optimized_arrow(
                painter, 
                pointlist, 
                painter.pen().color(),
                self.main_window.tool_width
            )
            
        except Exception as e:
            print(f"钉图绘制箭头错误: {e}")

    def _finalize_vector_stroke(self):
        if not self._active_stroke or not self._current_stroke_meta:
            self._active_stroke = []
            self._current_stroke_meta = None
            return
        color, width, is_highlight = self._current_stroke_meta
        self._pending_vectors.append(
            {
                "type": "stroke",
                "points": [tuple(pt) for pt in self._active_stroke],
                "color": QColor(color),
                "width": width,
                "is_highlight": is_highlight,
            }
        )
        self._active_stroke = []
        self._current_stroke_meta = None

    def clear(self):
        """清理PinnedPaintLayer的绘画数据"""
        try:
            # 停止并清理painter
            if hasattr(self, 'pixPainter') and self.pixPainter:
                try:
                    self.pixPainter.end()
                except:
                    pass
                self.pixPainter = None
            
            # 清理pixmap
            empty_pix = QPixmap(1, 1)
            empty_pix.fill(Qt.transparent)
            self.setPixmap(empty_pix)
            
            # ⚠️ 断开循环引用 - 防止内存泄漏
            self._parent_widget = None
            self.main_window = None
            
            # 调用父类清理
            super().clear()
            
        except Exception as e:
            print(f"⚠️ PinnedPaintLayer清理时出错: {e}")

class Freezer(QLabel):
    def __init__(self, parent=None, img=None, x=0, y=0, listpot=0, main_window=None):
        super().__init__()
        self.main_window = main_window  # 保存主截图窗口的引用
        
        # 初始化安全状态标记
        self._is_closed = False  # 标记窗口是否已关闭
        self._should_cleanup = False  # 标记是否应该被清理
        self._is_editing = False  # 标记是否正在编辑
        self.closed = False  # QPainter安全标记
        
        # 删除原来的侧边工具栏
        
        self.tips_shower = TipsShower(" ",(QApplication.desktop().width()//2,50,120,50))
        self.tips_shower.hide()
        
        # 内存优化：只保留 layer_document，删除冗余的 origin_imgpix 和 showing_imgpix
        # 底图存储在 layer_document._base_pixmap 中，需要时从 layer_document 渲染
        self.layer_document = VectorLayerDocument(img)
        
        self.listpot = listpot
        
        # 设置图像（从 layer_document 渲染）
        if img and not img.isNull():
            self.setPixmap(img)
        else:
            # 如果图像无效，直接报错而不是创建无意义的空白图
            raise ValueError("钉图窗口初始化失败: 传入的图像为空或无效")
        
        self.settingOpacity = False
        self.setWindowOpacity(1.0)  # 设置为完全不透明
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        # 关闭时自动删除，避免悬挂对象
        try:
            self.setAttribute(Qt.WA_DeleteOnClose, True)
        except Exception:
            pass
        self.setMouseTracking(True)
        self.drawRect = True
        # self.setContextMenuPolicy(Qt.CustomContextMenu)
        if img and not img.isNull():
            self.setGeometry(x, y, img.width(), img.height())
        
        # 初始化DPI记录
        self.initialize_dpi_tracking()
        self._last_dpi_check_at = 0.0
        
        # === 创建绘画层，完全照搬截图窗口的逻辑 ===
        self.paintlayer = PinnedPaintLayer(self, self.main_window)
        if img and not img.isNull():
            self.paintlayer.setGeometry(0, 0, img.width(), img.height())
        self.paintlayer.show()
        
        # 创建右上角的关闭按钮
        self.close_button = QPushButton('×', self)
        self.close_button.setFixedSize(20, 20)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 0, 0, 180);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 220);
            }
            QPushButton:pressed {
                background-color: rgba(200, 0, 0, 220);
            }
        """)
        self.close_button.setToolTip("关闭钉图窗口 (ESC)")
        self.close_button.clicked.connect(self.close_window_with_esc)
        self.close_button.hide()  # 初始隐藏，鼠标悬停时显示
        
        # 更新关闭按钮位置
        self.update_close_button_position()
        
        self.show()
        self.drag = self.resize_the_window = False
        self.is_drawing_drag = False  # 添加绘画拖拽标志
        self.resize_direction = None  # 调整大小的方向
        self.resize_start_pos = QPoint()  # 调整大小开始的位置
        self.resize_start_geometry = QRect()  # 调整大小开始时的几何信息
        self.on_top = True
        self.p_x = self.p_y = 0
        # self.setMaximumSize(QApplication.desktop().size())
        self.timer = QTimer(self)  # 创建一个定时器
        self.timer.setInterval(200)  # 设置定时器的时间间隔为200ms
        self.timer.timeout.connect(self.check_mouse_leave)  # 定时器超时时触发check_mouse_leave函数
        
        # 创建延迟隐藏工具栏的定时器
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)  # 只触发一次
        self.hide_timer.setInterval(500)  # 0.5秒延迟
        self.hide_timer.timeout.connect(self._hide_toolbar_delayed)
        
        # 删除原来的侧边工具栏信号连接
        # self.hung_widget.button_signal.connect(self.hw_signalcallback)
        # self.hung_widget.show()
        
        self.move(x, y)
        
        # 添加右键菜单状态标志，防止菜单显示时触发工具栏重新布局
        self._context_menu_active = False
        
        # 初始化备份系统（改为矢量状态）
        self.backup_pic_list = []
        self.backup_ssid = -1
        self._capture_history_state(initial=True)
        
        # 异步触发 OCR 文字识别层
        self._init_ocr_text_layer_async()
    
    def _is_auto_toolbar_enabled(self):
        """读取设置，判断是否应自动显示钉图工具栏。"""
        try:
            slabel = getattr(self, 'main_window', None)
            if slabel is not None:
                host = getattr(slabel, 'parent', None)
                config_manager = getattr(host, 'config_manager', None)
                if config_manager is not None:
                    return config_manager.get_pinned_auto_toolbar()
        except Exception as e:
            print(f"⚠️ 钉图工具栏设置读取失败: {e}")
        return True
    
    def _check_drawing_status(self) -> bool:
        """检查是否处于绘图模式（供 OCR 文字层回调）"""
        try:
            if self.main_window and hasattr(self.main_window, 'painter_tools'):
                # 检查是否有任何绘图工具被激活 (值为1)
                return 1 in self.main_window.painter_tools.values()
        except Exception:
            pass
        return False

    def _init_ocr_text_layer_async(self):
        """异步初始化 OCR 文字选择层（不阻塞主线程）"""
        try:
            from PyQt5.QtCore import QThread
            from PyQt5.QtWidgets import QMessageBox
            from jietuba_ocr import _ocr_manager, is_ocr_available, initialize_ocr
            from jietuba_ocr_text_layer import OCRTextLayer
            
            # 检查 OCR 功能是否被启用（从设置读取）
            ocr_enabled = False
            # 注意：RapidOCR Python API 自动支持多语言识别，无需指定语言
            enable_grayscale = True  # 默认启用灰度
            enable_upscale = False   # 默认不启用放大
            upscale_factor = 1.5     # 默认放大1.5倍
            try:
                slabel = getattr(self, 'main_window', None)
                if slabel is not None:
                    host = getattr(slabel, 'parent', None)
                    config_manager = getattr(host, 'config_manager', None)
                    if config_manager is not None:
                        ocr_enabled = config_manager.get_ocr_enabled()
                        enable_grayscale = config_manager.get_ocr_grayscale_enabled()
                        enable_upscale = config_manager.get_ocr_upscale_enabled()
                        upscale_factor = config_manager.get_ocr_upscale_factor()
            except Exception as e:
                print(f"⚠️ [OCR] 读取 OCR 设置失败: {e}")
            
            # 如果 OCR 功能被禁用，直接返回
            if not ocr_enabled:
                print("ℹ️ [OCR] OCR 功能已禁用，跳过初始化")
                return
            
            # 检查 OCR 是否可用
            if not is_ocr_available():
                print("⚠️ [OCR] OCR 模块不可用（无OCR版本或未安装模块），静默跳过")
                # 静默跳过，不显示弹窗（无OCR版本的友好处理）
                # 用户可以在设置页面看到 OCR 模块状态
                return
            
            # 初始化 OCR 引擎（自动支持多语言）
            init_result = initialize_ocr()
            if not init_result:
                print(f"⚠️ [OCR] OCR 引擎初始化失败，静默跳过")
                # 静默跳过，不显示弹窗
                # 如果用户真的需要OCR功能，会在设置页面看到相关提示
                return
            
            print(f"✅ [OCR] OCR 引擎已就绪（支持中日韩英混合识别）")
            
            # 创建透明文字层
            self.ocr_text_layer = OCRTextLayer(self)
            self.ocr_text_layer.setGeometry(0, 0, self.width(), self.height())
            # 设置动态检查回调
            self.ocr_text_layer.is_drawing_callback = self._check_drawing_status
            # 启用文字层（这会触发 _apply_effective_enabled）
            self.ocr_text_layer.set_enabled(True)
            
            # 创建异步 OCR 识别线程
            class OCRThread(QThread):
                def __init__(self, pixmap, enable_grayscale, enable_upscale, upscale_factor, parent=None):
                    super().__init__(parent)
                    self.pixmap = pixmap
                    self.enable_grayscale = enable_grayscale
                    self.enable_upscale = enable_upscale
                    self.upscale_factor = upscale_factor
                    self.result = None
                
                def run(self):
                    try:
                        self.result = _ocr_manager.recognize_pixmap(
                            self.pixmap, 
                            return_format="dict",
                            enable_grayscale=self.enable_grayscale,
                            enable_upscale=self.enable_upscale,
                            upscale_factor=self.upscale_factor
                        )
                    except Exception as e:
                        print(f"❌ [OCR Thread] 识别失败: {e}")
                        self.result = None
            
            # 获取钉图的图像
            if hasattr(self, 'layer_document'):
                pixmap = self.layer_document.render_composited()
            else:
                pixmap = self.pixmap()
            
            # 保存原始尺寸用于归一化坐标
            original_width = pixmap.width()
            original_height = pixmap.height()
            
            # 启动异步识别
            self.ocr_thread = OCRThread(pixmap, enable_grayscale, enable_upscale, upscale_factor, self)
            
            def on_ocr_finished():
                try:
                    # 明确检查 result 是否为字典（避免 numpy 数组的真值判断问题）
                    if self.ocr_thread.result is not None and isinstance(self.ocr_thread.result, dict):
                        if self.ocr_thread.result.get('code') == 100:
                            # 加载 OCR 结果到文字层（传入原始尺寸用于归一化）
                            self.ocr_text_layer.load_ocr_result(
                                self.ocr_thread.result, 
                                original_width, 
                                original_height
                            )
                            print(f"✅ [OCR] 钉图文字层已就绪，识别到 {len(self.ocr_thread.result.get('data', []))} 个文字块")
                except Exception as e:
                    print(f"❌ [OCR] 加载结果失败: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    # 清理线程
                    if hasattr(self, 'ocr_thread'):
                        self.ocr_thread.deleteLater()
                        self.ocr_thread = None
            
            self.ocr_thread.finished.connect(on_ocr_finished)
            self.ocr_thread.start()
            
        except ImportError:
            # OCR 模块不存在，静默跳过
            pass
        except Exception as e:
            print(f"⚠️ [OCR] 初始化失败: {e}")

    # ======================== 矢量绘制辅助 ========================
    def _current_display_size(self) -> Tuple[int, int]:
        if hasattr(self, 'paintlayer') and self.paintlayer:
            return max(1, self.paintlayer.width()), max(1, self.paintlayer.height())
        base = self.layer_document.base_size if hasattr(self, 'layer_document') else QSize(1, 1)
        return max(1, base.width()), max(1, base.height())

    def _normalize_point(self, point: Sequence[float]) -> Tuple[float, float]:
        disp_w, disp_h = self._current_display_size()
        x = 0.0 if disp_w == 0 else max(0.0, min(1.0, float(point[0]) / disp_w))
        y = 0.0 if disp_h == 0 else max(0.0, min(1.0, float(point[1]) / disp_h))
        return (x, y)

    def _normalized_width(self, width_px: float) -> float:
        disp_w, disp_h = self._current_display_size()
        ref = max(1.0, float(min(disp_w, disp_h)))
        return max(0.0, float(width_px) / ref)

    def _trim_history(self, limit: int = 20) -> None:
        if not hasattr(self, 'backup_pic_list'):
            return
        if len(self.backup_pic_list) <= limit:
            return
        overflow = len(self.backup_pic_list) - limit
        self.backup_pic_list = self.backup_pic_list[overflow:]
        self.backup_ssid = max(0, len(self.backup_pic_list) - 1)

    def _render_for_display(self, width: int, height: int) -> Optional[QPixmap]:
        target_size = QSize(max(1, int(width)), max(1, int(height)))
        if hasattr(self, 'layer_document'):
            try:
                return self.layer_document.render_composited(target_size)
            except Exception as e:
                print(f"⚠️ 钉图矢量渲染失败: {e}")
                # 回退：从 layer_document 的 base 渲染
                try:
                    return self.layer_document.render_base(target_size)
                except Exception as e2:
                    print(f"⚠️ 钉图基础渲染也失败: {e2}")
        return None

    def _capture_history_state(self, *, initial: bool = False) -> None:
        snapshot = {
            "mode": "vector",
            "state": self.layer_document.export_state() if hasattr(self, 'layer_document') else [],
        }
        if initial or not hasattr(self, 'backup_pic_list'):
            self.backup_pic_list = []
            self.backup_ssid = -1
        if self.backup_ssid < len(self.backup_pic_list) - 1:
            self.backup_pic_list = self.backup_pic_list[: self.backup_ssid + 1]
        if self.backup_pic_list and self.backup_pic_list[-1].get("mode") == "vector":
            last_state = self.backup_pic_list[-1].get("state")
            current_state = snapshot["state"]
            if last_state == current_state:
                print(f"🔍 钉图备份: 状态未变化，跳过备份 (命令数: {len(current_state)})")
                self.backup_ssid = len(self.backup_pic_list) - 1
                return
            else:
                # 输出差异帮助调试
                print(f"🔍 钉图备份: 状态已变化 - 上次命令数: {len(last_state)}, 当前命令数: {len(current_state)}")
        self.backup_pic_list.append(snapshot)
        self.backup_ssid = len(self.backup_pic_list) - 1
        print(f"✅ 钉图备份: 已创建备份 - 位置: {self.backup_ssid}, 总数: {len(self.backup_pic_list)}, 命令数: {len(snapshot['state'])}")
        self._trim_history()

    def _clear_overlay(self) -> None:
        if hasattr(self, 'paintlayer') and self.paintlayer:
            pix = self.paintlayer.pixmap()
            if pix and not pix.isNull():
                pix.fill(Qt.transparent)
            self.paintlayer.update()

    def _refresh_from_document(self, *, clear_overlay: bool = False) -> None:
        """从矢量文档重新渲染并更新显示。
        
        内存优化：不再缓存 showing_imgpix，直接渲染到显示。
        """
        if not hasattr(self, 'layer_document'):
            return
        try:
            target_w = max(1, self.width())
            target_h = max(1, self.height())
            display = self.layer_document.render_composited(QSize(target_w, target_h))
            self.setPixmap(display)
        except Exception as e:
            print(f"⚠️ 钉图矢量刷新失败: {e}")
        if clear_overlay:
            self._clear_overlay()

    def _apply_history_entry(self, entry: Dict) -> None:
        try:
            mode = entry.get("mode")
            if mode == "vector":
                self.layer_document.import_state(entry.get("state", []))
                
                # 恢复序号计数器：扫描所有序号命令，找到最大序号值
                max_number = 0
                if hasattr(self.layer_document, 'commands'):
                    for cmd in self.layer_document.commands:
                        if cmd.kind == "number" and hasattr(cmd, 'extra') and 'number' in cmd.extra:
                            number = int(cmd.extra.get('number', 0))
                            max_number = max(max_number, number)
                
                # 设置主窗口的序号计数器为最大序号+1
                if hasattr(self, 'main_window') and self.main_window:
                    if max_number > 0:
                        self.main_window.drawnumber_counter = max_number + 1
                        print(f"🔢 钉图序号计数器恢复: 最大序号={max_number}, 下一个序号={self.main_window.drawnumber_counter}")
                    else:
                        self.main_window.drawnumber_counter = 1
                        
            elif mode == "bitmap":
                pixmap = entry.get("pixmap")
                if pixmap and not pixmap.isNull():
                    self.layer_document.set_base_pixmap(pixmap)
                    self.layer_document.clear()
            self._refresh_from_document(clear_overlay=True)
        except Exception as e:
            print(f"⚠️ 钉图历史应用失败: {e}")

    def _after_vector_change(self, *, push_history: bool = True) -> None:
        self._refresh_from_document(clear_overlay=True)
        if push_history:
            self._capture_history_state()

    def notify_external_tool_commit(self, tool_label: str = "") -> None:
        """供截图主窗口回调，确保钉图窗口刷新并写入历史。"""
        try:
            self._refresh_from_document(clear_overlay=False)
            self._capture_history_state()
            if tool_label:
                print(f"📋 钉图矢量历史: 已记录来自{tool_label}的操作")
        except Exception as e:
            print(f"⚠️ 钉图历史通知失败: {e}")

    def ingest_vector_commands(self, payload: List[Dict]) -> None:
        if not payload or not hasattr(self, 'layer_document'):
            return
        changed = False
        for item in payload:
            if item.get("type") != "stroke":
                continue
            points = [self._normalize_point(pt) for pt in item.get("points", [])]
            width_ratio = self._normalized_width(item.get("width", 1))
            color = item.get("color")
            if isinstance(color, QColor):
                qcolor = QColor(color)
            elif color is not None:
                qcolor = QColor(color)
            else:
                qcolor = QColor(255, 0, 0)
            is_highlight = bool(item.get("is_highlight"))
            blend = "multiply" if is_highlight else "normal"
            brush_style = "square" if is_highlight else "round"
            self.layer_document.add_stroke(
                points, qcolor, width_ratio, blend=blend, brush=brush_style
            )
            changed = True
        if changed:
            self._after_vector_change()

    def record_rectangle_command(self, start_pt, end_pt, color, width):
        try:
            self.layer_document.add_rect(
                self._normalize_point(start_pt),
                self._normalize_point(end_pt),
                QColor(color),
                self._normalized_width(width),
            )
            self._after_vector_change()
        except Exception as e:
            print(f"⚠️ 钉图矢量矩形记录失败: {e}")

    def record_circle_command(self, start_pt, end_pt, color, width):
        try:
            self.layer_document.add_circle(
                self._normalize_point(start_pt),
                self._normalize_point(end_pt),
                QColor(color),
                self._normalized_width(width),
            )
            self._after_vector_change()
        except Exception as e:
            print(f"⚠️ 钉图矢量圆形记录失败: {e}")

    def record_arrow_command(self, start_pt, end_pt, color, width):
        try:
            self.layer_document.add_arrow(
                self._normalize_point(start_pt),
                self._normalize_point(end_pt),
                QColor(color),
                self._normalized_width(width),
            )
            self._after_vector_change()
        except Exception as e:
            print(f"⚠️ 钉图矢量箭头记录失败: {e}")

    def record_number_command(self, center, number, text_color, bg_color, size):
        """记录序号标注的矢量命令"""
        try:
            self.layer_document.add_number(
                self._normalize_point(center),
                int(number),
                QColor(text_color),
                QColor(bg_color),
                self._normalized_width(size),
            )
            self._after_vector_change()
        except Exception as e:
            print(f"⚠️ 钉图矢量序号记录失败: {e}")

    def record_text_command(self, anchor_point, text, color, font_size, line_ratio,
                        font_family=None, font_weight=None, font_italic=False):
        try:
            self.layer_document.add_text(
                self._normalize_point(anchor_point),
                text,
                QColor(color),
                self._normalized_width(font_size),
                float(line_ratio),
                font_family=str(font_family) if font_family else "",
                font_weight=int(font_weight) if font_weight is not None else 50,
                font_italic=bool(font_italic),
            )
            self._after_vector_change()
            return True
        except Exception as e:
            print(f"⚠️ 钉图矢量文字记录失败: {e}")
            return False

    def _update_for_resize(self, new_width, new_height):
        """窗口缩放时根据矢量文档重新渲染，保持清晰。"""
        try:
            display = self._render_for_display(new_width, new_height)
            if display is not None:
                self.setPixmap(display)
        except Exception as e:
            print(f"❌ 钉图缩放: 更新失败: {e}")
    
    def update_close_button_position(self):
        """更新关闭按钮的位置到右上角"""
        if hasattr(self, 'close_button'):
            button_size = 20
            margin = 5
            x = self.width() - button_size - margin
            y = margin
            self.close_button.move(x, y)
            self.close_button.raise_()  # 确保按钮在最上层
    
    def close_window_with_esc(self):
        """模拟ESC键关闭窗口"""
        try:
            # 创建ESC键事件
            esc_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
            # 发送ESC事件到窗口
            self.keyPressEvent(esc_event)
        except Exception as e:
            print(f"模拟ESC关闭失败: {e}")
            # 如果模拟ESC失败，直接调用关闭方法
            self.close()
    
    # ========================= 尺寸/缩放同步工具 =========================
    def _sync_paintlayer_on_resize(self, new_w: int, new_h: int):
        """窗口尺寸变化时，同步绘画层几何与已绘制内容的缩放，避免错位。"""
        try:
            if not hasattr(self, 'paintlayer') or self.paintlayer is None:
                return
            pl = self.paintlayer
            # 当前内容
            try:
                cur_pix = pl.pixmap()
            except Exception:
                cur_pix = None

            # 同步几何
            try:
                pl.setGeometry(0, 0, int(new_w), int(new_h))
            except Exception:
                pass

            # 同步内容
            if cur_pix is not None and (not cur_pix.isNull()):
                if cur_pix.width() != int(new_w) or cur_pix.height() != int(new_h):
                    try:
                        scaled = cur_pix.scaled(int(new_w), int(new_h), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                        pl.setPixmap(scaled)
                    except Exception as e:
                        print(f"⚠️ 绘画层内容缩放失败: {e}")
            else:
                # 确保存在透明底
                try:
                    empty = QPixmap(max(1, int(new_w)), max(1, int(new_h)))
                    empty.fill(Qt.transparent)
                    pl.setPixmap(empty)
                except Exception as e:
                    print(f"⚠️ 创建空绘画层失败: {e}")
        except Exception as e:
            print(f"❌ 同步绘画层失败: {e}")
    
    def copy_screenshot_backup_history(self, crop_x, crop_y, crop_w, crop_h,
                                 final_vector_state=None, preserve_current_document=False):
        """
        复制截图窗口的绘制历史到钉图窗口，并进行坐标转换和区域裁剪。
        当提供 final_vector_state 时，会将其作为最终历史节点，确保当前矢量状态保留。
        
        Args:
            crop_x, crop_y: 截图区域的左上角坐标（在全屏坐标系中）
            crop_w, crop_h: 截图区域的宽度和高度
            final_vector_state: 可选的矢量状态快照，用于在历史列表末尾追加矢量节点
            preserve_current_document: 若为 True，则不在复制结束后应用最新历史，以避免覆盖当前矢量文档
        """
        try:
            # 验证矢量文档是否有效
            if not hasattr(self, 'layer_document') or not self.layer_document:
                print("❌ copy_screenshot_backup_history: 矢量文档未初始化，中止历史复制")
                return
            
            # 检查钉图窗口是否已经有自己的备份历史（表示已经进行过绘画操作）
            has_own_history = (hasattr(self, 'backup_pic_list') and 
                             len(self.backup_pic_list) > 1)
            
            if has_own_history:
                print(f"📋 钉图备份: 钉图窗口已有 {len(self.backup_pic_list)} 个备份，跳过历史复制，保持current_ssid={self.backup_ssid}")
                return
            
            source_history = getattr(self.main_window, 'backup_pic_list', None) or []
            source_active_index = getattr(self.main_window, 'backup_ssid', len(source_history) - 1)
            source_active_index = max(0, min(source_active_index, len(source_history) - 1)) if source_history else -1
            if source_history:
                print(f"📋 钉图备份: 开始复制主窗口的 {len(source_history)} 个历史状态")
                # 添加详细调试：显示每个历史的命令数
                for idx, entry in enumerate(source_history):
                    if isinstance(entry, dict) and entry.get("mode") == "overlay":
                        vec_state = entry.get("vector", [])
                        print(f"  - 主窗口历史 {idx}: overlay模式, 矢量命令数={len(vec_state) if vec_state else 0}")
            else:
                print("📋 钉图备份: 主窗口没有绘制历史，使用当前状态作为初始记录")

            converter = getattr(self.main_window, '_convert_backup_entry_for_crop', None)
            self.backup_pic_list = []
            source_index_map = []
            if callable(converter):
                for i, full_backup in enumerate(source_history):
                    converted = converter(full_backup, crop_x, crop_y, crop_w, crop_h)
                    if not converted:
                        print(f"⚠️ 钉图备份: 状态 {i} 无法转换，已跳过")
                        continue
                    cmd_count = len(converted.get("state", [])) if converted.get("mode") == "vector" else "N/A"
                    self.backup_pic_list.append(converted)
                    source_index_map.append(i)
                    print(f"📋 钉图备份: 复制历史状态 {i}, 模式: {converted.get('mode')}, 命令数: {cmd_count}")
            else:
                for i, full_backup in enumerate(source_history):
                    pixmap_candidate = None
                    if isinstance(full_backup, dict):
                        pixmap_candidate = full_backup.get("pixmap")
                    else:
                        pixmap_candidate = full_backup
                    if not pixmap_candidate or pixmap_candidate.isNull():
                        print(f"⚠️ 钉图备份: 状态 {i} 无效")
                        continue
                    cropped_backup = pixmap_candidate.copy(crop_x, crop_y, crop_w, crop_h)
                    if cropped_backup.isNull():
                        print(f"⚠️ 钉图备份: 状态 {i} 裁剪失败")
                        continue
                    self.backup_pic_list.append({"mode": "bitmap", "pixmap": cropped_backup})
                    source_index_map.append(i)
                    print(f"📋 钉图备份: 复制历史状态 {i}, 尺寸: {cropped_backup.width()}x{cropped_backup.height()}")

            if not self.backup_pic_list and not final_vector_state:
                print("📋 钉图备份: 无历史可复制，使用当前图像生成初始状态")
			
            target_pos = None
            if final_vector_state is not None:
                vector_entry = {
                    "mode": "vector",
                    "state": [dict(entry) for entry in final_vector_state],
                }
                if source_active_index >= 0:
                    if source_index_map:
                        for pos, idx in enumerate(source_index_map):
                            if idx == source_active_index:
                                target_pos = pos
                                break
                    if target_pos is None:
                        insert_pos = 0
                        while insert_pos < len(source_index_map) and source_index_map[insert_pos] < source_active_index:
                            insert_pos += 1
                        self.backup_pic_list.insert(insert_pos, vector_entry)
                        source_index_map.insert(insert_pos, source_active_index)
                        target_pos = insert_pos
                        print(f"📋 钉图备份: 为撤销位置 {source_active_index} 插入裁剪后的矢量状态")
                    else:
                        print(f"📋 钉图备份: 将历史位置 {source_active_index} 同步为当前撤销状态（命令数: {len(final_vector_state)}）")
                        self.backup_pic_list[target_pos] = vector_entry
                else:
                    print(f"📋 钉图备份: 创建初始矢量状态（{len(final_vector_state)} 命令）")
                    self.backup_pic_list.append(vector_entry)
                    source_index_map.append(0)
                    target_pos = len(self.backup_pic_list) - 1
            elif not self.backup_pic_list:
                # 没有历史记录，创建初始矢量快照（避免 bitmap 复制）
                print("📋 钉图备份: 创建初始矢量快照")
                if hasattr(self, 'layer_document'):
                    initial_state = self.layer_document.export_state()
                    self.backup_pic_list.append({"mode": "vector", "state": initial_state})
                    source_index_map.append(source_active_index if source_active_index >= 0 else 0)
                else:
                    # 极端回退：无法获取矢量状态，使用 bitmap
                    try:
                        final_pixmap = self.pixmap()
                        if final_pixmap and not final_pixmap.isNull():
                            self.backup_pic_list.append({"mode": "bitmap", "pixmap": final_pixmap.copy()})
                            source_index_map.append(source_active_index if source_active_index >= 0 else 0)
                        else:
                            print("❌ 钉图备份: 无法获取图像，放弃复制")
                            return
                    except Exception as e:
                        print(f"❌ 钉图备份: 创建初始备份失败: {e}")
                        return

            if target_pos is None and source_active_index >= 0 and source_index_map:
                for pos, idx in enumerate(source_index_map):
                    if idx > source_active_index:
                        break
                    target_pos = pos
                if target_pos is None and source_index_map:
                    target_pos = 0

            if self.backup_pic_list:
                if target_pos is None:
                    target_pos = len(self.backup_pic_list) - 1
                self.backup_ssid = max(0, min(target_pos, len(self.backup_pic_list) - 1))
            else:
                self.backup_ssid = -1

            if not preserve_current_document and self.backup_pic_list and self.backup_ssid >= 0:
                self._apply_history_entry(self.backup_pic_list[self.backup_ssid])
            print(f"✅ 钉图备份: 历史复制完成，共 {len(self.backup_pic_list)} 个状态，当前位置: {self.backup_ssid}")
            
        except Exception as e:
            print(f"❌ 钉图备份: 复制历史失败: {e}")
            # 失败时创建基础备份，确保有撤回能力
            if not hasattr(self, 'backup_pic_list') or not self.backup_pic_list:
                self._capture_history_state(initial=True)
                print(f"📋 钉图备份: 创建应急备份状态")
    
    def backup_shortshot(self):
        """钉图窗口的备份方法 - 记录当前矢量状态"""
        try:
            self._capture_history_state()
        except Exception as e:
            print(f"❌ 钉图备份: 创建矢量备份失败: {e}")
    
    def last_step(self):
        """钉图窗口的撤销方法"""
        try:
            if not hasattr(self, 'backup_pic_list') or not self.backup_pic_list:
                print("📋 钉图撤销: 没有备份历史")
                return
            
            # 安全边界检查：确保backup_ssid在有效范围内
            if not hasattr(self, 'backup_ssid'):
                self.backup_ssid = len(self.backup_pic_list) - 1
                print(f"📋 钉图撤销: 初始化backup_ssid为 {self.backup_ssid}")
            
            # 边界保护
            if self.backup_ssid < 0:
                self.backup_ssid = 0
                print(f"📋 钉图撤销: 修正负数backup_ssid为 0")
            elif self.backup_ssid >= len(self.backup_pic_list):
                self.backup_ssid = len(self.backup_pic_list) - 1
                print(f"📋 钉图撤销: 修正超界backup_ssid为 {self.backup_ssid}")
                
            if self.backup_ssid > 0:
                self.backup_ssid -= 1
                entry = self.backup_pic_list[self.backup_ssid]
                self._apply_history_entry(entry)
                self.update()
                print(f"📋 钉图撤销: 撤销到位置 {self.backup_ssid}")
            else:
                print(f"📋 钉图撤销: 已经是第一步，不能再撤销 (backup_ssid={self.backup_ssid})")
                
        except Exception as e:
            print(f"❌ 钉图撤销: 撤销失败: {e}")
            import traceback
            traceback.print_exc()
    
    def next_step(self):
        """钉图窗口的前进方法"""
        try:
            if not hasattr(self, 'backup_pic_list') or not self.backup_pic_list:
                print("📋 钉图前进: 没有备份历史")
                return
            
            # 安全边界检查：确保backup_ssid在有效范围内
            if not hasattr(self, 'backup_ssid'):
                self.backup_ssid = len(self.backup_pic_list) - 1
                print(f"📋 钉图前进: 初始化backup_ssid为 {self.backup_ssid}")
            
            # 边界保护
            if self.backup_ssid < 0:
                self.backup_ssid = 0
                print(f"📋 钉图前进: 修正负数backup_ssid为 0")
            elif self.backup_ssid >= len(self.backup_pic_list):
                self.backup_ssid = len(self.backup_pic_list) - 1
                print(f"📋 钉图前进: 修正超界backup_ssid为 {self.backup_ssid}")
                
            if self.backup_ssid < len(self.backup_pic_list) - 1:
                self.backup_ssid += 1
                entry = self.backup_pic_list[self.backup_ssid]
                self._apply_history_entry(entry)
                self.update()
                print(f"📋 钉图前进: 前进到位置 {self.backup_ssid}")
            else:
                print(f"📋 钉图前进: 已经是最新步骤，不能再前进 (backup_ssid={self.backup_ssid})")
                
        except Exception as e:
            print(f"❌ 钉图前进: 前进失败: {e}")
            import traceback
            traceback.print_exc()

    def initialize_dpi_tracking(self):
        """初始化DPI跟踪"""
        try:
            # 获取当前显示器
            screens = QApplication.screens()
            current_screen = None
            g = self.geometry()
            window_center_x = g.x() + g.width() // 2
            window_center_y = g.y() + g.height() // 2
            # 调试：输出用于判定的中心点
            # print(f"[DPI调试] center={window_center_x},{window_center_y} geo=({g.x()},{g.y()},{g.width()}x{g.height()})")
            
            for screen in screens:
                geometry = screen.geometry()
                if (window_center_x >= geometry.x() and window_center_x < geometry.x() + geometry.width() and
                    window_center_y >= geometry.y() and window_center_y < geometry.y() + geometry.height()):
                    current_screen = screen
                    break
            
            if current_screen:
                self._last_dpi = current_screen.devicePixelRatio()
                print(f"钉图窗口初始DPI: {self._last_dpi}")
            else:
                self._last_dpi = 1.0
                print("钉图窗口: 无法确定初始DPI，使用默认值1.0")
                
        except Exception as e:
            print(f"DPI初始化失败: {e}")
            self._last_dpi = 1.0

    def ocr(self):
        # OCR功能已移除
        print("⚠️ OCR機能は現在利用できません。")
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(None, "OCR機能", "OCR機能は現在利用できません。by李")
        return
        
        # 原OCR实现已注释 - 如需恢复请取消注释并安装依赖
        # if self.ocr_status == "ocr":
        #     # 移除了認識をキャンセル提示
        #     self.ocr_status = "abort"
        #     self.Loading_label.stop()
        #     self.text_shower.hide()
        #     self.showing_imgpix = self.origin_imgpix
        #     self.setPixmap(self.showing_imgpix.scaled(self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        #     
        #     return
        # elif self.ocr_status == "show":#正在展示结果,取消展示
        #     # 移除了文字認識を終了提示
        #     self.ocr_status = "waiting"
        #     self.Loading_label.stop()
        #     self.text_shower.hide()
        #     self.showing_imgpix = self.origin_imgpix
        #     self.setPixmap(self.showing_imgpix.scaled(self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        #     return
        # self.ocr_status = "ocr"
        # if not os.path.exists("j_temp"):
        #     os.mkdir("j_temp")
        # self.pixmap().save("j_temp/tempocr.png", "PNG")
        # cv_image = cv2.imread("j_temp/tempocr.png")
        # from jampublic import CONFIG_DICT
        # self.ocrthread = OcrimgThread(cv_image, lang=CONFIG_DICT.get('ocr_lang', 'ch'))
        # self.ocrthread.result_show_signal.connect(self.ocr_res_signalhandle)
        # self.ocrthread.boxes_info_signal.connect(self.orc_boxes_info_callback)
        # self.ocrthread.det_res_img.connect(self.det_res_img_callback)
        # self.ocrthread.start()
        # self.Loading_label = Loading_label(self)
        # self.Loading_label.setGeometry(0, 0, self.width(), self.height())
        # self.Loading_label.start()
        # 
        # self.text_shower.setPlaceholderText("認識中、お待ちください...")
        # self.text_shower.move(self.x(), self.y()+self.height()+10)  # 向下移动10像素
        # self.text_shower.show()
        # self.text_shower.clear()
        # QApplication.processEvents()
        
    def contextMenuEvent(self, event):
        # 标记右键菜单正在显示，防止其他事件干扰
        self._context_menu_active = True
        # 停止计时器，防止菜单显示时触发工具栏隐藏
        if hasattr(self, 'timer') and self.timer is not None:
            try:
                self.timer.stop()
            except Exception as e:
                print(f"⚠️ [定时器警告] 右键菜单停止定时器失败: {e}")
        
        menu = QMenu(self)
        quitAction = menu.addAction("終了")
        saveaction = menu.addAction('名前を付けて保存')
        copyaction = menu.addAction('コピー')
        # ocrAction = menu.addAction('文字認識')  # OCR功能已删除，注释掉此按钮
        paintaction = None
        if not self._is_auto_toolbar_enabled():
            paintaction = menu.addAction('ツールバー')
        topaction = menu.addAction('(キャンセル)最前面表示')
        rectaction = menu.addAction('(キャンセル)枠線')

        action = menu.exec_(self.mapToGlobal(event.pos()))
        
        # 标记右键菜单已结束
        self._context_menu_active = False
        
        # 如果用户没有选择退出，重新启动计时器以恢复正常的工具栏隐藏逻辑
        if action != quitAction and action is not None:
            if (hasattr(self, 'timer') and self.timer is not None and 
                not getattr(self, 'closed', False) and 
                not getattr(self, '_is_closed', False)):
                try:
                    self.timer.start()
                except Exception as e:
                    print(f"⚠️ [定时器警告] 右键菜单后启动定时器失败: {e}")
        elif action is None:
            # 用户取消了菜单（点击空白区域），重新启动计时器
            if (hasattr(self, 'timer') and self.timer is not None and 
                not getattr(self, 'closed', False) and 
                not getattr(self, '_is_closed', False)):
                try:
                    self.timer.start()
                except Exception as e:
                    print(f"⚠️ [定时器警告] 取消菜单后启动定时器失败: {e}")
        
        if action == quitAction:
            # 延迟执行清理操作，避免立即刷新界面导致菜单消失
            QTimer.singleShot(100, self.clear)
        elif action == saveaction:
            print("🔍 [调试] 开始处理钉图窗口保存操作")
            
            # 设置保存状态标志，防止意外关闭
            self._is_saving = True
            # 同时设置一个全局标志，防止任何清理操作
            self._prevent_clear = True
            
            if hasattr(self, 'layer_document') and self.layer_document:
                try:
                    # 停止所有可能导致清理的定时器
                    if hasattr(self, 'timer') and self.timer:
                        self.timer.stop()
                    if hasattr(self, 'hide_timer') and self.hide_timer:
                        self.hide_timer.stop()
                    
                    # 合并原图和绘画内容创建最终图像
                    final_img = self._create_merged_image()
                    print("🔍 [调试] 准备打开保存对话框")
                    
                    # 获取当前窗口位置和状态，保存对话框关闭后恢复
                    current_pos = self.pos()
                    current_visible = self.isVisible()
                    
                    path, l = QFileDialog.getSaveFileName(self, "另存为", QStandardPaths.writableLocation(
                        QStandardPaths.PicturesLocation), "png Files (*.png);;"
                                                          "jpg file(*.jpg);;jpeg file(*.JPEG);; bmp file(*.BMP );;ico file(*.ICO);;"
                                                          ";;all files(*.*)")
                    
                    print(f"🔍 [调试] 保存对话框返回结果: path='{path}', type='{l}'")
                    
                    # 确保窗口状态正确恢复
                    if current_visible and not self.isVisible():
                        print("🔍 [调试] 恢复窗口显示状态")
                        self.show()
                        self.move(current_pos)
                        self.raise_()
                    
                    if path:
                        print(f"🔍 [调试] 开始保存图像到: {path}")
                        final_img.save(path)
                        self.tips_shower.set_pos(self.x(),self.y())
                        # 移除了画像を保存しました提示
                        print(f"✅ 钉图窗口已保存到: {path}")
                        print("🔍 [调试] 保存完成，应该保持窗口开启状态")
                        # 注意：保存后不关闭窗口，保持钉图状态
                    else:
                        print("🔍 [调试] 用户取消了保存操作")
                        
                except Exception as e:
                    print(f"❌ [调试] 保存过程中出错: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    # 恢复定时器
                    if (hasattr(self, 'timer') and self.timer and not self.closed and 
                        not getattr(self, '_is_closed', False)):
                        try:
                            self.timer.start()
                        except:
                            pass
                    
                    # 清除所有保存状态标志
                    self._is_saving = False
                    self._prevent_clear = False
                    print("🔍 [调试] 保存操作完全结束，恢复正常状态")
            else:
                self._is_saving = False
                self._prevent_clear = False
                print("❌ [调试] 没有可保存的图像数据")
        elif action == copyaction:
            clipboard = QApplication.clipboard()
            try:
                if hasattr(self, 'layer_document') and self.layer_document:
                    # 合并原图和绘画内容创建最终图像
                    final_img = self._create_merged_image()
                    clipboard.setPixmap(final_img)
                    self.tips_shower.set_pos(self.x(),self.y())
                    # 移除了画像をコピーしました提示
                    print("✅ 已复制包含绘画内容的完整图像到剪贴板")
                else:
                    print('画像が存在しません')
            except Exception as e:
                print(f'コピー失敗: {e}')
        # elif action == ocrAction:  # OCR功能已删除，注释掉相关处理逻辑
        #     self.tips_shower.set_pos(self.x(),self.y())
        #     # 移除了文字识别中提示
        #     self.ocr()
        elif paintaction and action == paintaction:
            if self.main_window and hasattr(self.main_window, 'show_toolbar_for_pinned_window'):
                print("🎨 通过右键菜单手动显示钉图工具栏")
                self.main_window.show_toolbar_for_pinned_window(self)
            else:
                print("⚠️ 无法显示工具栏: 未找到主窗口或接口")
        elif action == topaction:
            self.change_ontop()
        elif action == rectaction:
            self.drawRect = not self.drawRect
            self.update()
            
    def _create_merged_image(self):
        """创建包含绘画内容的完整图像"""
        try:
            if not hasattr(self, 'layer_document'):
                print("⚠️ 矢量文档未初始化")
                # 回退到当前显示的pixmap
                fallback = self.pixmap()
                return fallback if fallback and not fallback.isNull() else QPixmap()

            target_size = QSize(max(1, self.width()), max(1, self.height()))
            merged_img = self.layer_document.render_composited(target_size)

            # 叠加仍在绘画层上的临时内容（例如还未提交的笔迹）
            if hasattr(self, 'paintlayer') and self.paintlayer and hasattr(self.paintlayer, 'pixmap'):
                paint_content = self.paintlayer.pixmap()
                if paint_content and not paint_content.isNull():
                    painter = QPainter(merged_img)
                    painter.setRenderHint(QPainter.Antialiasing)
                    if paint_content.size() != target_size:
                        painter.drawPixmap(
                            0,
                            0,
                            paint_content.scaled(
                                target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                            ),
                        )
                    else:
                        painter.drawPixmap(0, 0, paint_content)
                    painter.end()
            print(f"✅ 成功创建合并图像，尺寸: {merged_img.width()}x{merged_img.height()}")
            return merged_img
            
        except Exception as e:
            print(f"❌ 创建合并图像失败: {e}")
            # 出错时回退到当前显示的pixmap
            fallback = self.pixmap()
            return fallback if fallback and not fallback.isNull() else QPixmap()
            
    def change_ontop(self):
        if self.on_top:
            self.on_top = False
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.setWindowFlag(Qt.Tool, False)
            self.show()
        else:
            self.on_top = True
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.setWindowFlag(Qt.Tool, True)
            self.show()
    def setWindowOpacity(self,opacity):
        super().setWindowOpacity(opacity)
        
    def wheelEvent(self, e):
        if self.isVisible():
            angleDelta = e.angleDelta() / 8
            dy = angleDelta.y()
            if self.settingOpacity:
                if dy > 0:
                    if (self.windowOpacity() + 0.1) <= 1:
                        self.setWindowOpacity(self.windowOpacity() + 0.1)
                    else:
                        self.setWindowOpacity(1)
                elif dy < 0 and (self.windowOpacity() - 0.1) >= 0.11:
                    self.setWindowOpacity(self.windowOpacity() - 0.1)
            else:
                # 检查是否有绘画工具激活且主窗口存在
                if (self.main_window and hasattr(self.main_window, 'painter_tools') and 
                    hasattr(self.main_window, 'tool_width') and 1 in self.main_window.painter_tools.values()):
                    
                    # 调整画笔/文字大小（复制截图窗口的逻辑）
                    if dy > 0:
                        self.main_window.tool_width += 1
                    elif self.main_window.tool_width > 1:
                        self.main_window.tool_width -= 1
                    
                    # 如果有size_slider，同步更新
                    if hasattr(self.main_window, 'size_slider'):
                        self.main_window.size_slider.setValue(self.main_window.tool_width)
                    
                    # 如果有Tipsshower，显示提示
                    if hasattr(self.main_window, 'Tipsshower'):
                        # 移除了大小提示
                        pass
                    
                    # 如果文字工具激活，更新文字框字体（复制截图窗口的逻辑）
                    if (hasattr(self.main_window, 'painter_tools') and 
                        self.main_window.painter_tools.get('drawtext_on', 0) and 
                        hasattr(self.main_window, 'text_box')):
                        self.main_window.text_box.setFont(QFont('', self.main_window.tool_width))
                        self.main_window.text_box.textAreaChanged()
                    
                    print(f"🎨 [钉图滚轮] 画笔大小调整为: {self.main_window.tool_width}px")
                    
                elif 2 * QApplication.desktop().width() >= self.width() >= 50:
                    # 原来的缩放逻辑
                    # 获取鼠标所在位置相对于窗口的坐标
                    old_pos = e.pos()
                    old_width = self.width()
                    old_height = self.height()
                    w = self.width() + dy * 5
                    if w < 50: w = 50
                    if w > 2 * QApplication.desktop().width(): w = 2 * QApplication.desktop().width()
                    
                    aspect_source = None
                    if hasattr(self, 'layer_document'):
                        aspect_source = self.layer_document.base_size
                    if aspect_source:
                        scale = aspect_source.height() / max(1, aspect_source.width())
                    else:
                        scale = self.height() / max(1, self.width())
                    h = int(w * scale)
                    display = self._render_for_display(w, h)
                    if display is not None:
                        self.setPixmap(display)
                    self.resize(w, h)
                    # 同步绘画层（几何与内容）
                    self._sync_paintlayer_on_resize(int(w), int(h))
                    delta_x = -(w - old_width)*old_pos.x()/old_width
                    delta_y = -(h - old_height)*old_pos.y()/old_height
                    self.move(self.x() + delta_x, self.y() + delta_y)
                    QApplication.processEvents()

            self.update()
    def _clamp_position_to_virtual_desktop(self, x: int, y: int) -> Tuple[int, int]:
        """将窗口位置限制在虚拟桌面范围内，防止移动到极端坐标。"""
        screens = QApplication.screens()
        if not screens:
            return int(x), int(y)

        margin = 200  # 允许适度超出屏幕边缘，避免看起来被“吸附”
        left = min(screen.geometry().x() for screen in screens) - margin
        top = min(screen.geometry().y() for screen in screens) - margin
        right = max(screen.geometry().x() + screen.geometry().width() for screen in screens) + margin
        bottom = max(screen.geometry().y() + screen.geometry().height() for screen in screens) + margin

        max_x = right - self.width()
        max_y = bottom - self.height()
        if max_x < left:
            max_x = left
        if max_y < top:
            max_y = top

        clamped_x = max(left, min(int(x), max_x))
        clamped_y = max(top, min(int(y), max_y))
        if (clamped_x != int(x) or clamped_y != int(y)) and not getattr(self, '_suppress_move_debug', False):
            print(f"⚠️ 钉图窗口位置越界: 请求=({x},{y}) -> 调整为=({clamped_x},{clamped_y})")
        return clamped_x, clamped_y
    def move(self,x,y):
        x, y = self._clamp_position_to_virtual_desktop(x, y)
        super().move(x,y)
        
        # 避免在DPI调整过程中的递归调用
        if getattr(self, '_adjusting_dpi', False):
            return
        
        # 检测DPI变化并调整窗口大小
        self.check_and_adjust_for_dpi_change()
        
        # 如果有主窗口工具栏，更新其位置
        if self.main_window and hasattr(self.main_window, 'position_toolbar_for_pinned_window'):
            # 检查是否有保存的显示器信息，如果没有则重新获取
            if not hasattr(self, 'target_screen'):
                if hasattr(self.main_window, 'get_screen_for_point'):
                    self.target_screen = self.main_window.get_screen_for_point(
                        self.x() + self.width() // 2, self.y() + self.height() // 2)
            
            # 如果钉图窗口移动到了其他显示器，更新工具栏位置
            if hasattr(self, 'target_screen'):
                current_screen = self.main_window.get_screen_for_point(
                    self.x() + self.width() // 2, self.y() + self.height() // 2)
                if current_screen != self.target_screen:
                    self.target_screen = current_screen
                    print(f"钉图窗口移动到新显示器: {current_screen.geometry().getRect()}")
            
            self.main_window.position_toolbar_for_pinned_window(self)

    def _force_post_switch_resize(self, scale_changed: bool, new_scale: float):
        """显示器切换后模拟一次滚轮缩放，强制刷新钉图窗口尺寸。"""
        try:
            base_w = self.width()
            base_h = self.height()
            if hasattr(self, 'layer_document'):
                base_size = self.layer_document.base_size
                img_ratio = base_size.height() / max(1, base_size.width())
            else:
                img_ratio = base_h / max(1, base_w)
            if scale_changed:
                # 与基础缩放比较（如果有）
                base_scale = getattr(self, '_base_scale', new_scale)
                # 高->低 缩小一点，低->高 放大一点
                factor = 0.94 if new_scale < base_scale else 1.06
            else:
                factor = 1.0  # 不改变尺寸，仅刷新
            new_w = int(base_w * factor)
            if new_w < 50: new_w = 50
            if new_w > 2 * QApplication.desktop().width():
                new_w = 2 * QApplication.desktop().width()
            new_h = int(new_w * img_ratio)
            # 仅在需要时调整尺寸，不输出调试
            display = self._render_for_display(new_w, new_h)
            if display is not None:
                self.setPixmap(display)
            self.resize(new_w, new_h)
            self._sync_paintlayer_on_resize(new_w, new_h)
            QApplication.processEvents()
        except Exception as e:
            print(f"⚠️ 模拟滚轮调整失败: {e}")
    
    def check_and_adjust_for_dpi_change(self):
        """检测DPI变化并调整窗口大小 - 防止重复触发版本"""
        try:
            # 如果正在调整中，避免重复触发
            if getattr(self, '_adjusting_dpi', False):
                return

            # 节流：最多每0.5秒检查一次
            now = time.monotonic()
            last_check = getattr(self, '_last_dpi_check_at', 0.0)
            if now - last_check < 0.5:
                return
            self._last_dpi_check_at = now
                
            # 获取当前显示器
            screens = QApplication.screens()
            current_screen = None
            window_center_x = self.x() + self.width() // 2
            window_center_y = self.y() + self.height() // 2
            
            for screen in screens:
                geometry = screen.geometry()
                if (window_center_x >= geometry.x() and window_center_x < geometry.x() + geometry.width() and
                    window_center_y >= geometry.y() and window_center_y < geometry.y() + geometry.height()):
                    current_screen = screen
                    break
            
            if current_screen is None:
                return
            
            # 获取当前显示器的DPI和缩放信息
            current_dpi = current_screen.devicePixelRatio()
            logical_dpi = current_screen.logicalDotsPerInch()
            physical_dpi = current_screen.physicalDotsPerInch()
            
            # 计算Windows系统缩放比例
            system_scale = logical_dpi / 96.0  # Windows基准DPI是96
            screen_geometry_rect = current_screen.geometry().getRect()
            
            # 检查是否有保存的缩放信息
            if not hasattr(self, '_last_scale_info'):
                self._last_scale_info = {
                    'dpi': current_dpi,
                    'logical_dpi': logical_dpi,
                    'system_scale': system_scale,
                    'screen_geometry': screen_geometry_rect
                }
                # 保存原始图像信息作为基准
                if hasattr(self, 'layer_document') and self.layer_document:
                    # 使用图像的原始尺寸，不受当前显示缩放影响
                    base_size = self.layer_document.base_size
                    self._base_img_size = (base_size.width(), base_size.height())
                    # 记录初始显示尺寸和对应的缩放
                    self._base_display_size = (self.width(), self.height())
                    self._base_scale = system_scale
                else:
                    self._base_img_size = (800, 600)
                    self._base_display_size = (self.width(), self.height())
                    self._base_scale = system_scale
                    
                # 初次建立基准信息，不再冗余输出
                return
            
            # 检查是否发生了显示器切换（重要：只有屏幕几何变化才调整）
            last_screen = self._last_scale_info.get('screen_geometry')
            last_scale = self._last_scale_info.get('system_scale', 1.0)
            
            screen_changed = screen_geometry_rect != last_screen
            # 缩放变化阈值放宽到 0.05，提高灵敏度
            scale_changed = abs(system_scale - last_scale) > 0.05

            # 只要屏幕几何变了就视为切换；缩放是否变化决定是否重算尺寸
            if screen_changed:
                # 显示器切换，后续自动调整
                
                if hasattr(self, 'layer_document') and self.layer_document:
                    try:
                        # 设置调整标志，防止递归
                        self._adjusting_dpi = True
                        
                        # 基于当前尺寸和相对缩放比例计算理想显示尺寸
                        # 这样可以保留用户手动缩放后的效果
                        
                        # 计算相对缩放比例：旧缩放 / 新缩放
                        scale_ratio = last_scale / system_scale
                        
                        target_width = int(self.width() * scale_ratio)
                        target_height = int(self.height() * scale_ratio)
                        
                        # 获取显示器安全区域
                        screen_geometry = current_screen.geometry()
                        safe_margin = int(100 * system_scale)
                        max_width = screen_geometry.width() - safe_margin
                        max_height = screen_geometry.height() - safe_margin
                        min_size = int(150 * system_scale)
                        
                        # 限制尺寸在安全范围内
                        target_width = max(min_size, min(target_width, max_width))
                        target_height = max(min_size, min(target_height, max_height))
                        
                        current_width = self.width()
                        current_height = self.height()
                        
                        # 计算目标尺寸（调试输出已移除）
                        
                        # 一次性调整到目标尺寸
                        try:
                            # 创建调整后的图像
                            display = self._render_for_display(target_width, target_height)
                            if display is not None:
                                self.setPixmap(display)
                            self.resize(target_width, target_height)
                            # 同步绘画层（几何与内容）
                            self._sync_paintlayer_on_resize(int(target_width), int(target_height))
                            
                            # 检查位置是否需要调整
                            current_pos = self.pos()
                            new_x = current_pos.x()
                            new_y = current_pos.y()
                            
                            if current_pos.x() + target_width > screen_geometry.right():
                                new_x = screen_geometry.right() - target_width
                            if current_pos.y() + target_height > screen_geometry.bottom():
                                new_y = screen_geometry.bottom() - target_height
                            if new_x < screen_geometry.left():
                                new_x = screen_geometry.left()
                            if new_y < screen_geometry.top():
                                new_y = screen_geometry.top()
                            
                            if new_x != current_pos.x() or new_y != current_pos.y():
                                self.move(new_x, new_y)
                            
                            # 切换完成
                            # 触发一次模拟滚轮以强制执行与用户滚轮一致的缩放修正, 解决偶发未刷新
                            self._force_post_switch_resize(scale_changed, system_scale)
                            
                            # 钉图窗口调整完成后，重新生成工具栏以匹配新的DPI
                            if self.main_window and hasattr(self.main_window, 'relayout_toolbar_for_pinned_mode'):
                                # 重新生成工具栏以匹配新DPI
                                self.main_window.relayout_toolbar_for_pinned_mode()
                            
                        except Exception:
                            pass
                        
                    except Exception:
                        pass
                    finally:
                        # 更新保存的缩放信息（重要：防止重复触发）
                        self._last_scale_info = {
                            'dpi': current_dpi,
                            'logical_dpi': logical_dpi,
                            'system_scale': system_scale,
                            'screen_geometry': screen_geometry_rect
                        }
                        # 重新启用moveEvent
                        self._adjusting_dpi = False
                
                # 更新工具栏位置
                if self.main_window and hasattr(self.main_window, 'position_toolbar_for_pinned_window'):
                    self.main_window.position_toolbar_for_pinned_window(self)
            
            # 移动但未跨屏时不需要处理
            elif not screen_changed:
                pass
                
        except Exception as e:
            print(f"❌ DPI调整失败: {e}")
            import traceback
            traceback.print_exc()
        
    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        if hasattr(self,"Loading_label"):
            self.Loading_label.setGeometry(0, 0, self.width(), self.height())
        
        # 缩放时更新底图和备份历史
        self._update_for_resize(self.width(), self.height())
        
        # 任意方式触发的尺寸变化，都同步绘画层
        self._sync_paintlayer_on_resize(self.width(), self.height())
        
        # 同步 OCR 文字层大小
        if hasattr(self, 'ocr_text_layer') and self.ocr_text_layer:
            self.ocr_text_layer.setGeometry(0, 0, self.width(), self.height())
        
        # 更新关闭按钮位置
        self.update_close_button_position()
        
        # 如果钉图窗口大小改变，检查是否需要重新生成工具栏
        if (self.main_window and hasattr(self.main_window, 'relayout_toolbar_for_pinned_mode') and 
            hasattr(self.main_window, 'mode') and self.main_window.mode == "pinned"):
            print(f"📏 钉图窗口尺寸变化: {self.width()}x{self.height()}, 重新生成工具栏")
            self.main_window.relayout_toolbar_for_pinned_mode()
            # 重新定位工具栏
            if hasattr(self.main_window, 'position_toolbar_for_pinned_window'):
                self.main_window.position_toolbar_for_pinned_window(self)
        
    def mousePressEvent(self, event):
        # 先检查是否有绘图工具激活
        has_main_window = self.main_window is not None
        has_mode = hasattr(self.main_window, 'mode') if has_main_window else False
        is_pinned_mode = self.main_window.mode == "pinned" if has_mode else False
        has_painter_tools = hasattr(self.main_window, 'painter_tools') if has_main_window else False
        has_active_tools = False
        if has_painter_tools:
            tools = self.main_window.painter_tools
            has_active_tools = (tools.get('drawtext_on', 0) == 1 or 
                              tools.get('pen_on', 0) == 1 or 
                              tools.get('eraser_on', 0) == 1 or
                              tools.get('arrow_on', 0) == 1 or
                              tools.get('rect_on', 0) == 1 or
                              tools.get('ellipse_on', 0) == 1 or
                              tools.get('line_on', 0) == 1)
        
        # 如果有绘图工具激活，优先处理绘图，不检查文字层
        if not has_active_tools:
            # 没有绘图工具时，检查 OCR 文字层是否应该处理该事件
            if hasattr(self, 'ocr_text_layer') and self.ocr_text_layer:
                # 检查鼠标是否在文字上
                if self.ocr_text_layer._is_pos_on_text(event.pos()):
                    # 直接调用文字层的鼠标事件处理
                    self.ocr_text_layer.mousePressEvent(event)
                    return
                else:
                    # 点击在非文字区域，清除现有选择
                    if self.ocr_text_layer.selection_start or self.ocr_text_layer.selection_end:
                        self.ocr_text_layer.clear_selection()
        
        # 检查是否有主窗口工具栏显示且有绘画工具激活
        # has_main_window = self.main_window is not None (已定义)
        # has_mode, is_pinned_mode, has_painter_tools, has_active_tools 已在上面定义
        
        # 尝试委托给主窗口处理（无论是绘画工具还是选择操作）
        if (has_main_window and has_mode and is_pinned_mode):
            # 记录调用前的状态
            was_selection_active = getattr(self.main_window, 'selection_active', False)
            
            # 构造委托事件
            main_event = QMouseEvent(event.type(), event.pos(), 
                                   event.globalPos(), event.button(), event.buttons(), event.modifiers())
            main_event._from_pinned_window = True
            main_event._pinned_window_instance = self
            
            # 调用主窗口处理
            self.main_window.mousePressEvent(main_event)
            
            # 检查主窗口是否处理了该事件
            # 1. 有激活的绘画工具
            # 2. 进入了选区模式（选中了绘制元素）
            # 3. 之前就是选区模式（正在调整元素）
            is_selection_active = getattr(self.main_window, 'selection_active', False)
            
            if has_active_tools or is_selection_active or was_selection_active:
                # 主窗口处理了事件，我们不再处理窗口拖动
                self.is_drawing_drag = True
                super().mousePressEvent(event)
                return
            
        # print("钉图鼠标按下调试: 条件不满足，使用默认处理")
        # 重置绘画拖拽标志
        self.is_drawing_drag = False
        if event.button() == Qt.LeftButton:
            # 检测边缘区域（8个方向的调整大小）
            edge_size = 10  # 边缘检测区域大小
            x, y = event.x(), event.y()
            w, h = self.width(), self.height()
            
            # 判断在哪个边缘或角落
            on_left = x < edge_size
            on_right = x > w - edge_size
            on_top = y < edge_size
            on_bottom = y > h - edge_size
            
            if on_left or on_right or on_top or on_bottom:
                # 在边缘，准备调整大小
                self.resize_the_window = True
                self.resize_start_pos = event.globalPos()
                self.resize_start_geometry = self.geometry()
                
                # 确定调整方向
                if on_top and on_left:
                    self.resize_direction = 'top-left'
                    self.setCursor(Qt.SizeFDiagCursor)
                elif on_top and on_right:
                    self.resize_direction = 'top-right'
                    self.setCursor(Qt.SizeBDiagCursor)
                elif on_bottom and on_left:
                    self.resize_direction = 'bottom-left'
                    self.setCursor(Qt.SizeBDiagCursor)
                elif on_bottom and on_right:
                    self.resize_direction = 'bottom-right'
                    self.setCursor(Qt.SizeFDiagCursor)
                elif on_left:
                    self.resize_direction = 'left'
                    self.setCursor(Qt.SizeHorCursor)
                elif on_right:
                    self.resize_direction = 'right'
                    self.setCursor(Qt.SizeHorCursor)
                elif on_top:
                    self.resize_direction = 'top'
                    self.setCursor(Qt.SizeVerCursor)
                elif on_bottom:
                    self.resize_direction = 'bottom'
                    self.setCursor(Qt.SizeVerCursor)
            else:
                # 不在边缘，准备拖动窗口
                self.setCursor(Qt.SizeAllCursor)
                self.drag = True
                self.p_x, self.p_y = event.x(), event.y()
                try:
                    self._drag_offset = event.globalPos() - self.pos()
                except Exception:
                    self._drag_offset = QPoint(self.p_x, self.p_y)
            # self.resize(self.width()/2,self.height()/2)
            # self.setPixmap(self.pixmap().scaled(self.pixmap().width()/2,self.pixmap().height()/2))

    def mouseReleaseEvent(self, event):
        # 优先检查 OCR 文字层是否应该处理该事件
        if hasattr(self, 'ocr_text_layer') and self.ocr_text_layer:
            # 检查是否正在选择文字
            if self.ocr_text_layer.is_selecting:
                # 直接调用文字层的鼠标释放事件
                self.ocr_text_layer.mouseReleaseEvent(event)
                return
        
        # 检查是否有主窗口工具栏显示且有绘画工具激活，或者正在进行绘画拖拽
        has_active_tools = False
        if (self.main_window and hasattr(self.main_window, 'painter_tools')):
            tools = self.main_window.painter_tools
            has_active_tools = (tools.get('drawtext_on', 0) == 1 or 
                              tools.get('pen_on', 0) == 1 or 
                              tools.get('eraser_on', 0) == 1 or
                              tools.get('arrow_on', 0) == 1 or
                              tools.get('rect_on', 0) == 1 or
                              tools.get('ellipse_on', 0) == 1 or
                              tools.get('line_on', 0) == 1)
        
        if ((self.main_window and hasattr(self.main_window, 'mode') and 
            self.main_window.mode == "pinned" and has_active_tools) or 
            getattr(self, 'is_drawing_drag', False)):
            # 有绘画工具激活时，将事件传递给主窗口处理
            # 在钉图模式下，直接使用钉图窗口的本地坐标
            main_event = QMouseEvent(event.type(), event.pos(), 
                                   event.globalPos(), event.button(), event.buttons(), event.modifiers())
            # 添加标记表示这是来自钉图窗口的委托事件
            main_event._from_pinned_window = True
            main_event._pinned_window_instance = self  # 添加当前钉图窗口引用
            print(f"钉图委托调试: 调用主窗口mouseReleaseEvent，坐标=({event.x()}, {event.y()})")
            self.main_window.mouseReleaseEvent(main_event)
            # 重置绘画拖拽标志
            self.is_drawing_drag = False
            return
            
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ArrowCursor)
            self.drag = self.resize_the_window = False
            self.resize_direction = None  # 重置调整方向
    def underMouse(self) -> bool:
        return super().underMouse()
    def mouseMoveEvent(self, event):
        # 优先检查 OCR 文字层是否应该处理该事件
        if hasattr(self, 'ocr_text_layer') and self.ocr_text_layer:
            # 检查是否正在选择文字或鼠标在文字上
            if self.ocr_text_layer.is_selecting or self.ocr_text_layer._is_pos_on_text(event.pos()):
                # 直接调用文字层的鼠标移动事件
                self.ocr_text_layer.mouseMoveEvent(event)
                # 如果不是正在选择，也要处理窗口的其他逻辑（如显示关闭按钮）
                if not self.ocr_text_layer.is_selecting:
                    if hasattr(self, 'close_button') and self.close_button is not None:
                        self.close_button.show()
                return
        
        # 显示关闭按钮（当鼠标在窗口内时）
        if hasattr(self, 'close_button') and self.close_button is not None:
            self.close_button.show()
        
        # 解析按钮状态
        left_pressed = event.buttons() & Qt.LeftButton
        
        # 检查是否有主窗口工具栏显示且有绘画工具激活，或者正在进行绘画拖拽
        has_active_tools = False
        if (self.main_window and hasattr(self.main_window, 'painter_tools')):
            tools = self.main_window.painter_tools
            has_active_tools = (tools.get('drawtext_on', 0) == 1 or 
                              tools.get('pen_on', 0) == 1 or 
                              tools.get('eraser_on', 0) == 1 or
                              tools.get('arrow_on', 0) == 1 or
                              tools.get('rect_on', 0) == 1 or
                              tools.get('ellipse_on', 0) == 1 or
                              tools.get('line_on', 0) == 1)
        
        if ((self.main_window and hasattr(self.main_window, 'mode') and 
            self.main_window.mode == "pinned" and has_active_tools) or 
            getattr(self, 'is_drawing_drag', False)):
            # 有绘画工具激活时，将事件传递给主窗口处理
            # 在钉图模式下，直接使用钉图窗口的本地坐标
            main_event = QMouseEvent(event.type(), event.pos(), 
                                   event.globalPos(), event.button(), event.buttons(), event.modifiers())
            # 添加标记表示这是来自钉图窗口的委托事件
            main_event._from_pinned_window = True
            main_event._pinned_window_instance = self  # 添加当前钉图窗口引用
            self.main_window.mouseMoveEvent(main_event)
            return
            
        if self.isVisible():
            if self.drag:
                if hasattr(self, '_drag_offset') and isinstance(self._drag_offset, QPoint):
                    global_pos = event.globalPos()
                    new_pos = global_pos - self._drag_offset
                    self.move(new_pos.x(), new_pos.y())
                else:
                    self.move(event.x() + self.x() - self.p_x, event.y() + self.y() - self.p_y)
                # 拖拽移动时检查DPI变化
                self.check_and_adjust_for_dpi_change()
            elif self.resize_the_window:
                # 处理八个方向的调整大小（所有方向都保持宽高比）
                if not hasattr(self, 'resize_direction'):
                    return
                    
                delta = event.globalPos() - self.resize_start_pos
                geometry = self.resize_start_geometry
                
                # 获取原始图像的宽高比
                if hasattr(self, 'layer_document') and self.layer_document:
                    base_size = self.layer_document.base_size
                    aspect_ratio = base_size.height() / base_size.width()
                else:
                    aspect_ratio = geometry.height() / geometry.width()
                
                # 最小尺寸限制
                min_size = 50
                
                # 根据不同方向计算新的几何参数
                new_x = geometry.x()
                new_y = geometry.y()
                new_w = geometry.width()
                new_h = geometry.height()
                
                direction = self.resize_direction
                
                # 计算宽度变化（用于所有方向）
                if 'left' in direction:
                    # 从左边调整：宽度减少
                    new_w = geometry.width() - delta.x()
                elif 'right' in direction:
                    # 从右边调整：宽度增加
                    new_w = geometry.width() + delta.x()
                elif direction == 'top':
                    # 从上边调整：根据高度变化计算宽度
                    new_h = geometry.height() - delta.y()
                    new_w = int(new_h / aspect_ratio)
                elif direction == 'bottom':
                    # 从下边调整：根据高度变化计算宽度
                    new_h = geometry.height() + delta.y()
                    new_w = int(new_h / aspect_ratio)
                
                # 应用最小尺寸限制
                if new_w < min_size:
                    new_w = min_size
                
                # 根据宽度计算高度（保持宽高比）
                new_h = int(new_w * aspect_ratio)
                
                if new_h < min_size:
                    new_h = min_size
                    new_w = int(new_h / aspect_ratio)
                
                # 调整位置（如果从左边或上边调整）
                if 'left' in direction:
                    new_x = geometry.x() + geometry.width() - new_w
                if 'top' in direction:
                    new_y = geometry.y() + geometry.height() - new_h
                
                # 应用新的几何参数
                self.setGeometry(new_x, new_y, new_w, new_h)
                
                # 缩放并更新图像
                display = self._render_for_display(new_w, new_h)
                if display is not None:
                    self.setPixmap(display)
                
                # 同步绘画层（几何与内容）
                self._sync_paintlayer_on_resize(int(new_w), int(new_h))
            else:
                # 没有拖动或调整大小时，更新鼠标光标
                edge_size = 10
                x, y = event.x(), event.y()
                w, h = self.width(), self.height()
                
                on_left = x < edge_size
                on_right = x > w - edge_size
                on_top = y < edge_size
                on_bottom = y > h - edge_size
                
                if (on_top and on_left) or (on_bottom and on_right):
                    self.setCursor(Qt.SizeFDiagCursor)
                elif (on_top and on_right) or (on_bottom and on_left):
                    self.setCursor(Qt.SizeBDiagCursor)
                elif on_left or on_right:
                    self.setCursor(Qt.SizeHorCursor)
                elif on_top or on_bottom:
                    self.setCursor(Qt.SizeVerCursor)
                else:
                    self.setCursor(Qt.ArrowCursor)
    def enterEvent(self,e):
        super().enterEvent(e)
        if hasattr(self, 'timer') and self.timer and not self.closed:
            self.timer.stop()
        # 停止延迟隐藏定时器（如果正在运行）
        if hasattr(self, 'hide_timer') and self.hide_timer is not None:
            if self.hide_timer.isActive():
                print("🕐 鼠标重新进入，停止延迟隐藏定时器")
                self.hide_timer.stop()
        # 如果右键菜单正在显示，不触发工具栏重新布局
        if getattr(self, '_context_menu_active', False):
            return
            
        if not self._is_auto_toolbar_enabled():
            return

        # 只有在工具栏未显示时才显示工具栏，避免重复初始化导致二级菜单被隐藏
        if self.main_window and hasattr(self.main_window, 'show_toolbar_for_pinned_window'):
            # 检查工具栏是否已经显示
            if (hasattr(self.main_window, 'botton_box') and 
                not self.main_window.botton_box.isVisible()):
                print("🔧 工具栏未显示，重新显示工具栏")
                self.main_window.show_toolbar_for_pinned_window(self)
            else:
                # 工具栏已经显示，只需要确保它是可见的，不要重新初始化
                if hasattr(self.main_window, 'botton_box'):
                    self.main_window.botton_box.show()
                    self.main_window.botton_box.raise_()
                    print("🔧 工具栏已存在，仅确保可见性")
            
    def leaveEvent(self,e):
        super().leaveEvent(e)
        
        # 隐藏关闭按钮（当鼠标离开窗口时）
        if hasattr(self, 'close_button') and self.close_button is not None:
            self.close_button.hide()
        
        # 如果右键菜单正在显示，不启动计时器
        if not getattr(self, '_context_menu_active', False):
            # 检查timer是否还存在且有效，且窗口未关闭
            if (hasattr(self, 'timer') and self.timer is not None and 
                not getattr(self, 'closed', False) and 
                not getattr(self, '_is_closed', False)):
                try:
                    self.timer.start()
                except Exception as e:
                    print(f"⚠️ [定时器警告] 启动定时器失败: {e}")
            else:
                print("⚠️ [定时器警告] timer不可用，跳过启动")
        self.settingOpacity = False
        
    def _hide_toolbar_delayed(self):
        """延迟隐藏工具栏的方法"""
        # 再次检查鼠标位置，确保仍然不在窗口或工具栏上
        if not self.underMouse():
            if self.main_window and hasattr(self.main_window, 'is_toolbar_under_mouse'):
                if not self.main_window.is_toolbar_under_mouse():
                    # 检查是否有绘画工具激活，如果有则不隐藏工具栏
                    if (hasattr(self.main_window, 'painter_tools') and 
                        1 in self.main_window.painter_tools.values()):
                        print("绘画工具激活中，不隐藏工具栏")
                        return
                    
                    # 检查是否有二级菜单正在显示且处于活跃状态
                    if (hasattr(self.main_window, 'paint_tools_menu') and 
                        self.main_window.paint_tools_menu.isVisible()):
                        # 检查二级菜单是否有焦点或者鼠标刚刚在其上
                        print("二级菜单正在显示，暂不隐藏工具栏")
                        return
                    
                    # 检查是否刚刚点击了绘画工具按钮（给用户一些反应时间）
                    current_time = QTimer().remainingTime() if hasattr(QTimer(), 'remainingTime') else 0
                    
                    # 执行隐藏工具栏
                    if hasattr(self.main_window, 'hide_toolbar_for_pinned_window'):
                        print("🔒 0.5秒延迟后隐藏钉图工具栏")
                        self.main_window.hide_toolbar_for_pinned_window()

    def check_mouse_leave(self):
        # 如果右键菜单正在显示，不执行隐藏操作
        if getattr(self, '_context_menu_active', False):
            return
            
        # 检查是否离开钉图窗口和主工具栏
        if not self.underMouse():
            if self.main_window and hasattr(self.main_window, 'is_toolbar_under_mouse'):
                if not self.main_window.is_toolbar_under_mouse():
                    # 检查是否有绘画工具激活，如果有则应该更谨慎地处理隐藏逻辑
                    if (hasattr(self.main_window, 'painter_tools') and 
                        1 in self.main_window.painter_tools.values()):
                        print("绘画工具激活中，检查是否真的需要隐藏工具栏")
                        
                        # 当绘画工具激活时，只有在鼠标明确远离工作区域时才隐藏工具栏
                        # 检查鼠标是否在钉图窗口的合理范围内（包括一定的缓冲区）
                        cursor_pos = QCursor.pos()
                        window_rect = self.geometry()
                        # 扩大检测范围，给用户更多的操作空间
                        buffer_zone = 50
                        from PyQt5.QtCore import QRect
                        extended_rect = QRect(
                            window_rect.x() - buffer_zone,
                            window_rect.y() - buffer_zone,
                            window_rect.width() + 2 * buffer_zone,
                            window_rect.height() + 2 * buffer_zone
                        )
                        
                        if extended_rect.contains(cursor_pos):
                            print("鼠标仍在工作区域附近，保持工具栏显示")
                            return
                        
                        # 即使要隐藏，也给更长的延迟时间
                        if hasattr(self, 'hide_timer') and self.hide_timer is not None:
                            print("🕐 绘画工具激活时延长隐藏延迟到2秒")
                            self.hide_timer.setInterval(2000)  # 延长到2秒
                            self.hide_timer.start()
                        
                        if (hasattr(self, 'timer') and self.timer is not None and 
                            not getattr(self, 'closed', False) and 
                            not getattr(self, '_is_closed', False)):
                            try:
                                self.timer.stop()
                            except Exception as e:
                                print(f"⚠️ [定时器警告] 绘画工具激活时停止定时器失败: {e}")
                        return
                    
                    # 检查是否有右键菜单正在显示（通过检查当前活动窗口）
                    active_window = QApplication.activeWindow()
                    if active_window and "QMenu" in str(type(active_window)):
                        print("右键菜单正在显示，延迟隐藏工具栏")
                        QTimer.singleShot(500, self.check_mouse_leave)  # 500ms后再次检查
                        return
                    
                    # 普通情况下启动0.5秒延迟隐藏定时器
                    if hasattr(self, 'hide_timer') and self.hide_timer is not None:
                        print("🕐 启动0.5秒延迟隐藏工具栏定时器")
                        self.hide_timer.setInterval(500)  # 重置为默认的0.5秒
                        self.hide_timer.start()
                    
                    # 安全停止检查定时器
                    if hasattr(self, 'timer') and self.timer is not None:
                        try:
                            self.timer.stop()
                        except Exception as e:
                            print(f"⚠️ [定时器警告] 停止定时器失败: {e}")
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.clear()
        elif e.key() == Qt.Key_Control:
            self.settingOpacity = True
        elif self.settingOpacity:  # 如果已经按下了ctrl
            if e.key() == Qt.Key_Z:  # Ctrl+Z 撤回
                print("🔄 [钉图窗口] 检测到 Ctrl+Z，执行撤回")
                self.last_step()
            elif e.key() == Qt.Key_Y:  # Ctrl+Y 重做
                print("🔄 [钉图窗口] 检测到 Ctrl+Y，执行重做")
                self.next_step()

    def keyReleaseEvent(self, e) -> None:
        if e.key() == Qt.Key_Control:
            self.settingOpacity = False

    def paintEvent(self, event):
        super().paintEvent(event)
        
        # 钉图窗口只负责绘制边框，绘画内容由paintlayer处理
        if self.drawRect:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(64, 224, 208), 1, Qt.SolidLine))
            painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
            painter.end()

    def clear(self):
        print(f"🧹 [内存清理] 开始清理钉图窗口 (listpot={self.listpot})")
        
        # 添加调用栈追踪，找出是谁调用了clear()
        import traceback
        stack_trace = traceback.format_stack()
        print("🔍 [调用栈] clear() 被调用的完整路径：")
        for i, frame in enumerate(stack_trace[-5:]):  # 只显示最后5个调用栈
            print(f"   {i}: {frame.strip()}")
        
        # 检查是否正在保存，如果是则拒绝清理
        if hasattr(self, '_is_saving') and self._is_saving:
            print("🚫 [内存清理] 正在保存中，拒绝执行清理操作")
            return
            
        # 检查是否有防清理标志
        if hasattr(self, '_prevent_clear') and self._prevent_clear:
            print("🚫 [内存清理] 检测到防清理标志，拒绝执行清理操作")
            return
        
        # 立即标记为已关闭，防止后续绘画操作
        self.closed = True
        
        # 立即停止所有绘画工具，防止QPainter冲突
        if self.main_window:
            try:
                # 停止所有绘画工具激活状态
                if hasattr(self.main_window, 'painter_tools'):
                    for key in self.main_window.painter_tools:
                        self.main_window.painter_tools[key] = 0
                
                # 清空所有绘画点列表
                if hasattr(self.main_window, 'pen_pointlist'):
                    self.main_window.pen_pointlist.clear()
                if hasattr(self.main_window, 'drawrect_pointlist'):
                    self.main_window.drawrect_pointlist = [[-2, -2], [-2, -2], 0]
                if hasattr(self.main_window, 'drawcircle_pointlist'):
                    self.main_window.drawcircle_pointlist = [[-2, -2], [-2, -2], 0]
                if hasattr(self.main_window, 'drawarrow_pointlist'):
                    self.main_window.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
                if hasattr(self.main_window, 'drawtext_pointlist'):
                    self.main_window.drawtext_pointlist.clear()
                    
                print(f"🧹 [内存清理] 已停止所有绘画操作")
            except Exception as e:
                print(f"⚠️ 停止绘画操作时出错: {e}")
        
        # 记录清理前的内存使用
        try:
            import importlib, os
            psutil = importlib.import_module("psutil")
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            print(f"📊 [内存监控] 清理前内存: {memory_before:.1f} MB")
        except Exception:
            memory_before = None
        
        # 标记为已关闭，防止后续操作
        self._is_closed = True
        self._is_editing = False
        
        # 停止所有定时器
        if hasattr(self, 'timer') and self.timer:
            self.timer.stop()
            self.timer.deleteLater()
            self.timer = None
            print(f"🧹 [内存清理] 定时器已停止并删除")
        
        # 停止延迟隐藏定时器
        if hasattr(self, 'hide_timer') and self.hide_timer:
            self.hide_timer.stop()
            self.hide_timer.deleteLater()
            self.hide_timer = None
            print(f"🧹 [内存清理] 延迟隐藏定时器已停止并删除")
        
        # 清理图像数据 - 注意：不再使用 origin_imgpix 和 showing_imgpix，仅清理 OCR 相关图片
        if hasattr(self, 'ocr_res_imgpix') and self.ocr_res_imgpix:
            self.ocr_res_imgpix = None
            print(f"🧹 [内存清理] ocr_res_imgpix已清理")
        
        # 清理QPixmap相关属性
        if hasattr(self, '_cached_pixmap'):
            self._cached_pixmap = None
        if hasattr(self, '_scaled_pixmap'):
            self._scaled_pixmap = None
        
        # 清理工具栏 - 解决ESC后工具栏残留的问题
        if hasattr(self, 'toolbar') and self.toolbar:
            try:
                self.toolbar.hide()
                self.toolbar.deleteLater()
                self.toolbar = None
                print(f"🧹 [内存清理] 工具栏已清理")
            except Exception as e:
                print(f"⚠️ 清理工具栏时出错: {e}")
        
        # 通知主窗口隐藏钉图工具栏（新版工具栏在主窗口上）
        # ⚠️ 重要：只有当前钉图窗口是正在编辑的窗口时，才隐藏工具栏
        # 因为可能有多个钉图窗口，工具栏可能正在编辑另一个窗口
        if self.main_window and hasattr(self.main_window, 'hide_toolbar_for_pinned_window'):
            try:
                # 检查当前窗口是否是主窗口正在编辑的钉图窗口
                is_current = (hasattr(self.main_window, 'current_pinned_window') and 
                             self.main_window.current_pinned_window == self)
                
                if is_current:
                    self.main_window.hide_toolbar_for_pinned_window()
                    print(f"🧹 [内存清理] 已隐藏工具栏 (当前编辑窗口 listpot={self.listpot} 被关闭)")
                else:
                    current_window_id = getattr(self.main_window.current_pinned_window, 'listpot', '无') if hasattr(self.main_window, 'current_pinned_window') and self.main_window.current_pinned_window else '无'
                    print(f"🧹 [内存清理] 跳过隐藏工具栏 (关闭窗口 listpot={self.listpot}, 当前编辑窗口={current_window_id})")
            except Exception as e:
                print(f"⚠️ 隐藏主窗口工具栏时出错: {e}")
            
        self.clearMask()
        self.hide()
        
        # 停止并清理 OCR 线程，避免线程持有引用导致泄露
        if hasattr(self, 'ocrthread') and self.ocrthread:
            try:
                try:
                    # 断开信号连接
                    self.ocrthread.result_show_signal.disconnect()
                except Exception:
                    pass
                try:
                    self.ocrthread.boxes_info_signal.disconnect()
                except Exception:
                    pass
                try:
                    self.ocrthread.det_res_img.disconnect()
                except Exception:
                    pass
                # 请求线程退出
                try:
                    self.ocrthread.requestInterruption()
                except Exception:
                    pass
                try:
                    self.ocrthread.quit()
                except Exception:
                    pass
                try:
                    # 等待短时间确保退出
                    self.ocrthread.wait(500)
                except Exception:
                    pass
                try:
                    self.ocrthread.deleteLater()
                except Exception:
                    pass
            except Exception as e:
                print(f"⚠️ 清理OCR线程时出错: {e}")
            finally:
                self.ocrthread = None

        # 清理Loading_label
        if hasattr(self,"Loading_label") and self.Loading_label:
            try:
                self.Loading_label.stop()
                self.Loading_label.deleteLater()
                self.Loading_label = None
                print(f"🧹 [内存清理] Loading_label已清理")
            except Exception as e:
                print(f"⚠️ 清理Loading_label时出错: {e}")
        
        # 清理text_shower
        if hasattr(self, 'text_shower') and self.text_shower:
            try:
                self.text_shower.clear()
                self.text_shower.hide()
                self.text_shower.deleteLater()
                self.text_shower = None
                print(f"🧹 [内存清理] text_shower已清理")
            except Exception as e:
                print(f"⚠️ 清理text_shower时出错: {e}")
        
        # 清理tips_shower
        if hasattr(self, 'tips_shower') and self.tips_shower:
            try:
                self.tips_shower.hide()
                self.tips_shower.deleteLater()
                self.tips_shower = None
                print(f"🧹 [内存清理] tips_shower已清理")
            except Exception as e:
                print(f"⚠️ 清理tips_shower时出错: {e}")
        
        # 清理paintlayer
        if hasattr(self, 'paintlayer') and self.paintlayer:
            try:
                # 调用paintlayer的clear方法进行安全清理
                if hasattr(self.paintlayer, 'clear'):
                    self.paintlayer.clear()
                else:
                    # 备用清理方法
                    self.paintlayer.hide()
                    self.paintlayer.clear()
                
                self.paintlayer.deleteLater()
                self.paintlayer = None
                print(f"🧹 [内存清理] paintlayer已清理")
            except Exception as e:
                print(f"⚠️ 清理paintlayer时出错: {e}")
        
        # 清理备份历史（图像数据）
        if hasattr(self, 'backup_pic_list'):
            try:
                self.backup_pic_list.clear()
                self.backup_pic_list = []
                print(f"🧹 [内存清理] backup_pic_list已清理")
            except Exception as e:
                print(f"⚠️ 清理backup_pic_list时出错: {e}")
        
        # 清理 origin_imgpix 和 showing_imgpix（已废弃，不再使用）
        
        # 清理关闭按钮
        if hasattr(self, 'close_button') and self.close_button:
            try:
                self.close_button.deleteLater()
                self.close_button = None
                print(f"🧹 [内存清理] close_button已清理")
            except Exception as e:
                print(f"⚠️ 清理close_button时出错: {e}")
        
        # 清理主窗口的文字输入框（如果被独立出来了）
        # 必须在清理子控件之前执行，否则如果text_box是子控件会被误删
        if self.main_window and hasattr(self.main_window, 'text_box'):
            try:
                self.main_window.text_box.hide()
                self.main_window.text_box.clear()
                # 如果文字框处于独立窗口状态，将其恢复为主窗口的子组件
                self.main_window.text_box.setParent(self.main_window)
                self.main_window.text_box.setWindowFlags(Qt.Widget)
                print(f"🧹 [内存清理] 主窗口文字框已重置")
            except Exception as e:
                print(f"⚠️ 清理主窗口文字框时出错: {e}")

        # 清理所有可能的子控件
        for child in self.findChildren(QWidget):
            try:
                child.setParent(None)  # 先解除父子关系
                child.deleteLater()
            except Exception:
                pass
        
        # 强制处理所有待删除的对象
        try:
            QApplication.processEvents()
            print(f"🧹 [内存清理] Qt事件已处理，待删除对象已清理")
        except Exception as e:
            print(f"⚠️ 处理Qt事件时出错: {e}")
        
        # 清理主窗口的绘画数据列表 - 防止累积
        if self.main_window:
            try:
                # 清理绘画点列表
                if hasattr(self.main_window, 'pen_pointlist'):
                    self.main_window.pen_pointlist.clear()
                if hasattr(self.main_window, 'drawrect_pointlist'):
                    self.main_window.drawrect_pointlist = [[-2, -2], [-2, -2], 0]
                if hasattr(self.main_window, 'drawcircle_pointlist'):
                    self.main_window.drawcircle_pointlist = [[-2, -2], [-2, -2], 0]
                if hasattr(self.main_window, 'drawarrow_pointlist'):
                    self.main_window.drawarrow_pointlist = [[-2, -2], [-2, -2], 0]
                if hasattr(self.main_window, 'drawtext_pointlist'):
                    self.main_window.drawtext_pointlist.clear()
                    
                print(f"🧹 [内存清理] 主窗口绘画数据已清理")
            except Exception as e:
                print(f"⚠️ 清理主窗口绘画数据时出错: {e}")
        
        # 清理QLabel的pixmap内容
        try:
            self.setPixmap(QPixmap())
            print(f"🧹 [内存清理] 窗口pixmap已重置为空")
        except Exception as e:
            print(f"⚠️ 重置pixmap时出错: {e}")
        
        # 清理父类内容
        try:
            super().clear()
        except Exception as e:
            print(f"⚠️ 调用父类clear时出错: {e}")
        
        # 断开所有引用，避免循环引用
        self.main_window = None
        self.parent = None
        
        # 立即强制垃圾回收，不等待系统调度
        import gc
        
        # 多次垃圾回收确保彻底清理（包括循环引用）
        for i in range(3):
            collected = gc.collect()
            if i == 0 and collected > 0:
                print(f"🗑️ [垃圾回收] 第{i+1}次回收: 清理了 {collected} 个对象")
            if collected > 0:
                print(f"🧹 [强制回收] 第{i+1}次垃圾回收释放了 {collected} 个对象")
        
        # 强制处理Qt事件队列，确保deleteLater生效
        try:
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
            # 再次垃圾回收
            collected = gc.collect()
            if collected > 0:
                print(f"🧹 [Qt事件后] 额外回收了 {collected} 个对象")
        except Exception:
            pass
        
        print(f"🧹 [内存清理] 钉图窗口清理完成")

    def closeEvent(self, e):
        """窗口关闭事件 - 激进的内存回收"""
        print(f"🔒 [关闭事件] 钉图窗口关闭事件触发 (listpot={self.listpot})")
        
        # 检查是否正在保存，如果是则阻止关闭
        if hasattr(self, '_is_saving') and self._is_saving:
            print("🚫 [关闭事件] 正在保存中，阻止窗口关闭")
            e.ignore()
            return
        
        # 防止重复关闭
        if hasattr(self, '_is_closed') and self._is_closed:
            super().closeEvent(e)
            return
        
        # 立即从主窗口的列表中移除自己
        main_window_ref = self.main_window  # 保存引用
        if main_window_ref and hasattr(main_window_ref, 'freeze_imgs'):
            try:
                if self in main_window_ref.freeze_imgs:
                    main_window_ref.freeze_imgs.remove(self)
                    print(f"✅ [关闭事件] 已从主窗口列表中移除钉图窗口 (剩余: {len(main_window_ref.freeze_imgs)})")
                    
                    # 如果当前窗口是主窗口正在编辑的钉图，需要清除引用
                    if (hasattr(main_window_ref, 'current_pinned_window') and 
                        main_window_ref.current_pinned_window == self):
                        print(f"🧹 [关闭事件] 清除主窗口的 current_pinned_window 引用")
                        main_window_ref.current_pinned_window = None
                    
                    # 如果这是最后一个窗口，执行深度清理
                    if len(main_window_ref.freeze_imgs) == 0:
                        print("🧹 [最后窗口] 执行深度内存清理...")
                        # 多次垃圾回收确保彻底清理
                        import gc
                        for _ in range(3):
                            gc.collect()
                        try:
                            from PyQt5.QtCore import QCoreApplication
                            QCoreApplication.processEvents()
                        except:
                            pass
                        print("🧹 [最后窗口] 深度内存清理完成")
                        
            except (ValueError, AttributeError) as ex:
                print(f"⚠️ 从列表移除时出错: {ex}")
        
        # 断开循环引用 - 防止内存泄漏
        self.main_window = None
        
        # 立即执行清理，不等待
        try:
            self.clear()
        except Exception as ex:
            print(f"⚠️ 清理过程中出错: {ex}")
        
        # 立即隐藏和断开连接
        self.hide()
        self.setParent(None)
        
        # 调用父类的closeEvent
        super().closeEvent(e)
        
        # 立即删除，不等待定时器
        self.deleteLater()
        
        # 立即强制处理删除事件和垃圾回收
        try:
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
            import gc
            gc.collect()
        except:
            pass
        
        print(f"🔒 [关闭事件] 钉图窗口已立即删除")


