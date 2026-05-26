import threading
from typing import Callable, Dict, List, Any
from .logger import get_logger

logger = get_logger(__name__)

class EventBus:
    """
    统一的线程安全事件总线 (EventBus)。
    实现核心模块的松耦合通信，为未来的 TaskSystem 和 WebSocket 推送做铺垫。
    避免引入重量级的消息队列（如 Redis/RabbitMQ），保持单体应用的轻量化。
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_name: str, callback: Callable[[Dict[str, Any]], None]):
        """
        订阅事件。回调函数应接收一个 dict 类型的 payload 参数。
        """
        with self._lock:
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []
            if callback not in self._subscribers[event_name]:
                self._subscribers[event_name].append(callback)
                logger.debug(f"已订阅事件: {event_name} -> {callback.__name__}")

    def unsubscribe(self, event_name: str, callback: Callable):
        """取消订阅指定的事件。"""
        with self._lock:
            if event_name in self._subscribers:
                try:
                    self._subscribers[event_name].remove(callback)
                    logger.debug(f"已取消订阅事件: {event_name} -> {callback.__name__}")
                except ValueError:
                    pass

    def emit(self, event_name: str, payload: Dict[str, Any] = None):
        """
        分发事件 (同步执行)。
        在执行 listener 时捕获异常，确保某个 listener 的崩溃不会中断整个系统的分发链。
        """
        if payload is None:
            payload = {}
            
        logger.debug(f"[EventBus] Emit: {event_name} | Payload: {payload}")
        
        # 为了防止在回调中再次调用 subscribe/unsubscribe 导致死锁或迭代器异常，
        # 我们拷贝一份当前的 callbacks 列表进行执行。
        with self._lock:
            callbacks = self._subscribers.get(event_name, []).copy()
            
        for callback in callbacks:
            try:
                callback(payload)
            except Exception as e:
                logger.error(f"[EventBus] Listener 异常 - Event: {event_name}, Callback: {callback.__name__}, Error: {e}", exc_info=True)
