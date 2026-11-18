"""Shortest paths over the explicit, schematic multi-floor graph (not metres)."""
import heapq
import math

STEP_FREE_STATES = ['Not verified', 'Step-free', 'Not step-free']


def edge_key(a: str, b: str) -> tuple:
    return tuple(sorted((a, b)))


def nearest_place_name(campus: dict, node: str) -> str:
    graph = campus['routing']
    floor, (x, y) = graph['node_floors'][node], graph['nodes'][node]
    best, name = math.inf, None
    for p in campus['places']:
        if p['has_position'] and p['map_floor'] == floor:
            distance = math.dist((x, y), (p['x'] * campus['width'], p['y'] * campus['height']))
            if distance < best:
                best, name = distance, p['name']
    return name or node


def connection_label(campus: dict, a: str, b: str) -> str:
    graph = campus['routing']
    edge = next((e for e in graph['edges'] if edge_key(e['a'], e['b']) == edge_key(a, b)), None)
    if edge and edge.get('label'):
        return edge['label']
    first, second = nearest_place_name(campus, a), nearest_place_name(campus, b)
    floor = graph['node_floors'][a]
    if first == second:
        return f'Floor {floor} corridor beside {first}'
    return f'Floor {floor} corridor between {first} and {second}'


def nearby_connections(campus: dict, map_key: str, depth: int = 2, limit: int = 8) -> list[dict]:
    """Connections within a few steps of a place's approach, nearest first, one per distinct label."""
    graph = campus['routing']
    start = graph['attachments'].get(map_key)
    if not start:
        return []
    rows, seen_edges, seen_labels, frontier, reached = [], set(), set(), {start}, {start}
    for _ in range(depth):
        following = set()
        for e in graph['edges']:
            for a, b in ((e['a'], e['b']), (e['b'], e['a'])):
                key = edge_key(a, b)
                if a not in frontier or key in seen_edges:
                    continue
                seen_edges.add(key)
                label = connection_label(campus, a, b)
                names = frozenset(label.removeprefix(f'Floor {graph["node_floors"][a]} corridor between ').split(' and '))
                if names not in seen_labels:
                    seen_labels.add(names)
                    rows.append({'a': a, 'b': b, 'kind': e['kind'], 'label': label,
                                 'floor': graph['node_floors'][a], 'to_floor': graph['node_floors'][b]})
                if b not in reached:
                    reached.add(b)
                    following.add(b)
        frontier = following
    return rows[:limit]


def network(campus: dict, path_status: dict | None = None) -> list[dict]:
    """Every mapped connection with its step-free and closure state."""
    path_status = path_status or {}
    graph = campus['routing']
    rows = []
    for e in graph['edges']:
        state = path_status.get(edge_key(e['a'], e['b']))
        rows.append({'a': e['a'], 'b': e['b'], 'kind': e['kind'], 'label': e.get('label'),
                     'from_floor': graph['node_floors'][e['a']], 'to_floor': graph['node_floors'][e['b']],
                     'step_free': e['kind'] != 'stairs' and state != 'not_step_free',
                     'closed': state == 'closed'})
    return rows


def draft_route(campus: dict, start: int, destination: int, avoid_stairs: bool = False,
                path_status: dict | None = None) -> dict:
    path_status = path_status or {}
    places = {p['id']: p for p in campus['places']}
    graph = campus.get('routing', {})
    attachments = graph.get('attachments', {})
    origin, target = places.get(start), places.get(destination)
    base = {'distance_m': None, 'duration_min': None, 'floor': origin['map_floor'] if origin else 1,
            'accessibility_verified': False, 'avoid_stairs': avoid_stairs,
            'points': [], 'segments': [], 'steps': [], 'connections': [], 'warnings': []}
    if not origin or not target:
        return {**base, 'status': 'unmapped', 'message': 'This place is not in the mapped catalogue.'}
    if any(p.get('access', 'public') != 'public' for p in (origin, target)):
        return {**base, 'status': 'restricted', 'message': 'This draft network only includes public approaches.'}
    if any(p['map_key'] not in attachments for p in (origin, target)):
        return {**base, 'status': 'unmapped', 'message': 'One of these places has no connected approach in the schematic network.'}
    if avoid_stairs and any(p['category'] == 'Stairs' for p in (origin, target)):
        return {**base, 'status': 'no_step_free_route', 'message': 'A staircase cannot be a step-free endpoint. Choose a corridor lift instead; accessibility remains unverified.'}
    if avoid_stairs:
        blocked = [p['name'] for p in (origin, target) if p.get('step_free_access') == 'Not step-free']
        if blocked:
            return {**base, 'status': 'no_step_free_route',
                    'message': f'{" and ".join(blocked)} is marked as not step-free, so no step-free route can be offered. Choose another start or destination, or turn off Avoid stairs.'}
    if start == destination:
        return {**base, 'status': 'same_location', 'message': 'Start and destination are the same place.'}
    nodes = graph['nodes']
    source, end = attachments[origin['map_key']], attachments[target['map_key']]

    def shortest(use_closures: bool, step_free_only: bool):
        adjacency = {key: [] for key in nodes}
        for e in graph['edges']:
            a, b = e['a'], e['b']
            state = path_status.get(edge_key(a, b))
            if use_closures and state == 'closed':
                continue
            if step_free_only and (e['kind'] == 'stairs' or state == 'not_step_free'):
                continue
            weight = 200 if e['kind'] == 'lift' else 80 if e['kind'] == 'stairs' else math.dist(nodes[a], nodes[b])
            adjacency[a].append((b, weight))
            adjacency[b].append((a, weight))
        queue = [(0, source)]
        costs, parents = {source: 0}, {}
        while queue:
            cost, node = heapq.heappop(queue)
            if cost > costs[node]:
                continue
            if node == end:
                break
            for neighbor, weight in adjacency[node]:
                updated = cost + weight
                if updated < costs.get(neighbor, math.inf):
                    costs[neighbor], parents[neighbor] = updated, node
                    heapq.heappush(queue, (updated, neighbor))
        if end not in costs:
            return None
        path = [end]
        while path[-1] != source:
            path.append(parents[path[-1]])
        return path[::-1]

    path = shortest(True, avoid_stairs)
    if path is None:
        if avoid_stairs and shortest(True, False):
            return {**base, 'status': 'no_step_free_route',
                    'message': f'No step-free route to {target["name"]}: every mapped connection uses stairs or a path marked not step-free. Turn off Avoid stairs in your preferences to see the stairs route, or ask campus staff for assistance.'}
        if shortest(False, avoid_stairs):
            return {**base, 'status': 'no_route',
                    'message': f'No route to {target["name"]} is available while a reported path is closed. Try again after it reopens or choose another destination.'}
        return {**base, 'status': 'no_route', 'message': 'No connected draft path was found.'}

    edges = {edge_key(e['a'], e['b']): e for e in graph['edges']}

    def point(p):
        return [round(p['x'] * campus['width'], 3), round(p['y'] * campus['height'], 3)]
    floors = graph['node_floors']
    points = [point(origin) if origin['has_position'] else nodes[source], *[nodes[n] for n in path], point(target) if target['has_position'] else nodes[end]]
    segments = [{'from': points[0], 'to': nodes[source], 'floor': floors[source], 'approximate_door': True}]
    transfers, connections = [], []
    for a, b in zip(path, path[1:]):
        e = edges[edge_key(a, b)]
        connections.append({'a': a, 'b': b, 'kind': e['kind'], 'label': connection_label(campus, a, b),
                            'floor': floors[a], 'to_floor': floors[b],
                            'step_free': e['kind'] != 'stairs' and path_status.get(edge_key(a, b)) != 'not_step_free'})
        if floors[a] != floors[b]:
            transfers.append({'kind': e['kind'], 'label': e['label'], 'from_floor': floors[a], 'to_floor': floors[b]})
        else:
            segments.append({'from': nodes[a], 'to': nodes[b], 'floor': floors[a], 'approximate_door': False})
    segments.append({'from': nodes[end], 'to': points[-1], 'floor': floors[end], 'approximate_door': True})
    points = [segments[0]['from'], *[s['to'] for s in segments]] if segments else points
    steps = [f'Start at {origin["name"]} on floor {floors[source]}. Your start is manually selected, not GPS.']
    steps.append(f'Follow the highlighted corridor on floor {floors[source]}.')
    for transfer in transfers:
        steps.append(f'Take {transfer["label"]} from floor {transfer["from_floor"]} to floor {transfer["to_floor"]}. Switch the map floor to continue.')
        steps.append(f'Continue along the highlighted corridor on floor {transfer["to_floor"]}.' if transfer['to_floor'] in [1, 2] else 'The staircase leads into the floor-3 canteen; no general third-floor corridor is mapped.')
    if target['block'].startswith('Block ') and target['category'] in ['Classroom', 'Lift']:
        steps.append(f'Enter the {target["block"]} side corridor and follow the highlighted branch.')
    steps.append(f'Approach {target["name"]}. The final connection is an approximate doorway/landing position.')
    warnings = []
    # Say why a route looks unusual when it goes around a reported closure.
    unclosed = shortest(False, avoid_stairs) if 'closed' in path_status.values() else path
    for a, b in zip(unclosed, unclosed[1:]):
        if path_status.get(edge_key(a, b)) == 'closed':
            warnings.append(f'Goes around a closed path: {connection_label(campus, a, b)}.')
    if avoid_stairs:
        for p in (origin, target):
            if p.get('step_free_access') == 'Step-free':
                warnings.append(f'{p["name"]} is recorded as having step-free access.')
            else:
                warnings.append(f'Step-free access at {p["name"]} is not verified.')
    if any(e['kind'] == 'lift' for e in connections):
        warnings.append('Lift operation is not monitored. Check the lift is working before you set off.')
    message = ('Step-free draft: corridors and lifts only, no mapped stairs. Doorways and lifts remain unverified.'
               if avoid_stairs else
               'Draft traced from the map, not a verified navigation or accessible route. Dashed ends are approximate door connections.')
    return {**base, 'status': 'schematic_draft', 'points': points, 'segments': segments,
            'node_path': path, 'steps': steps, 'transfers': transfers, 'connections': connections, 'warnings': warnings,
            'route_floors': list(dict.fromkeys(floors[n] for n in path)),
            'start': origin['name'], 'destination': target['name'], 'message': message}
