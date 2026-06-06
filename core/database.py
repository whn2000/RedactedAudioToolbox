import sqlite3
import threading
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

from .paths import app_paths
from .logger import get_logger

logger = get_logger(__name__)

# 当前代码库的目标 Schema 版本
CURRENT_SCHEMA_VERSION = 3

INIT_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_cache (
    query_hash TEXT PRIMARY KEY,
    result_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_processed (
    hash TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    progress REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS risk_scores (
    torrent_id TEXT PRIMARY KEY,
    score REAL NOT NULL,
    details TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_runtime (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    state TEXT NOT NULL,
    progress REAL DEFAULT 0.0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS discovery_cache (
    id TEXT PRIMARY KEY,
    artist TEXT NOT NULL,
    album TEXT NOT NULL,
    year INTEGER,
    edition TEXT,
    platform TEXT NOT NULL,
    platform_id TEXT NOT NULL,
    platform_url TEXT,
    upc TEXT,
    label TEXT,
    best_quality TEXT,
    red_status TEXT DEFAULT 'unchecked',
    red_group_id INTEGER,
    red_missing_formats TEXT,
    red_existing_editions TEXT,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checked_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watch_artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name TEXT NOT NULL UNIQUE,
    platforms TEXT DEFAULT '["all"]',
    target_sites TEXT DEFAULT '["RED"]',
    enabled INTEGER DEFAULT 1,
    check_interval INTEGER DEFAULT 43200,
    last_checked TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS discovery_results (
    id TEXT PRIMARY KEY,
    artist TEXT NOT NULL,
    album TEXT NOT NULL,
    year INTEGER,
    platform TEXT NOT NULL,
    platform_id TEXT NOT NULL,
    red_exists INTEGER DEFAULT 0,
    ops_exists INTEGER DEFAULT 0,
    jps_exists INTEGER DEFAULT 0,
    dic_exists INTEGER DEFAULT 0,
    red_group_id INTEGER,
    ops_group_id INTEGER,
    jps_group_id INTEGER,
    dic_group_id INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS discovery_tasks (
    id TEXT PRIMARY KEY,
    discovery_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    output_path TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (discovery_id) REFERENCES discovery_cache(id)
);
"""

class DBManager:
    """
    第一阶段基础数据库层封装。
    采用 Thread-Local 连接池配合 WAL 模式实现并发安全，
    并提供严格的参数化查询接口 (防注入)。
    遵守渐进式重构原则，暂不引入复杂的 Worker Queue。
    """
    def __init__(self):
        self.db_path = app_paths.database_dir / "app.db"
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """为当前线程获取或创建一个稳定的连接"""
        if not hasattr(self._local, "conn"):
            # check_same_thread=False 防止跨框架假性多线程拦截，主要仍靠 thread-local 隔离并发
            conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=15.0 # 提供15秒重试缓冲，降低并发锁表 (Busy) 概率
            )
            # Row factory 实现类似字典的查询结果返回
            conn.row_factory = sqlite3.Row
            
            # 开启 WAL 模式 (Write-Ahead Logging) 以极大提升 SQLite 的读写并发性能
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        """自动完成数据库建表及 Meta 版本初始化"""
        try:
            with self.transaction() as cursor:
                cursor.executescript(INIT_SQL)
                
                # 初始化 schema_version
                cursor.execute("SELECT value FROM meta WHERE key = 'schema_version'")
                row = cursor.fetchone()
                if not row:
                    cursor.execute(
                        "INSERT INTO meta (key, value) VALUES ('schema_version', ?)", 
                        (str(CURRENT_SCHEMA_VERSION),)
                    )
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    @contextmanager
    def transaction(self):
        """
        提供事务安全的上下文管理器。
        正常结束自动 commit，发生异常自动 rollback。
        """
        conn = self._get_connection()
        try:
            yield conn.cursor()
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库事务异常回滚: {e}")
            raise

    def execute(self, sql: str, params: tuple = ()) -> int:
        """
        执行写操作 (INSERT/UPDATE/DELETE)。
        强制使用参数化查询防御 SQL 注入。
        返回受影响的行数。
        """
        with self.transaction() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """获取单条记录，并转换为 Python 字典返回"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"数据库 fetch_one 异常: {e}")
            return None

    def fetch_all(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """获取所有匹配记录，返回字典列表"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"数据库 fetch_all 异常: {e}")
            return []

    def close(self):
        """关闭当前线程连接。常在线程退出或销毁对象时显式调用"""
        if hasattr(self._local, "conn"):
            try:
                self._local.conn.close()
            except Exception:
                pass
            del self._local.conn
