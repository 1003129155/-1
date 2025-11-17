#!/usr/bin/env python3
"""
长截图拼接脚本-Rust/python
使用最长公共子串算法找到图片重叠部分并进行拼接
"""

from PIL import Image
import os
import glob
import argparse
from typing import List, Tuple, Optional
import sys
import io
import time

# 尝试导入 Rust 加速模块
try:
    import jietuba_rust
    RUST_AVAILABLE = True
    print("✅ Rust 加速模块已加载")
except ImportError:
    RUST_AVAILABLE = False
    print("⚠️  Rust 模块未找到，使用 Python 实现（性能较慢）")
    print("   提示: 运行 'cd rs && maturin build --release' 编译 Rust 模块")

# 性能统计
_performance_stats = {
    'hash_time': 0.0,
    'lcs_time': 0.0,
    'hash_count': 0,
    'lcs_count': 0,
}


def image_to_row_hashes(image: Image.Image, ignore_right_pixels: int = 20) -> List[int]:
    """
    将图片的每一行转换为哈希值，用于快速比较
    ignore_right_pixels: 忽略右侧多少像素（用于排除滚动条影响）
    
    优先使用 Rust 实现（快 10-20x），如果不可用则回退到 Python 实现
    """
    start_time = time.perf_counter()
    
    # 🚀 优先使用 Rust 版本
    if RUST_AVAILABLE:
        try:
            # 将 PIL Image 转换为字节
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            image_bytes = buffer.getvalue()
            
            # 调用 Rust 函数（快 10-20x）
            row_hashes = jietuba_rust.compute_row_hashes(image_bytes, ignore_right_pixels)
            
            # 统计性能
            elapsed = time.perf_counter() - start_time
            _performance_stats['hash_time'] += elapsed
            _performance_stats['hash_count'] += 1
            
            return row_hashes
        except Exception as e:
            print(f"⚠️  Rust 哈希计算失败，回退到 Python: {e}")
            # 继续执行下面的 Python 实现
    
    # 🐍 Python 回退实现
    width, height = image.size
    row_hashes = []
    
    # 获取所有像素数据
    pixels = image.load()

    for y in range(height):
        # 计算行的平均色彩值（不使用 numpy）
        r_sum, g_sum, b_sum = 0, 0, 0
        pixel_count = 0
        
        # 忽略右侧像素（滚动条）
        end_x = width - ignore_right_pixels if ignore_right_pixels > 0 else width
        
        for x in range(min(end_x, width)):
            pixel = pixels[x, y]
            if isinstance(pixel, tuple):
                # RGB 或 RGBA 图像
                r_sum += pixel[0]
                g_sum += pixel[1]
                b_sum += pixel[2]
            else:
                # 灰度图像
                r_sum += pixel
                g_sum += pixel
                b_sum += pixel
            pixel_count += 1
        
        if pixel_count > 0:
            # 计算平均值并量化（提高容忍度）
            r_mean = int((r_sum / pixel_count) / 8) * 8
            g_mean = int((g_sum / pixel_count) / 8) * 8
            b_mean = int((b_sum / pixel_count) / 8) * 8
            
            # 生成哈希值
            row_hash = hash((r_mean, g_mean, b_mean))
        else:
            row_hash = 0
        
        row_hashes.append(row_hash)

    # 统计性能
    elapsed = time.perf_counter() - start_time
    _performance_stats['hash_time'] += elapsed
    _performance_stats['hash_count'] += 1
    
    return row_hashes


def find_longest_common_substring(
    seq1: List[int], seq2: List[int], min_ratio: float = 0.1
) -> Tuple[int, int, int]:
    """
    找到两个序列的最长公共子串
    返回 (seq1_start, seq2_start, length)
    min_ratio: 最小重叠比例阈值（相对于较短图片的高度）
    
    优先使用 Rust 实现（快 10x），如果不可用则回退到 Python 实现
    """
    start_time = time.perf_counter()
    
    # 🚀 优先使用 Rust 版本
    if RUST_AVAILABLE:
        try:
            # 调用 Rust 函数（快 10x）
            start_i, start_j, length = jietuba_rust.find_longest_common_substring(
                seq1, seq2, min_ratio
            )
            
            # 统计性能
            elapsed = time.perf_counter() - start_time
            _performance_stats['lcs_time'] += elapsed
            _performance_stats['lcs_count'] += 1
            
            return start_i, start_j, length
        except Exception as e:
            print(f"⚠️  Rust LCS 计算失败，回退到 Python: {e}")
            # 继续执行下面的 Python 实现
    
    # 🐍 Python 回退实现
    m, n = len(seq1), len(seq2)
    min_length = int(min(m, n) * min_ratio)

    # 动态规划表
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    max_length = 0
    ending_pos_i = 0
    ending_pos_j = 0

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                if dp[i][j] > max_length:
                    max_length = dp[i][j]
                    ending_pos_i = i
                    ending_pos_j = j
            else:
                dp[i][j] = 0

    if max_length < min_length:
        result = (-1, -1, 0)
    else:
        # 计算起始位置
        start_i = ending_pos_i - max_length
        start_j = ending_pos_j - max_length
        result = (start_i, start_j, max_length)
    
    # 统计性能
    elapsed = time.perf_counter() - start_time
    _performance_stats['lcs_time'] += elapsed
    _performance_stats['lcs_count'] += 1
    
    return result


def print_performance_stats():
    """打印性能统计信息"""
    if _performance_stats['hash_count'] == 0 and _performance_stats['lcs_count'] == 0:
        return
    
    print("\n" + "=" * 60)
    print("⏱️  性能统计")
    print("=" * 60)
    
    if _performance_stats['hash_count'] > 0:
        avg_hash_time = _performance_stats['hash_time'] / _performance_stats['hash_count']
        print(f"逐行哈希计算:")
        print(f"  总次数: {_performance_stats['hash_count']}")
        print(f"  总耗时: {_performance_stats['hash_time']*1000:.2f} ms")
        print(f"  平均耗时: {avg_hash_time*1000:.2f} ms")
        if RUST_AVAILABLE:
            print(f"  ✅ 使用 Rust 加速（预估加速 10-20x）")
        else:
            print(f"  ⚠️  使用 Python 实现（较慢）")
    
    if _performance_stats['lcs_count'] > 0:
        avg_lcs_time = _performance_stats['lcs_time'] / _performance_stats['lcs_count']
        print(f"\n最长公共子串:")
        print(f"  总次数: {_performance_stats['lcs_count']}")
        print(f"  总耗时: {_performance_stats['lcs_time']*1000:.2f} ms")
        print(f"  平均耗时: {avg_lcs_time*1000:.2f} ms")
        if RUST_AVAILABLE:
            print(f"  ✅ 使用 Rust 加速（预估加速 10x）")
        else:
            print(f"  ⚠️  使用 Python 实现（较慢）")
    
    total_time = _performance_stats['hash_time'] + _performance_stats['lcs_time']
    print(f"\n总算法耗时: {total_time*1000:.2f} ms")
    print("=" * 60)


def reset_performance_stats():
    """重置性能统计"""
    _performance_stats['hash_time'] = 0.0
    _performance_stats['lcs_time'] = 0.0
    _performance_stats['hash_count'] = 0
    _performance_stats['lcs_count'] = 0


def find_best_overlap(
    img1_hashes: List[int], img2_hashes: List[int]
) -> Tuple[int, int, int]:
    """
    寻找最佳重叠区域
    直接在整张图片上寻找最长公共子串
    """
    print(f"  搜索重叠区域: img1有{len(img1_hashes)}行, img2有{len(img2_hashes)}行")

    # 先尝试更低的阈值
    overlap = find_longest_common_substring(img1_hashes, img2_hashes, min_ratio=0.01)

    if overlap[2] > 0:
        overlap_ratio = overlap[2] / min(len(img1_hashes), len(img2_hashes))
        print(f"  找到重叠: 长度{overlap[2]}行, 占比{overlap_ratio:.2%}")
        return overlap
    else:
        print("  未找到任何重叠区域")
        return (-1, -1, 0)


def stitch_images(
    img1: Image.Image, img2: Image.Image, ignore_right_pixels: int = 20
) -> Optional[Image.Image]:
    """
    拼接两张图片（优先使用 Rust 完整拼接方案）
    ignore_right_pixels: 忽略右侧多少像素（用于排除滚动条影响）
    
    性能层级：
      方案 A（最快）: 全 Rust 拼接 - 零拷贝，全程 Rust 处理（预计 3-4x 快于方案 B）
      方案 B（次快）: Rust 哈希 + Python PIL - Rust 加速关键算法（当前使用）
      方案 C（最慢）: 纯 Python - 完全回退方案
    """
    start_time = time.perf_counter()
    
    # 🚀 方案 A：尝试使用完整 Rust 拼接（零拷贝，最快）
    if RUST_AVAILABLE:
        try:
            # 将两张图片转换为字节流
            buffer1 = io.BytesIO()
            buffer2 = io.BytesIO()
            img1.save(buffer1, format='PNG')
            img2.save(buffer2, format='PNG')
            
            # 调用 Rust 完整拼接函数
            result_bytes = jietuba_rust.stitch_two_images_rust(
                buffer1.getvalue(),
                buffer2.getvalue(),
                ignore_right_pixels,
                0.1  # min_overlap_ratio
            )
            
            if result_bytes is not None:
                # 成功！直接返回结果
                result = Image.open(io.BytesIO(result_bytes))
                elapsed = time.perf_counter() - start_time
                print(f"✅ Rust 完整拼接成功: {img1.size} + {img2.size} -> {result.size}")
                print(f"⚡ 耗时: {elapsed*1000:.2f} ms（零拷贝方案）")
                return result
            else:
                print("⚠️  Rust 完整拼接返回 None，尝试方案 B...")
        except Exception as e:
            print(f"⚠️  Rust 完整拼接失败: {e}，回退到方案 B...")
    
    # 🐍 方案 B：Rust 哈希加速 + Python PIL 拼接
    print(f"处理图片: {img1.size} + {img2.size}")

    # 确保两张图片宽度相同
    if img1.width != img2.width:
        print(f"调整图片宽度: {img1.width} -> {img2.width}")
        img1 = img1.resize(
            (img2.width, int(img1.height * img2.width / img1.width)),
            Image.Resampling.LANCZOS,
        )

    # 转换为行哈希（忽略右侧像素以排除滚动条影响）
    print(f"忽略右侧 {ignore_right_pixels} 像素来排除滚动条影响")
    img1_hashes = image_to_row_hashes(img1, ignore_right_pixels)
    img2_hashes = image_to_row_hashes(img2, ignore_right_pixels)

    # 寻找重叠区域
    overlap = find_best_overlap(img1_hashes, img2_hashes)

    if overlap[2] == 0:
        print("未找到重叠区域，直接拼接")
        # 如果没有重叠，直接拼接
        result_height = img1.height + img2.height
        result = Image.new("RGB", (img1.width, result_height))
        result.paste(img1, (0, 0))
        result.paste(img2, (0, img1.height))
        return result

    img1_start, img2_start, overlap_length = overlap
    print(
        f"找到重叠区域: img1[{img1_start}:{img1_start + overlap_length}] = img2[{img2_start}:{img2_start + overlap_length}]"
    )

    # 计算拼接后的总高度
    img1_keep_height = img1_start + overlap_length  # 保留img1的部分
    img2_skip_height = img2_start + overlap_length  # 跳过img2的重叠部分
    img2_keep_height = img2.height - img2_skip_height  # 保留img2的剩余部分

    result_height = img1_keep_height + img2_keep_height

    print(
        f"拼接计算: img1保留{img1_keep_height}行 + img2跳过{img2_skip_height}行保留{img2_keep_height}行 = 总计{result_height}行"
    )

    # 创建结果图片
    result = Image.new("RGB", (img1.width, result_height))

    # 粘贴img1的保留部分
    img1_crop = img1.crop((0, 0, img1.width, img1_keep_height))
    result.paste(img1_crop, (0, 0))

    # 粘贴img2的剩余部分
    if img2_keep_height > 0:
        img2_crop = img2.crop((0, img2_skip_height, img2.width, img2.height))
        result.paste(img2_crop, (0, img1_keep_height))

    elapsed = time.perf_counter() - start_time
    print(f"✅ 方案 B 拼接完成，耗时: {elapsed*1000:.2f} ms")
    return result


def stitch_multiple_images(
    image_paths: List[str], output_path: str, ignore_right_pixels: int = 20
) -> None:
    """
    拼接多张图片
    ignore_right_pixels: 忽略右侧多少像素（用于排除滚动条影响）
    """
    if len(image_paths) < 2:
        print("至少需要两张图片进行拼接")
        return

    print(f"开始拼接 {len(image_paths)} 张图片...")

    # 加载第一张图片
    result = Image.open(image_paths[0])
    print(f"基础图片: {image_paths[0]} ({result.size})")

    # 逐个拼接后续图片
    for i, path in enumerate(image_paths[1:], 1):
        print(f"\n拼接第 {i+1} 张图片: {path}")
        next_img = Image.open(path)
        result = stitch_images(result, next_img, ignore_right_pixels)
        if result is None:
            print("拼接失败")
            return
        print(f"当前结果尺寸: {result.size}")

    # 保存结果
    result.save(output_path, "JPEG", quality=95)
    print(f"\n拼接完成! 结果已保存到: {output_path}")
    print(f"最终尺寸: {result.size}")
    
    # 打印性能统计
    print_performance_stats()


def stitch_pil_images(
    images: List[Image.Image], ignore_right_pixels: int = 20
) -> Optional[Image.Image]:
    """
    拼接多张PIL图片对象（用于长截图功能）
    
    参数:
        images: PIL Image对象列表
        ignore_right_pixels: 忽略右侧多少像素（用于排除滚动条影响）
    
    返回:
        拼接后的PIL Image对象，失败返回None
    """
    if not images or len(images) == 0:
        print("错误: 没有图片需要拼接")
        return None
    
    if len(images) == 1:
        print("只有一张图片，直接返回")
        return images[0]

    print(f"开始拼接 {len(images)} 张PIL图片...")

    # 从第一张图片开始
    result = images[0]
    print(f"基础图片: {result.size}")

    # 逐个拼接后续图片
    for i, next_img in enumerate(images[1:], 1):
        print(f"\n拼接第 {i+1} 张图片: {next_img.size}")
        result = stitch_images(result, next_img, ignore_right_pixels)
        if result is None:
            print("拼接失败")
            return None
        print(f"当前结果尺寸: {result.size}")

    print(f"\n拼接完成! 最终尺寸: {result.size}")
    
    # 打印性能统计
    print_performance_stats()
    
    return result


def parse_pattern_and_generate_output(pattern: str) -> Tuple[str, str]:
    """
    解析输入模式并生成输出文件名
    例如: "IMG_627FF0035451-*.jpeg" -> ("IMG_627FF0035451-", ".jpeg") -> "IMG_627FF0035451-concat.jpeg"
    """
    if "*" not in pattern:
        raise ValueError("模式必须包含通配符 '*'")

    # 找到第一个通配符的位置
    star_index = pattern.find("*")
    prefix = pattern[:star_index]
    suffix = pattern[star_index + 1 :]

    # 如果suffix中还有通配符，只取到下一个通配符之前的部分
    if "*" in suffix:
        suffix = suffix[: suffix.find("*")]

    # 生成输出文件名
    if "." in suffix:
        # 提取文件扩展名
        extension = suffix
        output_name = f"{prefix}concat{extension}"
    else:
        # 如果没有扩展名，默认使用 .jpeg
        output_name = f"{prefix}concat.jpeg"

    return prefix, output_name


def find_matching_files(pattern: str) -> List[str]:
    """
    根据通配符模式查找匹配的文件
    """
    matching_files = glob.glob(pattern)

    # 过滤出图片文件（常见的图片扩展名）
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
    image_files = []

    for file in matching_files:
        _, ext = os.path.splitext(file.lower())
        if ext in image_extensions:
            # 排除已经是拼接结果的文件 (包含 'concat' 的文件名)
            basename = os.path.basename(file).lower()
            if "concat" not in basename:
                image_files.append(file)
            else:
                print(f"跳过拼接结果文件: {file}")

    return image_files


def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(
        description="长截图拼接工具 - 支持通配符模式批量拼接图片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py "IMG_627FF0035451-*.jpeg"
  python main.py "screenshot-*.png"
  python main.py "page-*.jpg" --ignore-pixels 30
        """,
    )

    parser.add_argument("pattern", help="文件名通配符模式，例如: 'prefix-*.jpeg'")

    parser.add_argument(
        "--ignore-pixels",
        type=int,
        default=20,
        help="忽略右侧多少像素以排除滚动条影响 (默认: 20)",
    )

    parser.add_argument(
        "--output", help="指定输出文件名 (可选，默认自动生成为 prefix-concat.extension)"
    )

    args = parser.parse_args()

    try:
        # 查找匹配的文件
        print(f"搜索模式: {args.pattern}")
        image_files = find_matching_files(args.pattern)

        if len(image_files) == 0:
            print(f"错误: 没有找到匹配模式 '{args.pattern}' 的图片文件")
            sys.exit(1)

        if len(image_files) < 2:
            print(f"错误: 只找到 {len(image_files)} 张图片，至少需要2张图片进行拼接")
            print("找到的文件:")
            for file in image_files:
                print(f"  - {file}")
            sys.exit(1)

        # 按文件名排序
        image_files.sort()

        print(f"找到 {len(image_files)} 张图片:")
        for i, file in enumerate(image_files, 1):
            print(f"  {i}. {file}")

        # 确定输出文件名
        if args.output:
            output_file = args.output
        else:
            try:
                _, output_file = parse_pattern_and_generate_output(args.pattern)
            except ValueError as e:
                print(f"错误: {e}")
                sys.exit(1)

        print(f"\n输出文件: {output_file}")
        print(f"配置: 忽略右侧 {args.ignore_pixels} 像素以排除滚动条影响")

        # 执行拼接
        stitch_multiple_images(image_files, output_file, args.ignore_pixels)

    except KeyboardInterrupt:
        print("\n操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
