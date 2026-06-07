"""
GUI 工具类

从 elitetmhelper2.py 提取：RedirectText 等通用 GUI 组件。
"""

import tkinter as tk

from i18n import _

import threading

class RedirectText:
    """拦截 print 输出并重定向到 Tkinter 文本框，支持高频缓冲合并写入以防止 UI 卡顿"""
    def __init__(self, text_ctrl):
        self.output = text_ctrl
        self.buffer = []
        self.lock = threading.Lock()
        self.is_scheduled = False

    def write(self, string):
        if not string:
            return
        with self.lock:
            self.buffer.append(string)
            if not self.is_scheduled:
                self.is_scheduled = True
                # 延迟 50ms 批量写入，大幅降低 Tkinter 重绘频率
                try:
                    self.output.after(50, self._flush_buffer)
                except Exception:
                    self.is_scheduled = False

    def _flush_buffer(self):
        with self.lock:
            text_to_write = "".join(self.buffer)
            self.buffer.clear()
            self.is_scheduled = False
            
        if not text_to_write:
            return
            
        try:
            # 检查滚动条是否在底部
            yview = self.output.yview()
            is_at_bottom = yview[1] >= 0.98
            
            self.output.insert(tk.END, text_to_write)
            
            if is_at_bottom:
                self.output.see(tk.END)
        except Exception:
            pass

    def flush(self):
        pass
