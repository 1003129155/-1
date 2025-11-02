AI写的小工具自用,主要是因为公司的电脑不能下载软件,所以市面上好用的截图软件都用不了

主要是用Claude写的,99%的AI代码

2025/11/2更新
1,添加了在画笔和荧光笔功能绘制的时候,先按下shift再画,会识别是横还是竖且保持画直线
2,主界面下增加了版本信息和更新时间

### 系统要求
- Windows 7/8/10/11
- Python 3.7 或更高版本

### 安装 Python 依赖

pip install -r requirements.txt

主要依赖包:
```
PyQt5>=5.15.0
opencv-python>=4.5.0
Pillow>=8.0.0
numpy>=1.19.0
pynput>=1.7.0
```

## 🚀 快速开始

### 方式一: 直接运行 Python 脚本

python main.py


### 方式二: 打包成可执行文件

# 使用内置的打包脚本
python jietuba_build.py

## 🎮 使用方法

### 基本操作

1. **启动程序**
   - 运行 `main.py` 

2. **开始截图**
   - 点击主窗口的 "スクショ開始" 按钮
   - 或使用全局快捷键 (默认: `Ctrl+Shift+A`)
   - 或右键托盘图标选择 "スクリーンショット"

3. **选择区域**
   - 鼠标拖拽选择截图区域
   - 按 `鼠标右键` 取消截图

4. **编辑截图**
   - 选区确定后,工具栏自动显示
   - 选择需要的编辑工具进行标注
   - 点击 "完成" 保存截图

### 快捷键说明

| 快捷键 | 功能 |
|-------|------|
| `Ctrl+Shift+A` | 开始截图 (可自定义) |
| `Enter` | 完成截图/确认 |
| `Ctrl+Z` | 撤销 |
| `Ctrl+Y` | 重做 |
| 鼠标滚轮|调整钉图窗口大小 和各种画笔的大小 滚动长截图窗口|
|ctrl 加鼠标滚轮|调整钉图透明度,和各种画笔的透明度|

### 长截图功能

1. 在截图工具栏点击 "长截图" 按钮
2. 选择要捕获的区域
3. 使用鼠标慢慢一下一下滚轮滚动页面
4. 程序自动捕获每一屏
5. 完成后自动拼接成长图

### 钉图功能

1. 截图完成后点击 "钉图" 按钮
2. 截图会置顶显示在屏幕上
3. 可以继续在钉图上编辑

```
jietuba/
├── main.py                      # 主程序入口
├── jietuba_screenshot.py        # 截图核心功能
├── jietuba_widgets.py           # 自定义控件
├── jietuba_public.py            # 公共配置和工具
├── jietuba_resource.py          # Qt 资源文件
├── jietuba_scroll.py            # 滚动截图窗口
├── jietuba_stitch.py            # 简单垂直拼接
├── jietuba_smart_stitch.py      # 智能拼接(ORB)
├── jietuba_text_drawer.py       # 文字绘制组件
├── jietuba_build.py             # 打包脚本
├── requirements.txt             # Python 依赖
├── README.md                    # 项目说明
└── build/                       # 构建输出目录
```

## 🔧 开发说明

### 模块说明

| 模块 | 功能 |
|-----|------|
| `main.py` | 程序入口、主窗口、配置管理 |
| `jietuba_screenshot.py` | 截图、编辑、绘图工具 |
| `jietuba_widgets.py` | 钉图窗口、文本框等控件 |
| `jietuba_public.py` | 全局配置、工具函数 |
| `jietuba_scroll.py` | 滚动长截图功能 |
| `jietuba_stitch.py` | 简单图片拼接 |
| `jietuba_smart_stitch.py` | 智能特征匹配拼接 |
| `jietuba_text_drawer.py` | 文字绘制功能 |
| `jietuba_build.py` | PyInstaller 打包 |
| `jietuba_resource.py` | 图标和资源文件 |


欢迎提交 Issue 和 Pull Request!
