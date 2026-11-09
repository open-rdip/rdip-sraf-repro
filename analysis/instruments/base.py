"""Common shape every FAIR-style instrument is reduced to before auditing.

Why this exists
---------------
N1 audited one instrument (FAIR-R) and the analysis was written against that
instrument's own output shape: a 100-point budget, three graded levels, and a
`recommendations` list that records gaps rather than scores. N2 asks the same
question of F-UJI, howfairis and the ML Reproducibility Checklist, none of
which share any of that. F-UJI has 17 metrics and no 100-point budget,
howfairis has 5 binary checks, the checklist is scored by hand.

So the instrument-specific part is reduced to this dataclass, and everything
downstream (variance audit, Firth regression, cross-validated AUC) works on
the dataclass alone.

The one statistic that does NOT survive the reduction is "percentage of the
point budget that is invariant". Only a weighted instrument has a budget. The
comparable statistic across instruments is the *proportion of criteria* with
zero observed variance, which is why `InstrumentFrame.weighted` exists: the
reporter prints the point-weighted figure for instruments that have one and
suppresses it for the rest rather than inventing a denominator.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class InstrumentFrame:
    """One instrument scored over one corpus.

    name        short slug used in filenames and tables
    criteria    ordered criterion labels
    dim_of      criterion -> dimension (or group); may be the instrument name
    scores      one row per study. Index is study_id. For each criterion c:
                  `crit::c`  numeric earned value (points, or 0/1)
                  `lvl::c`   level label; graded instruments use
                             absent/partial/full, binary ones pass/fail
    max_points  criterion -> maximum achievable; empty when unweighted
    aggregate   column name in `scores` holding the instrument's own total,
                or None when the instrument does not define one
    baseline    criterion to report as a single-feature baseline, or None
    """

    name: str
    criteria: list[str]
    dim_of: dict[str, str]
    scores: pd.DataFrame
    max_points: dict[str, float] = field(default_factory=dict)
    aggregate: str | None = None
    baseline: str | None = None

    @property
    def weighted(self) -> bool:
        """True when the instrument carries a real point budget."""
        return bool(self.max_points) and len(set(self.max_points.values())) > 1

    @property
    def n(self) -> int:
        return len(self.scores)

    def crit_cols(self) -> list[str]:
        return [f"crit::{c}" for c in self.criteria]

    def validate(self) -> None:
        missing = [c for c in self.criteria
                   if f"crit::{c}" not in self.scores.columns
                   or f"lvl::{c}" not in self.scores.columns]
        if missing:
            raise ValueError(f"{self.name}: criteria missing score columns: {missing}")
        if self.aggregate and self.aggregate not in self.scores.columns:
            raise ValueError(f"{self.name}: aggregate column "
                             f"{self.aggregate!r} not in scores")
        if self.baseline and self.baseline not in self.criteria:
            raise ValueError(f"{self.name}: baseline {self.baseline!r} "
                             "is not one of the criteria")
        if self.scores.index.name != "study_id":
            raise ValueError(f"{self.name}: scores must be indexed by study_id")
