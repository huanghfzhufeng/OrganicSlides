"""
速率限制配置

Uses slowapi (backed by limits library) with client IP as key.
Falls back to a no-op decorator if slowapi is not installed.
"""

import logging

logger = logging.getLogger(__name__)

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200/minute"],
        storage_uri="memory://",
    )
    SLOWAPI_AVAILABLE = True

except ImportError:
    logger.warning("slowapi not installed — rate limiting disabled. Run: pip install slowapi")
    SLOWAPI_AVAILABLE = False

    class _NoopLimiter:
        """No-op drop-in so decorated endpoints keep working without slowapi."""
        def limit(self, _limit_value: str, **_kw):  # noqa: ANN
            def decorator(func):  # noqa: ANN
                return func
            return decorator

    limiter = _NoopLimiter()  # type: ignore[assignment]
