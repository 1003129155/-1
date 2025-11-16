"""
jietuba_toolbar.py - 工具栏管理模块

负责截图工具的工具栏初始化、布局、显示和隐藏等功能。
包括：
- 工具栏UI初始化
- 工具栏按钮布局
- 工具栏定位（多显示器支持）
- 钉图模式工具栏管理
- 绘画工具二级菜单管理
"""

from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QCursor, QFont
from PyQt5.QtWidgets import QApplication, QPushButton

from jietuba_ui_components import _enumerate_monitor_dpi
from jietuba_public import resource_path


class ToolbarManager:
    """工具栏管理器 - 负责工具栏的所有功能"""
    
    def init_slabel_ui(self):
        """初始化界面的参数"""
        self.setToolTip("左クリックで選択、右クリックで戻る")

        # 使用左右分布布局：左侧吸附其他按钮，右侧吸附钉图和确定按钮
        btn_width = 45  # 调整按钮宽度（原35）
        btn_height = 45  # 调整按钮高度（原35）
        
        # 左侧按钮从0开始布局
        left_btn_x = 0
        
        # 长截图按钮放在最左边
        self.long_screenshot_btn.setGeometry(left_btn_x, 0, 50, btn_height)  # 调整宽度（原40）
        left_btn_x += 50
        
        # 保存按钮在长截图按钮右边
        self.save_botton.setGeometry(left_btn_x, 0, 50, btn_height)  # 调整宽度（原40）
        self.save_botton.setToolTip('ファイルに保存')
        left_btn_x += 50
        
        # 复制按钮直接跟在保存按钮后面
        self.copy_botton.setGeometry(left_btn_x, 0, 50, btn_height)  # 调整宽度（原40）
        self.copy_botton.setIcon(QIcon(resource_path("svg/copy.svg")))  # 使用专门的复制SVG图标
        self.copy_botton.setIconSize(QSize(36, 36))  # 设置图标大小
        self.copy_botton.setToolTip('画像をコピー')
        self.copy_botton.clicked.connect(self.copy_pinned_image)
        self.copy_botton.hide()  # 默认隐藏,只在钉图模式下显示

        # 画笔工具
        self.pen.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width

        # 荧光笔工具
        self.highlighter.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width

        # 箭头工具
        self.drawarrow.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 矩形工具
        self.bs.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 圆形工具
        self.drawcircle.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 文字工具
        self.drawtext.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 颜色选择
        self.choice_clor_btn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 上一步
        self.lastbtn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 下一步
        self.nextbtn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width

        # 计算工具栏总宽度，为右侧按钮预留空间
        right_buttons_width = 50 + 70  # 钉图按钮50px + 确定按钮70px（原40+60）
        toolbar_total_width = left_btn_x + 20 + right_buttons_width  # 左侧按钮 + 间隔 + 右侧按钮
        
        # 右侧按钮从右往左布局
        right_btn_x = toolbar_total_width - 70  # 确定按钮位置（从右边开始）
        
        # 确定按钮吸附最右边
        self.sure_btn.setGeometry(right_btn_x, 0, 70, btn_height)  # 调整大小（原60x35）
        self.sure_btn.clicked.connect(self.handle_sure_btn_click)
        
        # 钉图按钮在确定按钮左边
        right_btn_x -= 50
        self.freeze_img_botton.setGeometry(right_btn_x, 0, 50, btn_height)  # 调整大小（原40x35）

        # 调整工具栏大小
        self.botton_box.resize(toolbar_total_width, btn_height)
        # 设置工具栏基板样式：白色背景，黑色描边，按钮默认淡背景避免悬停突变
        self.botton_box.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 2px solid #333333;
                border-radius: 6px;
                padding: 2px;
            }
            QPushButton {
                background-color: rgba(0, 0, 0, 0.02);
                border: none;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.08);
                border-radius: 0px;
            }
            QPushButton:pressed {
                background-color: rgba(0, 0, 0, 0.15);
                border-radius: 0px;
            }
        """)
        self.botton_box.hide()

        # 初始化二级菜单的布局和控件
        self.init_paint_tools_menu()

        # 设置钉图按钮的属性 - 使用SVG图标
        self.freeze_img_botton.setIcon(QIcon(resource_path("svg/钉图.svg")))
        self.freeze_img_botton.setIconSize(QSize(32, 32))  # 设置图标大小
        self.freeze_img_botton.setToolTip('画面にピン留め')
        self.freeze_img_botton.clicked.connect(self.freeze_img)
        
        # 设置长截图按钮的属性 - 使用SVG图标
        self.long_screenshot_btn.setIcon(QIcon(resource_path("svg/长截图.svg")))
        self.long_screenshot_btn.setIconSize(QSize(36, 36))  # 设置图标大小
        self.long_screenshot_btn.setToolTip('長スクリーンショット（スクロール）')
        self.long_screenshot_btn.clicked.connect(self.start_long_screenshot_mode)

        # 设置按钮工具提示和图标（这些按钮现在在底部导航栏中） - 使用SVG图标
        self.pen.setToolTip('ペンツール (Shiftキー押しながらで直線)')
        self.pen.setIcon(QIcon(resource_path("svg/画笔.svg")))
        self.pen.setIconSize(QSize(32, 32))  # 设置图标大小
        self.pen.clicked.connect(self.change_pen_fun)

        self.highlighter.setToolTip('蛍光ペン (Shiftキー押しながらで直線)')
        self.highlighter.setIcon(QIcon(resource_path("svg/荧光笔.svg")))
        self.highlighter.setIconSize(QSize(32, 32))  # 调整图标大小（原24x24）
        self.highlighter.clicked.connect(self.change_highlighter_fun)

        self.drawarrow.setToolTip('矢印を描画')
        self.drawarrow.setIcon(QIcon(resource_path("svg/箭头.svg")))
        self.drawarrow.setIconSize(QSize(32, 32))  # 设置图标大小
        self.drawarrow.clicked.connect(self.draw_arrow_fun)
        
        self.bs.setToolTip('矩形を描画')
        self.bs.setIcon(QIcon(resource_path("svg/方框.svg")))
        self.bs.setIconSize(QSize(32, 32))  # 设置图标大小
        self.bs.clicked.connect(self.change_bs_fun)
        
        self.drawcircle.setToolTip('円を描画')
        self.drawcircle.setIcon(QIcon(resource_path("svg/圆框.svg")))
        self.drawcircle.setIconSize(QSize(32, 32))  # 设置图标大小
        self.drawcircle.clicked.connect(self.drawcircle_fun)
        
        self.drawtext.setToolTip('テキストを追加')
        self.drawtext.setIcon(QIcon(resource_path("svg/文字.svg")))
        self.drawtext.setIconSize(QSize(32, 32))  # 设置图标大小
        self.drawtext.clicked.connect(self.drawtext_fun)
        
        self.choice_clor_btn.setToolTip('ペンの色を選択')
        self.choice_clor_btn.setIcon(QIcon(resource_path("svg/颜色设置.svg")))
        self.choice_clor_btn.setIconSize(QSize(32, 32))  # 设置图标大小
        self.choice_clor_btn.clicked.connect(self.get_color)
        # 移除悬停颜色菜单功能
        # self.choice_clor_btn.hoversignal.connect(self.Color_hoveraction)
        
        self.lastbtn.setToolTip('元に戻す')
        self.lastbtn.setIcon(QIcon(resource_path("svg/撤回.svg")))
        self.lastbtn.setIconSize(QSize(32, 32))  # 设置图标大小
        self.lastbtn.clicked.connect(self.last_step)
        
        self.nextbtn.setToolTip('やり直す')
        self.nextbtn.setIcon(QIcon(resource_path("svg/复原.svg")))
        self.nextbtn.setIconSize(QSize(32, 32))  # 设置图标大小
        self.nextbtn.clicked.connect(self.next_step)
        
        self.save_botton.setIcon(QIcon(resource_path("svg/下载.svg")))
        self.save_botton.setIconSize(QSize(36, 36))  # 设置图标大小
        
    def init_paint_tools_menu(self):
        """初始化绘画工具二级菜单"""
        menu_width = 385  # 增加宽度以容纳大型emoji按钮
        menu_height = 60  # 缩小高度
        
        # 设置二级菜单的大小和样式 - 白色背景
        self.paint_tools_menu.resize(menu_width, menu_height)
        self.paint_tools_menu.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QPushButton {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border: 1px solid #bbb;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
            QSlider {
                background-color: transparent;
            }
            QLabel {
                background-color: transparent;
            }
        """)
        
        # 布局调节控件
        # 画笔大小滑动条
        self.size_slider.setGeometry(5, 25, 80, 18)  # 缩小尺寸
        self.size_slider.setOrientation(Qt.Horizontal)
        self.size_slider.setToolTip('ペンのサイズを設定、マウスホイールでも調整可能')
        self.size_slider.valueChanged.connect(self.change_size_fun)
        self.size_slider.setMaximum(99)
        self.size_slider.setValue(5)
        self.size_slider.setMinimum(1)
        
        self.sizetextlabel.setText("大小")
        self.sizetextlabel.setGeometry(5, 5, 30, 16)  # 缩小并重新定位
        self.sizetextlabel.setStyleSheet('color: rgb(51,51,51); font-size: 12px;')  # 改为深灰色，在白色背景上可见
        
        self.size_slider_label.setGeometry(90, 25, 25, 18)  # 调整位置
        self.size_slider_label.setStyleSheet('color: rgb(51,51,51); font-size: 12px;')  # 改为深灰色
        self.size_slider_label.setText("5")
        
        # 透明度滑动条
        self.alpha_slider.setGeometry(130, 25, 80, 18)  # 缩小并重新定位
        self.alpha_slider.setOrientation(Qt.Horizontal)
        self.alpha_slider.setToolTip('ペンの透明度を設定、Ctrl+ホイールでも調整可能')
        self.alpha_slider.valueChanged.connect(self.change_alpha_fun)
        self.alpha_slider.setMaximum(255)
        self.alpha_slider.setValue(255)
        self.alpha_slider.setMinimum(1)
        
        self.alphatextlabel.setText("透明度")
        self.alphatextlabel.setGeometry(130, 5, 50, 16)  # 缩小并重新定位
        self.alphatextlabel.setStyleSheet('color: rgb(51,51,51); font-size: 12px;')  # 改为深灰色
        
        self.alpha_slider_label.setGeometry(215, 25, 30, 18)  # 调整位置
        self.alpha_slider_label.setStyleSheet('color: rgb(51,51,51); font-size: 12px;')  # 改为深灰色
        self.alpha_slider_label.setText("255")
        
        # 设置3个颜色预设按钮 - 水平排列，红黄绿三色
        preset_btn_size = 40   # 正方形按钮，更大更容易点击
        preset_start_x = 250   # 起始位置
        preset_y = 10          # 垂直居中位置
        preset_spacing = 45    # 按钮间距
        
        # 预设1: 红色
        self.preset_btn_1.setGeometry(preset_start_x, preset_y, preset_btn_size, preset_btn_size)
        self.preset_btn_1.setText("●")
        self.preset_btn_1.setToolTip('赤色\n#FF0000')
        self.preset_btn_1.clicked.connect(self.apply_color_preset_red)
        
        # 预设2: 黄色
        self.preset_btn_2.setGeometry(preset_start_x + preset_spacing, preset_y, preset_btn_size, preset_btn_size)
        self.preset_btn_2.setText("●")
        self.preset_btn_2.setToolTip('黄色\n#FFFF00')
        self.preset_btn_2.clicked.connect(self.apply_color_preset_yellow)
        
        # 预设3: 绿色
        self.preset_btn_3.setGeometry(preset_start_x + preset_spacing * 2, preset_y, preset_btn_size, preset_btn_size)
        self.preset_btn_3.setText("●")
        self.preset_btn_3.setToolTip('緑色\n#00FF00')
        self.preset_btn_3.clicked.connect(self.apply_color_preset_green)
        
        # 设置颜色预设按钮样式
        # 红色按钮
        red_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 100, 100, 200), stop:1 rgba(255, 0, 0, 200));
                color: rgb(139, 0, 0);
                border: 3px solid #CC0000;
                border-radius: 8px;
                font-size: 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 120, 120, 240), stop:1 rgba(255, 30, 30, 240));
                border: 3px solid #FF0000;
            }
            QPushButton:pressed {
                background: rgba(255, 0, 0, 250);
                border: 3px solid #AA0000;
            }
        """
        
        # 黄色按钮
        yellow_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 120, 200), stop:1 rgba(255, 255, 0, 200));
                color: rgb(139, 139, 0);
                border: 3px solid #CCCC00;
                border-radius: 8px;
                font-size: 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 150, 240), stop:1 rgba(255, 255, 30, 240));
                border: 3px solid #FFFF00;
            }
            QPushButton:pressed {
                background: rgba(255, 255, 0, 250);
                border: 3px solid #AAAA00;
            }
        """
        
        # 绿色按钮
        green_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(100, 255, 100, 200), stop:1 rgba(0, 255, 0, 200));
                color: rgb(0, 100, 0);
                border: 3px solid #00CC00;
                border-radius: 8px;
                font-size: 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(120, 255, 120, 240), stop:1 rgba(30, 255, 30, 240));
                border: 3px solid #00FF00;
            }
            QPushButton:pressed {
                background: rgba(0, 255, 0, 250);
                border: 3px solid #00AA00;
            }
        """
        
        self.preset_btn_1.setStyleSheet(red_style)
        self.preset_btn_2.setStyleSheet(yellow_style)
        self.preset_btn_3.setStyleSheet(green_style)
        
    def show_paint_tools_menu(self):
        """显示绘画工具二级菜单"""
        if hasattr(self, 'botton_box') and self.botton_box.isVisible():
            # 钉图模式：使用全局坐标与目标屏幕边界
            if hasattr(self, 'mode') and self.mode == 'pinned':
                try:
                    toolbar_pos = self.botton_box.pos()
                    screen = QApplication.screenAt(toolbar_pos)
                    if screen is None:
                        screen = QApplication.primaryScreen()
                    sx, sy, sw, sh = screen.geometry().getRect()

                    menu_x = self.botton_box.x()
                    menu_y_below = self.botton_box.y() + self.botton_box.height() + 5
                    menu_y_above = self.botton_box.y() - self.paint_tools_menu.height() - 5

                    if menu_y_below + self.paint_tools_menu.height() <= sy + sh:
                        menu_y = menu_y_below
                    elif menu_y_above >= sy:
                        menu_y = menu_y_above
                    else:
                        menu_y = min(max(sy, self.botton_box.y()), sy + sh - self.paint_tools_menu.height())

                    if menu_x + self.paint_tools_menu.width() > sx + sw:
                        menu_x = sx + sw - self.paint_tools_menu.width() - 5
                    if menu_x < sx + 5:
                        menu_x = sx + 5

                    self.paint_tools_menu.move(menu_x, menu_y)
                    self.paint_tools_menu.show()
                    self.paint_tools_menu.raise_()
                    # 控制预设按钮的显示 - 只有画笔工具时才显示
                    self.update_preset_buttons_visibility()
                    return
                except Exception as _e:
                    print(f"⚠️ 钉图模式显示画笔菜单失败，退回普通逻辑: {_e}")

            # 截图模式：使用应用窗口坐标
            menu_x = self.botton_box.x()
            
            # 优先尝试显示在工具栏下方
            menu_y_below = self.botton_box.y() + self.botton_box.height() + 5
            menu_y_above = self.botton_box.y() - self.paint_tools_menu.height() - 5
            
            # 检查下方是否有足够空间
            screen_height = QApplication.desktop().height()
            if menu_y_below + self.paint_tools_menu.height() + 20 <= screen_height:
                # 下方有足够空间，优先显示在下方
                menu_y = menu_y_below
            else:
                # 下方空间不足，显示在上方
                menu_y = menu_y_above
                
            # 确保不会超出屏幕左右边界
            screen_width = QApplication.desktop().width()
            if menu_x + self.paint_tools_menu.width() > screen_width:
                menu_x = screen_width - self.paint_tools_menu.width() - 5
            if menu_x < 5:
                menu_x = 5
                
            self.paint_tools_menu.move(menu_x, menu_y)
            self.paint_tools_menu.show()
            self.paint_tools_menu.raise_()
            
        # 控制预设按钮的显示 - 只有画笔工具时才显示
        self.update_preset_buttons_visibility()
    
    def update_preset_buttons_visibility(self):
        """根据当前激活的工具更新预设按钮的显示状态"""
        current_tool = self.get_current_tool()
        # 所有绘图工具都显示颜色预设按钮
        is_drawing_tool = current_tool in ('pen_on', 'highlight_on', 'drawarrow_on', 
                                           'drawrect_bs_on', 'drawcircle_on', 'drawtext_on')
        
        # 所有绘图工具都显示颜色预设按钮
        if hasattr(self, 'preset_btn_1'):
            self.preset_btn_1.setVisible(is_drawing_tool)
        if hasattr(self, 'preset_btn_2'):
            self.preset_btn_2.setVisible(is_drawing_tool)
        if hasattr(self, 'preset_btn_3'):
            self.preset_btn_3.setVisible(is_drawing_tool)
        
        if is_drawing_tool:
            print(f"🎨 [绘图工具] 显示颜色预设按钮 (当前工具: {current_tool})")
        else:
            print(f"🎨 [非绘图工具] 隐藏颜色预设按钮 (当前工具: {current_tool})")
    
    def hide_paint_tools_menu(self):
        """隐藏绘画工具二级菜单"""
        # 检查是否有绘画工具激活，如果有则不隐藏二级菜单
        if hasattr(self, 'painter_tools') and 1 in self.painter_tools.values():
            print("绘画工具激活中，不隐藏二级菜单")
            return
        self.paint_tools_menu.hide()
        # 隐藏菜单时也隐藏预设按钮
        self.update_preset_buttons_visibility()

    # ==================== 钉图窗口工具栏支持方法 ====================
    
    def show_toolbar_for_pinned_window(self, pinned_window):
        """为钉图窗口显示工具栏"""
        if hasattr(self, 'botton_box'):
            # 保存二级菜单的当前状态
            menu_was_visible = False
            if hasattr(self, 'paint_tools_menu') and self.paint_tools_menu is not None:
                menu_was_visible = self.paint_tools_menu.isVisible()
                
            # 让工具栏成为独立的顶级窗口，而不是显示整个截图窗口
            try:
                # 脱离父级，确保成为真正的顶层工具窗口
                self.botton_box.setParent(None)
            except Exception:
                pass
            self.botton_box.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
            # 钉图模式：将画笔设置二级菜单提升为顶层工具窗口，脱离截图窗口
            if hasattr(self, 'paint_tools_menu') and self.paint_tools_menu is not None:
                try:
                    # 暂时隐藏以便重新设置窗口标志
                    self.paint_tools_menu.hide()
                    self.paint_tools_menu.setParent(None)
                    self.paint_tools_menu.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
                except Exception as _e:
                    print(f"⚠️ 提升画笔二级菜单为顶层失败: {_e}")
            
            self.position_toolbar_for_pinned_window(pinned_window)
            self.botton_box.show()
            
            # 如果二级菜单之前是可见的，并且有绘画工具激活，则重新显示它
            if (menu_was_visible and hasattr(self, 'painter_tools') and 
                1 in self.painter_tools.values()):
                print("🎨 恢复二级菜单的显示状态")
                self.show_paint_tools_menu()
            
            # 切换到钉图模式 - 修改一些按钮的功能
            self.mode = "pinned"
            self.current_pinned_window = pinned_window
            
            # 只有在第一次初始化或者模式切换时才重新布局，避免重复布局
            if not hasattr(self, '_pinned_toolbar_initialized') or not self._pinned_toolbar_initialized:
                print("钉图工具栏: 开始初始化布局")
                # 设置编辑环境 - 钉图模式下不需要绘画层覆盖
                if hasattr(self, 'paintlayer'):
                    self.paintlayer.hide()  # 隐藏绘画层，直接在钉图窗口上绘制
                
                    
                # 创建钉图模式的初始备份（只在第一次切换到钉图模式时创建）
                if not hasattr(self, '_pinned_backup_initialized') or not self._pinned_backup_initialized:
                    if hasattr(pinned_window, 'paintlayer') and pinned_window.paintlayer:
                        initial_pixmap = pinned_window.paintlayer.pixmap()
                        if initial_pixmap:
                            from PyQt5.QtGui import QPixmap
                            self.backup_pic_list = [QPixmap(initial_pixmap)]
                            self.backup_ssid = 0
                            self._pinned_backup_initialized = True
                            print("钉图模式: 创建初始备份")
                    else:
                        # 如果没有paintlayer，使用原始图像
                        from PyQt5.QtGui import QPixmap
                        self.backup_pic_list = [QPixmap(pinned_window.showing_imgpix)]
                        self.backup_ssid = 0
                        self._pinned_backup_initialized = True
                        print("钉图模式: 使用原始图像创建初始备份")
                    
                # 设置选择区域为整个钉图窗口
                self.x0, self.y0 = pinned_window.x(), pinned_window.y()
                self.x1, self.y1 = pinned_window.x() + pinned_window.width(), pinned_window.y() + pinned_window.height()
                
                # 设置最终图像为钉图窗口的当前图像
                self.final_get_img = pinned_window.showing_imgpix
                

                # 这里保持内部行为不变，仅不显示该按钮。
                self.sure_btn.setText("閉じる")
                self.sure_btn.setToolTip("ピン留め画像ウィンドウを閉じる")
                # 隐藏按钮
                self.sure_btn.hide()
                
                # 修改智能选区按钮为置顶功能
                self.smartcursor_btn.setToolTip("ピン留め画像の最前面表示を切替")
                if self.current_pinned_window.on_top:
                    self.smartcursor_btn.setStyleSheet("background-color:rgb(50,50,50);")
                else:
                    self.smartcursor_btn.setStyleSheet("")
                
                # 隐藏钉图模式下不需要的按钮
                self.freeze_img_botton.hide()  # 隐藏钉图按钮，避免重复创建窗口
                self.long_screenshot_btn.hide()  # 隐藏长截图按钮,钉图模式下不需要
                
                # 在钉图模式下显示复制按钮
                self.copy_botton.show()
                
                # 隐藏箭头按钮
                if hasattr(self, 'drawarrow'):
                    self.drawarrow.hide()
                
                # 重新布局按钮以移除空隙
                self.relayout_toolbar_for_pinned_mode()
                
                # 恢复绘画工具按钮的视觉状态
                self.restore_painter_tools_visual_state()
                
                # 标记为已初始化
                self._pinned_toolbar_initialized = True
                print("钉图工具栏: 完成初始化布局")
            else:
                print("钉图工具栏: 跳过重复布局，保持现有状态")
    
    def relayout_toolbar_for_pinned_mode(self):
        """重新布局钉图模式下的工具栏按钮 - 支持DPI缩放，移除取色器和箭头，保持左右分布"""
        # 根据当前显示器的DPI缩放调整按钮尺寸（调得更小一些）
        dpi_scale = self.get_current_dpi_scale()
        btn_width = int(32 * dpi_scale)
        btn_height = int(32 * dpi_scale)

        print(f"🔧 工具栏重新布局: DPI缩放={dpi_scale:.2f}, 按钮尺寸={btn_width}x{btn_height}")

        # 左侧按钮收集
        left_buttons = []
        if self.save_botton.isVisible():
            left_buttons.append((self.save_botton, int(30 * dpi_scale)))

        # 在钉图模式下显示复制按钮
        if self.copy_botton.isVisible():
            left_buttons.append((self.copy_botton, int(30 * dpi_scale)))

        paint_buttons = [self.pen, self.highlighter, self.bs, self.drawcircle, self.drawtext, self.choice_clor_btn]
        for btn in paint_buttons:
            if btn.isVisible():
                left_buttons.append((btn, btn_width))

        if self.smartcursor_btn.isVisible():
            left_buttons.append((self.smartcursor_btn, btn_width))
        if self.lastbtn.isVisible():
            left_buttons.append((self.lastbtn, btn_width))
        if self.nextbtn.isVisible():
            left_buttons.append((self.nextbtn, btn_width))

        right_buttons = []

        if self.sure_btn.isVisible():  # 当前逻辑下不会进入
            right_buttons.append((self.sure_btn, int(50 * dpi_scale)))

        left_total_width = sum(w for _, w in left_buttons)
        right_total_width = sum(w for _, w in right_buttons)
        spacing = 20 if left_buttons and right_buttons else 0
        toolbar_total_width = left_total_width + spacing + right_total_width

        # 左侧布局
        cur_x = 0
        for btn, w in left_buttons:
            btn.setGeometry(cur_x, 0, w, btn_height)
            cur_x += w

        # 右侧布局（从右往左）
        right_x = toolbar_total_width
        for btn, w in reversed(right_buttons):
            right_x -= w
            btn.setGeometry(right_x, 0, w, btn_height)

        # 隐藏不需要的按钮（箭头）
        if hasattr(self, 'drawarrow'):
            self.drawarrow.setVisible(False)

        if toolbar_total_width > 0:
            self.botton_box.resize(toolbar_total_width, btn_height)
            print(f"工具栏重新布局完成: {toolbar_total_width}x{btn_height}")

        # 顶层保持与重新定位
        try:
            if getattr(self, 'mode', None) == 'pinned' and getattr(self, 'current_pinned_window', None):
                try:
                    self.botton_box.setParent(None)
                except Exception:
                    pass
                self.botton_box.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
                self.position_toolbar_for_pinned_window(self.current_pinned_window)
                if not self.botton_box.isVisible():
                    self.botton_box.show()
        except Exception as _e:
            print(f"⚠️ 钉图模式重新布局后更新工具栏失败: {_e}")
    
    def get_current_dpi_scale(self):
        """获取当前的DPI缩放比例"""
        try:
            # 获取主窗口当前所在的显示器
            screens = QApplication.screens()
            current_screen = None
            
            # 如果有钉图窗口，使用钉图窗口的显示器
            if hasattr(self, 'freeze_imgs') and self.freeze_imgs:
                pinned_window = self.freeze_imgs[0]  # 取第一个钉图窗口
                window_center_x = pinned_window.x() + pinned_window.width() // 2
                window_center_y = pinned_window.y() + pinned_window.height() // 2
                
                for screen in screens:
                    geometry = screen.geometry()
                    if (window_center_x >= geometry.x() and window_center_x < geometry.x() + geometry.width() and
                        window_center_y >= geometry.y() and window_center_y < geometry.y() + geometry.height()):
                        current_screen = screen
                        break
            
            # 如果没有找到，使用主窗口的显示器
            if current_screen is None:
                window_center_x = self.x() + self.width() // 2
                window_center_y = self.y() + self.height() // 2
                
                for screen in screens:
                    geometry = screen.geometry()
                    if (window_center_x >= geometry.x() and window_center_x < geometry.x() + geometry.width() and
                        window_center_y >= geometry.y() and window_center_y < geometry.y() + geometry.height()):
                        current_screen = screen
                        break
            
            # 如果还是没找到，使用主显示器
            if current_screen is None:
                current_screen = QApplication.primaryScreen()
            
            # 计算DPI缩放比例（使用Windows系统缩放设置）
            try:
                import ctypes
                from ctypes import wintypes
                print("🔍 检测所有显示器DPI (Win32 枚举对比):")
                raw_list = _enumerate_monitor_dpi()
                # 建立 rect->dpi 映射，方便匹配 Qt 屏幕
                for i, raw in enumerate(raw_list):
                    l, t, r, b = raw['rect']
                    print(f"   [Raw{i+1}] rect=({l},{t})~({r},{b}) dpi={raw['dpi_x']} scale={raw['scale']:.2f}")

                # Qt 屏幕中心点测试
                for i, screen in enumerate(screens):
                    g = screen.geometry()
                    cx = g.x() + g.width() // 2
                    cy = g.y() + g.height() // 2
                    try:
                        pt = wintypes.POINT()
                        pt.x = int(cx)
                        pt.y = int(cy)
                        hmon = ctypes.windll.user32.MonitorFromPoint(pt, 2)
                        dpi_x = ctypes.c_uint()
                        dpi_y = ctypes.c_uint()
                        ctypes.windll.shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
                        print(f"   [Qt{i+1}] center=({cx},{cy}) QtGeo=({g.x()},{g.y()},{g.width()}x{g.height()}) -> DPI={dpi_x.value} scale={dpi_x.value/96.0:.2f}")
                    except Exception as _e:
                        print(f"   [Qt{i+1}] center=({cx},{cy}) 检测失败: {_e}")

                # 当前窗口对应显示器 DPI
                pt = wintypes.POINT()
                pt.x = int(window_center_x)
                pt.y = int(window_center_y)
                monitor = ctypes.windll.user32.MonitorFromPoint(pt, 2)
                dpi_x = ctypes.c_uint()
                dpi_y = ctypes.c_uint()
                ctypes.windll.shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
                real_dpi_scale = dpi_x.value / 96.0
                print(f"🔍 当前窗口DPI: center=({window_center_x},{window_center_y}) dpi={dpi_x.value} scale={real_dpi_scale:.2f}")

                # 右侧屏幕错判场景修正：如果所有 Qt 屏幕 x>=0 且 real_dpi_scale == 主屏 scale，但窗口中心不在主屏 geo 内 -> 强制用最匹配 raw rect 的 scale
                primary_geo = QApplication.primaryScreen().geometry()
                if all(sc.geometry().x() >= 0 for sc in screens) and not (primary_geo.x() <= window_center_x < primary_geo.x() + primary_geo.width() and primary_geo.y() <= window_center_y < primary_geo.y() + primary_geo.height()):
                    # 匹配 raw rect
                    for raw in raw_list:
                        l, t, r, b = raw['rect']
                        if l <= window_center_x < r and t <= window_center_y < b:
                            if abs(raw['scale'] - real_dpi_scale) > 1e-3:
                                print(f"⚠️ 发现可能的右侧屏幕误判，修正 DPI scale {real_dpi_scale:.2f} -> {raw['scale']:.2f}")
                                real_dpi_scale = raw['scale']
                            break
            except Exception as e:
                print(f"⚠️ 获取系统DPI失败，使用Qt DPI: {e}")
                logical_dpi = current_screen.logicalDotsPerInch()
                real_dpi_scale = logical_dpi / 96.0
            
            # 使用变化系数减缓缩放变化
            change_factor = 0.9  # 变化系数，值越小变化越缓和
            
            if real_dpi_scale > 1.0:
                # 高DPI：减缓放大效果
                dpi_scale = 1.0 + (real_dpi_scale - 1.0) * change_factor
            else:
                # 低DPI：减缓缩小效果  
                dpi_scale = real_dpi_scale + (1.0 - real_dpi_scale) * (1.0 - change_factor)
            
            # 限制缩放范围
            dpi_scale = max(0.8, min(dpi_scale, 1.8))
            
            print(f"🔍 DPI计算结果: 原始={real_dpi_scale:.2f} -> 调整后={dpi_scale:.2f}")
            
            return dpi_scale
            
        except Exception as e:
            print(f"❌ 获取DPI缩放失败: {e}")
            return 1.0  # 默认缩放
    
    def restore_painter_tools_visual_state(self):
        """恢复绘画工具按钮的视觉状态"""
        # 恢复所有绘画工具按钮的状态
        for tool_name, is_active in self.painter_tools.items():
            if is_active:
                if tool_name == "pen_on":
                    self.pen.setStyleSheet("background-color:rgb(50,50,50);")
                elif tool_name == "highlight_on":
                    self.highlighter.setStyleSheet("background-color:rgb(50,50,50);")
                elif tool_name == "drawrect_bs_on":
                    self.bs.setStyleSheet("background-color:rgb(50,50,50);")
                elif tool_name == "drawcircle_on":
                    self.drawcircle.setStyleSheet("background-color:rgb(50,50,50);")
                elif tool_name == "drawarrow_on":
                    self.drawarrow.setStyleSheet("background-color:rgb(50,50,50);")
                elif tool_name == "drawtext_on":
                    self.drawtext.setStyleSheet("background-color:rgb(50,50,50);")
            else:
                # 重置未激活按钮的样式
                if tool_name == "pen_on":
                    self.pen.setStyleSheet("")
                elif tool_name == "highlight_on":
                    self.highlighter.setStyleSheet("")
                elif tool_name == "drawrect_bs_on":
                    self.bs.setStyleSheet("")
                elif tool_name == "drawcircle_on":
                    self.drawcircle.setStyleSheet("")
                elif tool_name == "drawarrow_on":
                    self.drawarrow.setStyleSheet("")
                elif tool_name == "drawtext_on":
                    self.drawtext.setStyleSheet("")
    
    def hide_toolbar_for_pinned_window(self):
        """隐藏钉图窗口的工具栏"""
        if hasattr(self, 'botton_box'):
            self.botton_box.hide()
            self.hide_paint_tools_menu()
            
            # 重置初始化标志，下次显示时可以重新初始化（如果需要）
            if hasattr(self, '_pinned_toolbar_initialized'):
                self._pinned_toolbar_initialized = False
                print("钉图工具栏: 重置初始化标志")
            
            # 隐藏文字输入框（如果正在显示）
            if hasattr(self, 'text_box') and self.text_box.isVisible():
                self.text_box.hide()
                self.text_box.clear()
                # 将文字框恢复为主窗口的子组件
                try:
                    self.text_box.setParent(self)
                    self.text_box.setWindowFlags(Qt.Widget)
                except Exception:
                    pass
            
            # 还原画笔二级菜单为截图窗口的子部件
            if hasattr(self, 'paint_tools_menu') and self.paint_tools_menu is not None:
                try:
                    self.paint_tools_menu.hide()
                    self.paint_tools_menu.setParent(self)
                    self.paint_tools_menu.setWindowFlags(Qt.Widget)
                except Exception as _e:
                    print(f"⚠️ 还原画笔二级菜单父子关系失败: {_e}")
            
            # 恢复工具栏为截图窗口的子组件
            try:
                self.botton_box.setParent(self)
            except Exception:
                pass
            self.botton_box.setWindowFlags(Qt.Widget)
            
            # 恢复按钮的原始状态
            self.sure_btn.setText("确定")
            self.sure_btn.setToolTip("")
            # 退出钉图模式时恢复显示
            if not self.sure_btn.isVisible():
                self.sure_btn.show()
            
            # 恢复智能选区按钮
            self.smartcursor_btn.setToolTip("スマート選択")
            if self.settings.value("screenshot/smartcursor", True, type=bool):
                self.smartcursor_btn.setStyleSheet("background-color:rgb(50,50,50);")
            else:
                self.smartcursor_btn.setStyleSheet("")
            
            # 恢复所有按钮的显示
            self.freeze_img_botton.show()  # 恢复钉图按钮
            self.long_screenshot_btn.show()  # 恢复长截图按钮
            self.copy_botton.hide()  # 隐藏复制按钮，只在钉图模式下使用
            self.lastbtn.show()
            self.nextbtn.show()
            if hasattr(self, 'drawarrow'):
                self.drawarrow.show()  # 恢复箭头按钮
            
            # 恢复原始的按钮布局
            self.restore_original_toolbar_layout()
            
            self.mode = "screenshot"
            self.current_pinned_window = None
    
    def restore_original_toolbar_layout(self):
        """恢复截图模式的原始工具栏布局"""
        # 使用左右分布布局：左侧吸附其他按钮，右侧吸附钉图和确定按钮
        btn_width = 35
        btn_height = 35
        
        # 左侧按钮从0开始布局
        left_btn_x = 0
        
        # 长截图按钮放在最左边
        self.long_screenshot_btn.setGeometry(left_btn_x, 0, 40, btn_height)
        left_btn_x += 40
        
        # 保存按钮在长截图按钮右边
        self.save_botton.setGeometry(left_btn_x, 0, 40, btn_height)
        left_btn_x += 40
        
        # 画笔工具
        self.pen.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 荧光笔工具
        self.highlighter.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 箭头工具
        self.drawarrow.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 矩形工具
        self.bs.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 圆形工具
        self.drawcircle.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 文字工具
        self.drawtext.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 颜色选择
        self.choice_clor_btn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width

        
        # 上一步
        self.lastbtn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width
        
        # 下一步
        self.nextbtn.setGeometry(left_btn_x, 0, btn_width, btn_height)
        left_btn_x += btn_width

        # 计算工具栏总宽度，为右侧按钮预留空间
        right_buttons_width = 40 + 60  # 钉图按钮40px + 确定按钮60px
        toolbar_total_width = left_btn_x + 20 + right_buttons_width  # 左侧按钮 + 间隔 + 右侧按钮
        
        # 右侧按钮从右往左布局
        right_btn_x = toolbar_total_width - 60  # 确定按钮位置（从右边开始）
        
        # 确定按钮吸附最右边
        self.sure_btn.setGeometry(right_btn_x, 0, 60, 35)
        
        # 钉图按钮在确定按钮左边
        right_btn_x -= 40
        self.freeze_img_botton.setGeometry(right_btn_x, 0, 40, 35)

        # 恢复工具栏大小
        self.botton_box.resize(toolbar_total_width, btn_height)
        print(f"恢复截图模式: 工具栏大小为 {toolbar_total_width}x{btn_height}")
        
        # 隐藏截图窗口
        self.hide()
    
    def position_toolbar_for_pinned_window(self, pinned_window):
        """为钉图窗口定位工具栏 - 支持多显示器"""
        if hasattr(self, 'botton_box') and pinned_window:
            # 获取钉图窗口所在的显示器
            pinned_screen = self.get_screen_for_point(
                pinned_window.x() + pinned_window.width() // 2,
                pinned_window.y() + pinned_window.height() // 2
            )
            
            screen_rect = pinned_screen.geometry().getRect()
            screen_x, screen_y, screen_w, screen_h = screen_rect
            
            toolbar_width = self.botton_box.width()
            toolbar_height = self.botton_box.height()
            
            # 计算工具栏位置，优先显示在钉图窗口右侧对齐下边缘
            # 首先尝试钉图窗口下方右对齐
            below_y = pinned_window.y() + pinned_window.height() + 0
            # 右对齐：工具栏右边缘与钉图窗口右边缘对齐
            toolbar_x_right_aligned = pinned_window.x() + pinned_window.width() - toolbar_width
            
            if below_y + toolbar_height <= screen_y + screen_h and toolbar_x_right_aligned >= screen_x:
                # 下方有足够空间且右对齐位置合理
                toolbar_x = max(screen_x, toolbar_x_right_aligned)
                toolbar_y = below_y
            else:
                # 下方空间不足或右对齐位置不合理，尝试上方右对齐
                above_y = pinned_window.y() - toolbar_height - 0
                if above_y >= screen_y and toolbar_x_right_aligned >= screen_x:
                    toolbar_x = max(screen_x, toolbar_x_right_aligned)
                    toolbar_y = above_y
                else:
                    # 上下都不够或右对齐不合理，显示在右侧
                    toolbar_x = pinned_window.x() + pinned_window.width() + 0
                    toolbar_y = max(screen_y, pinned_window.y())
                    
                    if toolbar_x + toolbar_width > screen_x + screen_w:
                        # 右侧也不够，显示在左侧
                        toolbar_x = pinned_window.x() - toolbar_width - 0
                        if toolbar_x < screen_x:
                            # 左侧也不够，显示在钉图窗口内部右下角
                            toolbar_x = pinned_window.x() + pinned_window.width() - toolbar_width - 0
                            toolbar_y = pinned_window.y() + pinned_window.height() - toolbar_height - 0
            
            # 确保工具栏完全在目标显示器内
            toolbar_x, toolbar_y = self.adjust_position_to_screen(
                toolbar_x, toolbar_y, toolbar_width, toolbar_height, pinned_screen)
            
            self.botton_box.move(toolbar_x, toolbar_y)
    
    def is_toolbar_under_mouse(self):
        """检查工具栏或画笔设置菜单是否在鼠标下方，以及是否正在与UI交互"""
        if hasattr(self, 'botton_box') and self.botton_box.isVisible():
            if self.botton_box.underMouse():
                return True
        
        # 也检查画笔设置二级菜单
        if hasattr(self, 'paint_tools_menu') and self.paint_tools_menu.isVisible():
            if self.paint_tools_menu.underMouse():
                return True
            
            # 检查二级菜单中的任何子控件是否有焦点或正在被使用
            from PyQt5.QtWidgets import QWidget
            for child in self.paint_tools_menu.findChildren(QWidget):
                if child.hasFocus() or child.underMouse():
                    return True
            
            # 如果有绘画工具激活，给二级菜单更多保护时间
            if (hasattr(self, 'painter_tools') and 1 in self.painter_tools.values()):
                # 检查鼠标是否刚刚离开二级菜单区域（给一个小的缓冲时间和空间）
                cursor_pos = QCursor.pos()
                menu_rect = self.paint_tools_menu.geometry()
                # 稍微扩大二级菜单的检测范围
                buffer = 10
                expanded_menu_rect = QRect(
                    menu_rect.x() - buffer, 
                    menu_rect.y() - buffer,
                    menu_rect.width() + 2 * buffer, 
                    menu_rect.height() + 2 * buffer
                )
                
                # 将本地坐标转换为全局坐标
                if hasattr(self.paint_tools_menu, 'parent') and self.paint_tools_menu.parent():
                    global_menu_rect = QRect(
                        self.paint_tools_menu.mapToGlobal(expanded_menu_rect.topLeft()),
                        expanded_menu_rect.size()
                    )
                else:
                    global_menu_rect = expanded_menu_rect
                    
                if global_menu_rect.contains(cursor_pos):
                    return True
                
        return False
