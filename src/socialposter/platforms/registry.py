"""Plugin registry – discovers and manages platform plugins."""

from __future__ import annotations

from typing import Optional, Type

from socialposter.platforms.base import BasePlatform


class PlatformRegistry:
    """Central registry of all available platform plugins."""

    _plugins: dict[str, Type[BasePlatform]] = {}

    @classmethod
    def register(cls, platform_class: Type[BasePlatform]) -> Type[BasePlatform]:
        """Class decorator to register a platform plugin.

        Usage::

            @PlatformRegistry.register
            class LinkedInPlatform(BasePlatform):
                ...
        """
        # Instantiate briefly to read the name property
        instance = platform_class()
        cls._plugins[instance.name] = platform_class
        return platform_class

    @classmethod
    def get(cls, name: str) -> Optional[Type[BasePlatform]]:
        """Look up a registered platform by name."""
        return cls._plugins.get(name)

    @classmethod
    def all(cls) -> dict[str, Type[BasePlatform]]:
        """Return all registered platform classes keyed by name."""
        return dict(cls._plugins)

    @classmethod
    def names(cls) -> list[str]:
        """Return sorted list of registered platform names."""
        return sorted(cls._plugins.keys())

    @classmethod
    def create(cls, name: str) -> BasePlatform:
        """Instantiate and return a platform plugin by name."""
        platform_cls = cls._plugins.get(name)
        if platform_cls is None:
            raise ValueError(
                f"Unknown platform: '{name}'. "
                f"Available: {', '.join(cls.names())}"
            )
        return platform_cls()
