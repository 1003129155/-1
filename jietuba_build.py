#!/usr/bin/env python3
"""
jietuba_build.py - PyInstaller 打包脚本

使用 PyInstaller 将 jietuba 截图工具打包成独立可执行文件。
包含所有必要的依赖和资源文件,并进行体积优化。

主要功能:
- 自动检测或创建虚拟环境
- 配置 PyInstaller 打包参数
- 排除不必要的模块减小体积
- 生成单文件可执行程序

使用方法:
    python jietuba_build.py
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
    venv_dir = os.path.join(current_dir, 'venv')
    
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
    
    # 检查依赖是否已安装
    print("🔍 检查依赖包...")
    try:
        result = subprocess.run(
            [venv_pip, 'list'],
            capture_output=True,
            text=True,
            check=True
        )
        installed_packages = result.stdout.lower()
        
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
    """构建可执行文件"""
    
    # 导入 PyInstaller（必须在虚拟环境中）
    try:
        import PyInstaller.__main__
    except ImportError:
        print("❌ PyInstaller 未安装，请先安装: pip install PyInstaller")
        return False
    
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # PyInstaller 参数
    args = [
        'main.py',                          # 主程序入口
        '--name=jietuba',                   # 可执行文件名
        '--onefile',                        # 打包成单个文件
        '--windowed',                       # Windows下隐藏控制台
        # '--icon=icon.ico',                # 图标文件(如果有) - 暂时注释掉
        
        # 核心依赖
        '--hidden-import=PyQt5.QtCore',
        '--hidden-import=PyQt5.QtGui',
        '--hidden-import=PyQt5.QtWidgets',
        
        # PIL/Pillow（图像处理 + 长截图拼接）
        '--hidden-import=PIL',
        '--hidden-import=PIL.Image',
        
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
        
    
        '--exclude-module=cv2',             
        '--exclude-module=numpy',           
        '--exclude-module=opencv',
        '--exclude-module=opencv-python',
        
        # 输出目录
        '--distpath=dist',
        '--workpath=build',
        '--specpath=build',
        
        # 其他选项
        '--clean',                          # 清理临时文件
        '--noconfirm',                      # 不确认覆盖
        '--log-level=ERROR',                # 只显示错误信息
    ]
    
    print("🚀 开始打包 jietuba...")

    
    try:
        import PyInstaller.__main__
        PyInstaller.__main__.run(args)
        print("✅ 打包完成!")
        print("📁 可执行文件位置: dist/jietuba.exe")
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
    else:
        print("\n💥 打包失败！")
        sys.exit(1)
