import json
from pathlib import Path
from typing import Any, Optional
from .context import AppContext

class LegacyBridge:
    """
    旧系统平滑过渡桥梁 (Compatibility Bridge)。
    目的：让现有的业务逻辑（那些还在使用 open('config.json') 或 open('cookies.txt') 的代码）
    最小成本地迁移到 Runtime Core。
    机制：优先从新核心 (AppContext) 获取；若不存在则后备读取旧文件，读取成功后【自动静默迁移】到新核心，
    并且遵循要求【绝不立即删除旧文件】以保证随时能够回退和查错。
    """
    def __init__(self, ctx: AppContext, root_dir: str = "."):
        self.ctx = ctx
        self.root_dir = Path(root_dir)
        self.logger = ctx.logger.getChild("LegacyBridge")

    def get_config(self, new_key_path: str, old_json_key: str, default: Any = None) -> Any:
        """
        桥接获取配置。
        业务代码原先: val = json.load("config.json").get("max_size", 100)
        替换为: val = bridge.get_config("audio.max_size", "max_size", 100)
        """
        # 1. 尝试从新核心读取，若有值则直接返回
        val = self.ctx.config.get(new_key_path)
        if val is not None:
            return val
            
        # 2. 如果新核心中不存在，触发 Fallback，去旧文件中寻找
        old_config = self.root_dir / "config.json"
        if old_config.exists():
            try:
                with open(old_config, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if old_json_key in data:
                    old_val = data[old_json_key]
                    self.logger.info(f"[自动迁移] 发现旧版配置 [{old_json_key}]={old_val}，正在转移至新架构 YAML: [{new_key_path}]...")
                    self.ctx.config.set(new_key_path, old_val)
                    return old_val
            except Exception as e:
                self.logger.debug(f"Fallback 读取旧版 config.json 失败: {e}")
                
        # 3. 终极默认值
        return default

    def get_cookie(self, site_name: str) -> Optional[str]:
        """
        桥接获取敏感 Cookie。
        """
        secret_key = f"{site_name}_cookie"
        
        # 1. 优先加密保险箱
        val = self.ctx.secrets.get_secret(secret_key)
        if val:
            return val
            
        # 2. Fallback 明文旧文件
        old_cookie = self.root_dir / "cookies.txt"
        if old_cookie.exists():
            try:
                with open(old_cookie, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    self.logger.warning(f"[安全升级] 检测到明文 cookies.txt，为了您的安全，正在将其移送至加密保险箱中 (原文件保留不变)。")
                    self.ctx.secrets.set_secret(secret_key, content)
                    return content
            except Exception as e:
                self.logger.debug(f"Fallback 读取 cookies.txt 失败: {e}")
                
        return None
        
    def get_pipeline_state(self, task_id: str) -> dict:
        """
        桥接任务状态读取。
        将基于 JSON 散落文件的记录迁移到 SQLite。
        """
        # 1. 新核心 DB 查询
        row = self.ctx.db.fetch_one("SELECT status, progress FROM jobs WHERE job_id = ?", (task_id,))
        if row:
            return dict(row)
            
        # 2. Fallback 旧缓存文件
        old_cache = self.root_dir / "pipeline_cache.json"
        if old_cache.exists():
            try:
                with open(old_cache, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if task_id in data:
                    val = data[task_id]
                    status = val.get("status", "unknown")
                    progress = val.get("progress", 0.0)
                    
                    self.logger.info(f"[自动迁移] 发现旧版任务状态 [{task_id}]={status}，正在入库 SQLite...")
                    self.ctx.db.execute(
                        "INSERT OR IGNORE INTO jobs (job_id, type, status, progress) VALUES (?, ?, ?, ?)",
                        (task_id, "legacy_pipeline", status, progress)
                    )
                    return val
            except Exception as e:
                self.logger.debug(f"Fallback 读取 pipeline_cache.json 失败: {e}")
                
        return {}
