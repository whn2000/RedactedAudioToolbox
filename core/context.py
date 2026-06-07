from .paths import app_paths
from .logger import _setup_root_logger, get_logger
from .events import EventBus
from .state_manager import StateManager
from .config_manager import ConfigManager
from .secrets import SecretsManager
from .database import DBManager
from .database_queue import DBWriteQueue
from .cache_manager import CacheManager
from .migrations.runner import MigrationRunner
from .task_manager import TaskManager
from .consolidation import StorageGateway

class AppContext:
    """
    全局唯一的应用上下文 (Dependency Injection Container)。
    彻底取代旧有的全局单例满天飞的恶习。
    它负责按正确的拓扑顺序建立并销毁各核心模块，确保依赖的干净无环。
    未来的插件或 Task，只能获取到这个 ctx 对象。
    """
    def __init__(self):
        # 1. 基础路径先行 (确保有了落脚点)
        self.paths = app_paths
        self.paths.init_paths()
        
        # 2. 唤醒日志系统 (劫持全局输出)
        _setup_root_logger()
        self.logger = get_logger("AppContext")
        
        # 3. 中枢神经：EventBus
        self.events = EventBus()
        
        # 4. 全局大脑：状态管理器 (挂载到神经上)
        self.state = StateManager(self.events)
        
        # 5. 读取基石配置与凭据
        self.config = ConfigManager()
        self.secrets = SecretsManager()
        
        # 6. 数据底座：DBManager 与 DB 异步写队列
        self.db = DBManager()
        self.db_queue = DBWriteQueue(self.db)
        
        # 7. 体力清道夫：CacheManager
        self.cache = CacheManager(self.db)
        
        # 7.5. 统一存储网关：StorageGateway
        self.gateway = StorageGateway(self.config, self.secrets, self.cache, self.db)
        
        # 8. 无痛进化层：MigrationRunner
        self.migration = MigrationRunner(self.db, self.config)
        
        # 9. 任务执行大脑：TaskManager
        self.tasks = TaskManager(self)

    def startup(self):
        """
        正是由于有了统一上下文，我们可以规范整个启动流程。
        必须在进入主事件循环前调用。
        """
        self.logger.info("=========================================")
        self.logger.info("正在点火 RedactedAudioToolbox Runtime Core...")
        
        # 1. 强制执行迁移策略（带安全轮转备份）
        self.migration.run_migrations()
        
        # 2. 异步清空上一次遗留的临时数据和执行空间淘汰，避免阻塞主线程
        import threading
        threading.Thread(target=self.cache.init_cleanup, daemon=True).start()
        
        # 3. 播报核心准备就绪 (触发 app_state_changed 广播)
        from .state_manager import AppState
        self.state.set_state(AppState.IDLE, reason="Runtime Core 初始化完毕")
        
        self.logger.info("系统点火成功！随时准备接收外部调度。")
        self.logger.info("=========================================")

    def shutdown(self):
        """
        优雅的安全着陆机制。
        业务主函数通过 try...finally 或 atexit 捕获，并必须调用此函数。
        """
        self.logger.info("收到 Shutdown 信号，执行最后的数据封存...")
        
        from .state_manager import AppState
        self.state.set_state(AppState.SHUTTING_DOWN, reason="应用生命周期结束，安全停机")
        
        # 1. 拦截新任务入场，排空并等待当前任务终结
        self.tasks.shutdown()
        
        # 2. 不留垃圾
        self.cache.cleanup_temp()
        
        # 3. 将堆积的异步 SQL 刷入磁盘后安全下线 DB Worker
        self.db_queue.shutdown()
        
        # 4. 平滑断开底层连接
        self.db.close()
        
        self.logger.info("数据已全部安全入库。Runtime Core 引擎熄火。再会！")
