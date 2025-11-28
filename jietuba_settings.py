"""
设置界面模块
左侧导航 + 右侧内容的现代化设置界面
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QStackedWidget, QWidget,
    QGroupBox, QCheckBox, QComboBox, QLineEdit, QFormLayout,
    QFrame, QSpinBox, QDoubleSpinBox, QGridLayout, QScrollArea
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QFont


class SettingsDialog(QDialog):
    """现代化设置对话框 - 左侧导航+右侧内容布局"""

    def __init__(self, config_manager, current_hotkey="ctrl+shift+a", parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.current_hotkey = current_hotkey
        self.setWindowTitle("設定")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.resize(800, 550)
        self._setup_ui()

    def _setup_ui(self):
        """设置主界面"""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧导航栏
        self.nav_list = self._create_navigation()
        main_layout.addWidget(self.nav_list)

        # 添加分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #ddd;")
        main_layout.addWidget(separator)

        # 右侧内容区
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(15)

        # 标题区域
        self.content_title = QLabel("ショートカット設定")
        self.content_title.setStyleSheet("""
            font-weight: bold;
            font-size: 16pt;
            color: #2c3e50;
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 2px solid #4CAF50;
        """)
        right_layout.addWidget(self.content_title)

        # 内容堆栈
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self._create_hotkey_page())
        self.content_stack.addWidget(self._create_long_screenshot_page())
        self.content_stack.addWidget(self._create_smart_selection_page())
        right_layout.addWidget(self.content_stack)

        right_layout.addStretch()

        # 底部按钮区域
        btn_layout = self._create_button_area()
        right_layout.addLayout(btn_layout)

        right_container = QWidget()
        right_container.setLayout(right_layout)
        main_layout.addWidget(right_container, 1)

        self.setLayout(main_layout)

        # 连接导航切换事件
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        self.nav_list.setCurrentRow(0)

    def _create_navigation(self):
        """创建左侧导航栏"""
        nav_list = QListWidget()
        nav_list.setFixedWidth(220)
        nav_list.setSpacing(5)
        
        # 设置导航样式
        nav_list.setStyleSheet("""
            QListWidget {
                background-color: #f5f5f5;
                border: none;
                outline: none;
                padding: 10px 5px;
            }
            QListWidget::item {
                background-color: transparent;
                color: #333;
                padding: 15px 20px;
                border-radius: 6px;
                margin: 2px 5px;
                font-size: 11pt;
            }
            QListWidget::item:hover {
                background-color: #e0e0e0;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
        """)

        # 添加导航项
        items = [
            "⌨️ ショートカット設定",
            "📸 長いスクリーンショット設定",
            "🎯 スマート選択設定"
        ]
        
        for item_text in items:
            item = QListWidgetItem(item_text)
            item.setSizeHint(QSize(200, 50))
            nav_list.addItem(item)

        return nav_list

    def _create_hotkey_page(self):
        """创建快捷键设置页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(20)

        # 说明文字
        desc_label = QLabel("スクリーンショットを起動するためのグローバルホットキーを設定します。")
        desc_label.setStyleSheet("color: #666; font-size: 10pt; margin-bottom: 10px;")
        layout.addWidget(desc_label)

        # 快捷键输入组
        hotkey_group = QGroupBox("ホットキー")
        hotkey_group.setStyleSheet(self._get_group_style())
        
        group_layout = QFormLayout()
        group_layout.setSpacing(15)
        
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setText(self.current_hotkey)
        self.hotkey_input.setPlaceholderText("例: ctrl+shift+a")
        self.hotkey_input.setStyleSheet(self._get_input_style())
        
        group_layout.addRow("ホットキー:", self.hotkey_input)
        hotkey_group.setLayout(group_layout)
        layout.addWidget(hotkey_group)

        # 任务栏按钮设置组
        taskbar_group = QGroupBox("スクショボタン")
        taskbar_group.setStyleSheet(self._get_group_style())
        
        taskbar_layout = QVBoxLayout()
        taskbar_layout.setSpacing(10)
        
        self.taskbar_button_checkbox = QCheckBox("スクショボタンを表示")
        self.taskbar_button_checkbox.setChecked(self.config_manager.get_taskbar_button())
        self.taskbar_button_checkbox.setStyleSheet(self._get_checkbox_style())

        taskbar_desc = QLabel("スクショボタンを表示します。")
        taskbar_desc.setStyleSheet("color: #666; font-size: 9pt; margin-left: 25px;")
        
        taskbar_layout.addWidget(self.taskbar_button_checkbox)
        taskbar_layout.addWidget(taskbar_desc)
        
        taskbar_group.setLayout(taskbar_layout)
        layout.addWidget(taskbar_group)

        # 使用说明
        hint_label = QLabel(
            "💡 ヒント:\n"
            "• Ctrl、Shift、Altなどの修飾キーと組み合わせて使用できます（手入力）\n"
            "• 例: ctrl+shift+a, alt+q, ctrl+alt+s\n"
            "• 他のアプリケーションと競合しないキーの組み合わせを選択してください"
        )
        hint_label.setStyleSheet("""
            background-color: #e3f2fd;
            color: #1976d2;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #2196F3;
            font-size: 9pt;
            line-height: 1.6;
        """)
        layout.addWidget(hint_label)

        layout.addStretch()
        return page

    def _create_long_screenshot_page(self):
        """创建长截图设置页面"""
        page = QWidget()
        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #f5f5f5;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # 创建内容容器
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 10, 10, 10)
        layout.setSpacing(20)

        # 说明文字
        desc_label = QLabel("スクロールして連続撮影する長いスクリーンショットの設定を行います。")
        desc_label.setStyleSheet("color: #666; font-size: 10pt; margin-bottom: 10px;")
        layout.addWidget(desc_label)

        # 拼接引擎设置组
        engine_group = QGroupBox("拼接エンジン")
        engine_group.setStyleSheet(self._get_group_style())
        
        group_layout = QVBoxLayout()
        group_layout.setSpacing(15)
        
        engine_label = QLabel("マッチングの方法を選択:")
        engine_label.setStyleSheet("color: #333; font-size: 10pt; font-weight: bold;")
        group_layout.addWidget(engine_label)
        
        self.engine_combo = QComboBox()
        # 🆕 暂时屏蔽自动选择和特征匹配，只保留哈希匹配选项
        # self.engine_combo.addItem("🔄 自動選択", "auto")
        # self.engine_combo.addItem("⚡ ピクセル特徴", "rust")
        self.engine_combo.addItem("🦀 Rustハッシュ値", "hash_rust")
        self.engine_combo.addItem("🐍 Pythonハッシュ値", "hash_python")
        
        # 设置当前选中的引擎
        current_engine = self.config_manager.get_long_stitch_engine()
        
        # 🆕 如果配置中是auto或rust，自动切换为hash_rust
        if current_engine in ['auto', 'rust']:
            current_engine = 'hash_rust'
            self.main_window.set_long_stitch_engine(current_engine)
            print(f"⚠️ 检测到已禁用的引擎 {current_engine}，自动切换为 hash_rust")
        
        for i in range(self.engine_combo.count()):
            if self.engine_combo.itemData(i) == current_engine:
                self.engine_combo.setCurrentIndex(i)
                break
        
        self.engine_combo.setStyleSheet(self._get_combo_style())
        group_layout.addWidget(self.engine_combo)
        
        # 引擎说明
        engine_desc = QLabel(
            "• Rustハッシュ値: Rust実装、ハッシュ値マッチング（最速、11倍高速）\n"
            "• Pythonハッシュ値: Python実装、ハッシュ値マッチング（デバッグ用）"
        )
        engine_desc.setStyleSheet("color: #666; font-size: 9pt; margin-top: 10px;")
        group_layout.addWidget(engine_desc)
        
        engine_group.setLayout(group_layout)
        layout.addWidget(engine_group)

        # Rust 引擎高级参数设置组
        rust_params_group = QGroupBox("マーチングパラメータ")
        rust_params_group.setStyleSheet(self._get_group_style())
        
        rust_params_layout = QGridLayout()
        rust_params_layout.setSpacing(12)
        rust_params_layout.setColumnStretch(0, 1)  # 标签列可伸缩
        rust_params_layout.setColumnStretch(1, 0)  # 输入框列固定宽度
        
        # 采样率
        sample_rate_label = QLabel("采样率 (sample_rate):")
        sample_rate_label.setToolTip("控制图片缩放比例，越高精度越高但速度越慢 (0.0-1.0)")
        self.sample_rate_input = QDoubleSpinBox()
        self.sample_rate_input.setRange(0.1, 1.0)
        self.sample_rate_input.setSingleStep(0.1)
        self.sample_rate_input.setDecimals(1)
        self.sample_rate_input.setFixedWidth(120)
        self.sample_rate_input.setValue(
            self.config_manager.settings.value('screenshot/rust_sample_rate', 0.6, type=float)
        )
        rust_params_layout.addWidget(sample_rate_label, 0, 0)
        rust_params_layout.addWidget(self.sample_rate_input, 0, 1)
        
        # 最小采样尺寸
        min_sample_label = QLabel("最小采样尺寸:")
        min_sample_label.setToolTip("采样后图片的最小尺寸 (像素)")
        self.min_sample_size_input = QSpinBox()
        self.min_sample_size_input.setRange(100, 1000)
        self.min_sample_size_input.setSingleStep(50)
        self.min_sample_size_input.setFixedWidth(120)
        self.min_sample_size_input.setValue(
            self.config_manager.settings.value('screenshot/rust_min_sample_size', 300, type=int)
        )
        rust_params_layout.addWidget(min_sample_label, 1, 0)
        rust_params_layout.addWidget(self.min_sample_size_input, 1, 1)
        
        # 最大采样尺寸
        max_sample_label = QLabel("最大采样尺寸:")
        max_sample_label.setToolTip("采样后图片的最大尺寸 (像素)")
        self.max_sample_size_input = QSpinBox()
        self.max_sample_size_input.setRange(400, 2000)
        self.max_sample_size_input.setSingleStep(100)
        self.max_sample_size_input.setFixedWidth(120)
        self.max_sample_size_input.setValue(
            self.config_manager.settings.value('screenshot/rust_max_sample_size', 800, type=int)
        )
        rust_params_layout.addWidget(max_sample_label, 2, 0)
        rust_params_layout.addWidget(self.max_sample_size_input, 2, 1)
        
        # 特征点阈值
        corner_threshold_label = QLabel("特征点阈值 (corner_threshold):")
        corner_threshold_label.setToolTip("越低检测越多特征点，推荐10-64")
        self.corner_threshold_input = QSpinBox()
        self.corner_threshold_input.setRange(5, 128)
        self.corner_threshold_input.setSingleStep(5)
        self.corner_threshold_input.setFixedWidth(120)
        self.corner_threshold_input.setValue(
            self.config_manager.settings.value('screenshot/rust_corner_threshold', 30, type=int)
        )
        rust_params_layout.addWidget(corner_threshold_label, 3, 0)
        rust_params_layout.addWidget(self.corner_threshold_input, 3, 1)
        
        # 描述符块大小
        descriptor_label = QLabel("描述符块大小:")
        descriptor_label.setToolTip("特征描述符的块大小 (像素)，推荐9或11")
        self.descriptor_patch_size_input = QSpinBox()
        self.descriptor_patch_size_input.setRange(5, 15)
        self.descriptor_patch_size_input.setSingleStep(2)
        self.descriptor_patch_size_input.setFixedWidth(120)
        self.descriptor_patch_size_input.setValue(
            self.config_manager.settings.value('screenshot/rust_descriptor_patch_size', 9, type=int)
        )
        rust_params_layout.addWidget(descriptor_label, 4, 0)
        rust_params_layout.addWidget(self.descriptor_patch_size_input, 4, 1)
        
        # 索引重建阈值
        min_size_delta_label = QLabel("索引重建阈值:")
        min_size_delta_label.setToolTip("最小变化量阈值 (像素)，设为1强制每张都更新")
        self.min_size_delta_input = QSpinBox()
        self.min_size_delta_input.setRange(1, 128)
        self.min_size_delta_input.setSingleStep(1)
        self.min_size_delta_input.setFixedWidth(120)
        self.min_size_delta_input.setValue(
            self.config_manager.settings.value('screenshot/rust_min_size_delta', 1, type=int)
        )
        rust_params_layout.addWidget(min_size_delta_label, 5, 0)
        rust_params_layout.addWidget(self.min_size_delta_input, 5, 1)
        
        # 回滚匹配
        self.try_rollback_checkbox = QCheckBox("启用回滚匹配 (try_rollback)")
        self.try_rollback_checkbox.setToolTip("允许在另一个队列中查找匹配")
        self.try_rollback_checkbox.setChecked(
            self.config_manager.settings.value('screenshot/rust_try_rollback', True, type=bool)
        )
        self.try_rollback_checkbox.setStyleSheet(self._get_checkbox_style())
        rust_params_layout.addWidget(self.try_rollback_checkbox, 6, 0, 1, 2)
        
        # 距离阈值
        distance_threshold_label = QLabel("距离阈值 (distance_threshold):")
        distance_threshold_label.setToolTip("特征匹配距离阈值，越低越严格 (0.05-0.3)")
        self.distance_threshold_input = QDoubleSpinBox()
        self.distance_threshold_input.setRange(0.05, 0.5)
        self.distance_threshold_input.setSingleStep(0.05)
        self.distance_threshold_input.setDecimals(2)
        self.distance_threshold_input.setFixedWidth(120)
        self.distance_threshold_input.setValue(
            self.config_manager.settings.value('screenshot/rust_distance_threshold', 0.1, type=float)
        )
        rust_params_layout.addWidget(distance_threshold_label, 7, 0)
        rust_params_layout.addWidget(self.distance_threshold_input, 7, 1)
        
        # HNSW 搜索参数
        ef_search_label = QLabel("HNSW搜索参数 (ef_search):")
        ef_search_label.setToolTip("HNSW搜索参数，越高准确率越高但速度越慢 (16-128)")
        self.ef_search_input = QSpinBox()
        self.ef_search_input.setRange(16, 128)
        self.ef_search_input.setSingleStep(8)
        self.ef_search_input.setFixedWidth(120)
        self.ef_search_input.setValue(
            self.config_manager.settings.value('screenshot/rust_ef_search', 32, type=int)
        )
        rust_params_layout.addWidget(ef_search_label, 8, 0)
        rust_params_layout.addWidget(self.ef_search_input, 8, 1)
        
        # 参数说明
        params_desc = QLabel(
            "💡 これらのパラメータはピクセル特徴の計算に影響します。\n"
            "   スティッチングが失敗する場合は、以下をお試しください：\n"
            "   • corner_threshold を下げる (10-20) - より多くの特徴点を検出\n"
            "   • sample_rate を上げる (0.7-0.9) - より多くの詳細を保持\n"
            "   • distance_threshold を上げる (0.15-0.2) - マッチング条件を緩和\n"
            "   • ef_search を上げる (48-64) - 検索精度を向上\n"
            "   • ロールバックマッチングを有効化 - 成功率を向上"
        )
        params_desc.setStyleSheet("color: #666; font-size: 9pt; margin-top: 10px; padding: 10px; background-color: #f9f9f9; border-radius: 4px;")
        rust_params_layout.addWidget(params_desc, 9, 0, 1, 2)
        
        rust_params_group.setLayout(rust_params_layout)
        layout.addWidget(rust_params_group)

        layout.addStretch()
        
        # 设置滚动区域的内容
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        return page

    def _create_smart_selection_page(self):
        """创建智能选区设置页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(20)

        # 说明文字
        desc_label = QLabel("画面内のウィンドウやUI要素を自動認識する機能の設定を行います。")
        desc_label.setStyleSheet("color: #666; font-size: 10pt; margin-bottom: 10px;")
        layout.addWidget(desc_label)

        # 智能选择功能组
        smart_group = QGroupBox("スマート選択")
        smart_group.setStyleSheet(self._get_group_style())
        
        group_layout = QVBoxLayout()
        group_layout.setSpacing(15)
        
        self.smart_selection_checkbox = QCheckBox("スマート選択を有効にする")
        self.smart_selection_checkbox.setChecked(self.config_manager.get_smart_selection())
        self.smart_selection_checkbox.setStyleSheet(self._get_checkbox_style())
        
        smart_desc = QLabel(
            "スマート選択を有効にすると、マウスカーソルの位置に応じて\n"
            "ウィンドウやボタンなどのUI要素を自動的に検出し、\n"
            "より正確な範囲選択が可能になります。"
        )
        smart_desc.setStyleSheet("color: #666; font-size: 9pt; margin-left: 25px;")
        
        group_layout.addWidget(self.smart_selection_checkbox)
        group_layout.addWidget(smart_desc)
        
        smart_group.setLayout(group_layout)
        layout.addWidget(smart_group)

        # 使用说明
        hint_label = QLabel(
            "💡 使い方:\n"
            "• スクリーンショット時に、カーソルを移動するとUI要素が自動的にハイライトされます\n"
            "• ハイライトされた領域をクリックすると、その範囲でキャプチャーを取れます\n"
            "• もちろん手動で範囲を選択も大丈夫です"
        )
        hint_label.setStyleSheet("""
            background-color: #f3e5f5;
            color: #7b1fa2;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #9c27b0;
            font-size: 9pt;
            line-height: 1.6;
        """)
        layout.addWidget(hint_label)

        layout.addStretch()
        return page

    def _create_button_area(self):
        """创建底部按钮区域"""
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        # 重置按钮（左侧）
        reset_btn = QPushButton("🔄 リセット")
        reset_btn.clicked.connect(self._reset_all_settings)
        reset_btn.setFixedSize(150, 40)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                padding: 8px 20px;
                font-size: 10pt;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #fb8c00;
            }
            QPushButton:pressed {
                background-color: #f57c00;
            }
        """)
        btn_layout.addWidget(reset_btn)
        
        btn_layout.addStretch()

        # 取消按钮
        cancel_btn = QPushButton("cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setFixedSize(120, 40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 2px solid #ddd;
                padding: 8px 20px;
                font-size: 10pt;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-color: #bbb;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        btn_layout.addWidget(cancel_btn)

        # 确定按钮
        ok_btn = QPushButton("適用")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        ok_btn.setFixedSize(120, 40)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 20px;
                font-size: 10pt;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        btn_layout.addWidget(ok_btn)

        return btn_layout

    def _reset_all_settings(self):
        """重置所有设置为默认值"""
        from PyQt5.QtWidgets import QMessageBox
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            '設定をリセット',
            'すべての設定をデフォルト値にリセットしますか？\nこの操作は元に戻せません。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 重置快捷键
            self.hotkey_input.setText("ctrl+1")
            
            # 重置任务栏按钮（默认关闭）
            self.taskbar_button_checkbox.setChecked(False)
            
            # 重置智能选择（默认关闭）
            self.smart_selection_checkbox.setChecked(False)
            
            # 重置长截图引擎
            self.engine_combo.setCurrentIndex(0)  # 自動選択
            
            # 重置 Rust 引擎参数
            self.sample_rate_input.setValue(1.0)
            self.min_sample_size_input.setValue(300)
            self.max_sample_size_input.setValue(800)
            self.corner_threshold_input.setValue(10)
            self.descriptor_patch_size_input.setValue(9)
            self.min_size_delta_input.setValue(1)
            self.try_rollback_checkbox.setChecked(True)
            self.distance_threshold_input.setValue(0.2)
            self.ef_search_input.setValue(32)
            
            print("✅ すべての設定をデフォルト値にリセットしました")
            QMessageBox.information(
                self,
                '完了',
                'すべての設定をデフォルト値にリセットしました。\n「適用」ボタンをクリックして保存してください。',
                QMessageBox.Ok
            )

    def _on_nav_changed(self, index):
        """导航切换事件"""
        titles = [
            "ショートカット設定",
            "長いスクショ設定",
            "スマート選択設定"
        ]
        if 0 <= index < len(titles):
            self.content_title.setText(titles[index])
            self.content_stack.setCurrentIndex(index)

    def get_hotkey(self):
        """获取设置的快捷键"""
        return self.hotkey_input.text().strip()

    def accept(self):
        """应用设置"""
        # 保存快捷键设置（由调用者处理）
        
        # 保存智能选择设置
        self.config_manager.set_smart_selection(self.smart_selection_checkbox.isChecked())
        print(f"💾 智能选择设置已保存: {self.smart_selection_checkbox.isChecked()}")
        
        # 保存任务栏按钮设置
        self.config_manager.set_taskbar_button(self.taskbar_button_checkbox.isChecked())
        print(f"💾 任务栏按钮设置已保存: {self.taskbar_button_checkbox.isChecked()}")
        
        # 保存长截图引擎设置
        selected_engine = self.engine_combo.currentData()
        self.config_manager.set_long_stitch_engine(selected_engine)
        print(f"💾 长截图拼接引擎已保存: {selected_engine}")
        
        # 保存 Rust 引擎参数
        self.config_manager.settings.setValue('screenshot/rust_sample_rate', self.sample_rate_input.value())
        self.config_manager.settings.setValue('screenshot/rust_min_sample_size', self.min_sample_size_input.value())
        self.config_manager.settings.setValue('screenshot/rust_max_sample_size', self.max_sample_size_input.value())
        self.config_manager.settings.setValue('screenshot/rust_corner_threshold', self.corner_threshold_input.value())
        self.config_manager.settings.setValue('screenshot/rust_descriptor_patch_size', self.descriptor_patch_size_input.value())
        self.config_manager.settings.setValue('screenshot/rust_min_size_delta', self.min_size_delta_input.value())
        self.config_manager.settings.setValue('screenshot/rust_try_rollback', self.try_rollback_checkbox.isChecked())
        self.config_manager.settings.setValue('screenshot/rust_distance_threshold', self.distance_threshold_input.value())
        self.config_manager.settings.setValue('screenshot/rust_ef_search', self.ef_search_input.value())
        print(f"💾 Rust 引擎参数已保存:")
        print(f"   sample_rate={self.sample_rate_input.value()}")
        print(f"   corner_threshold={self.corner_threshold_input.value()}")
        print(f"   min_sample_size={self.min_sample_size_input.value()}")
        print(f"   max_sample_size={self.max_sample_size_input.value()}")
        print(f"   distance_threshold={self.distance_threshold_input.value()}")
        print(f"   ef_search={self.ef_search_input.value()}")
        
        # 动态更新长截图配置
        self._apply_long_stitch_config()
        
        super().accept()

    def _apply_long_stitch_config(self):
        """动态应用长截图引擎配置"""
        try:
            from jietuba_long_stitch_unified import configure as long_stitch_configure
            long_stitch_configure(
                engine=self.engine_combo.currentData(),
                direction=0,
                sample_rate=self.sample_rate_input.value(),
                min_sample_size=self.min_sample_size_input.value(),
                max_sample_size=self.max_sample_size_input.value(),
                corner_threshold=self.corner_threshold_input.value(),
                descriptor_patch_size=self.descriptor_patch_size_input.value(),
                min_size_delta=self.min_size_delta_input.value(),
                try_rollback=self.try_rollback_checkbox.isChecked(),
                distance_threshold=self.distance_threshold_input.value(),
                ef_search=self.ef_search_input.value(),
                verbose=True,
            )
            print(f"✅ 长截图配置已更新")
        except Exception as e:
            print(f"⚠️  更新长截图配置失败: {e}")

    def keyPressEvent(self, event):
        """处理键盘事件，回车确认"""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.accept()
        else:
            super().keyPressEvent(event)

    # ==================== 样式定义 ====================
    
    @staticmethod
    def _get_group_style():
        """获取GroupBox样式"""
        return """
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                color: #2c3e50;
            }
        """

    @staticmethod
    def _get_input_style():
        """获取输入框样式"""
        return """
            QLineEdit {
                padding: 10px 12px;
                font-size: 11pt;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
            QLineEdit:hover {
                border-color: #c0c0c0;
            }
        """

    @staticmethod
    def _get_combo_style():
        """获取下拉框样式"""
        return """
            QComboBox {
                padding: 10px 12px;
                font-size: 10pt;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
            }
            QComboBox:focus {
                border-color: #4CAF50;
            }
            QComboBox:hover {
                border-color: #c0c0c0;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #666;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
                selection-background-color: #4CAF50;
                selection-color: white;
                padding: 5px;
            }
        """

    @staticmethod
    def _get_checkbox_style():
        """获取复选框样式"""
        return """
            QCheckBox {
                color: #333;
                font-size: 10pt;
                padding: 8px;
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #bbb;
                background-color: white;
                border-radius: 4px;
            }
            QCheckBox::indicator:unchecked:hover {
                border-color: #4CAF50;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4CAF50;
                background-color: #4CAF50;
                border-radius: 4px;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEzLjMzMzMgNEw2IDExLjMzMzNMMi42NjY2NyA4IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
            }
        """
