"""Self-tests for candidate A. Synthetic data only -- nothing here opens the match files.

    python -m solution.a_opus.tests            # quick: decoder, parser, tags
    python -m solution.a_opus.tests --full     # + a short synthetic match end to end

Exit code 0 if everything passed.
"""

import itertools
import os
import shutil
import sys
import tempfile

import numpy as np

from . import atd, decode, pipeline, synth, tags
from .atd import HOME, AWAY

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
import possession_metrics as pm  # noqa: E402
import games  # noqa: E402


def valid_path(states, k):
    """Every stoppage lasts at least k frames."""
    run = 0
    for state in list(states) + [-1]:
        if state == decode.D:
            run += 1
        else:
            if 0 < run < k:
                return False
            run = 0
    return True


def test_decoder_is_exact():
    """Viterbi with minimum stoppage equals brute force on small random problems."""
    rng = np.random.RandomState(0)
    for _ in range(300):
        n, k = rng.randint(1, 9), rng.randint(1, 4)
        eh, ea, ed = rng.normal(0, 2, (3, n))
        lam = rng.uniform(0, 4, 3)
        path = decode.viterbi(eh, ea, ed, lam[0], lam[1], lam[2], k)
        assert valid_path(path, k), "decoded path violates the minimum stoppage"
        best = max(decode.path_score(np.array(c), eh, ea, ed, *lam)
                   for c in itertools.product((0, 1, 2), repeat=n) if valid_path(c, k))
        got = decode.path_score(path, eh, ea, ed, *lam)
        assert abs(got - best) < 1e-9, "decoder not optimal: {} < {}".format(got, best)


def test_decoder_ties():
    """Flights switch late, stoppages start early and end late."""
    eh = np.array([1, 1, 0, 0, 0, 0, -1, -1.])
    path = "".join("HAD"[s] for s in decode.viterbi(eh, -eh, np.full(8, -5.), 1.5, 3, 3, 2))
    assert path == "HHHHHHAA", path
    team = np.array([2, 2, 0, 0, 0, 3, 3, 3, 0, 0, 0, 0, 2, 2.])
    dead = np.array([-9, -9, 0, 0, 0, 9, 9, 9, 0, 0, 0, 0, -9, -9.])
    path = "".join("HAD"[s] for s in decode.viterbi(team / 2, -team / 2, dead + np.abs(team) / 2,
                                                    1, 1, 1, 2))
    assert path == "HHDDDDDDDDDDHH", path


def test_first_touch_dating():
    """A change moves back to where the new side reached the ball, never across a flight."""
    H, A = decode.H, decode.A
    states = np.array([H, H, H, H, H, A, A, A], dtype=np.int8)
    c_home = np.array([0.9, 0.9, 0.0, 0.2, 0.3, 0.1, 0.0, 0.0])
    c_away = np.array([0.0, 0.0, 0.0, 0.6, 0.7, 0.9, 0.9, 0.9])
    out, moved = decode.date_team_changes(states, c_home, c_away, window=25, min_control=0.3)
    assert "".join("HAD"[s] for s in out) == "HHHAAAAA" and moved == [2], (out, moved)
    # Frame 2 is a flight (nobody within reach): the change must not cross it.
    c_away2 = c_away.copy()
    c_away2[2] = 0.0
    out, _ = decode.date_team_changes(states, c_home, c_away2, window=25, min_control=0.3)
    assert out[2] == H


def one_frame_ctx(ball_v, home, away):
    """A one-frame context for control_scores: ball velocity and (distance, player velocity) of
    each side's nearest player."""
    from .evidence import control_scores  # noqa: F401  (imported where used)
    ctx = {"n": 1, "bvx": np.array([ball_v[0]]), "bvy": np.array([ball_v[1]]),
           "pvx": np.array([[home[1][0], away[1][0]]]), "pvy": np.array([[home[1][1], away[1][1]]]),
           "pspeed": np.array([[np.hypot(*home[1]), np.hypot(*away[1])]])}
    ctx["near"] = {HOME: (np.array([home[0]]), np.array([0])),
                   AWAY: (np.array([away[0]]), np.array([1]))}
    return ctx


def test_p3_control_cases():
    """#15: a pass flying past a defender is not control; a reception at the feet is."""
    from . import config
    from .evidence import control_scores
    cfg = config.build()
    scale = (cfg["team.d0"], cfg["team.sigma_d"])
    # Pass at 15 m/s brushing a defender (away, 0.5 m) who jogs at 3 m/s; passer 6 m back.
    c_home, c_away = control_scores(one_frame_ctx((15.0, 0.0), (6.0, (2.0, 0.0)),
                                                  (0.5, (0.0, 3.0))), cfg, scale)
    assert c_away[0] < 0.05, c_away
    # Reception: ball at 0.6 m from the receiver (home), moving with him.
    c_home, c_away = control_scores(one_frame_ctx((3.0, 0.0), (0.6, (2.8, 0.2)),
                                                  (4.0, (1.0, 0.0))), cfg, scale)
    assert c_home[0] > 0.9 and c_away[0] < 0.05, (c_home, c_away)
    # Duel: both at the ball with it -> nearly no net evidence for either side.
    c_home, c_away = control_scores(one_frame_ctx((2.0, 0.0), (0.7, (2.0, 0.0)),
                                                  (0.8, (2.0, 0.0))), cfg, scale)
    assert abs(c_home[0] - c_away[0]) < 0.1, (c_home, c_away)


def decode_team(team, dead=None, cfg=None):
    """Decode a sequence of team evidence with the candidate's costs (H-favoured if > 0)."""
    from . import config
    cfg = cfg or config.build()
    team = np.asarray(team, dtype=np.float64)
    dead = np.full(len(team), -0.1) if dead is None else np.asarray(dead, dtype=np.float64)
    states = decode.viterbi(0.5 * team, -0.5 * team, dead + 0.5 * np.abs(team),
                            cfg["decode.lam_ha"], cfg["decode.lam_ad"], cfg["decode.lam_da"],
                            cfg["decode.min_dead"])
    return "".join("HAD"[s] for s in states)


def runs_of(path):
    """'HHHAAH' -> [('H', 3), ('A', 2), ('H', 1)]."""
    out = []
    for c in path:
        if out and out[-1][0] == c:
            out[-1][1] += 1
        else:
            out.append([c, 1])
    return [tuple(r) for r in out]


def test_p3_p4_scenarios():
    """#15 and #16 cases with the candidate's own costs (alpha 0.4 per frame of clear control,
    1.5 per touch, lam_ha 3): what changes possession and what does not."""
    from . import config
    cfg = config.build()
    alpha, touch = cfg["team.alpha"], cfg["touch.beta"]
    hold = [alpha] * 50                                   # H in clear control, 2 s
    flight = [0.0] * 12                                   # ball in the air, nobody near
    # Interception: H passes, A gets it and keeps it -> one change, at A's first contact.
    path = decode_team(hold + flight + [-alpha] * 60)
    assert runs_of(path) == [("H", 62), ("A", 60)], runs_of(path)
    # Rebound / deflection: an A touch and two frames near the ball, then H again -> no change.
    path = decode_team(hold + [-touch - alpha, -alpha] + flight + hold)
    assert set(path) == {"H"}, runs_of(path)
    # Duel with no control afterwards: contested frames carry no net evidence -> no change.
    path = decode_team(hold + [0.0] * 40 + hold)
    assert set(path) == {"H"}, runs_of(path)
    # Isolated noise: one frame of strong A evidence inside H's possession -> no change.
    path = decode_team(hold + [-2.0] + hold)
    assert set(path) == {"H"}, runs_of(path)
    # Short real recovery: A controls for 1.2 s (30 frames) then loses it -> kept as a short
    # A possession, not filtered away by a minimum duration.
    path = decode_team(hold + [-alpha] * 30 + hold)
    assert runs_of(path) == [("H", 50), ("A", 30), ("H", 50)], runs_of(path)
    # Change across a gap in the ball track: H, 2 s with no ball, then A -> the change is
    # placed where A's evidence starts, not inside the gap.
    path = decode_team(hold + [0.0] * 50 + [-alpha] * 60)
    assert runs_of(path) == [("H", 100), ("A", 60)], runs_of(path)


def test_p4_first_frames_of_a_half():
    """#16: a half that opens with a stoppage (the 2nd-half kick-off) decodes D first; one that
    opens in play takes the side of its first evidence from frame 0."""
    from . import config
    cfg = config.build()
    alpha = cfg["team.alpha"]
    dead = [0.3] * 80 + [-0.3] * 60
    path = decode_team([0.0] * 80 + [alpha] * 60, dead=dead, cfg=cfg)
    assert runs_of(path) == [("D", 80), ("H", 60)], runs_of(path)
    path = decode_team([-alpha] * 60)
    assert path == "A" * 60, path


def test_alternative_decoders():
    """#16: hysteresis and vote return one valid state per frame and respect the obvious cases."""
    h = np.array([0.5] * 100 + [-0.5] * 100)
    for states in (decode.hysteresis(h / 2, -h / 2, np.full(200, -1.0), 3, 4, 4, 50),
                   decode.vote(h / 2, -h / 2, np.full(200, -1.0), 25)):
        assert len(states) == 200 and set(np.unique(states)) <= {0, 1, 2}
        assert states[0] == decode.H and states[-1] == decode.A


def write_tiny_atd(folder, with_spec, shorthand):
    """A 6-frame ATD with 4 slots, interleaved teams, optionally a bare 'NaN' for a slot."""
    meta = ['<main><Metadata>',
            '<Sessions><Session><MatchParameters><Score idLocalTeam="B" idVisitingTeam="A"/>'
            '</MatchParameters></Session></Sessions>',
            '<Teams><Team id="A"><Name>Athletic Club</Name></Team>'
            '<Team id="B"><Name>FC Barcelona</Name></Team></Teams><Players>']
    teams = ["A", "B", "B", "A"]
    for i, team in enumerate(teams):
        meta.append('<Player id="p{}" teamId="{}"><Name>Track {}</Name></Player>'.format(
            i, team, i + 1))
    meta.append('</Players><Devices><Device><Sensors><Sensor id="position"><Channels>'
                '<Channel id="x"><Name>position_x</Name></Channel>'
                '<Channel id="y"><Name>position_y</Name></Channel></Channels></Sensor>'
                '<Sensor id="speed"><Channels><Channel id="speed"><Name>speed</Name></Channel>'
                '</Channels></Sensor></Sensors></Device></Devices><PlayerChannels>')
    for i in range(4):
        for ch in ("x", "y", "speed"):
            meta.append('<PlayerChannel id="c{0}{1}" playerId="p{0}" channelId="{1}"/>'.format(
                i, ch))
    meta.append('</PlayerChannels></Metadata>')
    if with_spec:
        meta.append('<DataFormatSpecifications><DataFormatSpecification separator=":">'
                    '<StringRegister name="frameCount"/><SplitRegister separator=";">')
        for i in range(4):
            meta.append('<SplitRegister separator=",">' + "".join(
                '<PlayerChannelRef playerChannelId="c{}{}"/>'.format(i, ch)
                for ch in ("x", "y", "speed")) + "</SplitRegister>")
        meta.append('</SplitRegister><SplitRegister separator=",">'
                    '<BallChannelRef channelId="x"/><BallChannelRef channelId="y"/>'
                    '<BallChannelRef channelId="z"/></SplitRegister>'
                    '</DataFormatSpecification></DataFormatSpecifications>')
    meta.append("</main>")
    meta_path = os.path.join(folder, "m.xml")
    with open(meta_path, "w") as handle:
        handle.write("".join(meta))
    raw_path = os.path.join(folder, "r.txt")
    with open(raw_path, "w") as handle:
        for frame in range(1, 7):
            groups = ["0.{0}1,0.{0}2,1.5".format(i) for i in range(4)]
            if shorthand and frame == 3:
                groups[2] = "NaN"
            ball = "0.5,0.5,0.0" if frame != 4 else "NaN,NaN,NaN"
            handle.write("{}:{}:{}\n".format(frame, ";".join(groups), ball))
    return meta_path, raw_path


def test_parser_variants():
    """Layout from the spec or the fallback, NaN shorthand, home by name, interleaved teams."""
    folder = tempfile.mkdtemp()
    try:
        for with_spec, shorthand in ((True, False), (False, False), (True, True)):
            meta_path, raw_path = write_tiny_atd(folder, with_spec, shorthand)
            data = atd.load(meta_path, raw_path, 6, (100.0, 50.0))
            s = data["summary"]
            assert s["n_records"] == 6 and s["contiguous"], s
            assert s["home_rule"] == "team name" and not s["first_team_is_home"], s
            assert list(data["slot_team"]) == [AWAY, HOME, HOME, AWAY], data["slot_team"]
            assert np.allclose(data["px"][0], [1, 11, 21, 31]), data["px"][0]
            assert np.allclose(data["py"][0], [1, 6, 11, 16]), data["py"][0]
            assert np.isnan(data["bx"][3]) and data["bx"][0] == 50.0
            if shorthand:
                assert np.isnan(data["px"][2, 2]) and s["slow_lines"] > 0
            assert s["layout_source"] == ("DataFormatSpecification" if with_spec
                                          else "documented fallback"), s["layout_source"]
    finally:
        shutil.rmtree(folder)


def test_tag_sides():
    names = ("FC Barcelona", "Athletic Club")
    assert tags.side_of("Barcelona", names) == HOME
    assert tags.side_of("Atletic Club", names) == AWAY
    assert tags.side_of("N/A", names) is None
    assert tags.side_of("Barcelona", ("Home", "Away")) == HOME
    assert tags.side_of("Atletic Club", ("Home", "Away")) == AWAY


def test_end_to_end():
    """A short synthetic match through the whole pipeline; the file must validate."""
    folder = tempfile.mkdtemp()
    try:
        assert synth.main(["--out-dir", folder, "--seed", "3", "--minutes", "3"]) == 0
        out = os.path.join(folder, "pred.csv")
        pipeline.run(out, folder, log=lambda *a: None)
        table = pm.read_label_csv(out)
        n = games.source_frames("tactical")
        assert pm.validate_submission(table, n) is None
        codes = pm.label_codes(table)
        graded = np.zeros(n, dtype=bool)
        for _, first, last in games.half_video_blocks(games.GAME):
            graded[first:last + 1] = True
        assert np.all(codes[~graded] == pm.X) and not np.any(codes[graded] == pm.X)
        gt = pm.label_codes(pm.read_label_csv(os.path.join(folder, "synthetic_gt.csv")))
        score = pm.evaluate(gt, codes)["spell_f1_mean"]
        assert score > 0.3, "synthetic spellF1 suspiciously low: {:.3f}".format(score)
        print("  end-to-end synthetic spellF1 {:.3f}".format(score))
    finally:
        shutil.rmtree(folder)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    tests = [test_decoder_is_exact, test_decoder_ties, test_first_touch_dating,
             test_p3_control_cases, test_p3_p4_scenarios, test_p4_first_frames_of_a_half,
             test_alternative_decoders, test_parser_variants, test_tag_sides]
    if "--full" in argv:
        tests.append(test_end_to_end)
    failed = 0
    for test in tests:
        try:
            test()
            print("ok    {}".format(test.__name__))
        except AssertionError as error:
            failed += 1
            print("FAIL  {}: {}".format(test.__name__, error))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
