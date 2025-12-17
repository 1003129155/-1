"""
智能屏幕捕获器 - 自动选择最佳方案
支持 DXGI (最快) -> Qt5 (降级)
"""
import sys
import numpy as np
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPixmap, QImage, QPainter, QCursor
from PyQt5.QtCore import Qt

class SmartScreenCapture:
    """智能屏幕捕获 - DXGI优先，自动降级到Qt5"""
    
    def __init__(self, enable_dxgi=True):
        """
        初始化智能捕获器
        
        Args:
            enable_dxgi: 是否启用DXGI（False则直接用Qt5）
        """
        self.use_dxgi = False
        self.cameras = []
        self.screens_info = []
        
        if enable_dxgi:
            self._init_dxgi()
        
        if not self.use_dxgi:
            print("📸 使用 Qt5 截图方案")
    
    def _init_dxgi(self):
        """初始化 DXGI 捕获器"""
        try:
            import dxcam
            
            screens = QApplication.screens()
            num_screens = len(screens)
            
            print(f"🔍 检测到 {num_screens} 个屏幕，尝试初始化 DXGI...")
            
            # 尝试为每个屏幕创建 capturer
            for i in range(num_screens):
                try:
                    cam = dxcam.create(output_idx=i, output_color="RGB")
                    if cam is None:
                        print(f"  ⚠️ 屏幕 {i} DXGI 创建失败")
                        self._cleanup_cameras()
                        return
                    
                    geo = screens[i].geometry()
                    self.cameras.append(cam)
                    self.screens_info.append({
                        'camera': cam,
                        'x': geo.x(),
                        'y': geo.y(),
                        'width': cam.width,
                        'height': cam.height,
                    })
                    print(f"  ✅ 屏幕 {i}: {cam.width}x{cam.height} at ({geo.x()}, {geo.y()})")
                    
                except Exception as e:
                    print(f"  ❌ 屏幕 {i} 初始化失败: {e}")
                    self._cleanup_cameras()
                    return
            
            if len(self.cameras) > 0:
                self.use_dxgi = True
                print(f"✅ DXGI 初始化成功！{len(self.cameras)} 个屏幕")
            
        except ImportError:
            print("⚠️ dxcam 未安装，使用 Qt5 方案")
            print("   安装命令: pip install dxcam")
        except Exception as e:
            print(f"⚠️ DXGI 初始化失败: {e}")
            self._cleanup_cameras()
    
    def _cleanup_cameras(self):
        """清理已创建的 cameras"""
        for cam in self.cameras:
            try:
                cam.release()
            except:
                pass
        self.cameras = []
        self.screens_info = []
        self.use_dxgi = False
    
    def capture_all_screens(self):
        """
        捕获所有屏幕
        
        Returns:
            tuple: (QPixmap, virtual_desktop_info)
        """
        if self.use_dxgi:
            try:
                return self._capture_dxgi()
            except Exception as e:
                print(f"⚠️ DXGI 捕获失败，降级到 Qt5: {e}")
                # 不禁用 DXGI，下次继续尝试
                return self._capture_qt5()
        else:
            return self._capture_qt5()
    
    def _capture_dxgi(self):
        """DXGI 方式捕获"""
        # 触发屏幕更新（关键！）
        pos = QCursor.pos()
        QCursor.setPos(pos.x() + 1, pos.y())
        QCursor.setPos(pos)
        
        # 抓取所有屏幕
        frames = []
        for i, info in enumerate(self.screens_info):
            frame = info['camera'].grab()
            if frame is None:
                print(f"⚠️ DXGI 屏幕 {i} 返回 None，降级到 Qt5")
                return self._capture_qt5()
            frames.append((frame, info))
        
        # 单屏：直接返回
        if len(frames) == 1:
            frame, info = frames[0]
            qimage = self._numpy_to_qimage(frame)
            pixmap = QPixmap.fromImage(qimage)
            
            virtual_info = {
                'offset_x': 0,
                'offset_y': 0,
                'width': info['width'],
                'height': info['height'],
                'min_x': 0,
                'min_y': 0,
                'max_x': info['width'],
                'max_y': info['height'],
            }
            
            return pixmap, virtual_info
        
        # 多屏：需要合成
        return self._composite_dxgi_frames(frames)
    
    def _composite_dxgi_frames(self, frames):
        """
        合成多个 DXGI 帧（GPU 加速优化）
        
        策略：直接在 QPixmap 上用 QPainter 合成，避免 CPU 端 numpy 拷贝
        - numpy 合成 (CPU): 需要额外内存拷贝
        - QPainter 合成 (GPU): 直接在显存操作，更快
        """
        # 计算虚拟桌面边界
        min_x = min(info['x'] for _, info in frames)
        min_y = min(info['y'] for _, info in frames)
        max_x = max(info['x'] + info['width'] for _, info in frames)
        max_y = max(info['y'] + info['height'] for _, info in frames)
        
        total_width = max_x - min_x
        total_height = max_y - min_y
        
        # ✅ 直接创建 QPixmap 画布（GPU 内存）
        combined = QPixmap(total_width, total_height)
        combined.fill(Qt.black)
        
        # ✅ 用 QPainter 在 GPU 上合成
        painter = QPainter(combined)
        
        for frame, info in frames:
            x_offset = info['x'] - min_x
            y_offset = info['y'] - min_y
            
            # 转换单个屏幕（只需一次 CPU→GPU 上传）
            qimage = self._numpy_to_qimage(frame)
            pixmap = QPixmap.fromImage(qimage)
            
            # GPU 上绘制（无需 CPU 内存拷贝）
            painter.drawPixmap(x_offset, y_offset, pixmap)
        
        painter.end()
        
        virtual_info = {
            'offset_x': min_x,
            'offset_y': min_y,
            'width': total_width,
            'height': total_height,
            'min_x': min_x,
            'min_y': min_y,
            'max_x': max_x,
            'max_y': max_y,
        }
        
        return combined, virtual_info
    
    def _numpy_to_qimage(self, array):
        """
        numpy array 转 QImage（零拷贝优化）
        
        关键：保持 array 引用，避免被 GC 释放
        """
        height, width, channels = array.shape
        bytes_per_line = channels * width
        
        # 确保数据是连续的
        if not array.flags['C_CONTIGUOUS']:
            array = np.ascontiguousarray(array)
        
        qimage = QImage(
            array.data,
            width,
            height,
            bytes_per_line,
            QImage.Format_RGB888
        )
        
        # ✅ 零拷贝：将 array 保存为 QImage 的属性，延长生命周期
        # 这样 QImage 就能安全使用 array 的内存，无需拷贝
        qimage._numpy_holder = array
        
        return qimage
    
    def _capture_qt5(self):
        """Qt5 降级方案"""
        screens = QApplication.screens()
        
        # 单屏
        if len(screens) == 1:
            screen = screens[0]
            pixmap = screen.grabWindow(0)
            geo = screen.geometry()
            
            virtual_info = {
                'offset_x': 0,
                'offset_y': 0,
                'width': geo.width(),
                'height': geo.height(),
                'min_x': 0,
                'min_y': 0,
                'max_x': geo.width(),
                'max_y': geo.height(),
            }
            
            return pixmap, virtual_info
        
        # 多屏：需要合成
        captures = []
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        for screen in screens:
            pm = screen.grabWindow(0)
            geo = screen.geometry()
            
            captures.append({
                'pixmap': pm,
                'x': geo.x(),
                'y': geo.y(),
                'width': geo.width(),
                'height': geo.height(),
            })
            
            min_x = min(min_x, geo.x())
            min_y = min(min_y, geo.y())
            max_x = max(max_x, geo.x() + geo.width())
            max_y = max(max_y, geo.y() + geo.height())
        
        # 合成
        total_width = max_x - min_x
        total_height = max_y - min_y
        combined = QPixmap(total_width, total_height)
        combined.fill(Qt.black)
        
        painter = QPainter(combined)
        for cap in captures:
            rx = cap['x'] - min_x
            ry = cap['y'] - min_y
            painter.drawPixmap(rx, ry, cap['pixmap'])
        painter.end()
        
        virtual_info = {
            'offset_x': min_x,
            'offset_y': min_y,
            'width': total_width,
            'height': total_height,
            'min_x': min_x,
            'min_y': min_y,
            'max_x': max_x,
            'max_y': max_y,
        }
        
        return combined, virtual_info
    
    def release(self):
        """释放资源"""
        self._cleanup_cameras()
    
    def __del__(self):
        """析构函数"""
        self.release()


# 测试代码
if __name__ == "__main__":
    import time
    
    app = QApplication(sys.argv)
    
    print("="*60)
    print("测试智能屏幕捕获器")
    print("="*60)
    
    # 创建捕获器
    capturer = SmartScreenCapture(enable_dxgi=True)
    
    # 测试性能
    print("\n性能测试:")
    times = []
    for i in range(5):
        start = time.perf_counter()
        pixmap, info = capturer.capture_all_screens()
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
        print(f"  第{i+1}次: {elapsed:.2f} ms - {pixmap.width()}x{pixmap.height()}")
    
    avg = sum(times) / len(times)
    print(f"\n📊 平均耗时: {avg:.2f} ms")
    print(f"📐 虚拟桌面: {info['width']}x{info['height']}")
    
    # 清理
    capturer.release()
    
    print("\n✅ 测试完成")
