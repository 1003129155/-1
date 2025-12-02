#!/usr/bin/env python3
"""
jietuba_logger.py - jietuba 日志管理模块

提供统一的日志记录功能，支持：
- 自动创建日志目录
- 按日期分割日志文件
- stdout/stderr 重定向到日志
- 异常捕获和记录
- 心跳监控
- 可配置的日志开关

使用示例：
    from jietuba_logger import JietubaLogger
    
    # 初始化日志
    logger = JietubaLogger(enabled=True)
    logger.setup()
    
    # 记录日志
    logger.info("程序启动")
    logger.error("发生错误")
    
    # 关闭日志
    logger.close()
"""

import sys
import os
import io
import time
import atexit
import traceback
import signal
import faulthandler
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional


class _TeeStream(io.TextIOBase):
    """将输出同步写入多个流（终端 + 文件）。"""

    def __init__(self, *targets):
        super().__init__()
        self._targets = [t for t in targets if t]

    def write(self, data):
        for target in self._targets:
            try:
                target.write(data)
            except Exception:
                pass
        return len(data)

    def flush(self):
        for target in self._targets:
            try:
                target.flush()
            except Exception:
                pass


class JietubaLogger:
    """jietuba 日志管理器
    
    功能：
    - 日志文件自动按日期命名
    - 同时输出到终端和文件
    - 捕获未处理的异常
    - 定期心跳日志
    - 可通过开关禁用
    
    属性：
        enabled (bool): 是否启用日志
        log_dir (Path): 日志目录路径
        log_file (file): 当前日志文件对象
    """
    
    # 单例模式
    _instance: Optional['JietubaLogger'] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """确保只有一个日志实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, log_dir: Optional[Path] = None, enabled: bool = True):
        """初始化日志管理器
        
        Args:
            log_dir: 日志目录路径，默认为 ~/.jietuba/logs
            enabled: 是否启用日志，默认启用
        """
        # 避免重复初始化
        if hasattr(self, '_initialized'):
            return
        
        self.enabled = enabled
        self.log_dir = log_dir or (Path.home() / ".jietuba" / "logs")
        self.log_file: Optional[io.TextIOWrapper] = None
        self._ready = False
        self._start_ts = time.time()
        
        # 保存原始流
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._original_excepthook = sys.excepthook
        self._original_threading_excepthook = getattr(threading, "excepthook", None)
        
        # 心跳线程
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop = threading.Event()
        
        self._initialized = True
    
    def setup(self):
        """初始化日志系统（启用监控、重定向输出）"""
        if not self.enabled:
            print("⚠️ [Logger] 日志功能已禁用")
            return
        
        if self._ready:
            return
        
        try:
            # 创建日志目录
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
            # 打开日志文件
            log_path = self.log_dir / f"runtime_{datetime.now():%Y%m%d}.log"
            self.log_file = open(log_path, "a", encoding="utf-8", buffering=1)
            
            self.info("🚀 [Logger] 日志系统启动")
            
        except Exception as exc:
            print(f"⚠️ [Logger] 无法创建日志文件: {exc}")
            self.enabled = False
            return
        
        # 重定向 stdout/stderr（保留终端输出）
        sys.stdout = _TeeStream(self._original_stdout, self.log_file)
        sys.stderr = _TeeStream(self._original_stderr, self.log_file)
        
        # 启用 faulthandler（捕获底层崩溃）
        try:
            faulthandler.enable(self.log_file, all_threads=True)
        except Exception as exc:
            self.warning(f"启用 faulthandler 失败: {exc}")
        
        # 设置异常处理
        self._setup_exception_handlers()
        
        # 设置信号处理
        self._setup_signal_handlers()
        
        # 设置退出钩子
        atexit.register(self._atexit_hook)
        
        # 启动心跳线程
        self._start_heartbeat()
        
        self._ready = True
        self.info("✅ [Logger] 日志系统就绪")
    
    def _setup_exception_handlers(self):
        """设置异常捕获处理器"""
        def handle_exception(exc_type, exc_value, exc_tb):
            stack = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
            self.error(f"未捕获异常:\n{stack}")
            if self._original_excepthook:
                self._original_excepthook(exc_type, exc_value, exc_tb)
        
        sys.excepthook = handle_exception
        
        # 线程异常处理
        if hasattr(threading, "excepthook"):
            def threading_hook(args):
                stack = ''.join(traceback.format_exception(
                    args.exc_type, args.exc_value, args.exc_traceback
                ))
                thread_name = getattr(args.thread, 'name', 'unknown')
                self.error(f"线程异常 (name={thread_name}):\n{stack}")
                if self._original_threading_excepthook:
                    self._original_threading_excepthook(args)
            
            threading.excepthook = threading_hook
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def handle_signal(sig_name):
            def inner(signum, frame):
                self.warning(f"收到信号 {sig_name}({signum})，准备退出")
                # 这里可以添加清理逻辑
            return inner
        
        for sig_name in ("SIGINT", "SIGTERM"):
            if hasattr(signal, sig_name):
                try:
                    signal.signal(getattr(signal, sig_name), handle_signal(sig_name))
                except Exception:
                    pass
        
        # Windows 特有信号
        if hasattr(signal, "SIGBREAK"):
            try:
                signal.signal(signal.SIGBREAK, handle_signal("SIGBREAK"))
            except Exception:
                pass
    
    def _start_heartbeat(self):
        """启动心跳线程（每10分钟记录一次）"""
        def heartbeat():
            while not self._heartbeat_stop.is_set():
                uptime = time.time() - self._start_ts
                self.info(
                    f"❤️ [Heartbeat] pid={os.getpid()}, "
                    f"线程数={threading.active_count()}, "
                    f"运行时长={uptime/3600:.2f}h"
                )
                # 等待10分钟或直到停止信号
                self._heartbeat_stop.wait(600)
        
        self._heartbeat_thread = threading.Thread(
            target=heartbeat,
            daemon=True,
            name="LoggerHeartbeat"
        )
        self._heartbeat_thread.start()
    
    def _atexit_hook(self):
        """程序退出时的清理工作"""
        uptime = time.time() - self._start_ts
        self.info(f"📦 [Logger] 进程准备退出，运行时长 {uptime:.0f}s")
    
    def _write(self, level: str, message: str):
        """写入日志（带时间戳和级别）
        
        Args:
            level: 日志级别（INFO/WARNING/ERROR）
            message: 日志内容
        """
        if not self.enabled or self.log_file is None:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.log_file.write(f"{timestamp} [{level}] {message}\n")
            self.log_file.flush()
        except Exception:
            pass
    
    def info(self, message: str):
        """记录信息日志
        
        Args:
            message: 日志内容
        """
        self._write("INFO", message)
    
    def warning(self, message: str):
        """记录警告日志
        
        Args:
            message: 日志内容
        """
        self._write("WARNING", f"⚠️ {message}")
    
    def error(self, message: str):
        """记录错误日志
        
        Args:
            message: 日志内容
        """
        self._write("ERROR", f"❌ {message}")
    
    def debug(self, message: str):
        """记录调试日志
        
        Args:
            message: 日志内容
        """
        self._write("DEBUG", f"🔍 {message}")
    
    def set_enabled(self, enabled: bool):
        """动态启用/禁用日志
        
        Args:
            enabled: 是否启用
        """
        if enabled and not self.enabled:
            # 启用日志
            self.enabled = True
            if not self._ready:
                self.setup()
        elif not enabled and self.enabled:
            # 禁用日志
            self.enabled = False
            self.info("⚠️ [Logger] 日志功能已禁用")
    
    def set_log_dir(self, log_dir: Path):
        """设置日志目录（需要重启日志系统）
        
        Args:
            log_dir: 新的日志目录路径
        """
        if self.log_dir != log_dir:
            self.info(f"📂 [Logger] 日志目录将更改为: {log_dir}")
            self.log_dir = log_dir
            # 注意：需要重启应用才能生效
    
    def get_log_dir(self) -> Path:
        """获取当前日志目录
        
        Returns:
            日志目录路径
        """
        return self.log_dir
    
    def get_current_log_file(self) -> Optional[Path]:
        """获取当前日志文件路径
        
        Returns:
            当前日志文件路径，如果未启用则返回 None
        """
        if not self.enabled or not self._ready:
            return None
        return self.log_dir / f"runtime_{datetime.now():%Y%m%d}.log"
    
    def close(self):
        """关闭日志系统（恢复原始流）"""
        if not self._ready:
            return
        
        self.info("📦 [Logger] 日志系统关闭")
        
        # 停止心跳线程
        if self._heartbeat_thread:
            self._heartbeat_stop.set()
            self._heartbeat_thread.join(timeout=1)
        
        # 恢复原始流
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        sys.excepthook = self._original_excepthook
        
        if self._original_threading_excepthook and hasattr(threading, "excepthook"):
            threading.excepthook = self._original_threading_excepthook
        
        # 关闭日志文件
        if self.log_file:
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None
        
        self._ready = False


# 全局日志实例（单例）
_global_logger: Optional[JietubaLogger] = None


def get_logger(log_dir: Optional[Path] = None, enabled: bool = True) -> JietubaLogger:
    """获取全局日志实例
    
    Args:
        log_dir: 日志目录路径
        enabled: 是否启用日志
    
    Returns:
        全局日志实例
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = JietubaLogger(log_dir=log_dir, enabled=enabled)
    return _global_logger
