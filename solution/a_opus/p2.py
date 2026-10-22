"""P3: the P2 dead-ball detector (#14, solution/dead_ball.py) as one more dead-ball term.

P2 is run once on the whole match, exactly as Pablo validated it (its own loader, thresholds and
events), and only its local candidates are used, turned into nats:

- tagged_preparation: the ball still in a zone that fits the set piece, then sustained motion.
  D from the first still frame up to the restart, and alive just after it. This is what
  setpiece_llr cannot know: where inside the Smart Tagging window the ball is played.
- initial_kickoff_context: D before the first kick-off of each half, up to the refined restart
  (or up to the window when no restart was confirmed).
- observed_exit: the ball seen outside the pitch. Our own out/exit terms already count this, so
  its weight is 0 unless p2.exit_beta says otherwise.

Nothing here reads labels or prints frames; summary() returns counts only.
"""
import numpy as np

import games

PREPARATION, KICKOFF, EXIT = "tagged_preparation", "initial_kickoff_context", "observed_exit"


def candidates(data_dir, game=games.GAME):
    """P2's local candidates for the whole match (frames on the tactical video grid)."""
    from solution import dead_ball
    from solution.hold import make_period_id
    from starter.load_smart_tagging import load as load_events
    ball, observed, collective, counts = dead_ball.load_geometry(data_dir, game)
    periods = make_period_id(len(ball), games.half_video_blocks(game))
    _, found, summary = dead_ball.detect(
        ball, observed, periods, load_events(game, data_dir), games.GAMES[game]["fps"],
        games.GAMES[game]["pitch"], collective, counts)
    return found, summary


def p2_llr(ctx, found, cfg):
    """Dead-ball evidence in nats for one graded half [ctx first, ctx first + n)."""
    llr = np.zeros(ctx["n"])
    beta = {PREPARATION: cfg["p2.dead_beta"], KICKOFF: cfg["p2.dead_beta"],
            EXIT: cfg["p2.exit_beta"]}
    for c in found:
        weight = beta.get(c["evidence"], 0.0) * c["confidence"]
        a = max(c["start_frame"] - ctx["first"], 0)
        b = min(c["end_frame"] - ctx["first"], ctx["n"])
        if weight > 0 and b > a:
            llr[a:b] += weight
        restart = c.get("restart_frame")
        if restart is not None and c["evidence"] != EXIT:
            r = restart - ctx["first"]
            a, b = max(r, 0), min(r + cfg["p2.restart_post"], ctx["n"])
            if b > a:
                llr[a:b] -= cfg["p2.restart_beta"]
    return llr


def summary(found):
    """How many candidates of each kind, and how many with a confirmed restart."""
    kinds = {}
    for c in found:
        entry = kinds.setdefault(c["evidence"], [0, 0])
        entry[0] += 1
        entry[1] += c.get("restart_frame") is not None
    return kinds
