from __future__ import annotations

"""Config-driven adapter dispatch map (D-01, D-02).

Maps provider string -> adapter class. The worker reads llm_provider and
llm_model from app_settings per cycle (D-06 / Pitfall 6), then calls
get_adapter() to retrieve the live adapter instance.
"""

import importlib
import logging

from trumptrade.analysis.base import BaseAdapter

logger = logging.getLogger(__name__)

_PROVIDER_MAP: dict[str, str] = {
    "anthropic": "trumptrade.analysis.anthropic_adapter.AnthropicAdapter",
    "groq": "trumptrade.analysis.groq_adapter.GroqAdapter",
}


def get_adapter(provider: str, model: str) -> BaseAdapter:
    """Return an adapter instance for the given provider and model (D-01).

    Called per analysis cycle — not cached — so provider switches take effect
    immediately on the next cycle (Pitfall 6).

    Raises:
        ValueError: If provider is not in the dispatch map.
    """
    if provider not in _PROVIDER_MAP:
        raise ValueError(
            f"Unknown provider {provider!r}. "
            f"Valid providers: {list(_PROVIDER_MAP.keys())}"
        )

    class_path = _PROVIDER_MAP[provider]
    module_path, class_name = class_path.rsplit(".", 1)

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    adapter: BaseAdapter = cls(model=model)
    logger.debug("Dispatching to %s model=%s", class_name, model)
    return adapter


__all__ = ["get_adapter"]
