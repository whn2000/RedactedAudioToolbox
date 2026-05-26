import time
from typing import Callable, Any
from .tasks import Task
from .logger import get_logger

logger = get_logger(__name__)

class LegacyFunctionAdapter(Task):
    """
    通用型万能旧业务包裹器 (Adapter Pattern)。
    目的：不修改任何现有的黑盒函数，直接将其转换为支持被 TaskManager 调度的标准 Task。
    局限性：由于是纯黑盒，无法实现颗粒度的进度更新（只能从 0% 直接跳到 100%），
    并且如果旧函数本身不支持中断，它将无法响应取消指令（只能等它卡完）。
    """
    def __init__(self, task_id: str, name: str, func: Callable, *args, **kwargs):
        super().__init__(id=task_id, name=name, type="legacy_adapter")
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self, context: Any):
        logger.info(f"[适配器] 开始调度旧模块: {self.name}")
        
        # 仅仅在进入黑盒前，有机会响应一下外界的取消/暂停
        self.check_flags()
        self.update_progress(5.0) 
        
        # --- [黑盒执行区] ---
        # 如果您的旧函数其实可以接受一个 progress_callback，您应该这样传进去：
        # self.kwargs['progress_callback'] = self.update_progress
        result = self.func(*self.args, **self.kwargs)
        # -------------------
        
        self.update_progress(100.0)
        logger.info(f"[适配器] 旧模块运行告捷: {self.name}")
        return result

class SpectrogramAdapterTask(Task):
    """
    专用的具体业务适配器示例 (针对“频谱分析”流程)。
    相对于上方的万能黑盒，如果我们能轻微改动旧代码，将大循环拆出来放到 run 里，
    就能获得完美的进度条支持和瞬间的响应打断能力。
    """
    def __init__(self, task_id: str, file_path: str):
        # 自动利用父类的 dataclass 特性补全状态
        super().__init__(id=task_id, name=f"降频与频谱生成", type="spectrogram")
        self.file_path = file_path

    def run(self, context: Any):
        self.update_progress(0.0)
        
        # ========================================================
        # 此处展示了如何以“最小侵入式”复用旧算法：
        # 原本的代码可能是：
        # old_module.do_everything_in_one_function(self.file_path)
        # 
        # 我们最好将其拆为：
        # total = old_module.get_total_tracks(self.file_path)
        # for track in tracks:
        #     old_module.process_single(track)
        # ========================================================
        
        # [演示代码] 用休眠模拟分步处理旧逻辑：
        total_steps = 10
        for step in range(1, total_steps + 1):
            
            # --- 核心：每完成一个子步骤，都必须呼叫 check_flags() ---
            # 如果外界点了取消，这里会直接抛 InterruptedError，安全结束该线程！
            # 如果外界点了暂停，它就会在此处死等，直到重新 resume。
            self.check_flags()
            
            time.sleep(0.5) # 假装这里在调用旧的 ffmpeg 分析
            
            # --- 自动通过 EventBus 广播并同步到 SQLite
            self.update_progress((step / total_steps) * 100)
            
        logger.info(f"频谱处理任务 {self.id} 完美完工。")
