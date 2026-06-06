"""
elitetmhelper2.py - 兼容桥接模块

从旧的大文件中拆分后，此文件保留为向后兼容的导入桥接。
新代码应直接从 gui.search_tab / core.searcher / core.site_config / gui.widgets 导入。
"""

from core.site_config import SITE_CONFIGS, GENRE_TAGS, ORDER_COMBOS, MEDIA_TYPES, Color
from core.searcher import Cache, get_edition, FoundTorrent, search_result_iterator, perform_search
from gui.widgets import RedirectText
from gui.search_tab import AppGUI
from redacted_session import RedactedSession
from errors import APIError as RedactedAPIError
