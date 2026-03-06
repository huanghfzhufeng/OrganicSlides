"""
Style Registry — loads and indexes all style JSON files from backend/static/styles/.

Each JSON file must have: id, name_zh, name_en, tier, colors, typography,
use_cases, sample_image_path, render_paths, base_style_prompt.
"""

import json
from pathlib import Path
from typing import Optional, Union

# Canonical style dict type alias (plain dict avoids tight coupling)
StyleDict = dict

# Default location of style JSON files
_DEFAULT_STYLES_DIR = Path(__file__).parent.parent / "static" / "styles"


class StyleRegistry:
    """
    Loads all style JSON files from a directory and provides lookup methods.
    Immutable after initialization — all returned values are new copies.
    """

    def __init__(self, styles_dir: Optional[Path] = None) -> None:
        self._dir = Path(styles_dir) if styles_dir else _DEFAULT_STYLES_DIR
        self._styles: dict[str, StyleDict] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        """Load every *.json file in the styles directory."""
        if not self._dir.exists():
            raise FileNotFoundError(
                f"Styles directory not found: {self._dir}"
            )

        loaded: dict[str, StyleDict] = {}
        for json_file in sorted(self._dir.glob("*.json")):
            try:
                with json_file.open(encoding="utf-8") as fh:
                    data: StyleDict = json.load(fh)
                style_id = data.get("id")
                if not style_id:
                    continue
                self._validate_style(data, json_file.name)
                loaded[style_id] = data
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                # Log and skip malformed files — do not crash on startup
                import logging
                logging.getLogger(__name__).warning(
                    "Skipping malformed style file %s: %s", json_file.name, exc
                )

        self._styles = loaded

    @staticmethod
    def _validate_style(data: StyleDict, filename: str) -> None:
        """Raise ValueError if required fields are missing."""
        required = {
            "id", "name_zh", "name_en", "tier",
            "colors", "typography", "use_cases",
            "sample_image_path", "render_paths", "base_style_prompt",
        }
        missing = required - set(data.keys())
        if missing:
            raise ValueError(
                f"Style file '{filename}' is missing fields: {missing}"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_style(self, style_id: str) -> Optional[StyleDict]:
        """Return a copy of the style dict for *style_id*, or None."""
        style = self._styles.get(style_id)
        return dict(style) if style else None

    def list_styles(self) -> list[StyleDict]:
        """Return copies of all styles ordered by id."""
        return [dict(s) for s in self._styles.values()]

    def list_by_tier(
        self, tier: Union[int, str]
    ) -> list[StyleDict]:
        """
        Return copies of styles whose 'tier' matches *tier*.
        *tier* can be an int (1, 2, 3) or a string ("editorial").
        """
        return [
            dict(s)
            for s in self._styles.values()
            if str(s.get("tier")) == str(tier)
        ]

    def exists(self, style_id: str) -> bool:
        """Return True if *style_id* is registered."""
        return style_id in self._styles

    @property
    def style_ids(self) -> list[str]:
        """Return a sorted list of all registered style IDs."""
        return sorted(self._styles.keys())


# ---------------------------------------------------------------------------
# Module-level singleton — created lazily so unit tests can substitute dirs
# ---------------------------------------------------------------------------

_registry: Optional[StyleRegistry] = None


def get_registry(styles_dir: Optional[Path] = None) -> StyleRegistry:
    """
    Return the module-level StyleRegistry singleton.

    Pass *styles_dir* only when you need to override the default path
    (e.g. in tests). The singleton is (re-)initialized if *styles_dir*
    differs from the current one or does not yet exist.
    """
    global _registry
    if _registry is None or styles_dir is not None:
        _registry = StyleRegistry(styles_dir)
    return _registry
