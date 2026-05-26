import concurrent.futures
import threading
from typing import Dict
from .logger import get_logger

logger = get_logger(__name__)

class WorkerPool:
    """
    基于 ThreadPoolExecutor 构建的轻量级任务线程池。
    专门配合 TaskManager 调度长生命周期的任务，避免引入 Celery 等重依赖。
    并自带 Future 跟踪机制，以便支持 Graceful Shutdown。
    """
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="TaskWorker"
        )
        # 用来追踪尚未执行完的底层 Future 对象
        self.futures: Dict[str, concurrent.futures.Future] = {}
        self._lock = threading.RLock()

    def submit(self, task_id: str, func, *args, **kwargs):
        """将耗时函数扔进池子，并注册回收钩子防内存泄露"""
        with self._lock:
            future = self.executor.submit(func, *args, **kwargs)
            self.futures[task_id] = future
            
            # 当该任务因报错或正常结束退出时，自动将其踢出追踪队列
            future.add_done_callback(lambda f: self._cleanup_future(task_id))
            return future

    def _cleanup_future(self, task_id: str):
        with self._lock:
            self.futures.pop(task_id, None)

    def shutdown(self, wait=True):
        """
        断开入口，不再接客，并视情况等待客人们执行完毕。
        属于 Graceful Shutdown 的重要一环。
        """
        active_count = len(self.futures)
        if active_count > 0:
            logger.info(f"WorkerPool 正在执行下线，等待 {active_count} 个正在执行的线程安全结束...")
        
        # 阻塞直到所有工作线程从 run() 中退出
        self.executor.shutdown(wait=wait)
        logger.info("WorkerPool 已清空，所有工作线程安全退场。")
