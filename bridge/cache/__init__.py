"""Result caches for the Virtual Office.

Currently:
    vision_cache.VisionCache - SHA-256 cache for vision tier results.
"""

from .vision_cache import VisionCache, make_cache_key

__all__ = ["VisionCache", "make_cache_key"]
