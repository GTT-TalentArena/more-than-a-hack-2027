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
             test_parser_variants, test_tag_sides]
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
