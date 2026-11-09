"""Instrument adapters for the cross-instrument variance audit (N2)."""
from __future__ import annotations

from typing import Callable

from analysis.instruments.base import InstrumentFrame


def _sraf() -> InstrumentFrame:
    from analysis.instruments.sraf import frame
    return frame()


def _howfairis() -> InstrumentFrame:
    from analysis.instruments.howfairis_fs import frame
    return frame()


# Imported lazily so a missing cache for one instrument does not stop the rest.
REGISTRY: dict[str, Callable[[], InstrumentFrame]] = {
    "sraf": _sraf,
    "howfairis": _howfairis,
}


def load(name: str) -> InstrumentFrame:
    if name not in REGISTRY:
        raise KeyError(f"unknown instrument {name!r}; have {sorted(REGISTRY)}")
    return REGISTRY[name]()
