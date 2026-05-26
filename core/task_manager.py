import threading
import queue
from typing import Dict, List, Optional
from .tasks import Task, TaskState
from .worker_pool import WorkerPool
from .logger import get_logger

logger = get_logger(__name__)

class TaskManager:
    """
    业务执行层的大脑 (Execution Orchestrator)。
    负责所有的 Task 排队、分发、注册表管理以及对生命周期的干预（取消/恢复）。
    自带单线分发器与多线执行池 (WorkerPool)，以及安全的系统阻断与关机机制。
    """
    def __init__(self, context, max_workers: int = 5):
        self.ctx = context
        self.pool = WorkerPool(max_workers=max_workers)
        
        # 内存中央注册表，便于随时检索进度
        self.registry: Dict[str, Task] = {}
        self._registry_lock = threading.RLock()
        
        # 具有缓冲机制的待命队列
        self.pending_queue = queue.Queue()
        self._stop_event = threading.Event()
        
        # 启动唯一的专属调配线程
        self._dispatcher_thread = threading.Thread(target=self._dispatcher_loop, name="TaskDispatcher", daemon=True)
        self._dispatcher_thread.start()

    def submit(self, task: Task):
        """暴露给外部的唯一投递口"""
        if self._stop_event.is_set():
            logger.warning(f"TaskManager 正在关机，拒绝接单: {task.name}")
            return
            
        with self._registry_lock:
            self.registry[task.id] = task
            
        task.bind_context(self.ctx)
        task.update_state(TaskState.PENDING)
        
        # 初次声明，将记录打入数据库进行持久化
        sql = """
        INSERT OR REPLACE INTO task_runtime 
        (id, name, type, state, progress) 
        VALUES (?, ?, ?, ?, ?)
        """
        self.ctx.db_queue.execute_async(sql, (
            task.id, task.name, task.type, task.state.value, task.progress
        ))
        
        self.pending_queue.put(task)
        logger.info(f"任务成功过检并入库排队: [{task.id}] {task.name}")

    def _dispatcher_loop(self):
        """从队列源源不断抓取 PENDING，推入底层 WorkerPool"""
        while not self._stop_event.is_set() or not self.pending_queue.empty():
            try:
                task = self.pending_queue.get(timeout=0.5)
            except queue.Empty:
                continue
                
            if task is None: # 收到了毒丸信号
                self.pending_queue.task_done()
                break
                
            # 有可能排队时被外界直接干掉了
            if task.state == TaskState.CANCELLED:
                self.pending_queue.task_done()
                continue
                
            # 移交给实际的线程池
            self.pool.submit(task.id, self._run_task_wrapper, task)
            self.pending_queue.task_done()

    def _run_task_wrapper(self, task: Task):
        """Worker 线程真正执行的方法，必须加固以防雪崩"""
        try:
            task.update_state(TaskState.RUNNING)
            task.run(self.ctx)
            
            # 业务方跑完了，如果状态还没有被定性，说明是自然完成
            with task._lock:
                if task.state not in (TaskState.PAUSED, TaskState.CANCELLED, TaskState.FAILED):
                    task.update_progress(100.0)
                    task.update_state(TaskState.COMPLETED)
                    
        except InterruptedError as e:
            # 响应了合作式中断 (cancel 被点击触发了)
            task.update_state(TaskState.CANCELLED, error=str(e))
        except Exception as e:
            logger.error(f"[TaskManager] 任务崩溃脱轨 [{task.id}]: {e}", exc_info=True)
            task.update_state(TaskState.FAILED, error=str(e))
        finally:
            logger.info(f"资源释放: [{task.id}] 最终被落定为 {task.state.name}")

    def get_task(self, task_id: str) -> Optional[Task]:
        """供未来 WebUI 或 API 轮询"""
        with self._registry_lock:
            return self.registry.get(task_id)

    def list_tasks(self) -> List[Task]:
        with self._registry_lock:
            return list(self.registry.values())

    def cancel_task(self, task_id: str):
        """提供统一的指令代理"""
        task = self.get_task(task_id)
        if task:
            task.cancel()

    def shutdown(self):
        """配合全局 AppContext 完成极度平滑的安全关机 (Graceful Shutdown)"""
        logger.info("TaskManager 接到撤退命令，封锁入口并排空队列...")
        self._stop_event.set()
        self.pending_queue.put(None)
        
        # 为了保证立刻关机，而不是等长任务耗几个小时，我们将存活的任务统一掐断
        with self._registry_lock:
            for task in self.registry.values():
                if task.state in (TaskState.PENDING, TaskState.RUNNING, TaskState.PAUSED):
                    task.cancel()
                    
        # 等待工作线程因响应 Cancel 而退出循环
        self.pool.shutdown(wait=True)
        
        if self._dispatcher_thread.is_alive():
            self._dispatcher_thread.join(timeout=5.0)
            
        logger.info("TaskManager 辖下所有工人均已结账离场。")
