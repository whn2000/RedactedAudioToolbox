"""
站点配置常量

从 elitetmhelper2.py 中提取，包含所有站点的 API 配置、
搜索拆分策略所需常量（流派标签、排序组合、媒体类型等）。
"""


# ==========================================
# 站点配置
# ==========================================

SITE_CONFIGS = {
    "RED": {
        "name": "RED (Redacted)",
        "api_url": "https://redacted.sh/ajax.php",
        "base_url": "https://redacted.sh",
        "tracker_url": "https://flacsfor.me/announce",
        "source": "RED",
        "max_pages": 20,
        "enable_tag_split": True,
        "auth_type": "api_key",
    },
    "OPS": {
        "name": "OPS (Orpheus)",
        "api_url": "https://orpheus.network/ajax.php",
        "base_url": "https://orpheus.network",
        "tracker_url": "https://home.opsfet.ch/announce",
        "source": "OPS",
        "max_pages": 20,
        "enable_tag_split": True,
        "auth_type": "api_key",
    },
    "JPS": {
        "name": "JPS (JPopsuki)",
        "api_url": "https://jpopsuki.eu/ajax.php",
        "base_url": "https://jpopsuki.eu",
        "tracker_url": "https://jpopsuki.eu/announce",
        "source": "JPS",
        "max_pages": 20,
        "enable_tag_split": False,
        "auth_type": "cookie",
    },
    "DIC": {
        "name": "DIC (DicMusic)",
        "api_url": "https://dicmusic.com/ajax.php",
        "base_url": "https://dicmusic.com",
        "tracker_url": "https://dicmusic.com/announce",
        "source": "DIC",
        "max_pages": 20,
        "enable_tag_split": False,
        "auth_type": "cookie",
    },
}

# ==========================================
# 搜索拆分策略常量
# ==========================================

# 流派标签 - 用于 Layer 3 拆分 (仅 RED)
GENRE_TAGS = [
    'rock', 'electronic', 'pop', 'hip.hop', 'jazz', 'classical',
    'folk', 'metal', 'soul', 'r.and.b', 'country', 'blues',
    'ambient', 'experimental', 'punk', 'funk', 'world',
    'drum.and.bass', 'house', 'techno', 'indie',
]

# 多排序组合 - 用于 Layer 4 拆分
ORDER_COMBOS = [
    ('time', 'desc'),
    ('time', 'asc'),
    ('size', 'desc'),
    ('size', 'asc'),
    ('seeders', 'desc'),
    ('snatched', 'desc'),
]

# 完整 media 列表 - 用于 Layer 2 拆分
MEDIA_TYPES = ['CD', 'WEB', 'Vinyl', 'SACD', 'Cassette', 'Blu-Ray', 'DVD', 'Soundboard', 'DAT', 'Other']

# ==========================================
# 核心业务逻辑 (基于原脚本优化)
# ==========================================

class Color:
    # GUI 中其实用不到颜色代码，但为了兼容原脚本的打印逻辑予以保留
    PURPLE = ''
    CYAN = ''
    DARKCYAN = ''
    BLUE = ''
    GREEN = ''
    YELLOW = ''
    RED = ''
    GREY = ''
    BOLD = ''
    UNDERLINE = ''
    END = ''
