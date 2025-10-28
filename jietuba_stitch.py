"""
jietuba_stitch.py - 简单图片垂直拼接模块

提供将多张图片垂直拼接成长截图的纯函数,不依赖任何 UI 组件。
适用于简单的垂直堆叠拼接,不检测图片重叠。

主要功能:
- 垂直拼接多张图片
- 支持左/中/右对齐
- 支持自定义间距和背景色

主要函数:
- stitch_images_vertical(images, align='left', spacing=0, bg_color=(255, 255, 255))

参数说明:
- images: list[Union[str, os.PathLike, pathlib.Path, PIL.Image.Image]]
  可以是图片路径或已打开的 PIL Image 对象,混用也可以。
- align: 'left' | 'center' | 'right',控制每张图片在目标宽度中的水平对齐方式。
- spacing: 相邻两张图片之间的像素间距,默认 0。
- bg_color: 背景填充颜色(用于宽度不一致时的左右留白或间距区域)。

返回值:
- PIL.Image.Image: 拼接后的新图像对象。

异常:
- ValueError: 当 images 为空或包含无效条目时抛出。

使用示例:
>>> from PIL import Image
>>> from jietuba_stitch import stitch_images_vertical
>>> imgs = [Image.new('RGB', (300, 200), 'red'), Image.new('RGB', (260, 300), 'green')]
>>> out = stitch_images_vertical(imgs, align='center', spacing=10)
>>> out.size
(300, 200 + 10 + 300)
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple, Union

from PIL import Image

ImageLike = Union[str, Path, Image.Image]


def _to_image(item: ImageLike) -> Tuple[Image.Image, bool]:
    """将输入转换为 PIL Image 对象。

    返回 (image, opened_here)
    - opened_here: 为 True 表示函数内部通过路径新打开的，需要在外部复制后关闭释放句柄。
    """
    if isinstance(item, Image.Image):
        return item, False
    # 允许 str / Path / os.PathLike
    path = Path(item)
    img = Image.open(path)
    return img, True


def _has_alpha(img: Image.Image) -> bool:
    mode = img.mode
    if mode in ("RGBA", "LA"):
        return True
    if mode == "P":
        # 调色板模式可能携带透明通道
        return "transparency" in img.info
    return False


def stitch_images_vertical(
    images: Iterable[ImageLike],
    align: str = "left",
    spacing: int = 0,
    bg_color: Tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """将多张图片按顺序垂直拼接为一张长图。

    参数：
    - images: 图片路径或 PIL Image 列表。
    - align: 'left' | 'center' | 'right'，水平对齐方式。
    - spacing: 相邻图片之间的像素间距。
    - bg_color: 背景填充颜色（RGB），当宽度不一致或存在间距时使用。

    返回：
    - 新的 PIL.Image.Image 对象。
    """
    imgs_raw = list(images)
    if not imgs_raw:
        raise ValueError("images 不能为空")

    opened: List[Image.Image] = []  # 由本函数打开的图片
    refs: List[Image.Image] = []    # 最终用于拼接的 Image 引用（已转换模式）
    try:
        # 读取与预处理
        has_any_alpha = False
        for item in imgs_raw:
            img, opened_here = _to_image(item)
            if opened_here:
                opened.append(img)
            # 仅用于判断目标模式
            has_any_alpha = has_any_alpha or _has_alpha(img)
            refs.append(img)

        target_mode = "RGBA" if has_any_alpha else "RGB"

        # 统一为 target_mode，避免粘贴时出错；同时复制为内存图像，便于及时关闭文件句柄
        processed: List[Image.Image] = []
        max_width = 0
        total_height = 0
        for img in refs:
            if img.mode != target_mode:
                img_conv = img.convert(target_mode)
            else:
                # 即使模式一致，也复制一份，避免引用外部对象
                img_conv = img.copy()
            processed.append(img_conv)
            max_width = max(max_width, img_conv.width)
            total_height += img_conv.height

        if spacing > 0 and len(processed) > 1:
            total_height += spacing * (len(processed) - 1)

        # 创建画布
        if target_mode == "RGBA":
            # 对 RGBA 背景色补齐 alpha 通道
            bg = (*bg_color, 0)
        else:
            bg = bg_color
        result = Image.new(target_mode, (max_width, total_height), color=bg)

        # 粘贴
        y = 0
        for idx, img in enumerate(processed):
            if align == "left":
                x = 0
            elif align == "center":
                x = (max_width - img.width) // 2
            elif align == "right":
                x = max_width - img.width
            else:
                raise ValueError("align 仅支持 'left' | 'center' | 'right'")

            result.paste(img, (x, y))
            y += img.height
            if spacing > 0 and idx < len(processed) - 1:
                y += spacing

        return result
    finally:
        # 关闭由本函数打开的文件
        for img in opened:
            try:
                img.close()
            except Exception:
                pass
