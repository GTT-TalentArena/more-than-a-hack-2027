"""Invented trajectories exercise display interpolation without match assets."""

import copy
import unittest

from tools.match_viewer.estimation import estimated_window


class Source:
    fps = 10
    pitch = (105.3, 68)
    n_frames = 100
    blocks = [(1, 0, 99)]
    teams = ['H', 'H', 'A']
    slot_ids = ['1', '2', '3']

    def __init__(self, gap=(30, 40)):
        self.rows = [{'frame': frame,
                      'players': [[10 + frame * .05, 10], [30, 30], [50, 50]],
                      'ball': None if frame % 3 == 0 else [frame * .1, 20]}
                     for frame in range(self.n_frames)]
        for frame in range(*gap):
            self.rows[frame]['players'][0] = None

    def window(self, start, count):
        return copy.deepcopy(self.rows[start:start + count])


class EstimationTests(unittest.TestCase):
    def test_interpolation_keeps_every_original_player_and_ball_untouched(self):
        source = Source()
        original = copy.deepcopy(source.rows)
        result = estimated_window(source, 0, 100)
        self.assertEqual(source.rows, original)
        for row, raw in zip(result, original):
            self.assertEqual({key: row[key] for key in raw}, raw)
            for slot, point in enumerate(row['player_estimates']):
                if point is not None:
                    self.assertIsNone(row['players'][slot])
                    self.assertAlmostEqual(point[0], 10 + row['frame'] * .05)
                    self.assertEqual(point[1], 10)
        self.assertEqual(sum(row['player_estimates'][0] is not None for row in result), 10)

    def test_exact_gap_limit_and_no_one_sided_or_half_boundary_fill(self):
        for gap, blocks, expected in [((30, 50), [(1, 0, 99)], 20),
                                      ((30, 51), [(1, 0, 99)], 6),
                                      ((0, 10), [(1, 0, 99)], 0),
                                      ((90, 100), [(1, 0, 99)], 0),
                                      ((30, 40), [(1, 0, 34), (2, 35, 99)], 0),
                                      ((30, 40), [(1, 0, 29), (2, 40, 99)], 0)]:
            with self.subTest(gap=gap, blocks=blocks):
                source = Source(gap)
                source.blocks = blocks
                result = estimated_window(source, 0, 100)
                self.assertEqual(sum(row['player_estimates'][0] is not None for row in result), expected)

    def test_request_boundaries_do_not_change_estimates(self):
        for gap in ((30, 50), (30, 80)):
            source = Source(gap)
            full = estimated_window(source, 0, 100)
            for start, count in [(0, 1), (29, 2), (30, 1), (40, 1), (49, 2), (99, 2)]:
                self.assertEqual(estimated_window(source, start, count), full[start:start + count])

    def test_long_loss_gets_only_a_brief_decelerating_fade(self):
        source = Source((30, 80))
        rows = estimated_window(source, 0, 100)
        self.assertTrue(all(row['player_estimates'][0] is not None for row in rows[30:36]))
        self.assertTrue(all(row['player_estimates'][0] is None for row in rows[36:80]))
        fades = [row['player_estimate_fade'][0] for row in rows[30:36]]
        self.assertTrue(all(0 < b < a < 1 for a, b in zip(fades, fades[1:])))
        positions = [source.rows[29]['players'][0][0]] + [row['player_estimates'][0][0] for row in rows[30:36]]
        steps = [b-a for a,b in zip(positions,positions[1:])]
        self.assertTrue(all(0 < b < a for a,b in zip(steps,steps[1:])))
        # Never continue a prediction through a half boundary or empty team.
        source.blocks = [(1, 0, 32), (2, 40, 99)]
        self.assertTrue(all(row['player_estimates'][0] is None for row in estimated_window(source, 30, 50)))
        source.blocks = [(1, 0, 99)]
        for row in source.rows[30:80]:
            row['players'][1] = None
        self.assertTrue(all(row['player_estimates'][0] is None for row in estimated_window(source, 30, 50)))

    def test_implausible_speed_unstable_anchors_and_identity_jump_are_rejected(self):
        for mutation in ('speed', 'anchor', 'continuity', 'missing-anchor'):
            source = Source()
            if mutation == 'speed':
                for frame in range(40, 100):
                    source.rows[frame]['players'][0][0] += 30
            elif mutation == 'anchor':
                source.rows[28]['players'][0][0] += 5
            elif mutation == 'continuity':
                for frame in range(40, 100):
                    source.rows[frame]['players'][0][0] += 8
            else:
                source.rows[28]['players'][0] = None
            with self.subTest(mutation=mutation):
                self.assertTrue(all(row['player_estimates'][0] is None
                                    for row in estimated_window(source, 30, 10)))

    def test_duplicates_competing_estimates_and_full_or_empty_team_are_rejected(self):
        for case in ('observed-duplicate', 'estimated-duplicate', 'full-team', 'empty-team'):
            source = Source()
            if case == 'estimated-duplicate':
                for frame, row in enumerate(source.rows):
                    row['players'][1] = None if 30 <= frame < 40 else [10 + frame * .05, 10.2]
                source.teams = ['H', 'H', 'H']  # Keep another observed home track.
            else:
                for row in source.rows[30:40]:
                    if case == 'observed-duplicate':
                        row['players'][1] = [10 + row['frame'] * .05, 10.2]
                    elif case == 'empty-team':
                        row['players'][1] = None
            if case == 'full-team':
                source.teams = ['H'] * 12 + ['A']
                source.slot_ids = list(map(str, range(13)))
                for row in source.rows:
                    row['players'] = row['players'][:1] + [[40 + index, 40] for index in range(11)] + [[90, 50]]
            with self.subTest(case=case):
                self.assertTrue(all(row['player_estimates'][0] is None
                                    for row in estimated_window(source, 30, 10)))


if __name__ == '__main__':
    unittest.main()
