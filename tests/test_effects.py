"""Requested animation validation, pattern frames and the shared display encoder."""
import hashlib
import itertools
import math
import json
from pathlib import Path
import unittest

from test_bridge import b, decode
import configuration
import effects

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = json.loads((ROOT / 'tests/fixtures/lines-layout.json').read_text())
GROUPS = configuration.pair_lines(LAYOUT)
ZONES = {p['panelId']: p for p in LAYOUT['layout']['positionData']}
POSITIONS = [[sum(ZONES[p]['x'] for p in g) / 2, sum(ZONES[p]['y'] for p in g) / 2] for g in GROUPS]
LAYOUTS = {'fifteen': (GROUPS, POSITIONS), 'two': ([[101, 102], [103, 104]], [[0, 0], [10, 0]])}
WHITE = ['#ffffff'] * effects.MAX_COLORS


def command(**fields):
    return dict({'kind': 'animation.play', 'pattern': 'wave', 'colors': ['#0044aa', '#00aa66']}, **fields)


def lines(payload, groups):
    """Frames per Line, after checking that both zones of each Line carry identical frames."""
    frames = decode(payload)
    result = []
    for pair in groups:
        first = frames[pair[0]]
        for zone in pair:
            assert frames[zone] == first, 'paired zones differ'
        result.append(first)
    return result


def brightest(frames):
    return max(range(len(frames)), key=lambda k: sum(frames[k][:3]))


class ValidationTest(unittest.TestCase):
    def test_accepts_bounded_commands(self):
        for fields in ({}, {'speed': 'slow', 'direction': 'outward', 'loop': False},
                       {'pattern': 'pulse', 'colors': ['#ABCDEF']}, {'pattern': 'sparkle', 'colors': WHITE, 'speed': 'fast'},
                       {'pattern': 'gradient', 'direction': 'up'}, {'pattern': 'breathe', 'loop': True}):
            with self.subTest(fields=fields):
                self.assertTrue(effects.valid(command(**fields)))

    def test_rejects_malformed_commands(self):
        for fields in ({'pattern': 'strobe'}, {'colors': []}, {'colors': WHITE + ['#000000']}, {'colors': ['#12345']},
                       {'colors': ['red']}, {'colors': '#123456'}, {'colors': ['#1234567']}, {'colors': ['#12345g']},
                       {'speed': 'ludicrous'}, {'speed': 3}, {'direction': 'north'}, {'loop': 'yes'}, {'loop': 1},
                       {'pattern': 'pulse', 'direction': 'left'}, {'pattern': 'breathe', 'direction': 'up'},
                       {'pattern': 'sparkle', 'direction': 'inward'}, {'extra': True}, {'kind': 'animation.stop'},
                       {'colors': ['#123456\n']}):
            with self.subTest(fields=fields):
                self.assertFalse(effects.valid(command(**fields)))
        self.assertFalse(effects.valid(None))
        self.assertFalse(effects.valid({'kind': 'animation.play', 'pattern': 'wave'}))


class EncoderTest(unittest.TestCase):
    def test_display_encodes_zone_frames(self):
        write = effects.display([(7, [(1, 2, 3, 4)]), (9, [(5, 6, 7, 1), (8, 9, 10, 2)])], animated=True, loop=True, lines=True)
        self.assertEqual(write['animData'], '2 7 1 1 2 3 0 4 9 2 5 6 7 0 1 8 9 10 0 2')
        self.assertEqual((write['command'], write['animType'], write['loop'], write['logicalPanelsEnabled']), ('display', 'custom', True, True))
        static = effects.display([(7, [(1, 2, 3, 1)])], animated=False, loop=False, lines=False)
        self.assertEqual(static['animType'], 'static')
        self.assertNotIn('logicalPanelsEnabled', static)

    def test_cap_stays_below_the_live_verified_comet(self):
        # The middle-Line comet preview passed live checks on this 15-Line wall.
        config = dict(line_groups=GROUPS, line_positions=POSITIONS, kind='lines', _mode='work',
                      _comet={'source': len(GROUPS) // 2, 'started': 100.0})
        comet = b.effect_payload(config, [None] * len(GROUPS), 100.0, False)
        self.assertLess(effects.MAX_BYTES, effects.size(comet))
        self.assertLessEqual(effects.MAX_FRAMES, max(len(frames) for frames in decode(comet).values()))


class PatternTest(unittest.TestCase):
    def test_every_pattern_fits_the_proven_envelope(self):
        for name, (groups, positions) in LAYOUTS.items():
            for pattern in effects.PATTERNS:
                for colors in (['#336699'], WHITE, ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#00ffff', '#ff00ff', '#808080', '#ffffff']):
                    for speed in effects.SPEEDS:
                        for direction, loop in itertools.product(effects.DIRECTIONS if effects.PATTERNS[pattern] else (None,), (True, False)):
                            with self.subTest(layout=name, pattern=pattern, colors=len(colors), speed=speed, direction=direction, loop=loop):
                                fields = dict(pattern=pattern, colors=colors, speed=speed, loop=loop)
                                if direction is not None:
                                    fields['direction'] = direction
                                payload = effects.render(command(**fields), groups, positions)
                                self.assertLessEqual(effects.size(payload), effects.MAX_BYTES)
                                self.assertEqual(payload['write']['loop'], loop)
                                self.assertTrue(payload['write']['logicalPanelsEnabled'])
                                for frames in lines(payload, groups):
                                    self.assertTrue(1 <= len(frames) <= effects.MAX_FRAMES)
                                    for r, g, bl, w, t in frames:
                                        self.assertTrue(all(0 <= c <= 255 for c in (r, g, bl)) and w == 0 and t >= 1)


    def test_legacy_payload_bytes_are_unchanged(self):
        # Captured from f3c1384 before adding rotation and faster timing.
        hashes = {'fifteen': '0369586c426223e2ae1b489ce70f0e4d8a0dd5b696c3212e0919037d886b3f8f', 'two': '04c76ed471fb743de0ee33438680b04192c9675c2676f93f9058279dd5f8750b'}
        for name, (groups, positions) in LAYOUTS.items():
            digest = hashlib.sha256()
            for pattern in effects.PATTERNS:
                directions = ('left', 'right', 'up', 'down', 'outward', 'inward') if effects.PATTERNS[pattern] else (None,)
                for colors, speed, direction, loop in itertools.product(
                        (['#336699'], WHITE, ['#ff0000', '#00ff00', '#0000ff']),
                        ('slow', 'medium', 'fast'), directions, (True, False)):
                    fields = dict(pattern=pattern, colors=colors, speed=speed, loop=loop)
                    if direction is not None:
                        fields['direction'] = direction
                    digest.update(json.dumps(effects.render(command(**fields), groups, positions)).encode())
            self.assertEqual(digest.hexdigest(), hashes[name], name)

    def test_rotating_crests_follow_centroid_angles(self):
        for name, (groups, positions) in LAYOUTS.items():
            cx = sum(x for x, _ in positions) / len(positions)
            cy = sum(y for _, y in positions) / len(positions)
            for direction, sign in (('clockwise', -1), ('counterclockwise', 1)):
                expected = [(sign * math.atan2(y - cy, x - cx) / math.tau) % 1 for x, y in positions]
                for pattern, colors in (('wave', ['#ffffff']), ('gradient', ['#ffffff', '#000000'])):
                    with self.subTest(layout=name, direction=direction, pattern=pattern):
                        fields = dict(pattern=pattern, colors=colors, direction=direction)
                        self.assertTrue(effects.valid(command(**fields)))
                        frames = lines(effects.render(command(**fields), groups, positions), groups)
                        crests = [brightest(line) for line in frames]
                        for crest, phase in zip(crests, expected):
                            error = abs((crest / effects.KEYFRAMES - phase + 0.5) % 1 - 0.5)
                            self.assertLessEqual(error, 0.5 / effects.KEYFRAMES + 1e-9)
                        # Quantized crests ordered around the circle permit adjacent ties.
                        order = sorted(range(len(groups)), key=lambda i: expected[i])
                        unwrapped = [crest if crest else (effects.KEYFRAMES if expected[i] > 0.5 else 0)
                                     for i in order for crest in [crests[i]]]
                        self.assertEqual(unwrapped, sorted(unwrapped))
                        self.assertGreater(len(set(crests)), 1)

    def test_rotation_at_the_center_is_deterministic(self):
        for direction in ('clockwise', 'counterclockwise'):
            self.assertEqual(effects.phases([(0, 0), (0, 0)], direction), [0.0, 0.0])

    def test_faster_shortens_every_pattern_cycle(self):
        for pattern in effects.PATTERNS:
            with self.subTest(pattern=pattern):
                cycles = []
                for speed in ('fast', 'faster'):
                    fields = command(pattern=pattern, speed=speed)
                    self.assertTrue(effects.valid(fields))
                    frames = lines(effects.render(fields, *LAYOUTS['two']), LAYOUTS['two'][0])[0]
                    self.assertTrue(all(frame[4] >= 1 for frame in frames))
                    cycles.append(sum(frame[4] for frame in frames))
                self.assertLess(cycles[1], cycles[0])

    def test_defaults_loop_at_medium_speed(self):
        payload = effects.render(command(), *LAYOUTS['two'])
        self.assertTrue(payload['write']['loop'])
        self.assertEqual(payload, effects.render(command(speed='medium', direction='right', loop=True), *LAYOUTS['two']))

    def test_speed_sets_cycle_length(self):
        cycle = lambda speed: sum(f[4] for f in lines(effects.render(command(speed=speed), *LAYOUTS['two']), LAYOUTS['two'][0])[0])
        self.assertGreater(cycle('slow'), cycle('medium'))
        self.assertGreater(cycle('medium'), cycle('fast'))

    def test_wave_crest_travels_along_the_direction(self):
        groups, positions = LAYOUTS['fifteen']
        cx = sum(p[0] for p in positions) / len(positions); cy = sum(p[1] for p in positions) / len(positions)
        measures = {'right': lambda p: p[0], 'left': lambda p: -p[0], 'up': lambda p: p[1], 'down': lambda p: -p[1],
                    'outward': lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2, 'inward': lambda p: -((p[0] - cx) ** 2 + (p[1] - cy) ** 2)}
        for direction, measure in measures.items():
            with self.subTest(direction=direction):
                crests = [brightest(f) for f in lines(effects.render(command(colors=['#2080ff'], direction=direction), groups, positions), groups)]
                order = sorted(range(len(groups)), key=lambda i: measure(positions[i]))
                self.assertEqual([crests[i] for i in order], sorted(crests[i] for i in order))
                self.assertLess(crests[order[0]], crests[order[-1]])

    def test_gradient_spreads_colors_along_the_direction(self):
        groups, positions = LAYOUTS['fifteen']
        frames = lines(effects.render(command(pattern='gradient', colors=['#ff0000', '#0000ff'], direction='right'), groups, positions), groups)
        first = min(range(len(groups)), key=lambda i: positions[i][0]); last = max(range(len(groups)), key=lambda i: positions[i][0])
        self.assertEqual(frames[first][0][:3], [255, 0, 0])
        self.assertEqual(frames[last][0][:3], [0, 0, 255])
        self.assertNotEqual(frames[first][0], frames[first][1])

    def test_pulse_and_breathe_flash_every_line_together_in_color_order(self):
        for pattern in ('pulse', 'breathe'):
            with self.subTest(pattern=pattern):
                payload = effects.render(command(pattern=pattern, colors=['#ff0000', '#00ff00']), *LAYOUTS['fifteen'])
                frames = lines(payload, GROUPS)
                self.assertTrue(all(f == frames[0] for f in frames))
                self.assertEqual([f[:3] for f in frames[0][::2]], [[255, 0, 0], [0, 255, 0]])
                self.assertEqual(len(frames[0]), 4)
        pulse = lines(effects.render(command(pattern='pulse', colors=['#ffffff']), *LAYOUTS['two']), LAYOUTS['two'][0])[0]
        breathe = lines(effects.render(command(pattern='breathe', colors=['#ffffff']), *LAYOUTS['two']), LAYOUTS['two'][0])[0]
        self.assertLess(pulse[0][4], pulse[1][4])  # A sharp flash, then a slower decay.
        self.assertEqual(breathe[0][4], breathe[1][4])

    def test_sparkle_flashes_each_line_once_at_varied_times(self):
        frames = lines(effects.render(command(pattern='sparkle', colors=['#204060']), *LAYOUTS['fifteen']), GROUPS)
        flashes = []
        for line in frames:
            peak = max(sum(f[:3]) for f in line)
            self.assertEqual(sum(sum(f[:3]) == peak for f in line), 1)
            flashes.append(brightest(line))
        self.assertGreater(len(set(flashes)), 3)

    def test_spatial_patterns_need_positions_and_large_walls_are_rejected(self):
        groups = [[1, 2], [3, 4]]
        with self.assertRaises(effects.Rejected) as caught:
            effects.render(command(), groups, None)
        self.assertEqual(caught.exception.code, 'unsupported-capability')
        self.assertTrue(effects.render(command(pattern='pulse'), groups, None))
        huge = [[i, i + 1] for i in range(1000, 1600, 2)]
        with self.assertRaises(effects.Rejected) as caught:
            effects.render(command(pattern='pulse', colors=WHITE), huge, [[i, 0] for i in range(len(huge))])
        self.assertEqual(caught.exception.code, 'capacity')


if __name__ == '__main__':
    unittest.main()
