#!/usr/bin/env python3
"""
长截图拼接脚本 - Rust 加速版本
使用 Rust 实现的特征点匹配算法进行高性能图片拼接
"""

from PIL import Image
import io
from typing import List, Optional
import sys


class RustLongStitch:
    """使用 Rust 算法的长截图拼接类"""

    def __init__(
        self,
        direction: int = 0,  # 0=垂直, 1=水平
        sample_rate: float = 0.5,
        min_sample_size: int = 300,
        max_sample_size: int = 800,
        corner_threshold: int = 64,
        descriptor_patch_size: int = 9,
        min_size_delta: int = 64,
        try_rollback: bool = True,
    ):
        """
        初始化长截图拼接器

        参数:
            direction: 滚动方向 (0=垂直滚动, 1=水平滚动)
            sample_rate: 采样率 (0.0-1.0，用于缩放图片以加快处理)
            min_sample_size: 最小采样尺寸
            max_sample_size: 最大采样尺寸
            corner_threshold: 特征点检测阈值 (越低检测越多特征点)
            descriptor_patch_size: 特征描述符块大小
            min_size_delta: 最小变化量阈值
            try_rollback: 是否尝试回滚匹配
        """
        try:
            import jietuba_rust
        except ImportError:
            raise ImportError(
                "无法导入 jietuba_rust 模块。请先编译 Rust 代码:\n"
                "  cd rs\n"
                "  maturin develop --release\n"
                "或者:\n"
                "  pip install maturin\n"
                "  cd rs && maturin develop --release"
            )

        self.service = jietuba_rust.PyScrollScreenshotService()
        self.service.init(
            direction,
            sample_rate,
            min_sample_size,
            max_sample_size,
            corner_threshold,
            descriptor_patch_size,
            min_size_delta,
            try_rollback,
        )
        self.direction = direction

    def add_image(self, image: Image.Image, direction: int = 1) -> Optional[int]:
        """
        添加一张图片到拼接队列

        参数:
            image: PIL Image 对象
            direction: 0=上/左图片列表, 1=下/右图片列表

        返回:
            重叠尺寸 (像素)，如果未找到重叠则返回 None
        """
        # 将 PIL Image 转换为字节
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        # 调用 Rust 接口
        overlap_size, is_rollback, result_direction = self.service.add_image(
            image_bytes, direction
        )

        if is_rollback:
            print("  ⚠️  检测到回滚（图片可能重复或顺序错误）")

        if overlap_size is not None:
            print(f"  ✅ 找到重叠区域: {overlap_size} 像素")
            # 显示索引状态（调试用）
            top_count, bottom_count = self.get_image_count()
            print(f"     索引状态: top_list={top_count}张, bottom_list={bottom_count}张")
        else:
            print("  ❌ 未找到重叠区域")

        return overlap_size

    def export(self) -> Optional[Image.Image]:
        """
        导出最终合成的长截图

        返回:
            PIL Image 对象，如果没有图片则返回 None
        """
        result_bytes = self.service.export()

        if result_bytes is None:
            return None

        # 将字节转换为 PIL Image
        return Image.open(io.BytesIO(result_bytes))

    def clear(self):
        """清除所有已添加的图片"""
        self.service.clear()

    def get_image_count(self) -> tuple:
        """
        获取当前图片数量

        返回:
            (top_count, bottom_count) 元组
        """
        return self.service.get_image_count()


def stitch_pil_images(
    images: List[Image.Image],
    direction: int = 0,
    sample_rate: float = 0.5,
    corner_threshold: int = 30,
    min_size_delta: int = 1,
    try_rollback: bool = False,
    verbose: bool = True,
) -> Optional[Image.Image]:
    """
    拼接多张PIL图片对象（兼容原有接口）

    参数:
        images: PIL Image对象列表
        direction: 滚动方向 (0=垂直, 1=水平)
        sample_rate: 采样率，控制特征提取的图片缩放比例
        corner_threshold: 特征点阈值（越低检测越多特征点）
        min_size_delta: 索引重建阈值（像素），设为1强制每张都更新
        try_rollback: 是否尝试回滚匹配
        verbose: 是否输出详细信息

    返回:
        拼接后的PIL Image对象，失败返回None
    """
    if not images or len(images) == 0:
        if verbose:
            print("错误: 没有图片需要拼接")
        return None

    if len(images) == 1:
        if verbose:
            print("只有一张图片，直接返回")
        return images[0]

    if verbose:
        print(f"开始使用 Rust 算法拼接 {len(images)} 张图片...")
        print(f"方向: {'垂直' if direction == 0 else '水平'}")
        print(f"参数: sample_rate={sample_rate}, corner_threshold={corner_threshold}, min_size_delta={min_size_delta}, try_rollback={try_rollback}")

    try:
        # 创建拼接器
        stitcher = RustLongStitch(
            direction=direction,
            sample_rate=sample_rate,
            min_sample_size=300,
            max_sample_size=800,
            corner_threshold=corner_threshold,
            min_size_delta=min_size_delta,
            try_rollback=try_rollback,
        )

        # 添加所有图片
        has_failure = False  # 🆕 标记是否有图片失败
        for i, img in enumerate(images):
            if verbose:
                print(f"\n处理第 {i+1}/{len(images)} 张图片: {img.size}")

            # 向下滚动：所有图片都用 direction=1 (Bottom)
            # 第1张:添加到bottom,建立top_index
            # 第2张:在bottom_index中查找失败 → 回滚到top_index查找成功 → 添加到bottom
            overlap = stitcher.add_image(img, direction=1)
            
            # 🆕 检测添加是否失败（除第一张外）
            if i > 0 and overlap is None:
                has_failure = True
                if verbose:
                    print(f"  ⚠️  第 {i+1} 张图片添加失败，标记为需要切换引擎")

            top_count, bottom_count = stitcher.get_image_count()
            if verbose:
                print(f"  当前队列: top={top_count}, bottom={bottom_count}")

        # 🆕 如果有图片失败，直接返回 None 触发引擎切换
        if has_failure:
            if verbose:
                print("\n❌ 拼接过程中有图片失败，返回 None 以触发引擎切换")
            return None

        # 导出结果
        if verbose:
            print("\n正在合成最终图片...")

        result = stitcher.export()

        if result:
            if verbose:
                print(f"拼接完成! 最终尺寸: {result.size}")
            return result
        else:
            if verbose:
                print("拼接失败: 无法生成结果")
            return None

    except Exception as e:
        if verbose:
            print(f"拼接过程出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def stitch_multiple_images(
    image_paths: List[str],
    output_path: str,
    direction: int = 0,
    sample_rate: float = 0.5,
) -> None:
    """
    从文件路径拼接多张图片并保存

    参数:
        image_paths: 图片文件路径列表
        output_path: 输出文件路径
        direction: 滚动方向 (0=垂直, 1=水平)
        sample_rate: 采样率
    """
    if len(image_paths) < 2:
        print("至少需要两张图片进行拼接")
        return

    print(f"加载 {len(image_paths)} 张图片...")

    # 加载所有图片
    images = []
    for path in image_paths:
        try:
            img = Image.open(path)
            images.append(img)
            print(f"  加载: {path} ({img.size})")
        except Exception as e:
            print(f"  错误: 无法加载 {path}: {e}")
            return

    # 拼接图片
    result = stitch_pil_images(images, direction=direction, sample_rate=sample_rate)

    if result:
        # 保存结果
        result.save(output_path, "PNG", quality=95)
        print(f"\n结果已保存到: {output_path}")
        print(f"最终尺寸: {result.size}")
    else:
        print("\n拼接失败")


# 示例用法
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="长截图拼接工具 - Rust 加速版本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python jietuba_long_stitch_rust.py image1.png image2.png image3.png -o output.png
  python jietuba_long_stitch_rust.py *.png -o result.png --horizontal
  python jietuba_long_stitch_rust.py img*.jpg -o long.png --sample-rate 0.3
        """,
    )

    parser.add_argument("images", nargs="+", help="要拼接的图片文件路径")
    parser.add_argument("-o", "--output", required=True, help="输出文件路径")
    parser.add_argument(
        "--horizontal",
        action="store_true",
        help="水平拼接（默认为垂直拼接）",
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=0.5,
        help="采样率 (0.0-1.0，默认0.5)",
    )

    args = parser.parse_args()

    direction = 1 if args.horizontal else 0

    try:
        stitch_multiple_images(
            args.images,
            args.output,
            direction=direction,
            sample_rate=args.sample_rate,
        )
    except KeyboardInterrupt:
        print("\n操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
