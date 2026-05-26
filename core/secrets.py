import os
import json
from typing import Optional
import keyring
from keyring.backends.fail import Keyring as FailKeyring
try:
    from keyring.backends.chroot import Keyring as ChrootKeyring
except ImportError:
    ChrootKeyring = type('DummyChrootKeyring', (), {})
from cryptography.fernet import Fernet

from .paths import app_paths
from .logger import get_logger

logger = get_logger(__name__)
SERVICE_NAME = "RedactedAudioToolbox"

class SecretsManager:
    """
    敏感信息管理器。
    负责存储 RED cookie、API token、passkey 等高敏数据。
    自动检测 OS keyring（凭证管理器）是否可用，若不可用（如 NAS, Docker），
    则平滑回退至使用 cryptography 进行对称加密的 JSON 存储方案。
    """
    def __init__(self):
        self.use_fallback = self._check_fallback_needed()
        if self.use_fallback:
            self._init_fallback()

    def _check_fallback_needed(self) -> bool:
        """检查当前环境是否需要退化为 Fallback"""
        kr = keyring.get_keyring()
        
        # 1. 拦截已知的无效 Backend
        if isinstance(kr, (FailKeyring, ChrootKeyring)):
            logger.warning("未检测到有效的系统 Keyring 后端。准备启用 Fallback 模式...")
            return True
        
        # 2. 实际读写测试（很多 Linux 带有 dummy keyring 但不可写）
        try:
            keyring.set_password(SERVICE_NAME, "test_check", "test_value")
            keyring.delete_password(SERVICE_NAME, "test_check")
            return False
        except Exception as e:
            logger.warning(f"系统 Keyring 测试失败 ({e})。准备启用 Fallback 模式...")
            return True

    def _init_fallback(self):
        """初始化基于 Fernet 加密的 Fallback 机制"""
        self.fallback_file = app_paths.config_dir / "encrypted_secrets.json"
        
        master_key = os.environ.get("REDTOOLBOX_MASTER_KEY")
        if not master_key:
            # 严格禁止使用机器特征，以保证迁移性。我们在此生成安全的随机主密码。
            master_key_bytes = Fernet.generate_key()
            master_key = master_key_bytes.decode('utf-8')
            logger.warning(
                "\n======================================================\n"
                "无界面/NAS环境警告：未提供环境变量 REDTOOLBOX_MASTER_KEY\n"
                "系统已自动为您生成一个新的加密主密钥：\n\n"
                f"{master_key}\n\n"
                "重要: 请务必保存此密钥！\n"
                "您必须在下一次启动时通过配置环境变量 REDTOOLBOX_MASTER_KEY 注入此值，\n"
                "否则您将永远无法解密保存的 cookie 与敏感配置！\n"
                "======================================================"
            )
        
        try:
            self.fernet = Fernet(master_key.encode('utf-8'))
        except ValueError as e:
            logger.error(f"提供的 REDTOOLBOX_MASTER_KEY 格式不正确: {e}")
            raise

        if not self.fallback_file.exists():
            self._write_fallback({})

    def _read_fallback(self) -> dict:
        if not self.fallback_file.exists():
            return {}
        try:
            with open(self.fallback_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except Exception as e:
            logger.error(f"读取 fallback secrets 失败: {e}")
            return {}

    def _write_fallback(self, data: dict):
        try:
            with open(self.fallback_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"写入 fallback secrets 失败: {e}")

    def set_secret(self, name: str, value: str) -> bool:
        """统一写入入口（业务无需感知底层机制）"""
        if self.use_fallback:
            try:
                data = self._read_fallback()
                encrypted = self.fernet.encrypt(value.encode('utf-8')).decode('utf-8')
                data[name] = encrypted
                self._write_fallback(data)
                return True
            except Exception as e:
                logger.error(f"写入 Fallback secret 失败: {e}")
                return False
        else:
            try:
                keyring.set_password(SERVICE_NAME, name, value)
                return True
            except Exception as e:
                logger.error(f"写入 Keyring secret 失败: {e}")
                return False

    def get_secret(self, name: str) -> Optional[str]:
        """统一读取入口（业务无需感知底层机制）"""
        if self.use_fallback:
            try:
                data = self._read_fallback()
                encrypted = data.get(name)
                if not encrypted:
                    return None
                return self.fernet.decrypt(encrypted.encode('utf-8')).decode('utf-8')
            except Exception as e:
                logger.error(f"读取 Fallback secret 失败: {e}")
                return None
        else:
            try:
                return keyring.get_password(SERVICE_NAME, name)
            except Exception as e:
                logger.error(f"读取 Keyring secret 失败: {e}")
                return None

    def delete_secret(self, name: str) -> bool:
        """统一删除入口"""
        if self.use_fallback:
            try:
                data = self._read_fallback()
                if name in data:
                    del data[name]
                    self._write_fallback(data)
                return True
            except Exception as e:
                logger.error(f"删除 Fallback secret 失败: {e}")
                return False
        else:
            try:
                keyring.delete_password(SERVICE_NAME, name)
                return True
            except keyring.errors.PasswordDeleteError:
                return True # 若本来就不存在，当作成功删除
            except Exception as e:
                logger.error(f"删除 Keyring secret 失败: {e}")
                return False
