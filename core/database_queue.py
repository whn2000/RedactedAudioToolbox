import threading
import queue
from typing import Tuple, Any
from .database import DBManager
from .logger import get_logger

logger = get_logger(__name__)

class DBWriteQueue:
    """
    核心的单线程数据库写队列 (DB Worker Queue)。
    目标：彻底根除 SQLite 并发高负载下的 `database is locked` 异常。
    规则：所有的写操作 (INSERT/UPDATE/DELETE) 统一进入该队列排队；读操作仍直接调用 DBManager (得益于 WAL)。
    """
    def __init__(self, db_manager: DBManager):
        self.db = db_manager
        # 使用无界队列，任务在内存中缓冲
        self.queue = queue.Queue()
        self._stop_event = threading.Event()
        # Daemon=True 保证如果主线程崩溃它不会阻止进程退出
        self._worker_thread = threading.Thread(target=self._worker_loop, name="DBWorkerThread", daemon=True)
        self._worker_thread.start()

    def execute_async(self, sql: str, params: tuple = ()):
        """
        异步提交写任务到队列，立刻返回。
        非常适合日志、状态更新、进度汇报等不关心受影响行数的后台写入。
        """
        if self._stop_event.is_set():
            logger.warning("DBWriteQueue 正在关闭，拒绝了新的异步写任务。")
            return
        self.queue.put((sql, params))

    def _worker_loop(self):
        logger.info("DB Worker 线程已就位，准备处理写操作。")
        # 只要没有关闭信号，或者队列还有没干完的活，就继续循环
        while not self._stop_event.is_set() or not self.queue.empty():
            try:
                # 加上 timeout 使得它可以周期性地检查 _stop_event
                task = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if task is None: # 毒丸信号 (Poison Pill)
                self.queue.task_done()
                break

            sql, params = task
            try:
                # 利用 DBManager 已有的 context_manager 自动包裹事务
                self.db.execute(sql, params)
            except Exception as e:
                logger.error(f"[DBWorker] SQL执行失败: {e}\nSQL: {sql}\nParams: {params}", exc_info=True)
            finally:
                self.queue.task_done()

        logger.info("DB Worker 线程已清理完积压任务并安全退出。")

    def flush(self):
        """阻塞当前线程，直到队列中当前的排队任务全部完成"""
        self.queue.join()

    def shutdown(self):
        """Graceful shutdown. 停止接收新任务并阻塞等待当前队列清空。"""
        logger.info("正在执行 DBWriteQueue Graceful Shutdown...")
        self._stop_event.set()
        self.queue.put(None) # 放毒丸强制结束阻塞中的 get
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10.0) # 最多等 10 秒
            if self._worker_thread.is_alive():
                logger.error("DBWriteQueue 超时未能安全退出，可能有僵尸 SQL！")
        logger.info("DBWriteQueue 关闭完成。")
