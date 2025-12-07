"""jietuba_layer_system
========================

提供截图与钉图窗口共享的矢量绘图文档，实现如下目标：

1. 仅保留一张原始底图(QPixmap)，所有绘制操作以矢量命令形式存储。
2. 支持根据任意尺寸重新渲染绘图层，避免缩放导致的模糊。
3. 内置撤销/重做状态导出接口，供旧的 backup_shortshot 流程复用。
4. 区分普通混合与荧光笔(正片叠底)混合模式。

该模块不依赖具体窗口实现，只专注于数据结构与渲染逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from PyQt5.QtCore import QPointF, QSize, Qt
from PyQt5.QtGui import (QColor, QFont, QPainter, QPainterPath, QPen,
						 QPixmap)


ColorTuple = Tuple[int, int, int, int]
PointTuple = Tuple[float, float]


def _serialize_color(color: QColor) -> ColorTuple:
	"""将 QColor 转为 (r, g, b, a)。"""

	return color.red(), color.green(), color.blue(), color.alpha()


def _color_from_tuple(values: ColorTuple) -> QColor:
	r, g, b, a = values
	return QColor(r, g, b, a)


def _clamp(value: float, minimum: float, maximum: float) -> float:
	return max(minimum, min(value, maximum))


@dataclass
class VectorPaintCommand:
	"""表示一次矢量绘制命令。"""

	kind: str
	points: List[PointTuple]
	width_ratio: float
	color: ColorTuple
	blend: str = "normal"  # normal / multiply
	extra: Dict[str, float] = field(default_factory=dict)

	def clone(self) -> "VectorPaintCommand":
		return VectorPaintCommand(
			kind=self.kind,
			points=list(self.points),
			width_ratio=self.width_ratio,
			color=tuple(self.color),
			blend=self.blend,
			extra=dict(self.extra or {}),
		)


class VectorLayerDocument:
	"""维护单张原始图像以及对应的矢量绘制命令。"""

	def __init__(self, base_pixmap: Optional[QPixmap] = None):
		self._base_pixmap: Optional[QPixmap] = None
		self._base_size = QSize(1, 1)
		self.commands: List[VectorPaintCommand] = []
		if base_pixmap is not None:
			self.set_base_pixmap(base_pixmap)

	# ------------------------------------------------------------------
	# 基础配置
	# ------------------------------------------------------------------
	def set_base_pixmap(self, pixmap: QPixmap) -> None:
		if pixmap is None or pixmap.isNull():
			raise ValueError("Base pixmap must be a valid QPixmap")
		self._base_pixmap = pixmap.copy()
		self._base_size = self._base_pixmap.size()

	@property
	def base_size(self) -> QSize:
		return QSize(self._base_size)

	# ------------------------------------------------------------------
	# 命令增删
	# ------------------------------------------------------------------
	def clear(self) -> None:
		self.commands.clear()

	def add_stroke(
		self,
		points: Sequence[PointTuple],
		color: QColor,
		width_ratio: float,
		*,
		blend: str = "normal",
		brush: str = "round",
	) -> None:
		if not points:
			return
		cmd = VectorPaintCommand(
			kind="stroke",
			points=list(points),
			width_ratio=width_ratio,
			color=_serialize_color(color),
			blend=blend,
			extra={"brush": 1.0 if brush == "round" else 0.0},
		)
		self.commands.append(cmd)

	def add_rect(
		self,
		start: PointTuple,
		end: PointTuple,
		color: QColor,
		width_ratio: float,
	) -> None:
		self.commands.append(
			VectorPaintCommand(
				kind="rect",
				points=[start, end],
				width_ratio=width_ratio,
				color=_serialize_color(color),
			)
		)

	def add_circle(
		self,
		start: PointTuple,
		end: PointTuple,
		color: QColor,
		width_ratio: float,
	) -> None:
		self.commands.append(
			VectorPaintCommand(
				kind="circle",
				points=[start, end],
				width_ratio=width_ratio,
				color=_serialize_color(color),
			)
		)

	def add_arrow(
		self,
		start: PointTuple,
		end: PointTuple,
		color: QColor,
		width_ratio: float,
	) -> None:
		self.commands.append(
			VectorPaintCommand(
				kind="arrow",
				points=[start, end],
				width_ratio=width_ratio,
				color=_serialize_color(color),
			)
		)

	def add_text(
		self,
		anchor: PointTuple,
		text: str,
		color: QColor,
		font_ratio: float,
		line_spacing_ratio: float,
		*,
		font_family: str = "",
		font_weight: int = 50,
		font_italic: bool = False,
	) -> None:
		if not text.strip():
			return
		extra_payload = {
			"text": text,
			"line": line_spacing_ratio,
		}
		if font_family:
			extra_payload["font"] = font_family
		if font_weight is not None:
			extra_payload["weight"] = int(font_weight)
		extra_payload["italic"] = bool(font_italic)
		self.commands.append(
			VectorPaintCommand(
				kind="text",
				points=[anchor],
				width_ratio=font_ratio,
				color=_serialize_color(color),
				extra=extra_payload,
			)
		)

	def add_number(
		self,
		center: PointTuple,
		number: int,
		color: QColor,
		bg_color: QColor,
		size_ratio: float,
	) -> None:
		"""添加序号标注（带圆形背景的数字）"""
		self.commands.append(
			VectorPaintCommand(
				kind="number",
				points=[center],
				width_ratio=size_ratio,
				color=_serialize_color(color),
				extra={
					"number": number,
					"bg_r": bg_color.red(),
					"bg_g": bg_color.green(),
					"bg_b": bg_color.blue(),
					"bg_a": bg_color.alpha(),
				},
			)
		)

	# ------------------------------------------------------------------
	# 状态导入导出（给撤销/重做系统使用）
	# ------------------------------------------------------------------
	def export_state(self) -> List[Dict]:
		exported: List[Dict] = []
		for cmd in self.commands:
			exported.append(
				{
					"kind": cmd.kind,
					"points": list(cmd.points),
					"width_ratio": cmd.width_ratio,
					"color": tuple(cmd.color),
					"blend": cmd.blend,
					"extra": dict(cmd.extra or {}),
				}
			)
		return exported

	def import_state(self, snapshot: Iterable[Dict]) -> None:
		self.commands = []
		for raw in snapshot:
			self.commands.append(
				VectorPaintCommand(
					kind=raw.get("kind", "stroke"),
					points=[tuple(pt) for pt in raw.get("points", [])],
					width_ratio=float(raw.get("width_ratio", 0)),
					color=tuple(raw.get("color", (255, 0, 0, 255))),
					blend=raw.get("blend", "normal"),
					extra=dict(raw.get("extra", {})),
				)
			)

	# ------------------------------------------------------------------
	# 渲染
	# ------------------------------------------------------------------
	def render_base(self, size: Optional[QSize] = None) -> QPixmap:
		if not self._base_pixmap:
			raise RuntimeError("Base pixmap not set")
		if size is None or size == self._base_size:
			return self._base_pixmap.copy()
		return self._base_pixmap.scaled(
			size.width(),
			size.height(),
			Qt.IgnoreAspectRatio,
			Qt.SmoothTransformation,
		)

	def render_overlay(
		self,
		size: Optional[QSize] = None,
		*,
		blend_filter: Optional[Sequence[str]] = None,
	) -> QPixmap:
		target_w, target_h = self._target_size(size)
		overlay = QPixmap(target_w, target_h)
		overlay.fill(Qt.transparent)
		painter = QPainter(overlay)
		painter.setRenderHint(QPainter.Antialiasing)

		for cmd in self.commands:
			if blend_filter and cmd.blend not in blend_filter:
				continue
			self._render_command(painter, cmd, target_w, target_h)

		painter.end()
		return overlay

	def render_composited(self, size: Optional[QSize] = None) -> QPixmap:
		base = self.render_base(size)
		if not self.commands:
			return base

		target_w = base.width()
		target_h = base.height()
		painter = QPainter(base)
		painter.setRenderHint(QPainter.Antialiasing)

		normal = self.render_overlay(QSize(target_w, target_h), blend_filter=("normal",))
		painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
		painter.drawPixmap(0, 0, normal)

		multiply_overlay = self.render_overlay(
			QSize(target_w, target_h), blend_filter=("multiply",)
		)
		painter.setCompositionMode(QPainter.CompositionMode_Multiply)
		painter.drawPixmap(0, 0, multiply_overlay)
		painter.end()
		return base

	# ------------------------------------------------------------------
	# 内部渲染帮助函数
	# ------------------------------------------------------------------
	def _target_size(self, size: Optional[QSize]) -> Tuple[int, int]:
		if size is None:
			size = self._base_size
		return max(1, size.width()), max(1, size.height())

	def _scaled_point(self, point: PointTuple, width: int, height: int) -> QPointF:
		x = point[0] * width
		y = point[1] * height
		return QPointF(x, y)

	def _pen_width(self, cmd: VectorPaintCommand, width: int, height: int) -> float:
		return max(1.0, cmd.width_ratio * min(width, height))

	def _render_command(
		self, painter: QPainter, cmd: VectorPaintCommand, width: int, height: int
	) -> None:
		if not cmd.points:
			return
		color = _color_from_tuple(cmd.color)

		if cmd.kind == "stroke":
			path = QPainterPath()
			pts = [self._scaled_point(pt, width, height) for pt in cmd.points]
			path.moveTo(pts[0])
			for pt in pts[1:]:
				path.lineTo(pt)
			pen = QPen(color)
			pen.setWidthF(self._pen_width(cmd, width, height))
			pen.setJoinStyle(Qt.RoundJoin)
			brush = cmd.extra.get("brush", 1.0)
			pen.setCapStyle(Qt.RoundCap if brush >= 0.5 else Qt.SquareCap)
			painter.setPen(pen)
			painter.drawPath(path)
			return

		if cmd.kind in {"rect", "circle"}:
			start = self._scaled_point(cmd.points[0], width, height)
			end = self._scaled_point(cmd.points[1], width, height)
			left = min(start.x(), end.x())
			top = min(start.y(), end.y())
			w = abs(start.x() - end.x())
			h = abs(start.y() - end.y())
			pen = QPen(color)
			pen.setWidthF(self._pen_width(cmd, width, height))
			painter.setPen(pen)
			painter.setBrush(Qt.NoBrush)
			if cmd.kind == "rect":
				painter.drawRect(left, top, w, h)
			else:
				painter.drawEllipse(left, top, w, h)
			return

		if cmd.kind == "arrow":
			start = self._scaled_point(cmd.points[0], width, height)
			end = self._scaled_point(cmd.points[1], width, height)
			from jietuba_drawing import PaintLayer  # 延迟导入避免循环

			temp_layer = PaintLayer.__new__(PaintLayer)
			try:
				temp_layer._draw_optimized_arrow(
					painter,
					[[start.x(), start.y()], [end.x(), end.y()]],
					color,
					self._pen_width(cmd, width, height),
				)
			except Exception:
				pass
			return

		if cmd.kind == "text":
			anchor = self._scaled_point(cmd.points[0], width, height)
			font = QFont()
			family = cmd.extra.get("font")
			if family:
				font.setFamily(family)
			font.setPointSizeF(self._pen_width(cmd, width, height))
			if "weight" in cmd.extra:
				try:
					font.setWeight(int(cmd.extra.get("weight", 50)))
				except Exception:
					pass
			if cmd.extra.get("italic"):
				font.setItalic(True)
			painter.setFont(font)
			painter.setPen(QPen(color))
			text = cmd.extra.get("text", "")
			line_ratio = float(cmd.extra.get("line", 1.8))
			lines = text.split("\n")
			metrics = painter.fontMetrics()
			line_height = metrics.height() * line_ratio
			for i, line in enumerate(lines):
				painter.drawText(anchor.x(), anchor.y() + i * line_height, line)
			return

		if cmd.kind == "number":
			# 渲染序号标注（圆形背景+数字）
			center = self._scaled_point(cmd.points[0], width, height)
			number = int(cmd.extra.get("number", 1))
			
			# 获取背景颜色
			bg_color = QColor(
				int(cmd.extra.get("bg_r", 255)),
				int(cmd.extra.get("bg_g", 0)),
				int(cmd.extra.get("bg_b", 0)),
				int(cmd.extra.get("bg_a", 200))
			)
			
			# 计算圆形大小（根据 size_ratio）
			circle_radius = self._pen_width(cmd, width, height)
			
			# 绘制圆形背景
			painter.setPen(Qt.NoPen)
			painter.setBrush(bg_color)
			painter.drawEllipse(center, circle_radius, circle_radius)
			
			# 绘制数字
			font = QFont("Arial", int(circle_radius * 0.8), QFont.Bold)
			painter.setFont(font)
			painter.setPen(QPen(color))
			
			# 计算文字居中位置
			metrics = painter.fontMetrics()
			text = str(number)
			text_width = metrics.horizontalAdvance(text)
			text_height = metrics.height()
			text_x = center.x() - text_width / 2
			text_y = center.y() + text_height / 3  # 微调垂直居中
			
			painter.drawText(int(text_x), int(text_y), text)
			return


__all__ = ["VectorLayerDocument", "VectorPaintCommand"]
