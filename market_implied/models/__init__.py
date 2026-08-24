"""Asset-class models.

Importing this package registers every built-in model in the registry of
:mod:`market_implied.models.base`.
"""

from __future__ import annotations

from .base import (
    AssetSpec,
    ModelContext,
    ModelError,
    available_models,
    get_model,
    register,
)
from . import alternatives, bonds, credit, equity, real_assets  # noqa: F401

__all__ = [
    "AssetSpec",
    "ModelContext",
    "ModelError",
    "available_models",
    "get_model",
    "register",
]
