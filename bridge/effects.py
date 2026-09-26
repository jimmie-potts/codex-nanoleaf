"""Custom display effects: the shared frame encoder and requested animation patterns.

Frames are keyframes: the device fades into each frame's color over its
transition time, in deciseconds, and loops the whole list when asked.
"""
import json
import math
import re

# Spatial patterns take a direction; the others light every Line together or per Line.
PATTERNS = {'wave': True, 'gradient': True, 'pulse': False, 'breathe': False, 'sparkle': False}
SPEEDS = {'slow': 8, 'medium': 4, 'fast': 2, 'faster': 1}  # Deciseconds per keyframe.
DIRECTIONS = ('left', 'right', 'up', 'down', 'outward', 'inward', 'clockwise', 'counterclockwise')
DEFAULTS = {'speed': 'medium', 'direction': 'right', 'loop': True}
MIN_COLORS, MAX_COLORS = 1, 8
# The envelope already verified on the Lines: the middle-Line comet preview sends
# 20 frames per zone in a 9,009-byte request. Stay at or below both.
MAX_FRAMES = 20
MAX_BYTES = 8192
KEYFRAMES = 12
FIELDS = {'kind', 'pattern', 'colors', 'speed', 'direction', 'loop'}
COLOR = re.compile(r'#[0-9a-fA-F]{6}')
AXES = {'right': (1, 0), 'left': (-1, 0), 'up': (0, 1), 'down': (0, -1)}


class Rejected(ValueError):
    """A valid command that the configured Lines cannot play within the bounds."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def display(zones, animated, loop, lines):
    """The `display` write for [(panel, [(r, g, b, transition), ...]), ...] in zone order."""
    data = [len(zones)]
    for panel, frames in zones:
        data.extend([panel, len(frames)])
        for red, green, blue, transition in frames:
            data.extend([red, green, blue, 0, transition])
    write = {'command': 'display', 'version': '2.0',
             'animType': 'custom' if animated else 'static',
             'animData': ' '.join(map(str, data)), 'loop': bool(loop),
             'colorType': 'HSB', 'palette': [{'hue': 0, 'saturation': 0, 'brightness': 100}]}
    if lines:
        # Lines address their two logical zones; the Light Panels API defines no such flag.
        write['logicalPanelsEnabled'] = True
    return write


def size(payload):
    """Request body bytes exactly as the light transport encodes them."""
    return len(json.dumps(payload).encode())


def valid(command):
    if type(command) is not dict or command.get('kind') != 'animation.play':
        return False
    if not {'kind', 'pattern', 'colors'} <= set(command) or set(command) - FIELDS:
        return False
    pattern, colors = command['pattern'], command['colors']
    if type(pattern) is not str or pattern not in PATTERNS:
        return False
    if (type(colors) is not list or not MIN_COLORS <= len(colors) <= MAX_COLORS
            or any(type(color) is not str or not COLOR.fullmatch(color) for color in colors)):
        return False
    if 'speed' in command and (type(command['speed']) is not str or command['speed'] not in SPEEDS):
        return False
    if 'direction' in command and (not PATTERNS[pattern] or type(command['direction']) is not str
                                   or command['direction'] not in DIRECTIONS):
        return False
    return 'loop' not in command or type(command['loop']) is bool


def rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def scale(color, amount):
    return tuple(round(channel * amount) for channel in color)


def blend(colors, position):
    """A cyclic blend through the colors; position 0 is the first color, 1 wraps back to it."""
    point = (position % 1.0) * len(colors)
    index = min(int(point), len(colors) - 1)
    amount = point - index
    start, end = colors[index], colors[(index + 1) % len(colors)]
    return tuple(round(a + (b - a) * amount) for a, b in zip(start, end)), amount


def phases(positions, direction):
    """Each Line's phase: a normalized linear span or a fraction of a full turn."""
    if direction in ('clockwise', 'counterclockwise'):
        cx = sum(x for x, _ in positions) / len(positions)
        cy = sum(y for _, y in positions) / len(positions)
        sign = -1 if direction == 'clockwise' else 1
        # Positive Y is up, like AXES. Preserve the full circle even on sparse walls.
        return [(sign * math.atan2(y - cy, x - cx) / math.tau) % 1.0 for x, y in positions]
    if direction in ('outward', 'inward'):
        cx = sum(x for x, _ in positions) / len(positions)
        cy = sum(y for _, y in positions) / len(positions)
        values = [math.hypot(x - cx, y - cy) for x, y in positions]
        if direction == 'inward':
            values = [-value for value in values]
    else:
        ax, ay = AXES[direction]
        values = [x * ax + y * ay for x, y in positions]
    low, span = min(values), max(values) - min(values)
    return [(value - low) / span if span > 1e-9 else 0.0 for value in values]


def wave(index, colors, step, phase, circular=False):
    # Linear sweeps cover three quarters of a cycle; rotations cover the full circle.
    spread = 1.0 if circular else 0.75
    frames = []
    for k in range(KEYFRAMES):
        color, within = blend(colors, k / KEYFRAMES - spread * phase[index])
        frames.append((*scale(color, 0.15 + 0.85 * (0.5 + 0.5 * math.cos(2 * math.pi * within))), step))
    return frames


def gradient(index, colors, step, phase, circular=False):
    # The first color starts the direction and the last ends it; the band drifts along it.
    spread = 1.0 if circular else (len(colors) - 1) / len(colors)
    return [(*blend(colors, spread * phase[index] - k / KEYFRAMES)[0], step) for k in range(KEYFRAMES)]


def pulse(index, colors, step, phase):
    return [frame for color in colors for frame in ((*color, 1), (*scale(color, 0.1), 2 * step))]


def breathe(index, colors, step, phase):
    return [frame for color in colors for frame in ((*color, 3 * step), (*scale(color, 0.05), 3 * step))]


def sparkle(index, colors, step, phase):
    color = colors[index % len(colors)]
    flash = (5 * index + 3 * index * index + 7) % KEYFRAMES  # Deterministic, varied per Line.
    return [(*color, 1) if k == flash else (*scale(color, 0.25), step) for k in range(KEYFRAMES)]


RENDERERS = {'wave': wave, 'gradient': gradient, 'pulse': pulse, 'breathe': breathe, 'sparkle': sparkle}


def render(command, groups, positions):
    """The looped or one-shot display payload for a valid command on these Lines."""
    options = dict(DEFAULTS, **{key: command[key] for key in DEFAULTS if key in command})
    pattern = command['pattern']
    phase = None
    if PATTERNS[pattern]:
        if not positions or len(positions) != len(groups) or any(p is None for p in positions):
            raise Rejected('unsupported-capability')
        phase = phases(positions, options['direction'])
    colors = [rgb(color) for color in command['colors']]
    zones = []
    circular = ({'circular': True} if PATTERNS[pattern]
                and options['direction'] in ('clockwise', 'counterclockwise') else {})
    for index, zone_ids in enumerate(groups):
        frames = RENDERERS[pattern](index, colors, SPEEDS[options['speed']], phase, **circular)
        if len(frames) > MAX_FRAMES:
            raise Rejected('capacity')
        # Both zones of a Line share its frames.
        zones.extend((zone, frames) for zone in zone_ids)
    payload = {'write': display(zones, True, options['loop'], lines=True)}
    if size(payload) > MAX_BYTES:
        raise Rejected('capacity')
    return payload
