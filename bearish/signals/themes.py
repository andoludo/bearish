"""Investment themes tracked by the early-winner signals.

A theme is a set of exact phrases searched in SEC filings (EDGAR full-text
search) and, for research-driven themes, in arXiv abstracts. Phrases are
deliberately specific: a broad word such as "AI" matches boilerplate risk
factors in thousands of filings and would measure nothing.
"""

from typing import Dict, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


class Theme(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    label: str
    phrases: Tuple[str, ...] = Field(description="Exact phrases; a filing matches if it contains any of them")
    arxiv_phrases: Tuple[str, ...] = Field(default=(), description="Phrases searched in arXiv abstracts; empty = skip")
    sic_codes: Tuple[str, ...] = Field(default=(), description="SEC SIC codes of the industries most exposed")
    sectors: Tuple[str, ...] = Field(default=(), description="GICS-like sectors most exposed")
    ai_related: bool = Field(default=False, description="Exposed to hyperscaler AI capex")

    def edgar_query(self) -> str:
        return " OR ".join(f'"{phrase}"' for phrase in self.phrases)

    def arxiv_query(self) -> Optional[str]:
        if not self.arxiv_phrases:
            return None
        return " OR ".join(f'abs:"{phrase}"' for phrase in self.arxiv_phrases)


_THEMES: Tuple[Theme, ...] = (
    Theme(
        key="ai_accelerator",
        label="AI accelerators and GPUs",
        phrases=("AI accelerator", "AI accelerators", "GPU", "GPUs", "inference chip", "inference chips"),
        arxiv_phrases=("AI accelerator", "inference accelerator"),
        sic_codes=("3674",),
        sectors=("Information Technology",),
        ai_related=True,
    ),
    Theme(
        key="hbm",
        label="High-bandwidth memory",
        phrases=("high-bandwidth memory", "high bandwidth memory", "HBM3", "HBM3E", "HBM4"),
        arxiv_phrases=("high-bandwidth memory",),
        sic_codes=("3674",),
        sectors=("Information Technology",),
        ai_related=True,
    ),
    Theme(
        key="ai_datacenter",
        label="AI data-centre build-out (power, cooling, networking)",
        phrases=("AI data center", "AI data centers", "AI infrastructure", "liquid cooling", "AI factories"),
        sectors=("Industrials", "Utilities", "Information Technology", "Real Estate"),
        ai_related=True,
    ),
    Theme(
        key="photonics",
        label="Silicon photonics and optical interconnect",
        phrases=("silicon photonics", "co-packaged optics", "optical interconnect", "800G"),
        arxiv_phrases=("silicon photonics", "co-packaged optics"),
        sic_codes=("3674", "3661", "3357"),
        sectors=("Information Technology",),
        ai_related=True,
    ),
    Theme(
        key="glp1",
        label="GLP-1 obesity and diabetes drugs",
        phrases=("GLP-1", "semaglutide", "tirzepatide", "incretin"),
        arxiv_phrases=(),
        sic_codes=("2834", "2836"),
        sectors=("Health Care",),
    ),
    Theme(
        key="quantum",
        label="Quantum computing",
        phrases=("quantum computing", "quantum computer", "qubit", "qubits"),
        arxiv_phrases=("quantum computing", "quantum computer"),
        sectors=("Information Technology",),
    ),
    Theme(
        key="nuclear_smr",
        label="Small modular reactors and new nuclear",
        phrases=("small modular reactor", "small modular reactors", "advanced nuclear", "microreactor"),
        arxiv_phrases=("small modular reactor",),
        sectors=("Utilities", "Industrials", "Energy"),
    ),
    Theme(
        key="robotics_humanoid",
        label="Humanoid and general-purpose robots",
        phrases=("humanoid robot", "humanoid robots", "embodied AI", "general-purpose robot"),
        arxiv_phrases=("humanoid robot", "embodied AI"),
        sectors=("Industrials", "Information Technology", "Consumer Discretionary"),
    ),
    Theme(
        key="space_launch",
        label="Commercial space launch and satellites",
        phrases=("launch vehicle", "satellite constellation", "low Earth orbit", "space launch"),
        sectors=("Industrials", "Communication Services"),
    ),
    Theme(
        key="cybersecurity_ai",
        label="AI-driven cybersecurity",
        phrases=("AI-powered security", "AI-driven security", "agentic security", "AI security operations"),
        sectors=("Information Technology",),
    ),
    Theme(
        key="ev_battery_solid_state",
        label="Solid-state batteries",
        phrases=("solid-state battery", "solid-state batteries", "solid state battery", "lithium-metal battery"),
        arxiv_phrases=("solid-state battery", "solid-state electrolyte"),
        sectors=("Consumer Discretionary", "Industrials", "Materials"),
    ),
    Theme(
        key="drones_defense",
        label="Drones and counter-drone defence",
        phrases=("unmanned aerial", "counter-drone", "counter-UAS", "loitering munition"),
        sectors=("Industrials",),
    ),
)

THEMES: Dict[str, Theme] = {theme.key: theme for theme in _THEMES}

AI_THEMES: Tuple[str, ...] = tuple(theme.key for theme in _THEMES if theme.ai_related)


def theme_signal(theme_key: str) -> str:
    """TickerSignal name for a theme's per-company filing mentions."""
    return f"THEME_MENTIONS:{theme_key}"


def themes_by_key(keys: Optional[Tuple[str, ...]] = None) -> Tuple[Theme, ...]:
    if not keys:
        return _THEMES
    unknown = [key for key in keys if key not in THEMES]
    if unknown:
        raise ValueError(f"Unknown themes {unknown}; known: {sorted(THEMES)}")
    return tuple(THEMES[key] for key in keys)
