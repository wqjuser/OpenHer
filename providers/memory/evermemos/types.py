from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionContext:
    """
    Per-session context pulled from EverMemOS at session start.
    Cached locally to avoid repeated API calls within the same session.
    """

    user_profile: str
    episode_summary: str
    foresight_text: str
    interaction_count: int
    has_history: bool
    relationship_depth: float
    pending_foresight: float
    _fact_count: int = field(default=0, repr=False)
    _profile_count: int = field(default=0, repr=False)
    _episode_count: int = field(default=0, repr=False)
    _foresight_count: int = field(default=0, repr=False)
