"""Viewer acceptance checks use invented ATD and labels, never match assets."""

import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import numpy as np

from solution.a_opus.atd import read_metadata, read_raw
from tools.match_viewer.predictions import load_predictions
from tools.match_viewer.server import Session, make_server
from tools.match_viewer.synthetic import SyntheticTracking, write_fixture
from tools.match_viewer.tracking import IndexedTracking, ViewerError


class TrackingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.meta, self.raw = write_fixture(self.temp.name, 30, slots=4)

    def source(self):
        return IndexedTracking(self.meta, self.raw, n_frames=30)

    def test_first_last_coordinates_and_parity_with_existing_reader(self):
        source = self.source()
        players, ball, report = read_raw(self.raw, read_metadata(self.meta), 30)
        self.assertEqual(report["n_records"], 30)
        self.assertEqual(source.window(0, 1)[0]["frame"], 0)
        self.assertEqual(source.window(25, 1)[0]["frame"], 25)
        self.assertEqual(source.window(29, 5)[0]["frame"], 29)
        self.assertEqual(source.teams, ["H", "H", "A", "A"])
        for row in source.window(0, 30):
            index = row["frame"]
            np.testing.assert_allclose(row["players"], players[index, :, :2] * source.pitch)
            if np.isfinite(ball[index, :2]).all():
                np.testing.assert_allclose(row["ball"], ball[index, :2] * source.pitch)
            else:
                self.assertIsNone(row["ball"])

    def test_missing_zero_and_outside_are_distinct(self):
        lines = self.raw.read_text().splitlines()
        lines[1] = "2:NaN,NaN,NaN;0,0,0;1.1,0.5,0;0.5,0.5,0:-0.1,0.5,0"
        self.raw.write_text("\n".join(lines) + "\n")
        row = self.source().window(1, 1)[0]
        self.assertIsNone(row["players"][0])
        self.assertEqual(row["players"][1], [0, 0])
        self.assertGreater(row["players"][2][0], 105.3)
        self.assertLess(row["ball"][0], 0)
        self.assertIsNone(self.source().window(0, 1)[0]["ball"])

    def test_invalid_records_are_rejected_without_content(self):
        original = self.raw.read_text()
        for bad in [original.replace("2:", "1:", 1), original.replace("2:", "3:", 1),
                    original.rsplit("\n", 2)[0] + "\n", original + "31:bad:bad\n",
                    original.replace("0.5,0.5,0", "secret,0.5,0", 1),
                    original.replace("0.5,0.5,0", "inf,0.5,0", 1),
                    original.replace("0.5,0.5,0", "NaN,0.5,0", 1),
                    original.replace("0.5,0.5,0", "0.5,0.5", 1)]:
            with self.subTest(case=bad[:2]):
                self.raw.write_text(bad)
                with self.assertRaises(ViewerError) as error:
                    self.source()
                self.assertNotIn("secret", str(error.exception))
                self.assertNotIn(str(self.raw), str(error.exception))

    def test_unknown_team_and_changed_file_rejected(self):
        original = self.meta.read_text()
        self.meta.write_text(original.replace('teamId="h"', 'teamId="unknown"', 1))
        with self.assertRaises(ViewerError):
            self.source()
        self.meta.write_text(original)
        source = self.source()
        self.raw.write_text(self.raw.read_text() + "31:bad:bad\n")
        with self.assertRaises(ViewerError):
            source.window(0, 1)

    def test_channel_layout_from_metadata(self):
        # Reorder player and ball coordinates; the XML, not column assumptions, decides.
        slots = ''.join('<Player id="{}" teamId="{}"/>'.format(i, 'h' if i < 3 else 'a') for i in range(1, 5))
        channels = '<Channel id="y"><Name>y</Name></Channel><Channel id="x"><Name>x</Name></Channel>'
        refs = ''.join('<PlayerChannel id="p{0}{1}" playerId="{0}" channelId="{1}"/>'.format(i, role)
                       for i in range(1, 5) for role in ('y', 'x'))
        groups = ''.join('<SplitRegister separator=","><PlayerChannelRef playerChannelId="p{0}y"/>'
                         '<PlayerChannelRef playerChannelId="p{0}x"/></SplitRegister>'.format(i) for i in range(1, 5))
        self.meta.write_text('<root><Team id="h"><Name>Home</Name></Team><Team id="a"><Name>Away</Name></Team>' +
                             slots + channels + refs + '<DataFormatSpecification separator=":"><StringRegister/>'
                             '<SplitRegister separator=";">' + groups + '</SplitRegister><SplitRegister separator=",">'
                             '<BallChannelRef channelId="y"/><BallChannelRef channelId="x"/>'
                             '</SplitRegister></DataFormatSpecification></root>')
        self.raw.write_text(''.join('{}:0.25,0.75;0.25,0.75;0.25,0.75;0.25,0.75:0.2,0.8\n'.format(i) for i in range(1, 31)))
        row = self.source().window(0, 1)[0]
        np.testing.assert_allclose(row["players"][0], [105.3 * .75, 68 * .25])
        np.testing.assert_allclose(row["ball"], [105.3 * .8, 68 * .2])

    def test_local_verification_reports_aggregates_only(self):
        from tools.match_viewer.verify import verify
        result = verify(self.meta, self.raw, n_frames=30)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['frames_checked'], 30)
        self.assertEqual(result['slots'], 4)
        self.assertEqual(result['observed_ball_frames'], 25)
        self.assertTrue(result['all_frame_indices_aligned'])
        self.assertFalse(result['prediction_csv_validated'])
        self.assertFalse(result['public_gt_evaluated'])
        self.assertTrue(result['ball_matches_reference_reader'])
        self.assertTrue(result['observations_unchanged_by_estimation'])
        self.assertNotIn('players', result)
        self.assertNotIn('labels', result)

    def test_ball_reference_disagreement_is_detected_without_coordinates(self):
        from tools.match_viewer.verify import verify

        def corrupt_reference(*args):
            players, ball, report = read_raw(*args)
            ball[:, [0, 1]] = ball[:, [1, 0]]
            return players, ball, report

        with patch('tools.match_viewer.verify.read_raw', side_effect=corrupt_reference):
            with self.assertRaisesRegex(ViewerError, 'Ball position disagrees') as error:
                verify(self.meta, self.raw, n_frames=30)
        self.assertNotIn(str(self.raw), str(error.exception))


class PredictionTests(unittest.TestCase):
    def test_optional_and_official_validation(self):
        self.assertIsNone(load_predictions(None, 4))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.csv"
            path.write_text("frame,label\n0,h\n1, A \n2,D\n3,X\n")
            self.assertEqual(load_predictions(path, 4), list("HADX"))
            for text in ["frame,label\n0,H\n", "frame,label\n0,H\n0,A\n2,D\n3,X\n",
                         "frame,label\n0,H\n1,A\n2,D\n3,secret\n", "frame,label\n0,H\n1,A\n2,D\n3,\n",
                         "frame,label,extra\n0,H,1\n1,A,1\n2,D,1\n3,X,1\n"]:
                path.write_text(text)
                with self.assertRaises(ViewerError) as error:
                    load_predictions(path, 4)
                self.assertNotIn("secret", str(error.exception))


class SessionTests(unittest.TestCase):
    def test_label_context_is_bounded_and_keeps_x_separate_from_d(self):
        session = Session()
        session.load()
        context = session.label_context(550)
        self.assertEqual(context['start_frame'], 0)
        self.assertEqual(context['end_frame'], 551)
        self.assertEqual([spell['label'] for spell in context['spells']], list('HAD'))
        self.assertEqual(context['home_percent'], 50)
        self.assertEqual(context['spells'][-1]['end_frame'], 551)
        halftime = session.label_context(700)
        self.assertEqual(halftime['start_frame'], 700)
        self.assertEqual(halftime['spells'][0]['label'], 'X')
        self.assertIsNone(halftime['home_percent'])
        second = session.label_context(1000)
        self.assertEqual(second['start_frame'], 850)
        session.labels = None
        self.assertEqual(session.label_context(1000)['spells'], [])
        self.assertIsNone(session.label_context(1000)['home_percent'])

    def test_demo_does_not_resolve_real_paths_and_shows_gaps(self):
        with patch("games.asset_paths", side_effect=AssertionError("No match access")):
            session = Session()
            session.load()
        self.assertEqual(session.metadata()["status"], "ready")
        self.assertTrue(session.metadata()["synthetic"])
        self.assertEqual(session.metadata()["initial_frame"], 0)
        self.assertEqual(set(session.labels), set("HADX"))
        source = session.source
        self.assertIsNone(source.window(100, 1)[0]["ball"])
        self.assertIsNone(source.window(350, 1)[0]["players"][4])
        self.assertTrue(all(x is None for x in source.window(700, 1)[0]["players"]))
        self.assertTrue(any(x is not None for x in source.window(850, 1)[0]["players"]))
        empty = Session()
        empty.load(no_predictions=True)
        self.assertIsNone(empty.labels)
        self.assertFalse(empty.metadata()["has_predictions"])

    def test_loading_and_failed_input(self):
        session = Session()
        self.assertEqual(session.metadata()["status"], "loading")
        session.load(meta="missing-private-path.xml", raw="missing-private-path.txt")
        self.assertEqual(session.metadata()["status"], "error")
        self.assertNotIn("private-path", session.metadata()["message"])

    def test_real_source_starts_at_first_half_without_trimming_the_video(self):
        session = Session()
        session.source = SyntheticTracking()
        session.source.synthetic = False
        session.source.n_frames = 199319
        session.source.blocks = [(1, 11185, 90651), (2, 110808, 190197)]
        session.ready.set()
        self.assertEqual(session.metadata()["initial_frame"], 11185)
        self.assertEqual(session.metadata()["n_frames"], 199319)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.session.load()
        self.server = make_server(self.session, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:{}'.format(self.server.server_port)
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self, path, headers=None):
        return urlopen(Request(self.base + path, headers=headers or {}), timeout=5)

    def test_allowlist_headers_and_aligned_labels(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        with self.get('/') as response:
            self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertIsNone(response.headers.get('Access-Control-Allow-Origin'))
        with self.get('/fonts/geist-latin.woff2') as response:
            self.assertEqual(response.read(4), b'wOF2')
        with self.get('/api/context?frame=550') as response:
            self.assertEqual(json.load(response)['home_percent'], 50)
        for start in [0, 249, 500, 700, 850, 1499]:
            with self.get('/api/frames?start={}&count=2'.format(start)) as response:
                rows = json.load(response)["frames"]
            self.assertEqual(rows[0]["frame"], start)
            self.assertEqual(rows[0]["label"], self.session.labels[start])
        self.session.labels = None
        with self.get('/api/frames?start=0&count=1') as response:
            self.assertIsNone(json.load(response)["frames"][0]["label"])
        for path in ['/../games.py', '/data/tactical/private.txt', '/api/frames?start=-1&count=2',
                     '/api/frames?start=0&count=251', '/api/frames?start=1500&count=1',
                     '/api/frames?start=0&start=1&count=1', '/api/frames?start=0&count=1&path=secret']:
            with self.assertRaises(HTTPError) as error:
                self.get(path)
            self.assertIn(error.exception.code, [400, 404])
        for path in ['/api/context?frame=-1','/api/context?frame=1500',
                     '/api/context?frame=0&frame=1','/api/context?frame=0&path=secret',
                     '/fonts/geist-OFL.txt','/fonts/../server.py']:
            with self.assertRaises(HTTPError) as error:
                self.get(path)
            self.assertIn(error.exception.code, [400,404])

    def test_cross_origin_and_rebinding_are_blocked(self):
        for headers in [{'Host': 'attacker.invalid'}, {'Origin': 'https://attacker.invalid'},
                        {'Sec-Fetch-Site': 'cross-site'}, {'Sec-Fetch-Site': 'same-site'}]:
            with self.assertRaises(HTTPError) as error:
                self.get('/api/meta', headers)
            self.assertEqual(error.exception.code, 403)

    def test_an_existing_viewer_port_cannot_be_shared(self):
        with self.assertRaises(OSError):
            make_server(self.session, self.server.server_port)


if __name__ == '__main__':
    unittest.main()
