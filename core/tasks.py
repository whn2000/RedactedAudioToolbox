import time
import threading
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any

from .logger import get_logger

logger = get_logger(__name__)

class TaskState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Task(ABC):
    """
    高度标准化的业务抽象层 (Task System)。
    无论是“下载”、“频谱分析”还是“制种”，所有的野生子例程都要被包裹在此类中。
    自带线程安全的进度跟踪、事件通知、持久化防丢以及可中断循环。
    """
    id: str
    name: str
    type: str
    state: TaskState = TaskState.PENDING
    progress: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error_message: Optional[str] = None
    
    def __post_init__(self):
        # 初始化线程保护设施，dataclass 不会自动执行 init 所以用 post_init
        self._lock = threading.RLock()
        self._pause_event = threading.Event()
        self._pause_event.set() # 初始状态为放行 (不阻塞)
        self._cancel_flag = False
        self._context = None # 在由 TaskManager 分派执行时自动注入
        
    def bind_context(self, context):
        """在排队时将上下文注入到任务内"""
        self._context = context

    def _emit_update(self):
        """内部方法：利用 AppContext 进行双端推送（EventBus 通知 UI + 异步写库）"""
        self.updated_at = time.time()
        if not self._context:
            return
            
        try:
            # 1. 广播内存事件 (比如 WebSocket 通知前端更新进度条)
            self._context.events.emit("task_updated", {
                "id": self.id,
                "name": self.name,
                "state": self.state.value,
                "progress": self.progress,
                "error": self.error_message
            })
            
            # 2. 异步写队列持久化 (程序崩溃重启还能看到状态)
            # 需要在 context.py 里补上 db_queue，或者这里容错处理
            if hasattr(self._context, "db_queue"):
                sql = """
                UPDATE task_runtime 
                SET state=?, progress=?, error_message=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """
                self._context.db_queue.execute_async(sql, (
                    self.state.value, self.progress, self.error_message, self.id
                ))
        except Exception as e:
            logger.error(f"Task {_emit_update} 失败: {e}")

    def update_state(self, new_state: TaskState, error: str = None):
        """安全地跃迁状态并广播"""
        with self._lock:
            if self.state == new_state: return
            self.state = new_state
            if error:
                self.error_message = error
            logger.info(f"[Task {self.id}] 状态变更 -> {new_state.name}")
            self._emit_update()

    def update_progress(self, progress: float):
        """安全地汇报进度 (0.0 - 100.0)"""
        with self._lock:
            new_prog = round(max(0.0, min(100.0, progress)), 2)
            if self.progress != new_prog:
                self.progress = new_prog
                self._emit_update()

    def check_flags(self):
        """
        合作式中断检查。
        子类必须在 `run()` 的长循环中 (如每一块下载、每处理一张图) 频繁调用此方法。
        如果是暂停状态，这里会安全阻塞；如果被取消，会直接抛异常跳出循环。
        """
        if self._cancel_flag:
            raise InterruptedError("Task was explicitly cancelled by user or system.")
            
        # 阻塞直到 _pause_event 为 set 状态
        self._pause_event.wait()

    @abstractmethod
    def run(self, context: Any):
        """
        子类核心逻辑存放点。
        执行结束前不需要手动设置为 COMPLETED，TaskManager 会负责兜底处理。
        """
        pass

    def pause(self):
        """外部调用以暂停该任务"""
        with self._lock:
            if self.state == TaskState.RUNNING:
                self._pause_event.clear() # 挂起标志
                self.update_state(TaskState.PAUSED)
                
    def resume(self):
        """外部调用以恢复该任务"""
        with self._lock:
            if self.state == TaskState.PAUSED:
                self._pause_event.set() # 释放标志
                self.update_state(TaskState.RUNNING)
                
    def cancel(self):
        """外部调用以取消该任务"""
        with self._lock:
            if self.state not in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
                self._cancel_flag = True
                self._pause_event.set() # 强制解除因 Pause 导致的阻塞以允许其迅速退出
                self.update_state(TaskState.CANCELLED)
