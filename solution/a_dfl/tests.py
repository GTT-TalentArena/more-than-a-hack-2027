"""Self-tests for the variant. Synthetic data only -- nothing here opens match files of any game.

    python -m solution.a_dfl.tests            # quick: parity, fit, guards, shipped model
    python -m solution.a_dfl.tests --full     # + train on one synthetic match, run on another

Exit code 0 if everything passed.
"""

import os
import shutil
import sys
import tempfile

import numpy as np

import games
from evaluation import possession_metrics as pm
from heldout.run import DEVELOPMENT, HELDOUT
from solution.a_opus import ballfree, pipeline, synth
from solution.a_opus.atd import HOME, AWAY

from . import model as dfl
from . import train

PITCH = tuple(games.GAMES[games.GAME]["pitch"])


def fake_half(rng, n=600):
    """A half's ctx with only what ballfree.features reads: team shapes and the attack sign."""
    shape = {}
    for team in (HOME, AWAY):
        shape[team] = {key: rng.normal(scale, 1.0, n) for key, scale in
                       (("mx", 52.0), ("sx", 12.0), ("sy", 9.0), ("vx", 0.0), ("speed", 2.0))}
        shape[team]["n"] = np.full(n, 11)
    return {"shape": shape, "attack_sign": 1}


def swapped(ctx):
    return {"shape": {HOME: ctx["shape"][AWAY], AWAY: ctx["shape"][HOME]},
            "attack_sign": -ctx["attack_sign"]}


def test_feature_parity():
    """The parity model.py assumes is the one A's feature code has: swapping the teams negates
    exactly the odd columns and leaves the others unchanged."""
    ctx = fake_half(np.random.RandomState(0))
    X, valid = ballfree.features(ctx, PITCH)
    Y, valid_swapped = ballfree.features(swapped(ctx), PITCH)
    assert np.array_equal(valid, valid_swapped) and valid.sum() > 100
    odd = np.zeros(X.shape[1], dtype=bool)
    odd[dfl.odd_columns(X.shape[1])] = True
    assert np.allclose(Y[valid][:, odd], -X[valid][:, odd])
    assert np.allclose(Y[valid][:, ~odd], X[valid][:, ~odd])
    assert odd.sum() == 30 and X.shape[1] == 42


def test_fit_has_no_side():
    """Same coefficients whichever team is called home, logit 0 on a featureless frame, and the
    rule behind the labels is learnt."""
    rng = np.random.RandomState(1)
    X = rng.normal(0, 1, (4000, 42))
    signal = X[:, dfl.odd_columns(42)] @ rng.normal(0, 1, 30)
    y = (signal + rng.normal(0, 0.5, len(X)) + 0.8) > 0         # a home bias in the labels
    flip = np.where(np.isin(np.arange(42), dfl.odd_columns(42)), -1.0, 1.0)
    model = dfl.fit(X, y, 1.0)
    mirror = dfl.fit(X * flip, ~y, 1.0)
    assert np.allclose(model["coef"], mirror["coef"]) and np.allclose(model["scale"], mirror["scale"])
    valid = np.ones(len(X), dtype=bool)
    assert dfl.logit(np.zeros((1, 42)), np.ones(1, dtype=bool), model)[0] == 0.0
    assert np.allclose(dfl.logit(X * flip, valid, model), -dfl.logit(X, valid, model))
    assert np.mean((dfl.logit(X, valid, model) > 0) == (signal > 0)) > 0.9


def test_guards():
    """A model fitted on other code is refused, so are the reserved matches, and the install
    puts A's functions back even after an error."""
    model = dfl.fit(np.random.RandomState(2).normal(0, 1, (300, 42)), np.arange(300) % 2 == 0, 1.0)
    model["a_opus_sources_sha256"] = "0" * 64
    try:
        with dfl.installed(model):
            pass
        raise AssertionError("a model trained on other feature code was accepted")
    except RuntimeError:
        pass
    original = ballfree.cross_fit, ballfree.weight_from_accuracy
    model["a_opus_sources_sha256"] = dfl.sources_sha256()
    try:
        with dfl.installed(model):
            assert ballfree.cross_fit is not original[0]
            raise KeyError("boom")
    except KeyError:
        pass
    assert (ballfree.cross_fit, ballfree.weight_from_accuracy) == original
    for match_id in HELDOUT:
        try:
            train.check_development([match_id])
            raise AssertionError("reserved match {} accepted".format(match_id))
        except SystemExit:
            pass
    train.check_development(list(DEVELOPMENT))


def test_weights_round_trip():
    model = dfl.fit(np.random.RandomState(3).normal(0, 1, (500, 42)), np.arange(500) % 3 == 0, 1.0)
    model.update({"weight": 0.7, "training": {"matches": ["X1"], "frames": 500}})
    folder = tempfile.mkdtemp()
    try:
        path = os.path.join(folder, "weights.py")
        train.write_weights(model, path)
        scope = {}
        with open(path, encoding="utf-8") as handle:
            exec(handle.read(), scope)
        assert scope["MODEL"] == model
    finally:
        shutil.rmtree(folder)


def test_shipped_model():
    """weights.py matches A's current feature code and was trained on development matches only."""
    try:
        from .weights import MODEL
    except ImportError:
        print("  no weights.py yet: skipped")
        return
    dfl.check_sources(MODEL)
    matches = set(MODEL["training"]["matches"])
    assert matches and matches <= set(DEVELOPMENT) and not matches & set(HELDOUT)
    assert MODEL["n_columns"] == 42 and MODEL["columns"] == list(dfl.odd_columns(42))
    assert len(MODEL["coef"]) == len(MODEL["scale"]) == 30 and 0.0 <= MODEL["weight"] <= 1.0


def synthetic_match(folder, seed):
    assert synth.main(["--out-dir", folder, "--seed", str(seed), "--minutes", "3"]) == 0
    return pm.label_codes(pm.read_label_csv(os.path.join(folder, "synthetic_gt.csv")))


def test_end_to_end():
    """Train the model on one synthetic match as train.py does, run the variant on another: the
    file validates, A is byte-identical before and after, and the fixed weight is the one used."""
    first, second = tempfile.mkdtemp(), tempfile.mkdtemp()
    try:
        gt = synthetic_match(first, 3)
        store = []
        train.run_pipeline(first, os.path.join(first, "a.csv"), store=store)
        X, y = train.training_rows(train.stack_halves(store, gt))
        model = dfl.fit(X, y, 1.0, weight=0.8)
        model["a_opus_sources_sha256"] = dfl.sources_sha256()

        gt = synthetic_match(second, 4)
        paths = [os.path.join(second, name) for name in ("a1.csv", "v.csv", "a2.csv")]
        pipeline.run(paths[0], second, log=lambda *a: None)
        lines, _ = train.run_pipeline(second, paths[1], model=model)
        pipeline.run(paths[2], second, log=lambda *a: None)
        contents = []
        for path in paths:
            with open(path, "rb") as handle:
                contents.append(handle.read())
        assert contents[0] == contents[2], "A changed after the variant ran in the same process"
        table = pm.read_label_csv(paths[1])
        assert pm.validate_submission(table, games.source_frames("tactical")) is None
        assert any("-> weight 0.80 / 0.80" in line for line in lines), "fixed weight not used"
        score = pm.evaluate(gt, pm.label_codes(table))["spell_f1_mean"]
        assert score > 0.3, "synthetic spellF1 suspiciously low: {:.3f}".format(score)
        print("  variant synthetic spellF1 {:.3f} (A {:.3f})".format(score, pm.evaluate(
            gt, pm.label_codes(pm.read_label_csv(paths[0])))["spell_f1_mean"]))
    finally:
        shutil.rmtree(first)
        shutil.rmtree(second)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    tests = [test_feature_parity, test_fit_has_no_side, test_guards, test_weights_round_trip,
             test_shipped_model]
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
