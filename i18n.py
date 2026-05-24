import json
import os

CURRENT_LANG = "zh_CN"
OBSERVERS = []

def set_language(lang):
    global CURRENT_LANG
    if lang in ["zh_CN", "en_US"]:
        CURRENT_LANG = lang
        for observer in OBSERVERS:
            observer()

def subscribe_lang_change(callback):
    if callback not in OBSERVERS:
        OBSERVERS.append(callback)

def unsubscribe_lang_change(callback):
    if callback in OBSERVERS:
        OBSERVERS.remove(callback)

TRANSLATIONS = {
    "zh_CN": {
        "title": "Redacted Audio Toolbox - 三合一音乐工具箱",
        "tab_search": "🔍 Redacted 种子搜索与下载",
        "tab_downsample": "💽 FLAC 降频与制种",
        "tab_check": "🎵 频谱检测与真假无损验证",
        "view": "视图",
        "language": "Language / 语言",
        "small_window": "小窗口 (800x600)",
        "medium_window": "中窗口 (1024x768)",
        "large_window": "大窗口 (1280x900)",
        "huge_window": "超大窗口 (1600x1200)",
        "fit_screen": "自适应屏幕 (占全屏80%)",
        
        "core_config": "核心配置",
        "api_key": "API Key:",
        "media": "媒介:",
        "order_by": "排序方式:",
        "start_year": "起始年份:",
        "end_year": "截止年份:",
        "target_count": "目标数量:",
        "max_size_mb": "最大体积 (MB):",
        "req_interval": "请求间隔 (秒):",
        "save_path": "保存路径:",
        "browse": "浏览...",
        "advanced_filters": "高级过滤选项",
        "nyp_only": "仅限 Bandcamp (NYP Only)",
        "ignore_lossy": "忽略 Lossy 批准",
        "ignore_16bit": "忽略包含 16bit 的组",
        "ignore_trumpable": "忽略 Trumpable",
        "excl_0_snatches": "排除 0 完成数(Snatched)",
        "auto_dl_torrent": "自动下载种子",
        "buffer_limit_gb": "保护 Buffer (GB):",
        "formula": "公式:",
        "auto_use_fl_token": "自动使用 FL Token",
        "token_threshold_mb": "Token 大小阈值 (MB):",
        "release_type": "发行类型筛选",
        "album": "Album (专辑)",
        "ep": "EP",
        "single": "Single (单曲)",
        "auto_pipeline": "自动化工作流与 qBittorrent",
        "enable_pipeline": "启用完整流水线 (下载->降频->检查->尝试上传)",
        "qb_host": "qB Host:",
        "qb_port": "qB Port:",
        "qb_user": "qB User:",
        "qb_pass": "qB Pass:",
        "start_search": "▶ 开始搜索",
        "stop_search": "⏹ 停止搜索",
        "run_logs": "运行日志",
        
        "config": "配置项",
        "album_dir": "专辑主文件夹:",
        "tracker_url": "Tracker URL:",
        "source_flag": "Source 标识:",
        "start_downsample": "▶ 开始降频与制种",
        
        "start_check": "▶ 开始无损检测",
        "select_files": "选择文件",
        "select_dir": "选择目录",
        "clear_list": "清空列表",
        "start_analysis": "▶ 开始分析",
        "stop_analysis": "⏹ 停止",
        "status_wait": "等待...",
        "status_done": "完成",
        "status_fail": "失败",
        "file_list": "待检测文件列表",
        "file_path": "文件路径",
        "file_status": "状态"
    },
    "en_US": {
        "title": "Redacted Audio Toolbox - 3-in-1 Toolkit",
        "tab_search": "🔍 Redacted Search & DL",
        "tab_downsample": "💽 FLAC Downsampler",
        "tab_check": "🎵 Lossless Checker",
        "view": "View",
        "language": "Language / 语言",
        "small_window": "Small Window (800x600)",
        "medium_window": "Medium Window (1024x768)",
        "large_window": "Large Window (1280x900)",
        "huge_window": "Huge Window (1600x1200)",
        "fit_screen": "Auto Fit Screen (80%)",
        
        "core_config": "Core Config",
        "api_key": "API Key:",
        "media": "Media:",
        "order_by": "Order By:",
        "start_year": "Start Year:",
        "end_year": "End Year:",
        "target_count": "Target Count:",
        "max_size_mb": "Max Size (MB):",
        "req_interval": "Req Interval (s):",
        "save_path": "Save Path:",
        "browse": "Browse...",
        "advanced_filters": "Advanced Filters",
        "nyp_only": "Bandcamp (NYP Only)",
        "ignore_lossy": "Ignore Lossy Approved",
        "ignore_16bit": "Ignore 16bit Groups",
        "ignore_trumpable": "Ignore Trumpable",
        "excl_0_snatches": "Excl 0 Snatches",
        "auto_dl_torrent": "Auto DL Torrent",
        "buffer_limit_gb": "Protect Buffer (GB):",
        "formula": "Formula:",
        "auto_use_fl_token": "Auto use FL Token",
        "token_threshold_mb": "Token Threshold (MB):",
        "release_type": "Release Type Filter",
        "album": "Album",
        "ep": "EP",
        "single": "Single",
        "auto_pipeline": "Auto Pipeline & qBittorrent",
        "enable_pipeline": "Enable Pipeline (DL->Downsample->Check->Upload)",
        "qb_host": "qB Host:",
        "qb_port": "qB Port:",
        "qb_user": "qB User:",
        "qb_pass": "qB Pass:",
        "start_search": "▶ Start Search",
        "stop_search": "⏹ Stop Search",
        "run_logs": "Run Logs",
        
        "config": "Configuration",
        "album_dir": "Album Dir:",
        "tracker_url": "Tracker URL:",
        "source_flag": "Source Flag:",
        "start_downsample": "▶ Start Downsample & Torrent",
        
        "start_check": "▶ Start Lossless Check",
        "select_files": "Select Files",
        "select_dir": "Select Directory",
        "clear_list": "Clear List",
        "start_analysis": "▶ Start Analysis",
        "stop_analysis": "⏹ Stop",
        "status_wait": "Waiting...",
        "status_done": "Done",
        "status_fail": "Fail",
        "file_list": "Pending File List",
        "file_path": "File Path",
        "file_status": "Status"
    }
}

def _(key):
    return TRANSLATIONS.get(CURRENT_LANG, TRANSLATIONS["en_US"]).get(key, key)
