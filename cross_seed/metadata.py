import requests
import urllib.parse
from typing import Dict, Optional

class MetadataFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'EliteTMHelper_CrossSeed/1.0 ( https://github.com/yourrepo/EliteTMHelper )'
        }

    def fetch_release_info(self, artist: str, album: str) -> Dict[str, str]:
        """
        Fetch missing release info from MusicBrainz.
        Returns a dict with 'year', 'recordLabel', 'catalogueNumber', 'tags', 'description'.
        """
        result = {
            'year': '',
            'recordLabel': '',
            'catalogueNumber': '',
            'tags': '',
            'description': ''
        }

        query = f'artist:"{artist}" AND release:"{album}"'
        url = f'https://musicbrainz.org/ws/2/release/?query={urllib.parse.quote(query)}&fmt=json'

        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('releases'):
                    release = data['releases'][0] # Take the first match
                    
                    if 'date' in release:
                        result['year'] = release['date'][:4]
                        
                    if 'label-info' in release and release['label-info']:
                        label_info = release['label-info'][0]
                        if 'label' in label_info:
                            result['recordLabel'] = label_info['label'].get('name', '')
                        if 'catalog-number' in label_info:
                            result['catalogueNumber'] = label_info.get('catalog-number', '')
                            
                    # To get tags and description, we might need a more detailed query or just fallback to basic info
                    # For MVP, we extract basic info.
        except Exception as e:
            print(f"Failed to fetch metadata from MusicBrainz: {e}")

        return result
