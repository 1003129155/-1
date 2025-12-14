#!/usr/bin/env python3
"""
jietuba_build_no_ocr.py - PyInstaller 打包脚本（无OCR版本）

这是一个精简版本的打包脚本，不包含OCR相关依赖。
适用于不需要OCR功能的用户，可以大幅减小程序体积。

主要功能:
- 自动检测或创建虚拟环境
- 配置 PyInstaller 打包参数（排除OCR依赖）
- 排除不必要的模块减小体积
- 生成单文件可执行程序

使用方法:
    python jietuba_build_no_ocr.py
"""

import os
import sys
import subprocess
import platform

def check_venv():
    """检查是否在虚拟环境中运行"""
    return hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )

def setup_venv():
    """设置虚拟环境"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(current_dir, 'venv_no_ocr')
    
    # 检查是否已在虚拟环境中
    if check_venv():
        print("✅ 已在虚拟环境中运行")
        return True
    
    # 检查虚拟环境是否存在
    if not os.path.exists(venv_dir):
        print("🔧 虚拟环境不存在，正在创建...")
        try:
            subprocess.run([sys.executable, '-m', 'venv', venv_dir], check=True)
            print("✅ 虚拟环境创建成功")
        except subprocess.CalledProcessError as e:
            print(f"❌ 创建虚拟环境失败: {e}")
            return False
    
    # 确定虚拟环境的 Python 和 pip 路径
    if platform.system() == 'Windows':
        venv_python = os.path.join(venv_dir, 'Scripts', 'python.exe')
        venv_pip = os.path.join(venv_dir, 'Scripts', 'pip.exe')
    else:
        venv_python = os.path.join(venv_dir, 'bin', 'python')
        venv_pip = os.path.join(venv_dir, 'bin', 'pip')
    
    # 检查依赖是否已安装（不包含OCR相关依赖）
    print("🔍 检查依赖包...")
    try:
        result = subprocess.run(
            [venv_pip, 'list'],
            capture_output=True,
            text=True,
            check=True
        )
        installed_packages = result.stdout.lower()
        
        # 不包含 rapidocr 和 onnxruntime
        required_packages = ['pyqt5', 'pillow', 'pynput', 'pywin32', 'pyinstaller']
        missing_packages = [pkg for pkg in required_packages if pkg not in installed_packages]
        
        if missing_packages:
            print(f"📦 安装缺失的依赖包: {', '.join(missing_packages)}")
            subprocess.run(
                [venv_pip, 'install'] + ['PyQt5', 'Pillow', 'pynput', 'pywin32', 'PyInstaller'],
                check=True
            )
            print("✅ 依赖包安装完成")
        else:
            print("✅ 所有依赖包已安装")
        
        # 🔥 检查并安装 jietuba_rust 模块（从 wheel 文件）
        print("🔍 检查 Rust 模块...")
        wheel_dir = os.path.join(current_dir, 'rs', 'target', 'wheels')
        if os.path.exists(wheel_dir):
            wheel_files = [f for f in os.listdir(wheel_dir) if f.endswith('.whl')]
            if wheel_files:
                wheel_path = os.path.join(wheel_dir, wheel_files[0])
                print(f"📦 安装 Rust 模块: {wheel_files[0]}")
                try:
                    subprocess.run(
                        [venv_pip, 'install', wheel_path, '--force-reinstall'],
                        check=True
                    )
                    print("✅ Rust 模块安装完成")
                except subprocess.CalledProcessError as e:
                    print(f"⚠️  Rust 模块安装失败: {e}")
                    print("   打包后将只支持 Python 引擎")
            else:
                print("⚠️  未找到 Rust wheel 文件，请先运行: compile_and_install.bat")
                print("   打包后将只支持 Python 引擎")
        else:
            print("⚠️  未找到 rs/target/wheels 目录")
            print("   打包后将只支持 Python 引擎")
    except subprocess.CalledProcessError as e:
        print(f"❌ 检查或安装依赖失败: {e}")
        return False
    
    # 重新启动脚本使用虚拟环境
    print("🔄 使用虚拟环境重新启动打包脚本...")
    script_path = os.path.abspath(__file__)
    try:
        subprocess.run([venv_python, script_path, '--in-venv'], check=True)
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print(f"❌ 重新启动失败: {e}")
        return False

def build_executable():
    """构建可执行文件（无OCR版本）"""
    
    # 导入 PyInstaller（必须在虚拟环境中）
    try:
        import PyInstaller.__main__
    except ImportError:
        print("❌ PyInstaller 未安装，请先安装: pip install PyInstaller")
        return False
    
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # SVG 目录的绝对路径
    svg_dir = os.path.join(current_dir, 'svg')
    
    # PyInstaller 参数（无OCR版本）
    args = [
        'main.py',                          # 主程序入口
        '--name=jietuba_no_ocr',            # 可执行文件名（标记为无OCR版本）
        '--onefile',                        # 打包成单个文件
        '--windowed',                       # Windows下隐藏控制台
        # '--icon=icon.ico',                # 图标文件(如果有) - 暂时注释掉
        
        # 添加数据文件 - SVG图标（使用绝对路径）
        f'--add-data={svg_dir};svg',        # 包含svg目录及其所有文件
        
        # 核心依赖
        '--hidden-import=PyQt5.QtCore',
        '--hidden-import=PyQt5.QtGui',
        '--hidden-import=PyQt5.QtWidgets',
        
        # Python 标准库（确保包含）
        '--hidden-import=json',
        '--hidden-import=base64',
        '--hidden-import=subprocess',
        '--hidden-import=traceback',
        
        # PIL/Pillow（图像处理 + 长截图拼接）
        '--hidden-import=PIL',
        '--hidden-import=PIL.Image',
        '--hidden-import=PIL.ImageDraw',
        '--hidden-import=PIL.ImageFont',
        '--collect-submodules=PIL',
        
        # 键盘鼠标监听（长截图滚轮检测）
        '--hidden-import=pynput.mouse',
        '--hidden-import=pynput.keyboard',
        
        # Windows API（智能窗口选择）
        '--hidden-import=win32gui',
        '--hidden-import=win32api',
        '--hidden-import=win32con',
        '--hidden-import=win32ui',
        '--hidden-import=pywintypes',
        '--hidden-import=pythoncom',
        
        # 🔥 Rust 模块（长截图加速）
        '--hidden-import=jietuba_rust',
        '--collect-all=jietuba_rust',
        
        # 🔥 pywin32 需要收集所有子模块和DLL
        '--collect-all=pywin32',
        '--collect-all=win32com',
        '--hidden-import=pythoncom',
        
        # pywin32 的 DLL 收集
        '--collect-all=pywin32',
        '--collect-all=pywintypes',
        '--collect-all=pythoncom',
        
        # 🔥 排除不需要的大型模块
        '--exclude-module=matplotlib',      
        '--exclude-module=pandas',          
        '--exclude-module=scipy',           
        '--exclude-module=IPython',         
        '--exclude-module=notebook',        
        '--exclude-module=pytest',          
        '--exclude-module=setuptools',      
        '--exclude-module=pip',             
        '--exclude-module=wheel',           
        '--exclude-module=tcl',             
        '--exclude-module=tk',              
        '--exclude-module=tkinter',         
        '--exclude-module=_tkinter',
        '--exclude-module=unittest',
        '--exclude-module=xml.etree',
        '--exclude-module=lxml',
        
        # 🔥 排除OCR相关模块（无OCR版本的关键）
        '--exclude-module=rapidocr',
        '--exclude-module=onnxruntime',
        '--exclude-module=cv2',
        '--exclude-module=opencv',
        '--exclude-module=opencv-python',
        '--exclude-module=numpy',
        
        # 🔥 排除PyQt5不需要的模块
        '--exclude-module=PyQt5.QtNetwork',
        '--exclude-module=PyQt5.QtOpenGL',
        '--exclude-module=PyQt5.QtPrintSupport',
        '--exclude-module=PyQt5.QtSql',
        '--exclude-module=PyQt5.QtSvg',
        '--exclude-module=PyQt5.QtTest',
        '--exclude-module=PyQt5.QtWebEngine',
        '--exclude-module=PyQt5.QtWebEngineCore',
        '--exclude-module=PyQt5.QtWebEngineWidgets',
        '--exclude-module=PyQt5.QtWebSockets',
        '--exclude-module=PyQt5.QtXml',
        '--exclude-module=PyQt5.QtXmlPatterns',
        '--exclude-module=PyQt5.QtBluetooth',
        '--exclude-module=PyQt5.QtDBus',
        '--exclude-module=PyQt5.QtDesigner',
        '--exclude-module=PyQt5.QtHelp',
        '--exclude-module=PyQt5.QtLocation',
        '--exclude-module=PyQt5.QtMultimedia',
        '--exclude-module=PyQt5.QtMultimediaWidgets',
        '--exclude-module=PyQt5.QtNfc',
        '--exclude-module=PyQt5.QtPositioning',
        '--exclude-module=PyQt5.QtQml',
        '--exclude-module=PyQt5.QtQuick',
        '--exclude-module=PyQt5.QtQuickWidgets',
        '--exclude-module=PyQt5.QtSensors',
        '--exclude-module=PyQt5.QtSerialPort',
        
        # 输出目录
        '--distpath=dist',
        '--workpath=build_no_ocr',
        '--specpath=build_no_ocr',
        
        # 其他选项
        '--clean',                          # 清理临时文件
        '--noconfirm',                      # 不确认覆盖
        '--log-level=ERROR',                # 只显示错误信息
    ]
    
    print("🚀 开始打包 jietuba (无OCR版本)...")
    print("📦 这个版本不包含OCR功能，体积更小")
    
    try:
        import PyInstaller.__main__
        PyInstaller.__main__.run(args)
        print("✅ 打包完成!")
        print("📁 可执行文件位置: dist/jietuba_no_ocr.exe")
        print("💡 提示: 这是无OCR版本，界面上会显示'无OCR版本'")
    except Exception as e:
        print(f"❌ 打包失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    # 检查是否使用 --in-venv 参数（表示已在虚拟环境中重新启动）
    if '--in-venv' not in sys.argv:
        # 首次运行，设置虚拟环境
        if not setup_venv():
            print("\n💥 虚拟环境设置失败！")
            sys.exit(1)
    
    # 在虚拟环境中执行打包
    success = build_executable()
    if success:
        print("\n🎉 打包成功！")
        print("📝 这是无OCR版本，体积更小，适合不需要OCR功能的用户")
    else:
        print("\n💥 打包失败！")
        sys.exit(1)
