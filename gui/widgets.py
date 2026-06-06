"""
GUI 工具类

从 elitetmhelper2.py 提取：RedirectText 等通用 GUI 组件。
"""

import tkinter as tk

from i18n import _

class RedirectText:
    """拦截 print 输出并重定向到 Tkinter 文本框"""
    def __init__(self, text_ctrl):
        self.output = text_ctrl

    def write(self, string):
        def _write():
            try:
                # Check if scrollbar is at the bottom before inserting
                yview = self.output.yview()
                is_at_bottom = yview[1] >= 0.99
                
                self.output.insert(tk.END, string)
                
                if is_at_bottom:
                    self.output.see(tk.END)
            except Exception:
                pass
        self.output.after(0, _write)

    def flush(self):
        pass
