"""
Feature caching system.

Provides SHA1-based caching of AudioFeatures to avoid redundant
re-computation. Cached features are stored as JSON files with
automatic TTL-based expiration.
"""

from quality.cache.feature_cache import FeatureCache

__all__ = ["FeatureCache"]
