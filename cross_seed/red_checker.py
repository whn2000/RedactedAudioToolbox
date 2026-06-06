import re
import unicodedata
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

try:
    from rapidfuzz import fuzz
except ImportError:
    print("Warning: rapidfuzz not installed. Falling back to exact matching.")
    fuzz = None

@dataclass
class RedExistenceResult:
    exists: bool = False  # True if it exists on ANY of the target sites
    red_exists: bool = False
    ops_exists: bool = False
    jps_exists: bool = False
    dic_exists: bool = False
    red_group_id: Optional[int] = None
    ops_group_id: Optional[int] = None
    jps_group_id: Optional[int] = None
    dic_group_id: Optional[int] = None

class RedChecker:
    def __init__(self, sessions: Dict[str, Any], config: dict):
        """
        :param sessions: A dictionary mapping site names (e.g., 'RED', 'OPS') to RedactedSession instances.
        """
        self.sessions = sessions
        self.fuzzy_threshold = config.get("fuzzy_threshold", 85.0)
        self.year_tolerance = config.get("year_tolerance", 1)

    def normalize_string(self, s: str) -> str:
        """规范化字符串：去除非字母数字，统一小写，移除 THE 等前缀"""
        if not s:
            return ""
        s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')
        s = s.lower()
        s = re.sub(r'\(.*?\)|\[.*?\]|\{.*?\}', '', s)
        if s.startswith('the '):
            s = s[4:]
        s = re.sub(r'[^a-z0-9]', '', s)
        return s

    def is_match(self, str1: str, str2: str) -> bool:
        norm1 = self.normalize_string(str1)
        norm2 = self.normalize_string(str2)
        
        if not norm1 or not norm2:
            return False
            
        if norm1 == norm2:
            return True
            
        if fuzz:
            score = fuzz.ratio(norm1, norm2)
            return score >= self.fuzzy_threshold
        return False

    def check_album(self, artist: str, album: str, year: Optional[int] = None, edition: Optional[str] = None, target_sites: List[str] = None) -> RedExistenceResult:
        """
        检查专辑在目标站点上是否存在
        """
        if target_sites is None:
            target_sites = ["RED"]
            
        result = RedExistenceResult()
        
        search_str = f"{artist} {album}"
        
        for site in target_sites:
            session = self.sessions.get(site)
            if not session:
                print(f"Skipping {site} check because session is not configured.")
                continue
                
            try:
                params = {
                    "action": "browse",
                    "searchstr": search_str
                }
                
                res = session.get_api(params)
                if getattr(res, 'status_code', 200) != 200:
                    print(f"{site} API error: {getattr(res, 'status_code', 'Unknown')}")
                    continue
                    
                data = res.json()
                if data.get("status") != "success":
                    print(f"{site} API returned error: {data.get('error')}")
                    continue
                    
                results = data.get("response", {}).get("results", [])
                
                site_exists = False
                site_group_id = None
                
                for group in results:
                    group_artist = group.get("artist", "")
                    group_name = group.get("groupName", "")
                    
                    if self.is_match(group_artist, artist) and self.is_match(group_name, album):
                        # Found a matching group
                        site_exists = True
                        site_group_id = group.get("groupId")
                        break
                
                if site == "RED":
                    result.red_exists = site_exists
                    result.red_group_id = site_group_id
                elif site == "OPS":
                    result.ops_exists = site_exists
                    result.ops_group_id = site_group_id
                elif site == "JPS":
                    result.jps_exists = site_exists
                    result.jps_group_id = site_group_id
                elif site == "DIC":
                    result.dic_exists = site_exists
                    result.dic_group_id = site_group_id
                    
                if site_exists:
                    result.exists = True
                    
            except Exception as e:
                print(f"{site} check failed for {artist} - {album}: {e}")
                
        return result

