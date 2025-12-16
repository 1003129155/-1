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

from PyQt5.QtCore import QPointF, QSize, Qt, QRectF
from PyQt5.QtGui import (QColor, QFont, QPainter, QPen,
					 QPixmap, QTransform)


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
	rotation: float = 0.0
	scale: float = 1.0

	def clone(self) -> "VectorPaintCommand":
		return VectorPaintCommand(
			kind=self.kind,
			points=list(self.points),
			width_ratio=self.width_ratio,
			color=tuple(self.color),
			blend=self.blend,
			extra=dict(self.extra or {}),
			rotation=self.rotation,
			scale=self.scale,
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
		extra_meta: Optional[Dict[str, float]] = None,
	) -> None:
		if not points:
			return
		extra_payload: Dict[str, float] = {}
		if extra_meta:
			extra_payload.update(extra_meta)
		brush_tag = brush if isinstance(brush, str) else ("round" if float(brush or 0) >= 0.5 else "square")
		if brush_tag not in ("round", "square"):
			brush_tag = "round"
		extra_payload.setdefault("brush", brush_tag)
		cmd = VectorPaintCommand(
			kind="stroke",
			points=list(points),
			width_ratio=width_ratio,
			color=_serialize_color(color),
			blend=blend,
			extra=extra_payload,
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
	# 交互支持 (命中测试与变换)
	# ------------------------------------------------------------------
	def hit_test(self, pos: QPointF, tolerance: float = 10.0) -> int:
		"""检测指定位置命中了哪个命令，返回索引，未命中返回 -1。
		优先返回最后绘制的对象（最上层）。
		"""
		w, h = self._base_size.width(), self._base_size.height()
		if w <= 0 or h <= 0:
			return -1
			
		# 倒序遍历（从最上层开始）
		for i in range(len(self.commands) - 1, -1, -1):
			cmd = self.commands[i]
			
			# Transform pos to local coordinates
			local_pos = QPointF(pos)
			if cmd.rotation != 0 or cmd.scale != 1.0:
				center = self._get_command_center(cmd, w, h)
				transform = QTransform()
				transform.translate(center.x(), center.y())
				transform.rotate(cmd.rotation)
				transform.scale(cmd.scale, cmd.scale)
				transform.translate(-center.x(), -center.y())
				
				inverted, ok = transform.inverted()
				if ok:
					local_pos = inverted.map(pos)

			if self._is_hit_screen(cmd, local_pos.x(), local_pos.y(), tolerance, w, h):
				return i
		return -1

	def _is_hit_screen(self, cmd: VectorPaintCommand, x: float, y: float, tol: float, w: int, h: int) -> bool:
		if not cmd.points:
			return False
			
		# 将点转换为屏幕坐标
		screen_points = [(p[0] * w, p[1] * h) for p in cmd.points]
		
		if cmd.kind == "stroke":
			# 检查线段距离
			if len(screen_points) > 1:
				for i in range(len(screen_points) - 1):
					p1 = screen_points[i]
					p2 = screen_points[i+1]
					dist = self._dist_point_segment(x, y, p1, p2)
					if dist <= tol:
						return True
			# 如果只有一个点，检查点距离
			elif len(screen_points) == 1:
				p = screen_points[0]
				if ((p[0] - x)**2 + (p[1] - y)**2)**0.5 <= tol:
					return True
			return False
			
		elif cmd.kind in ("rect", "circle", "arrow"):
			if len(screen_points) < 2:
				return False
			p1, p2 = screen_points[0], screen_points[1]
			
			# 简单包围盒检测
			min_x = min(p1[0], p2[0]) - tol
			max_x = max(p1[0], p2[0]) + tol
			min_y = min(p1[1], p2[1]) - tol
			max_y = max(p1[1], p2[1]) + tol
			
			if min_x <= x <= max_x and min_y <= y <= max_y:
				return True
			return False
			
		elif cmd.kind == "text":
			p = screen_points[0]
			# 估算文本区域 (假设文本向右下方延伸)
			# 更好的做法是保存文本的宽高比，这里做个宽泛的估算
			font_size = self._pen_width(cmd, w, h)
			# 假设文本大概宽10个字，高1行
			if p[0] <= x <= p[0] + font_size * 10 and p[1] <= y <= p[1] + font_size * 2:
				return True
			# 检查锚点附近
			if ((p[0] - x)**2 + (p[1] - y)**2)**0.5 <= tol:
				return True
			return False
			
		elif cmd.kind == "number":
			p = screen_points[0]
			radius = self._pen_width(cmd, w, h)
			# 检查是否在圆内
			if ((p[0] - x)**2 + (p[1] - y)**2)**0.5 <= max(radius, tol):
				return True
				
		return False

	def _dist_point_segment(self, px, py, p1, p2):
		x1, y1 = p1
		x2, y2 = p2
		dx = x2 - x1
		dy = y2 - y1
		if dx == 0 and dy == 0:
			return ((px - x1)**2 + (py - y1)**2)**0.5
			
		t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
		t = max(0, min(1, t))
		
		closest_x = x1 + t * dx
		closest_y = y1 + t * dy
		return ((px - closest_x)**2 + (py - closest_y)**2)**0.5

	def translate_command(self, index: int, dx: float, dy: float) -> None:
		"""移动指定索引的命令。dx, dy 为屏幕像素单位。"""
		if not (0 <= index < len(self.commands)):
			return
			
		w, h = self._base_size.width(), self._base_size.height()
		if w <= 0 or h <= 0:
			return
			
		norm_dx = dx / w
		norm_dy = dy / h
		
		cmd = self.commands[index]
		new_points = []
		for pt in cmd.points:
			new_points.append((pt[0] + norm_dx, pt[1] + norm_dy))
		cmd.points = new_points
		
	def get_command_rect(self, index: int) -> Optional[QRectF]:
		"""获取命令的包围盒（屏幕坐标），考虑旋转和缩放变换。"""
		if not (0 <= index < len(self.commands)):
			return None
			
		cmd = self.commands[index]
		if not cmd.points:
			return None
			
		w, h = self._base_size.width(), self._base_size.height()
		
		# 特殊处理序号
		if cmd.kind == "number":
			p = cmd.points[0]
			radius = self._pen_width(cmd, w, h)
			base_rect = QRectF(p[0]*w - radius, p[1]*h - radius, radius*2, radius*2)
		else:
			min_x = min(p[0] for p in cmd.points)
			max_x = max(p[0] for p in cmd.points)
			min_y = min(p[1] for p in cmd.points)
			max_y = max(p[1] for p in cmd.points)
			
			# 对于文本，需要额外扩展
			if cmd.kind == "text":
				max_x += 0.2 # 估算
				max_y += 0.1
				
			# 计算基础包围盒
			base_rect = QRectF(min_x * w, min_y * h, (max_x - min_x) * w, (max_y - min_y) * h)
			
			# 扩展笔触宽度
			stroke_width = self._pen_width(cmd, w, h)
			margin = stroke_width / 2.0 + 4
			base_rect = base_rect.adjusted(-margin, -margin, margin, margin)
		
		# 如果有旋转或缩放变换，需要应用变换后重新计算包围盒
		if cmd.rotation != 0 or cmd.scale != 1.0:
			# 获取对象中心点
			center = self._get_command_center(cmd, w, h)
			
			# 创建变换矩阵
			transform = QTransform()
			transform.translate(center.x(), center.y())
			transform.rotate(cmd.rotation)
			transform.scale(cmd.scale, cmd.scale)
			transform.translate(-center.x(), -center.y())
			
			# 应用变换到包围盒的四个角点
			top_left = transform.map(base_rect.topLeft())
			top_right = transform.map(base_rect.topRight())
			bottom_left = transform.map(base_rect.bottomLeft())
			bottom_right = transform.map(base_rect.bottomRight())
			
			# 计算变换后的包围盒
			all_x = [top_left.x(), top_right.x(), bottom_left.x(), bottom_right.x()]
			all_y = [top_left.y(), top_right.y(), bottom_left.y(), bottom_right.y()]
			
			new_min_x = min(all_x)
			new_max_x = max(all_x)
			new_min_y = min(all_y)
			new_max_y = max(all_y)
			
			return QRectF(new_min_x, new_min_y, new_max_x - new_min_x, new_max_y - new_min_y)
		
		return base_rect

	def get_command_rect_untransformed(self, index: int) -> Optional[QRectF]:
		"""获取命令的原始包围盒（屏幕坐标），不考虑旋转和缩放变换。
		用于需要手动应用变换的场景。"""
		if not (0 <= index < len(self.commands)):
			return None
			
		cmd = self.commands[index]
		if not cmd.points:
			return None
			
		w, h = self._base_size.width(), self._base_size.height()
		
		# 特殊处理序号
		if cmd.kind == "number":
			p = cmd.points[0]
			radius = self._pen_width(cmd, w, h)
			return QRectF(p[0]*w - radius, p[1]*h - radius, radius*2, radius*2)
		
		min_x = min(p[0] for p in cmd.points)
		max_x = max(p[0] for p in cmd.points)
		min_y = min(p[1] for p in cmd.points)
		max_y = max(p[1] for p in cmd.points)
		
		# 对于文本，需要额外扩展
		if cmd.kind == "text":
			max_x += 0.2 # 估算
			max_y += 0.1
			
		# 计算基础包围盒
		base_rect = QRectF(min_x * w, min_y * h, (max_x - min_x) * w, (max_y - min_y) * h)
		
		# 扩展笔触宽度
		stroke_width = self._pen_width(cmd, w, h)
		margin = stroke_width / 2.0 + 4
		
		return base_rect.adjusted(-margin, -margin, margin, margin)

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
					"rotation": cmd.rotation,
					"scale": cmd.scale,
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
					rotation=float(raw.get("rotation", 0.0)),
					scale=float(raw.get("scale", 1.0)),
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

	def _get_command_center(self, cmd: VectorPaintCommand, width: int, height: int) -> QPointF:
		if not cmd.points:
			return QPointF(0, 0)
		
		min_x = min(p[0] for p in cmd.points)
		max_x = max(p[0] for p in cmd.points)
		min_y = min(p[1] for p in cmd.points)
		max_y = max(p[1] for p in cmd.points)
		
		# Center in screen coordinates
		center_x = (min_x + max_x) / 2.0 * width
		center_y = (min_y + max_y) / 2.0 * height
		return QPointF(center_x, center_y)

	def _render_command(
		self, painter: QPainter, cmd: VectorPaintCommand, width: int, height: int
	) -> None:
		if not cmd.points:
			return
		
		painter.save()
		try:
			# Apply transformation
			if cmd.rotation != 0 or cmd.scale != 1.0:
				center = self._get_command_center(cmd, width, height)
				painter.translate(center)
				painter.rotate(cmd.rotation)
				painter.scale(cmd.scale, cmd.scale)
				painter.translate(-center)

			color = _color_from_tuple(cmd.color)

			if cmd.kind == "stroke":
				scaled_points = [self._scaled_point(pt, width, height) for pt in cmd.points]
				stroke_width = self._pen_width(cmd, width, height)
				StrokeStampRenderer.render(
					painter,
					scaled_points,
					stroke_width,
					QColor(color),
					cmd.extra.get("brush"),
					cmd.extra.get("raw_alpha"),
				)
			elif cmd.kind in {"rect", "circle"}:
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
			elif cmd.kind == "arrow":
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
			elif cmd.kind == "text":
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
			elif cmd.kind == "number":
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
		finally:
			painter.restore()

class StrokeStampRenderer:
	"""统一的笔迹重放器，保证画笔与荧光笔渲染一致"""

	@staticmethod
	def render(
		painter: QPainter,
		points: Sequence[QPointF],
		stroke_width: float,
		base_color: QColor,
		brush_hint,
		raw_alpha,
	) -> None:
		if not points:
			return
		brush_kind = StrokeStampRenderer._normalize_brush(brush_hint)
		color = QColor(base_color)
		alpha = float(color.alpha())
		if raw_alpha is not None:
			try:
				slider_alpha = float(raw_alpha)
			except Exception:
				slider_alpha = alpha
			alpha = StrokeStampRenderer._effective_alpha(slider_alpha, stroke_width)
		color.setAlpha(int(round(min(255.0, alpha))))
		half = stroke_width / 2.0
		last_point = None
		for point in points:
			x, y = point.x(), point.y()
			StrokeStampRenderer._stamp(painter, x, y, half, stroke_width, color, brush_kind)
			if last_point is not None:
				for ix, iy in StrokeStampRenderer._interpolate(last_point, (x, y)):
					StrokeStampRenderer._stamp(painter, ix, iy, half, stroke_width, color, brush_kind)
			last_point = (x, y)
		painter.setBrush(Qt.NoBrush)
		painter.setPen(Qt.NoPen)

	@staticmethod
	def _normalize_brush(value) -> str:
		if isinstance(value, str):
			val = value.lower()
			if val in ("round", "square"):
				return val
		try:
			return "round" if float(value or 0) >= 0.5 else "square"
		except Exception:
			return "round"

	@staticmethod
	def _effective_alpha(slider_alpha: float, stroke_width: float) -> float:
		if slider_alpha >= 255.0:
			return 255.0
		denom = max(1.0, stroke_width / 2.0)
		return max(1.0, slider_alpha / denom)

	@staticmethod
	def _stamp(
		painter: QPainter,
		x: float,
		y: float,
		half: float,
		size: float,
		color: QColor,
		brush_kind: str,
	) -> None:
		rect = QRectF(x - half, y - half, size, size)
		if brush_kind == "square":
			painter.fillRect(rect, color)
		else:
			painter.setPen(Qt.NoPen)
			painter.setBrush(color)
			painter.drawEllipse(rect)

	@staticmethod
	def _interpolate(
		start: Tuple[float, float], end: Tuple[float, float]
	) -> List[Tuple[float, float]]:
		dx = end[0] - start[0]
		dy = end[1] - start[1]
		steps = int(max(abs(dx), abs(dy)))
		if steps <= 1:
			return []
		return [
			(start[0] + dx * (step / float(steps)), start[1] + dy * (step / float(steps)))
			for step in range(1, steps)
		]


__all__ = ["VectorLayerDocument", "VectorPaintCommand", "StrokeStampRenderer"]
