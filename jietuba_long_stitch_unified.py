#!/usr/bin/env python3
"""
长截图拼接统一接口
支持 Python哈希识别 版本和 rust特征点位 版本的自动切换
"""

from PIL import Image
from typing import List, Optional
import os


class LongStitchConfig:
    """长截图拼接配置"""
    
    # 引擎选择
    ENGINE_AUTO = "auto"      # 自动选择（优先 Rust）
    ENGINE_RUST = "rust"      # 强制使用 Rust
    ENGINE_PYTHON = "python"  # 强制使用 Python
    
    def __init__(self):
        # 默认配置
        self.engine = self.ENGINE_AUTO
        
        # 通用参数
        self.direction = 0  # 0=垂直, 1=水平
        self.verbose = True
        
        # Python 版本参数
        self.ignore_right_pixels = 20  # 忽略右侧像素（滚动条）
        
        # Rust 版本参数
        self.sample_rate = 0.5          # 采样率
        self.min_sample_size = 300      # 最小采样尺寸
        self.max_sample_size = 800      # 最大采样尺寸
        self.corner_threshold = 64      # 特征点阈值
        self.descriptor_patch_size = 9  # 描述符大小
        self.min_size_delta = 1         # 最小变化量（降低到1，强制每张都更新索引）
        self.try_rollback = False       # 是否尝试回滚（关闭以避免误判）


# 全局配置实例
config = LongStitchConfig()


def set_engine(engine: str):
    """
    设置拼接引擎
    
    参数:
        engine: "auto", "rust", "python"
    """
    if engine not in [LongStitchConfig.ENGINE_AUTO, 
                      LongStitchConfig.ENGINE_RUST, 
                      LongStitchConfig.ENGINE_PYTHON]:
        raise ValueError(f"Invalid engine: {engine}. Must be 'auto', 'rust', or 'python'")
    
    config.engine = engine
    if config.verbose:
        print(f"[长截图] 引擎设置为: {engine}")


def configure(
    engine: str = "auto",
    direction: int = 0,
    verbose: bool = True,
    # Python 版本参数
    ignore_right_pixels: int = 20,
    # Rust 版本参数
    sample_rate: float = 0.5,
    corner_threshold: int = 64,
    min_size_delta: int = 1,
    try_rollback: bool = False,
):
    """
    配置长截图拼接参数
    
    参数:
        engine: 引擎选择 ("auto", "rust", "python")
        direction: 方向 (0=垂直, 1=水平)
        verbose: 是否显示详细信息
        
        # Python 版本参数
        ignore_right_pixels: 忽略右侧像素数
        
        # Rust 版本参数
        sample_rate: 采样率 (0.0-1.0)
        corner_threshold: 特征点阈值
        min_size_delta: 索引重建阈值（像素）
        try_rollback: 是否启用回滚检测
    """
    config.engine = engine
    config.direction = direction
    config.verbose = verbose
    
    # Python 参数
    config.ignore_right_pixels = ignore_right_pixels
    
    # Rust 参数
    config.sample_rate = sample_rate
    config.corner_threshold = corner_threshold
    config.min_size_delta = min_size_delta
    config.try_rollback = try_rollback
    
    if verbose:
        print(f"[长截图] 配置已更新: engine={engine}, direction={direction}")


def _detect_engine() -> str:
    """检测可用的引擎"""
    if config.engine == LongStitchConfig.ENGINE_PYTHON:
        return "python"
    elif config.engine == LongStitchConfig.ENGINE_RUST:
        return "rust"
    
    # AUTO 模式：优先尝试 Rust
    try:
        import jietuba_rust
        return "rust"
    except ImportError:
        if config.verbose:
            print("[长截图] Rust 模块未安装，使用 Python 版本")
        return "python"


def stitch_images(images: List[Image.Image]) -> Optional[Image.Image]:
    """
    拼接多张图片（统一接口）
    
    参数:
        images: PIL Image 对象列表
    
    返回:
        拼接后的图片，失败返回 None
    """
    if not images or len(images) == 0:
        if config.verbose:
            print("[长截图] 错误: 没有图片需要拼接")
        return None
    
    if len(images) == 1:
        if config.verbose:
            print("[长截图] 只有一张图片，直接返回")
        return images[0]
    
    # 检测使用哪个引擎
    engine = _detect_engine()
    
    if config.verbose:
        print(f"[长截图] 🚀 使用 {engine.upper()} 引擎拼接 {len(images)} 张图片")
    
    try:
        if engine == "rust":
            result = _stitch_with_rust(images)
            if result:
                if config.verbose:
                    print(f"[长截图] ✅ Rust 引擎拼接成功")
                return result
            else:
                # Rust 返回 None（拼接失败）
                if config.verbose:
                    print(f"[长截图] ⚠️  Rust 引擎返回 None")
                # 如果是 AUTO 模式，尝试回退
                if config.engine == LongStitchConfig.ENGINE_AUTO:
                    if config.verbose:
                        print("[长截图] 🔄 自动回退到 Python 引擎...")
                    try:
                        result = _stitch_with_python(images)
                        if result and config.verbose:
                            print(f"[长截图] ✅ Python 引擎拼接成功（回退）")
                        return result
                    except Exception as e2:
                        if config.verbose:
                            print(f"[长截图] ❌ Python 拼接也失败: {e2}")
                        return None
                return None
        else:
            result = _stitch_with_python(images)
            if result and config.verbose:
                print(f"[长截图] ✅ Python 引擎拼接成功")
            return result
    except Exception as e:
        if config.verbose:
            print(f"[长截图] ❌ {engine.upper()} 引擎拼接失败: {e}")
        
        # 如果 Rust 失败且是 AUTO 模式，尝试回退到 Python
        if engine == "rust" and config.engine == LongStitchConfig.ENGINE_AUTO:
            if config.verbose:
                print("[长截图] 🔄 自动回退到 Python 引擎...")
            try:
                result = _stitch_with_python(images)
                if result and config.verbose:
                    print(f"[长截图] ✅ Python 引擎拼接成功（回退）")
                return result
            except Exception as e2:
                if config.verbose:
                    print(f"[长截图] ❌ Python 拼接也失败: {e2}")
                return None
        
        return None


def _stitch_with_rust(images: List[Image.Image]) -> Optional[Image.Image]:
    """使用 Rust 版本拼接"""
    from jietuba_long_stitch_rust import stitch_pil_images
    
    result = stitch_pil_images(
        images,
        direction=config.direction,
        sample_rate=config.sample_rate,
        corner_threshold=config.corner_threshold,
        min_size_delta=config.min_size_delta,
        try_rollback=config.try_rollback,
        verbose=config.verbose,
    )
    
    return result


def _stitch_with_python(images: List[Image.Image]) -> Optional[Image.Image]:
    """使用 Python 版本拼接"""
    from jietuba_long_stitch import stitch_pil_images
    
    result = stitch_pil_images(
        images,
        ignore_right_pixels=config.ignore_right_pixels,
    )
    
    return result


def stitch_files(
    image_paths: List[str],
    output_path: str,
    **kwargs
) -> bool:
    """
    从文件拼接图片并保存
    
    参数:
        image_paths: 图片文件路径列表
        output_path: 输出文件路径
        **kwargs: 其他配置参数（传递给 configure）
    
    返回:
        True=成功, False=失败
    """
    # 应用配置
    if kwargs:
        configure(**kwargs)
    
    if config.verbose:
        print(f"[长截图] 加载 {len(image_paths)} 张图片...")
    
    # 加载图片
    images = []
    for path in image_paths:
        try:
            img = Image.open(path)
            images.append(img)
            if config.verbose:
                print(f"  ✓ {path} ({img.size})")
        except Exception as e:
            if config.verbose:
                print(f"  ✗ {path}: {e}")
            return False
    
    # 拼接
    result = stitch_images(images)
    
    if result:
        # 保存
        try:
            result.save(output_path, "PNG", quality=95)
            if config.verbose:
                print(f"[长截图] ✓ 拼接成功，已保存到: {output_path}")
                print(f"[长截图]   最终尺寸: {result.size}")
            return True
        except Exception as e:
            if config.verbose:
                print(f"[长截图] ✗ 保存失败: {e}")
            return False
    else:
        if config.verbose:
            print(f"[长截图] ✗ 拼接失败")
        return False


# 便捷函数（向后兼容）
def stitch_pil_images(
    images: List[Image.Image],
    ignore_right_pixels: int = None,
    direction: int = None,
) -> Optional[Image.Image]:
    """
    向后兼容的接口（自动参数适配）
    
    参数:
        images: PIL Image 对象列表
        ignore_right_pixels: Python 版本参数（可选）
        direction: 方向（可选）
    
    返回:
        拼接后的图片
    """
    # 临时保存配置
    old_direction = config.direction
    old_ignore = config.ignore_right_pixels
    
    try:
        # 应用参数
        if direction is not None:
            config.direction = direction
        if ignore_right_pixels is not None:
            config.ignore_right_pixels = ignore_right_pixels
        
        # 拼接
        return stitch_images(images)
    finally:
        # 恢复配置
        config.direction = old_direction
        config.ignore_right_pixels = old_ignore


# 示例用法
if __name__ == "__main__":
    print("长截图拼接统一接口示例\n")
    
    # 示例 1: 自动选择引擎（推荐）
    print("=" * 60)
    print("示例 1: 自动选择引擎（优先 Rust）")
    print("=" * 60)
    print("""
from jietuba_long_stitch_unified import stitch_images, configure

# 配置（可选，使用默认值也可以）
configure(
    engine="auto",      # 自动选择（优先 Rust）
    direction=0,        # 垂直拼接
    verbose=True,       # 显示详情
)

# 加载图片
images = [Image.open(f"img{i}.png") for i in range(1, 4)]

# 拼接
result = stitch_images(images)

if result:
    result.save("output.png")
""")
    
    # 示例 2: 强制使用 Rust
    print("\n" + "=" * 60)
    print("示例 2: 强制使用 Rust 引擎")
    print("=" * 60)
    print("""
from jietuba_long_stitch_unified import stitch_images, configure

configure(
    engine="rust",          # 强制 Rust
    sample_rate=0.5,        # Rust 专用参数
    corner_threshold=64,
    try_rollback=False,
)

result = stitch_images(images)
""")
    
    # 示例 3: 强制使用 Python
    print("\n" + "=" * 60)
    print("示例 3: 强制使用 Python 引擎")
    print("=" * 60)
    print("""
from jietuba_long_stitch_unified import stitch_images, configure

configure(
    engine="python",            # 强制 Python
    ignore_right_pixels=20,     # Python 专用参数
)

result = stitch_images(images)
""")
    
    # 示例 4: 向后兼容
    print("\n" + "=" * 60)
    print("示例 4: 向后兼容旧代码")
    print("=" * 60)
    print("""
# 旧代码无需修改，自动适配
from jietuba_long_stitch_unified import stitch_pil_images

result = stitch_pil_images(images, ignore_right_pixels=20)
""")
    
    # 示例 5: 文件拼接
    print("\n" + "=" * 60)
    print("示例 5: 直接从文件拼接")
    print("=" * 60)
    print("""
from jietuba_long_stitch_unified import stitch_files

success = stitch_files(
    image_paths=["img1.png", "img2.png", "img3.png"],
    output_path="output.png",
    engine="auto",
    direction=0,
)
""")
    
    print("\n" + "=" * 60)
    print("配置说明")
    print("=" * 60)
    print("""
引擎选择:
  - "auto"   : 自动选择（优先 Rust，失败回退 Python）
  - "rust"   : 强制使用 Rust（更快，10倍加速）
  - "python" : 强制使用 Python（更稳定，兼容性好）

通用参数:
  - direction: 0=垂直, 1=水平
  - verbose: 是否显示详细信息

Python 专用参数:
  - ignore_right_pixels: 忽略右侧像素（排除滚动条）

Rust 专用参数:
  - sample_rate: 采样率（0.3-0.8，越低越精确但越慢）
  - corner_threshold: 特征点阈值（30-80，越低检测越多特征）
  - try_rollback: 回滚检测（False 避免误判，True 检测重复）
""")
