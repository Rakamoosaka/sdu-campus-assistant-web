"""Shortest paths over the explicit, schematic multi-floor graph (not metres)."""
import heapq
import math


def draft_route(campus: dict, start: int, destination: int, avoid_stairs: bool = False) -> dict:
    places = {p['id']: p for p in campus['places']}
    graph = campus.get('routing', {})
    attachments = graph.get('attachments', {})
    origin, target = places.get(start), places.get(destination)
    base = {'distance_m': None, 'duration_min': None, 'floor': origin['map_floor'] if origin else 1,
            'accessibility_verified': False, 'avoid_stairs': avoid_stairs,
            'points': [], 'segments': [], 'steps': []}
    if not origin or not target:
        return {**base, 'status': 'unmapped', 'message': 'This place is not in the mapped catalogue.'}
    if any(p.get('access', 'public') != 'public' for p in (origin, target)):
        return {**base, 'status': 'restricted', 'message': 'This draft network only includes public approaches.'}
    if any(p['map_key'] not in attachments for p in (origin, target)):
        return {**base, 'status': 'unmapped', 'message': 'One of these places has no connected approach in the schematic network.'}
    if avoid_stairs and any(p['category'] == 'Stairs' for p in (origin, target)):
        return {**base, 'status': 'no_step_free_route', 'message': 'A staircase cannot be a step-free endpoint. Choose a corridor lift instead; accessibility remains unverified.'}
    if start == destination:
        return {**base, 'status': 'same_location', 'message': 'Start and destination are the same place.'}
    nodes = graph['nodes']
    adjacency = {key: [] for key in nodes}
    edge_info = {}
    for e in graph['edges']:
        a, b = e['a'], e['b']
        if avoid_stairs and e['kind'] == 'stairs':
            continue
        weight = 200 if e['kind'] == 'lift' else 80 if e['kind'] == 'stairs' else math.dist(nodes[a], nodes[b])
        edge_info[a,b] = edge_info[b,a] = e
        adjacency[a].append((b, weight))
        adjacency[b].append((a, weight))
    source, end = attachments[origin['map_key']], attachments[target['map_key']]
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
        return {**base, 'status': 'no_route', 'message': 'No connected draft path was found.'}
    path = [end]
    while path[-1] != source:
        path.append(parents[path[-1]])
    path.reverse()
    def point(p):
        return [round(p['x'] * campus['width'], 3), round(p['y'] * campus['height'], 3)]
    floors = graph['node_floors']
    points = [point(origin) if origin['has_position'] else nodes[source], *[nodes[n] for n in path], point(target) if target['has_position'] else nodes[end]]
    segments = [{'from': points[0], 'to': nodes[source], 'floor': floors[source], 'approximate_door': True}]
    transfers = []
    for a,b in zip(path,path[1:]):
        e = edge_info[a,b]
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
        steps.append(f'Continue along the highlighted corridor on floor {transfer["to_floor"]}.' if transfer['to_floor'] in [1,2] else 'The staircase leads into the floor-3 canteen; no general third-floor corridor is mapped.')
    if target['block'].startswith('Block ') and target['category'] in ['Classroom', 'Lift']:
        steps.append(f'Enter the {target["block"]} side corridor and follow the highlighted branch.')
    steps.append(f'Approach {target["name"]}. The final connection is an approximate doorway/landing position.')
    return {**base, 'status': 'schematic_draft', 'points': points, 'segments': segments,
            'node_path': path, 'steps': steps, 'transfers': transfers, 'route_floors': list(dict.fromkeys(floors[n] for n in path)),
            'start': origin['name'], 'destination': target['name'],
            'message': 'Draft traced from the map, not a verified navigation or accessible route. Dashed ends are approximate door connections.'}
