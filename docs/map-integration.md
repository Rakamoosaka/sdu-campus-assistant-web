# Campus map integration

The React frontend (`web/src/MapWorkspace.tsx`) draws three floor backgrounds and places rooms, markers and routes on top of them. The backend serves the same generated catalogue and walking graph.

## Sources

- `docs/map-source/evacuation-plans/`: photos of the evacuation plans posted on floors 1–3, cropped to the plans. Each floor was posted as two or three overlapping sheets (`floor-N-south`, `-middle`, `-north`).
- `docs/map-source/evacuation-plans/floor-N-stitched.jpg`: each floor's sheets warped into one image in map units, with Block H at the top. They come from `scripts/stitch_evacuation_plans.py`, which matches overlapping sheets by image features. Sheets with no overlap, such as the north halves, are fitted on the corners of the classroom wings.
- `scripts/campus_layout.py`: the traced building. It holds the floor outlines, rooms, halls, stairs, open-to-below areas, the walking graph and every place position, all read off the stitched references.
- `docs/map-source/campus.yaml`: catalogue facts (names, types, served floors, access, notes). Positions no longer live here.
- `docs/map-source/legacy/`: the earlier floor-1 trace, routing draft and floor-2 sketch. They're kept for history and are no longer used.

## Regenerating

```bash
.venv/bin/pip install -r scripts/requirements-map.txt
.venv/bin/python scripts/stitch_evacuation_plans.py      # only when the photos change
cd scripts && ../.venv/bin/python import_campus_map.py ../docs/map-source
```

The importer writes `assets/maps/floor-{1,2,3}-background.svg` and two identical copies of `campus.json` (`assets/maps/` and `backend/app/data/`). It checks that every attachment exists on its place's floor and that only stairs and lifts change floor. Don't edit the generated files by hand.

## What the plans show

- **Orientation:** the posted plans are drawn upside down compared with the official campus map. The map keeps Block H at the top, the teaching blocks D–H to the west of the main corridor, and A, B and C at the south end.
- **Teaching blocks:** each block has a long wing with four classrooms plus an end room (H: two large rooms plus an end room) and an angled wing. On floor 1 the angled wing holds two rooms and the end staircase; on floors 2 and 3 it holds small offices and the staircase. On floor 2 the block corridor runs round a light well. A restroom core sits at each block entrance.
- **Floor 1:** the main corridor is a wide hall. East of it, from north to south: the Block H east wing, the Block G hall (Mini Red Hall) with the secondary entrance, the table tennis zone, Print & Stationery, the canteen, the food point and Red Canteen, then the four Bochkas with the spiral stairs. At the south end are the Block C atrium (WiFi Zone, cloakroom, main entrance), Block B (library) and Block A (Red Hall).
- **Floor 2:** a narrow corridor runs along the blocks, and most of the main hall below is open. A bridge leads to the canteen hall, and the Bochkas' upper seating levels sit on this floor. The library continues upstairs in Block B. The C atrium and the Red Hall are open from below.
- **Floor 3:** a narrow corridor runs along the blocks, with bridges to the canteen and to the tops of the Bochkas (one straight bridge, one Y-shaped). It also reaches the Block B upper hall and the Block C wing rooms. Block A has no third floor.
- **Not visible:** the area between the canteen and the first Bochka falls between photographed sheets. It's drawn from the official campus map.

## Catalogue decisions

- **Room numbers:** they follow the confirmed D101 pattern (01 nearest the main corridor, floor digit first). D101–D104 keep their confirmed order. Other room numbers, including all of floor 3, follow the same pattern but aren't individually verified. Block H has two classrooms per floor in the plans, so H103/H104/H203/H204 are retired.
- **D105 and D106:** provisional numbers placed in Block D's angled wing on floor 1. Their order is assumed.
- **Numbered staircases:** they keep their identifiers and match the user's location descriptions. S8 is the stair beside the Block G hall, S5 and S4 are the curved stairs between E/F and E/D, S3 is south of Block D, and S6 is below the table tennis zone, going straight to the floor-3 canteen with no floor-2 stop. S1 stays retired.
- **New staircases:** the two other curved stairs (H/G and G/F), the Block B and Block C staircases (floors 1–3) and the canteen stairs (floors 2–3). Served floors are inferred from where the plans draw them.
- **Lifts and end staircases:** the D, F and H lifts and every block end staircase link floors 1–3. The lifts' positions are approximate.

## Routing

Dijkstra in `backend/app/routing.py` uses drawing-unit distances, plus fixed costs of 80 per stair flight and 200 per lift ride. These are not metres or walking times. Several flights of the same stair or lift are reported as one step. With Avoid stairs on, every stairs edge is removed, so upper floors are reached by lift. Each lift ride is still flagged as unmonitored and every endpoint as unverified. The saved accessibility preference is applied by the server.

The route coverage test checks every ordered pair of the 137 routable public places, both normally and with stairs avoided.

## Limits

This is a schematic trace from photographs, not a survey. Doors, lift positions and stair landings are approximate. There's no basement plan, no measured scale and no live positioning.
