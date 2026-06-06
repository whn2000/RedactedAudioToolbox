"""
RedactedSession - 统一 API 会话管理

从 elitetmhelper2.py 中提取，职责是管理所有站点(Gazelle)的 HTTP 会话、
身份认证、请求限速和 API 调用。

使用示例:
    session = RedactedSession(api_key="...", site_config=SITE_CONFIGS["RED"])
    data = session.get_api({"action": "index"}).json()
"""
import time
import requests
from errors import APIError, RateLimitError, AuthError


class RedactedSession(requests.Session):
    """带限速和认证的 requests.Session 子类。"""

    def __init__(self, api_key: str = "", site_config: dict = None,
                 request_interval: float = 3.0, timeout: int = 15,
                 show_api_times: bool = False):
        super().__init__()
        self.last_request_time = 0.0
        self.request_interval = request_interval
        self.timeout = timeout
        self.show_api_times = show_api_times
        self.site_config = site_config or {}
        self.api_key = api_key

        if api_key:
            self._apply_auth()

    # ── 工厂方法 ──────────────────────────────────────────────

    @classmethod
    def from_options(cls, options) -> "RedactedSession":
        """从 SimpleNamespace/options 对象创建会话。"""
        site_config = getattr(options, 'site_config', {})
        session = cls(
            api_key=options.api_key,
            site_config=site_config,
            request_interval=getattr(options, 'request_interval', 3.0),
            timeout=15,
            show_api_times=getattr(options, 'show_api_times', False),
        )
        session._apply_headers(options)
        return session

    # ── 认证 ──────────────────────────────────────────────────

    def _apply_auth(self):
        """根据 site_config 的 auth_type 设置认证头。"""
        site_config = self.site_config
        auth_type = site_config.get("auth_type", "api_key")
        auth_key = self.api_key

        if auth_type == "cookie":
            if "=" not in auth_key:
                auth_key = (
                    f"PHPSESSID={auth_key}"
                    if site_config.get("source") == "JPS"
                    else f"session={auth_key}"
                )
            self.headers['Cookie'] = auth_key
        else:
            if site_config.get("source") == "OPS" and not auth_key.startswith("token "):
                auth_key = f"token {auth_key}"
            self.headers['Authorization'] = auth_key

    def _apply_headers(self, options):
        """设置 User-Agent 等通用请求头。"""
        self.headers.update({
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip,deflate,sdch',
            'Accept-Language': 'en-US,en;q=0.8'
        })
        # 重新应用认证（因为上面的 update 会覆盖 Authorization）
        self._apply_auth()

    # ── 限速 ──────────────────────────────────────────────────

    def wait(self):
        """等待至满足请求间隔要求。"""
        now = time.monotonic()
        elapsed = now - self.last_request_time
        if self.show_api_times:
            print(f" {round(elapsed, 2)} ", end="")
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        self.last_request_time = time.monotonic()

    def get(self, *args, **kwargs):
        self.wait()
        kwargs.setdefault('timeout', self.timeout)
        return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.wait()
        kwargs.setdefault('timeout', self.timeout)
        return super().post(*args, **kwargs)

    # ── API 调用 ──────────────────────────────────────────────

    def get_api(self, params: dict) -> requests.Response:
        """调用站点 JSON API，自动重试 5 次（遇到限流时）。"""
        api_url = self.site_config.get(
            "api_url", "https://redacted.sh/ajax.php"
        )
        retries = 5
        for attempt in range(retries):
            res = self.get(api_url, params=params)
            try:
                data = res.json()
            except Exception:
                return res

            if data.get("status") != "success" and data.get("error") == "Rate limit exceeded":
                print(f"\n\u26a0\ufe0f API rate limited, retrying in 10s ({attempt + 1}/{retries})...")
                time.sleep(10)
                continue

            return res
        return res

    def download_torrent(self, torrent_id: int, use_token: bool = False) -> requests.Response:
        """下载种子文件。"""
        site_config = self.site_config
        api_url = site_config.get("api_url", "https://redacted.sh/ajax.php")

        if site_config.get("source") in ["DIC", "JPS"]:
            base_url = site_config.get("base_url", api_url.replace("/ajax.php", ""))
            dl_url = f"{base_url}/torrents.php?action=download&id={torrent_id}"
        else:
            dl_url = f"{api_url}?action=download&id={torrent_id}"

        if use_token:
            dl_url += "&usetoken=1"

        return self.get(dl_url)

    def get_upload_url(self) -> str:
        """获取上传 API 端点。"""
        api_url = self.site_config.get("api_url", "https://redacted.sh/ajax.php")
        return f"{api_url}?action=upload"
