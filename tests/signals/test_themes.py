import pytest

from bearish.signals.themes import AI_THEMES, THEMES, theme_signal, themes_by_key


def test_theme_registry() -> None:
    assert len(THEMES) >= 12
    assert {"ai_accelerator", "hbm", "ai_datacenter", "glp1", "quantum", "photonics"} <= set(THEMES)
    assert set(AI_THEMES) == {"ai_accelerator", "hbm", "ai_datacenter", "photonics"}
    for key, theme in THEMES.items():
        assert theme.key == key
        assert theme.phrases, key


def test_queries() -> None:
    hbm = THEMES["hbm"]
    assert hbm.edgar_query().startswith('"high-bandwidth memory" OR ')
    assert hbm.arxiv_query() == 'abs:"high-bandwidth memory"'
    assert THEMES["glp1"].arxiv_query() is None
    assert theme_signal("hbm") == "THEME_MENTIONS:hbm"


def test_themes_by_key() -> None:
    assert len(themes_by_key()) == len(THEMES)
    assert [t.key for t in themes_by_key(("quantum", "hbm"))] == ["quantum", "hbm"]
    with pytest.raises(ValueError, match="Unknown themes"):
        themes_by_key(("nope",))
