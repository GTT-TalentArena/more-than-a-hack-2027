from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Physical scales and evidence budgets, fixed before any real-data execution.
    control_radius_m: float = 2.0
    separation_m: float = 1.5
    fast_ball_mps: float = 9.0
    max_ball_mps: float = 55.0
    interpolation_s: float = 0.24
    outside_margin_m: float = 0.35
    # v1 (Claude): a ball last seen this far beyond a line has unambiguously left the pitch
    # (ball radius 0.11 m plus tracking noise), even if it was seen for only one frame.
    clear_out_m: float = 1.0
    # v2 (Claude): in this tracking the ball is almost never missing for a short while
    # (< 0.2 min of gaps under 5 s in the whole match) but often for long stretches, whose
    # number and total length match a match's stoppages. A restart takes ~5-10 s for a quick
    # throw-in and more than 10 s for free kicks, goal kicks and corners.
    medium_gap_s: float = 5.0
    long_gap_s: float = 10.0
    team_evidence: float = 4.0
    tag_evidence: float = 0.55
    team_switch_cost: float = 0.65
    dead_switch_cost: float = 0.9
    restart_search_s: float = 2.0
    stop_lookback_s: float = 45.0


CONFIG = Config()
