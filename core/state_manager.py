import threading
from enum import Enum
from typing import Optional, Callable, Dict, Any
from .events import EventBus
from .logger import get_logger

logger = get_logger(__name__)

class AppState(Enum):
    """全局应用级别状态"""
    STARTING = "starting"
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"

class TaskState(Enum):
    """用于未来任务系统 (Task System) 的标准化状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

class StateManager:
    """
    统一核心状态机。
    全面废弃了旧版散落的魔法字符串状态 (status="processing")。
    结合 EventBus，在状态发生转移时，实现自动化广播。
    """
    def __init__(self, event_bus: Optional[EventBus] = None):
        self._app_state = AppState.STARTING
        self._lock = threading.RLock()
        self.events = event_bus

    def set_state(self, new_state: AppState, reason: str = ""):
        """安全地更新全局状态，并触发广播"""
        with self._lock:
            if self._app_state != new_state:
                old_state = self._app_state
                self._app_state = new_state
                logger.info(f"应用状态流转: [{old_state.name}] -> [{new_state.name}] (原因: {reason})")
                
                # 若已挂载事件总线，则自动广播通知 UI 或别的观察者
                if self.events:
                    self.events.emit("app_state_changed", {
                        "old_state": old_state.value,
                        "new_state": new_state.value,
                        "reason": reason
                    })

    def get_state(self) -> AppState:
        """获取当前的枚举状态"""
        with self._lock:
            return self._app_state

    def register_listener(self, callback: Callable[[Dict[str, Any]], None]):
        """
        供暂时不方便直接使用 EventBus 的旧系统快速注册监听。
        本质上就是映射到 EventBus。
        """
        if self.events:
            self.events.subscribe("app_state_changed", callback)
            logger.debug(f"通过 StateManager 代理注册了事件监听器: {callback.__name__}")
        else:
            logger.warning("StateManager 尚未绑定 EventBus，无法注册状态监听。")
