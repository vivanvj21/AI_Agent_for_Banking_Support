"""
Memory Engine package.

Public API — import from here::

    from memory import get_memory_manager, MemoryManager
    from memory.models import MemoryEntry, ContextPackage, MemoryType
    from memory.config import get_memory_config
"""

from memory.config import MemoryConfig, get_memory_config
from memory.manager import MemoryManager, get_memory_manager
from memory.models import (
    ContextPackage,
    MemoryEntry,
    MemoryRole,
    MemorySearchResult,
    MemoryType,
    SessionContext,
)

__all__ = [
    "ContextPackage",
    "MemoryConfig",
    "MemoryEntry",
    "MemoryManager",
    "MemoryRole",
    "MemorySearchResult",
    "MemoryType",
    "SessionContext",
    "get_memory_config",
    "get_memory_manager",
]
