#!/usr/bin/env python3
"""
jietuba_build.py - PyInstaller 打包脚本

使用 PyInstaller 将 jietuba 截图工具打包成独立可执行文件。
包含所有必要的依赖和资源文件,并进行体积优化。

主要功能:
- 配置 PyInstaller 打包参数
- 排除不必要的模块减小体积
- 生成单文件可执行程序
_ UPX 压缩支持

使用方法:
    python jietuba_build.py
"""

import PyInstaller.__main__
import os
import sys

def build_executable():
    """构建可执行文件"""
    
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # PyInstaller 参数
    args = [
        'main.py',                          # 主程序入口
        '--name=jietuba',                   # 可执行文件名
        '--onefile',                        # 打包成单个文件
        '--windowed',                       # Windows下隐藏控制台
        # '--icon=icon.ico',                # 图标文件(如果有) - 暂时注释掉
        
        # 🔥 压缩优化（关键！）
        '--upx-dir=UPX',                    # 启用UPX压缩
        '--strip',                          # 去除调试符号
        
        # 核心依赖
        '--hidden-import=PyQt5.QtCore',
        '--hidden-import=PyQt5.QtGui',
        '--hidden-import=PyQt5.QtWidgets',
        
        # OpenCV和NumPy（智能框体识别 + 长截图拼接）
        '--hidden-import=cv2',              
        '--hidden-import=numpy',
        
        # PIL/Pillow（长截图拼接必需）
        '--hidden-import=PIL',
        '--hidden-import=PIL.Image',
        
        # 键盘鼠标监听（长截图滚轮检测）
        '--hidden-import=pynput.mouse',
        '--hidden-import=pynput.keyboard',
        
        # 🔥 排除不需要的大型模块（关键优化！）
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
        
        # 🔥 排除PyQt5不需要的模块（最关键！）
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
        
        # 🔥 排除OpenCV不需要的模块
        '--exclude-module=cv2.aruco',       
        '--exclude-module=cv2.bgsegm',      
        '--exclude-module=cv2.bioinspired', 
        '--exclude-module=cv2.ccalib',      
        '--exclude-module=cv2.datasets',    
        '--exclude-module=cv2.dnn',         
        '--exclude-module=cv2.face',        
        '--exclude-module=cv2.ml',          
        '--exclude-module=cv2.optflow',     
        '--exclude-module=cv2.stereo',      
        '--exclude-module=cv2.superres',    
        '--exclude-module=cv2.tracking',    
        '--exclude-module=cv2.videostab',
        
        # 🔥 排除NumPy的测试和文档模块
        '--exclude-module=numpy.distutils',
        '--exclude-module=numpy.f2py',
        '--exclude-module=numpy.testing',
        
        # 输出目录
        '--distpath=dist',
        '--workpath=build',
        '--specpath=build',
        
        # 其他选项
        '--clean',                          # 清理临时文件
        '--noconfirm',                      # 不确认覆盖
        '--log-level=ERROR',                # 只显示错误信息
    ]
    
    print("🚀 开始打包 jietuba（体积优化版）...")
    print("📦 必需依赖:")
    print("   ✅ PyQt5 (仅Core/Gui/Widgets)")
    print("   ✅ OpenCV (cv2) - 仅核心功能")
    print("   ✅ NumPy - 核心数组计算")
    print("   ✅ PIL/Pillow - 图像处理")
    print("   ✅ pynput - 键鼠监听")
    print()
    print("🔥 体积优化措施:")
    print("   • 排除 PyQt5 的 20+ 个不需要的模块（Web/Network/SQL等）")
    print("   • 排除 OpenCV 的 10+ 个高级功能模块")
    print("   • 排除 matplotlib/pandas/scipy 等大型库")
    print("   • 启用 UPX 压缩（额外压缩 30-40%）")
    print("   • 启用符号剥离和压缩")
    print("   • 预计可减少 50-70% 的体积")
    print()
    
    try:
        PyInstaller.__main__.run(args)
        print("✅ 打包完成!")
        print("📁 可执行文件位置: dist/jietuba.exe")
    except Exception as e:
        print(f"❌ 打包失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = build_executable()
    if success:
        print("\n🎉 打包成功！")
    else:
        print("\n💥 打包失败！")
        sys.exit(1)
