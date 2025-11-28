#!/usr/bin/env python3
"""
测试 jietuba_long_stitch.py 的拼接接口

功能：
1. 选择两个图片文件（图片1和图片2）
2. 选择拼接方向（横向/竖向）
3. 选择拼接引擎（Rust/Python）
4. 执行拼接并显示结果
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import os
import sys
from pathlib import Path

# 导入拼接模块
try:
    from jietuba_long_stitch import stitch_images_rust, stitch_images_python, RUST_AVAILABLE
    print("✅ 成功导入拼接模块")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)


class StitchTestApp:
    """拼接测试应用"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("长截图拼接测试工具")
        self.root.geometry("900x700")
        
        # 图片路径
        self.img1_path = None
        self.img2_path = None
        self.result_img = None
        
        # 创建UI
        self.create_ui()
        
    def create_ui(self):
        """创建用户界面"""
        
        # 标题
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame, 
            text="🔧 长截图拼接测试工具", 
            font=("Microsoft YaHei", 16, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title_label.pack(pady=15)
        
        # 主容器
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== 图片选择区域 =====
        select_frame = tk.LabelFrame(main_frame, text="📁 图片选择", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=10)
        select_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 图片1
        img1_frame = tk.Frame(select_frame)
        img1_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(img1_frame, text="图片1 (顺序1):", width=15, anchor="w").pack(side=tk.LEFT)
        self.img1_label = tk.Label(img1_frame, text="未选择", fg="gray", anchor="w", width=40)
        self.img1_label.pack(side=tk.LEFT, padx=5)
        tk.Button(img1_frame, text="选择", command=self.select_img1, width=8).pack(side=tk.LEFT)
        
        # 图片2
        img2_frame = tk.Frame(select_frame)
        img2_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(img2_frame, text="图片2 (顺序2):", width=15, anchor="w").pack(side=tk.LEFT)
        self.img2_label = tk.Label(img2_frame, text="未选择", fg="gray", anchor="w", width=40)
        self.img2_label.pack(side=tk.LEFT, padx=5)
        tk.Button(img2_frame, text="选择", command=self.select_img2, width=8).pack(side=tk.LEFT)
        
        # ===== 拼接参数区域 =====
        param_frame = tk.LabelFrame(main_frame, text="⚙️ 拼接参数", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=10)
        param_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 拼接方向
        direction_frame = tk.Frame(param_frame)
        direction_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(direction_frame, text="拼接方向:", width=15, anchor="w").pack(side=tk.LEFT)
        self.direction_var = tk.StringVar(value="vertical")
        tk.Radiobutton(direction_frame, text="竖向拼接 (↓)", variable=self.direction_var, value="vertical").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(direction_frame, text="横向拼接 (→)", variable=self.direction_var, value="horizontal").pack(side=tk.LEFT, padx=5)
        
        # 拼接引擎
        engine_frame = tk.Frame(param_frame)
        engine_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(engine_frame, text="拼接引擎:", width=15, anchor="w").pack(side=tk.LEFT)
        self.engine_var = tk.StringVar(value="rust" if RUST_AVAILABLE else "python")
        
        rust_radio = tk.Radiobutton(
            engine_frame, 
            text="🚀 Rust (快速)", 
            variable=self.engine_var, 
            value="rust",
            state=tk.NORMAL if RUST_AVAILABLE else tk.DISABLED
        )
        rust_radio.pack(side=tk.LEFT, padx=5)
        
        python_radio = tk.Radiobutton(engine_frame, text="🐍 Python (调试)", variable=self.engine_var, value="python")
        python_radio.pack(side=tk.LEFT, padx=5)
        
        if not RUST_AVAILABLE:
            tk.Label(engine_frame, text="(Rust 未加载)", fg="orange").pack(side=tk.LEFT, padx=5)
        
        # 忽略像素数
        ignore_frame = tk.Frame(param_frame)
        ignore_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(ignore_frame, text="忽略右侧像素:", width=15, anchor="w").pack(side=tk.LEFT)
        self.ignore_pixels_var = tk.StringVar(value="20")
        tk.Entry(ignore_frame, textvariable=self.ignore_pixels_var, width=10).pack(side=tk.LEFT, padx=5)
        tk.Label(ignore_frame, text="(用于排除滚动条影响)", fg="gray").pack(side=tk.LEFT, padx=5)
        
        # 调试模式
        debug_frame = tk.Frame(param_frame)
        debug_frame.pack(fill=tk.X, pady=5)
        
        self.debug_var = tk.BooleanVar(value=False)
        tk.Checkbutton(debug_frame, text="启用调试输出", variable=self.debug_var).pack(side=tk.LEFT, padx=(0, 5))
        
        # ===== 执行按钮 =====
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.stitch_btn = tk.Button(
            button_frame, 
            text="🔗 开始拼接", 
            command=self.do_stitch,
            font=("Microsoft YaHei", 11, "bold"),
            bg="#27ae60",
            fg="white",
            height=2,
            cursor="hand2"
        )
        self.stitch_btn.pack(fill=tk.X)
        
        # ===== 结果显示区域 =====
        result_frame = tk.LabelFrame(main_frame, text="📊 拼接结果", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=10)
        result_frame.pack(fill=tk.BOTH, expand=True)
        
        # 结果信息
        self.result_text = tk.Text(result_frame, height=6, wrap=tk.WORD, font=("Consolas", 9))
        self.result_text.pack(fill=tk.X, pady=(0, 10))
        
        # 预览区域
        preview_label = tk.Label(result_frame, text="拼接结果预览:", anchor="w")
        preview_label.pack(fill=tk.X)
        
        # 创建可滚动的Canvas
        canvas_frame = tk.Frame(result_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg="white", highlightthickness=1, highlightbackground="gray")
        scrollbar_y = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        scrollbar_x = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 底部按钮
        bottom_frame = tk.Frame(result_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        tk.Button(bottom_frame, text="💾 保存结果", command=self.save_result).pack(side=tk.LEFT, padx=5)
        tk.Button(bottom_frame, text="🔄 清除", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        
    def select_img1(self):
        """选择图片1"""
        file_path = filedialog.askopenfilename(
            title="选择图片1",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp"), ("所有文件", "*.*")]
        )
        if file_path:
            self.img1_path = file_path
            self.img1_label.config(text=os.path.basename(file_path), fg="black")
            self.log(f"✅ 已选择图片1: {file_path}")
    
    def select_img2(self):
        """选择图片2"""
        file_path = filedialog.askopenfilename(
            title="选择图片2",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp"), ("所有文件", "*.*")]
        )
        if file_path:
            self.img2_path = file_path
            self.img2_label.config(text=os.path.basename(file_path), fg="black")
            self.log(f"✅ 已选择图片2: {file_path}")
    
    def log(self, message):
        """输出日志"""
        print(message)
        self.result_text.insert(tk.END, message + "\n")
        self.result_text.see(tk.END)
        self.root.update()
    
    def do_stitch(self):
        """执行拼接"""
        # 清空之前的日志
        self.result_text.delete(1.0, tk.END)
        
        # 检查图片是否已选择
        if not self.img1_path or not self.img2_path:
            messagebox.showerror("错误", "请先选择两张图片！")
            return
        
        try:
            self.log("=" * 60)
            self.log("🚀 开始拼接测试...")
            self.log(f"图片1: {self.img1_path}")
            self.log(f"图片2: {self.img2_path}")
            
            # 加载图片
            self.log("\n📥 加载图片...")
            img1 = Image.open(self.img1_path)
            img2 = Image.open(self.img2_path)
            self.log(f"图片1尺寸: {img1.size}")
            self.log(f"图片2尺寸: {img2.size}")
            
            # 获取参数
            direction = self.direction_var.get()
            engine = self.engine_var.get()
            debug = self.debug_var.get()
            
            try:
                ignore_pixels = int(self.ignore_pixels_var.get())
            except ValueError:
                ignore_pixels = 20
                self.log("⚠️  忽略像素数无效，使用默认值20")
            
            self.log(f"\n⚙️ 拼接参数:")
            self.log(f"  - 方向: {'竖向' if direction == 'vertical' else '横向'}")
            self.log(f"  - 引擎: {engine.upper()}")
            self.log(f"  - 忽略像素: {ignore_pixels}")
            self.log(f"  - 调试模式: {'开' if debug else '关'}")
            
            # 横向拼接需要旋转图片
            if direction == "horizontal":
                self.log("\n🔄 横向拼接，旋转图片...")
                # 逆时针旋转90度：竖向的"上下"变成横向的"左右"
                img1 = img1.rotate(-90, expand=True)
                img2 = img2.rotate(-90, expand=True)
                self.log(f"旋转后尺寸: {img1.size}, {img2.size}")
            
            # 执行拼接
            self.log(f"\n🔗 执行拼接 ({engine})...")
            import time
            start_time = time.perf_counter()
            
            if engine == "rust":
                result = stitch_images_rust(img1, img2, ignore_pixels, debug)
            else:
                result = stitch_images_python(img1, img2, ignore_pixels, debug)
            
            elapsed = time.perf_counter() - start_time
            
            if result is None:
                self.log(f"\n❌ 拼接失败！耗时: {elapsed*1000:.2f}ms")
                messagebox.showerror("拼接失败", "拼接过程返回了空结果，可能是图片无法找到重叠区域。")
                return
            
            # 横向拼接结果需要旋转回来
            if direction == "horizontal":
                self.log("\n🔄 旋转结果图片...")
                # 顺时针旋转90度，恢复正常方向
                result = result.rotate(90, expand=True)
            
            self.log(f"\n✅ 拼接成功！")
            self.log(f"  - 结果尺寸: {result.size}")
            self.log(f"  - 耗时: {elapsed*1000:.2f}ms")
            self.log(f"  - 性能: {(elapsed*1000):.2f}ms")
            
            # 显示结果
            self.result_img = result
            self.display_result(result)
            
            self.log("\n" + "=" * 60)
            
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            self.log(f"\n❌ 错误: {e}")
            self.log(error_msg)
            messagebox.showerror("错误", f"拼接过程出错：\n{e}")
    
    def display_result(self, img):
        """在Canvas上显示结果图片"""
        # 清空Canvas
        self.canvas.delete("all")
        
        # 缩放图片以适应Canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width = 600
            canvas_height = 300
        
        # 计算缩放比例
        img_width, img_height = img.size
        scale = min(canvas_width / img_width, canvas_height / img_height, 1.0)
        
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        
        # 缩放图片
        display_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 转换为Tkinter格式
        self.photo = ImageTk.PhotoImage(display_img)
        
        # 显示在Canvas中心
        x = max(canvas_width // 2, new_width // 2)
        y = max(canvas_height // 2, new_height // 2)
        
        self.canvas.create_image(x, y, image=self.photo, anchor=tk.CENTER)
        self.canvas.config(scrollregion=(0, 0, new_width, new_height))
    
    def save_result(self):
        """保存拼接结果"""
        if self.result_img is None:
            messagebox.showwarning("提示", "没有可保存的结果！")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="保存拼接结果",
            defaultextension=".png",
            filetypes=[("PNG图片", "*.png"), ("JPEG图片", "*.jpg"), ("所有文件", "*.*")]
        )
        
        if file_path:
            self.result_img.save(file_path)
            self.log(f"\n💾 结果已保存: {file_path}")
            messagebox.showinfo("成功", f"结果已保存到:\n{file_path}")
    
    def clear_all(self):
        """清除所有内容"""
        self.img1_path = None
        self.img2_path = None
        self.result_img = None
        
        self.img1_label.config(text="未选择", fg="gray")
        self.img2_label.config(text="未选择", fg="gray")
        self.result_text.delete(1.0, tk.END)
        self.canvas.delete("all")
        
        self.log("🔄 已清除所有内容")


def main():
    """主函数"""
    print("=" * 60)
    print("🔧 长截图拼接测试工具")
    print("=" * 60)
    print(f"Rust加速: {'✅ 可用' if RUST_AVAILABLE else '❌ 不可用'}")
    print("=" * 60)
    
    root = tk.Tk()
    app = StitchTestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
