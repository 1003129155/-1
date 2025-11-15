#!/usr/bin/env python3
"""
jietuba_build_nuitka.py - Nuitka 打包脚本

使用 Nuitka 将 jietuba 截图工具编译成高性能可执行文件。
相比 PyInstaller，Nuitka 生成的文件体积更小、启动更快。

主要功能:
- 使用现有虚拟环境
- 配置 Nuitka 编译参数
- 优化编译选项减小体积
- 生成单文件可执行程序

使用方法:
    python jietuba_build_nuitka.py
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
        print("❌ 虚拟环境不存在，请先运行 jietuba_build.py 创建虚拟环境")
        return False
    
    # 确定虚拟环境的 Python 和 pip 路径
    if platform.system() == 'Windows':
        venv_python = os.path.join(venv_dir, 'Scripts', 'python.exe')
        venv_pip = os.path.join(venv_dir, 'Scripts', 'pip.exe')
    else:
        venv_python = os.path.join(venv_dir, 'bin', 'python')
        venv_pip = os.path.join(venv_dir, 'bin', 'pip')
    
    if not os.path.exists(venv_python):
        print(f"❌ 虚拟环境 Python 未找到: {venv_python}")
        return False
    
    # 检查并安装 Nuitka
    print("🔍 检查 Nuitka...")
    try:
        result = subprocess.run(
            [venv_pip, 'show', 'nuitka'],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            print("📦 安装 Nuitka...")
            subprocess.run([venv_pip, 'install', 'nuitka', 'ordered-set'], check=True)
            print("✅ Nuitka 安装成功")
        else:
            print("✅ Nuitka 已安装")
    except subprocess.CalledProcessError as e:
        print(f"❌ 安装 Nuitka 失败: {e}")
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
    """使用 Nuitka 构建可执行文件"""
    
    # 检查 Nuitka 是否可用
    try:
        import nuitka
        # Nuitka 版本信息在 nuitka.Version 模块中
        try:
            from nuitka.Version import getNuitkaVersion
            print(f"✅ Nuitka 版本: {getNuitkaVersion()}")
        except:
            print("✅ Nuitka 已安装")
    except ImportError:
        print("❌ Nuitka 未安装，请先安装: pip install nuitka")
        return False
    
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Nuitka 参数
    args = [
        sys.executable,                     # 当前 Python 解释器
        '-m', 'nuitka',                     # 使用 Nuitka 模块
        
        # 基础选项
        '--standalone',                     # 独立模式，包含所有依赖
        '--onefile',                        # 打包成单个文件
        '--output-dir=dist/nuitka',         # 输出目录（避免与 PyInstaller 冲突）
        '--output-filename=jietuba.exe',    # 输出文件名
        
        # Windows 特定选项
        '--windows-disable-console',        # 隐藏控制台窗口
        # '--windows-icon-from-ico=icon.ico', # 图标文件（如果有）
        
        # 🔥 PyQt5 关键配置 - 必须包含插件和数据文件
        '--enable-plugin=pyqt5',            # 启用 PyQt5 插件（自动处理依赖）
        '--include-package=PyQt5',
        '--include-package-data=PyQt5',     # 包含 PyQt5 的数据文件（插件等）
        '--include-package=PIL',
        '--include-package=pynput',
        '--include-module=win32gui',
        '--include-module=win32api',
        '--include-module=win32con',
        '--include-module=win32ui',
        '--include-module=pywintypes',
        '--include-module=pythoncom',
        
        # 包含项目模块
        '--include-module=jietuba_build',
        '--include-module=jietuba_drawing',
        '--include-module=jietuba_long_stitch',
        '--include-module=jietuba_public',
        '--include-module=jietuba_resource',
        '--include-module=jietuba_screenshot',
        '--include-module=jietuba_scroll',
        '--include-module=jietuba_stitch',
        '--include-module=jietuba_toolbar',
        '--include-module=jietuba_ui_components',
        '--include-module=jietuba_widgets',
        
        # 🔥 明确告诉 Nuitka 不要尝试导入 win32com.gen_py 下的这些模块
        '--nofollow-import-to=win32com.gen_py.jietuba_build',
        '--nofollow-import-to=win32com.gen_py.jietuba_drawing',
        '--nofollow-import-to=win32com.gen_py.jietuba_long_stitch',
        '--nofollow-import-to=win32com.gen_py.jietuba_public',
        '--nofollow-import-to=win32com.gen_py.jietuba_resource',
        '--nofollow-import-to=win32com.gen_py.jietuba_screenshot',
        '--nofollow-import-to=win32com.gen_py.jietuba_scroll',
        '--nofollow-import-to=win32com.gen_py.jietuba_stitch',
        '--nofollow-import-to=win32com.gen_py.jietuba_toolbar',
        '--nofollow-import-to=win32com.gen_py.jietuba_ui_components',
        '--nofollow-import-to=win32com.gen_py.jietuba_widgets',
        '--nofollow-import-to=win32com.gen_py.main',
        
        # 排除不需要的大型模块
        '--nofollow-import-to=matplotlib',
        '--nofollow-import-to=pandas',
        '--nofollow-import-to=scipy',
        '--nofollow-import-to=IPython',
        '--nofollow-import-to=notebook',
        '--nofollow-import-to=pytest',
        '--nofollow-import-to=setuptools',
        '--nofollow-import-to=pip',
        '--nofollow-import-to=wheel',
        '--nofollow-import-to=tcl',
        '--nofollow-import-to=tk',
        '--nofollow-import-to=tkinter',
        '--nofollow-import-to=_tkinter',
        '--nofollow-import-to=unittest',
        '--nofollow-import-to=cv2',
        '--nofollow-import-to=numpy',
        '--nofollow-import-to=opencv',
        
        # 排除 PyQt5 不需要的模块
        '--nofollow-import-to=PyQt5.QtNetwork',
        '--nofollow-import-to=PyQt5.QtOpenGL',
        '--nofollow-import-to=PyQt5.QtPrintSupport',
        '--nofollow-import-to=PyQt5.QtSql',
        '--nofollow-import-to=PyQt5.QtSvg',
        '--nofollow-import-to=PyQt5.QtTest',
        '--nofollow-import-to=PyQt5.QtWebEngine',
        '--nofollow-import-to=PyQt5.QtWebEngineCore',
        '--nofollow-import-to=PyQt5.QtWebEngineWidgets',
        '--nofollow-import-to=PyQt5.QtWebSockets',
        '--nofollow-import-to=PyQt5.QtXml',
        
        # 优化选项
        '--assume-yes-for-downloads',       # 自动下载依赖
        '--remove-output',                  # 删除旧的输出文件
        '--show-progress',                  # 显示进度
        '--show-memory',                    # 显示内存使用
        
        # 主程序入口
        'main.py',
    ]
    
    print("🚀 开始使用 Nuitka 编译 jietuba...")
    print("⏳ 这可能需要几分钟，请耐心等待...\n")
    
    try:
        subprocess.run(args, check=True)
        print("\n✅ 编译完成!")
        print("📁 可执行文件位置: dist/nuitka/jietuba.exe")
        
        # 显示文件大小
        exe_path = os.path.join(current_dir, 'dist', 'nuitka', 'jietuba.exe')
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"📊 文件大小: {size_mb:.2f} MB")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 编译失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        return False

if __name__ == "__main__":
    # 检查是否使用 --in-venv 参数（表示已在虚拟环境中重新启动）
    if '--in-venv' not in sys.argv:
        # 首次运行，设置虚拟环境
        if not setup_venv():
            print("\n💥 虚拟环境设置失败！")
            sys.exit(1)
    
    # 在虚拟环境中执行打包
    print("="*60)
    print("🔧 Nuitka 编译器 - jietuba 截图工具")
    print("="*60 + "\n")
    
    success = build_executable()
    
    if success:
        print("\n" + "="*60)
        print("🎉 编译成功！")
        print("="*60)
        print("\n💡 提示:")
        print("  - Nuitka 生成的文件比 PyInstaller 更优化")
        print("  - 启动速度更快，内存占用更少")
        print("  - 可以直接运行 dist/jietuba.exe")
    else:
        print("\n" + "="*60)
        print("💥 编译失败！")
        print("="*60)
        sys.exit(1)
