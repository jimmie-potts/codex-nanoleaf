"""NL22 Light Panels geometry: reported triangles become stable one-zone elements."""
import math

import devices

TRIANGLE = 0
# Rhythm module and controllers report positions but emit no light.
NON_LIGHT = {1, 3, 4, 12}
SIDE = 150
# Edge-adjacent triangle centroids are two inradii apart.
NEIGHBOR = SIDE / math.sqrt(3)
TOLERANCE = 0.1


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1_000_000


def read_layout(panel_layout):
    """Validate a reported Light Panels layout and return its per-device layout entry."""
    if not isinstance(panel_layout, dict) or not isinstance(panel_layout.get('layout'), dict):
        raise ValueError('Invalid Light Panels layout.')
    points = panel_layout['layout'].get('positionData')
    if not isinstance(points, list) or not 1 <= len(points) <= 300:
        raise ValueError('Invalid Light Panels positions.')
    orientation = panel_layout.get('globalOrientation', {'value': 0})
    orientation = orientation.get('value') if isinstance(orientation, dict) else None
    if not _number(orientation):
        raise ValueError('Invalid Light Panels orientation.')
    seen, triangles = set(), []
    for point in points:
        if not isinstance(point, dict):
            raise ValueError('Invalid Light Panels position.')
        panel, shape = point.get('panelId'), point.get('shapeType')
        if type(panel) is not int or not 0 <= panel <= 65535 or panel in seen:
            raise ValueError('Invalid or duplicate panel identity.')
        if type(shape) is not int or (shape != TRIANGLE and shape not in NON_LIGHT):
            raise ValueError('Unsupported Light Panels shape.')
        if any(not _number(point.get(key)) for key in ('x', 'y', 'o')):
            raise ValueError('Invalid Light Panels coordinate.')
        seen.add(panel)
        if shape == TRIANGLE:
            triangles.append({key: point[key] for key in ('x', 'y', 'o')} | {'panelId': panel})
    if not triangles:
        raise ValueError('No Light Panels triangles.')
    angle = math.radians(orientation)
    def location(triangle):
        x, y = triangle['x'], triangle['y']
        return (round(x * math.cos(angle) - y * math.sin(angle)),
                round(x * math.sin(angle) + y * math.cos(angle)), triangle['panelId'])
    triangles.sort(key=location)
    ids = [str(t['panelId']) for t in triangles]
    neighbors, degree = [], [0] * len(triangles)
    for i, first in enumerate(triangles):
        for j in range(i + 1, len(triangles)):
            gap = math.dist((first['x'], first['y']), (triangles[j]['x'], triangles[j]['y']))
            if gap < NEIGHBOR * (1 - TOLERANCE):
                raise ValueError('Overlapping Light Panels triangles.')
            if gap <= NEIGHBOR * (1 + TOLERANCE):
                neighbors.append([ids[i], ids[j]])
                degree[i] += 1
                degree[j] += 1
    if max(degree) > 3:
        raise ValueError('A triangle has more than three edges.')
    reached, frontier = {ids[0]}, [ids[0]]
    while frontier:
        current = frontier.pop()
        for pair in neighbors:
            if current in pair:
                other = pair[1] if pair[0] == current else pair[0]
                if other not in reached:
                    reached.add(other)
                    frontier.append(other)
    if len(reached) != len(triangles):
        raise ValueError('Light Panels triangles are not connected.')
    elements = devices.validate_elements('panels', [
        {'id': ids[index], 'number': index + 1, 'zones': [t['panelId']], 'position': [t['x'], t['y']]}
        for index, t in enumerate(triangles)])
    geometry = {'version': 1, 'orientation': orientation, 'neighbors': neighbors,
                'triangles': [{'id': ids[index], 'panelId': t['panelId'], 'x': t['x'], 'y': t['y'], 'o': t['o']}
                              for index, t in enumerate(triangles)]}
    return {'kind': 'panels', 'elements': elements, 'panel_geometry': geometry}
