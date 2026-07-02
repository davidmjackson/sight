"""Shared risk + dependency vocabulary for the detector and the cross-team reconciler.

Two places look for the same thing in Sprint-15 Slack chatter: a delivery-risk phrase
co-occurring with a dependency noun. The baseline watermelon detector uses it to spot a
dependency raised in chat but missing from the RAID (`detector._find_hidden_dependency`,
moat B1/B3), and the cross-team dependency-slip reconciler uses it to decide a message is
worth reconciling (`crossteam.reconcile_cross_team`).

Keeping the vocabulary here means the two cannot drift apart. They had drifted: the
reconciler carried a stray extra keyword the detector never had, so a phrase one flagged
the other missed. This module is the single source of truth. The detector's set is the
eval-locked canonical (watermelon eval); any change here must keep that eval green.
"""

import re

# Delivery-risk phrasing. Matched case-insensitively.
RISK = re.compile(
    r"isn't ready|not ready|slipp|bite us|won't hold|blocked|building on sand", re.I
)
# Dependency nouns.
DEPENDENCY = re.compile(r"api|dependency|endpoint|service", re.I)


def mentions_risk_dependency(body: str) -> bool:
    """True if the text carries both a delivery-risk phrase and a dependency noun."""
    return bool(RISK.search(body) and DEPENDENCY.search(body))
