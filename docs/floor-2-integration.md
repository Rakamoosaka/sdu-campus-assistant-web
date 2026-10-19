# Floor 2 and cross-floor routing

The second-floor plan is based on the user's red drawing and follow-up corrections: all red corridors/platforms connect, the lower branch enters the library's second floor, and the staircase at the right end of the S5 walkway serves floors 2 and 3 and enters the third-floor canteen.

## Catalogue and geometry

- S1 is retired from maps, search and routes. Historical database records are preserved, not destructively deleted.
- D–H each have four room rectangles on floors 1 and 2, nearest-corridor room numbered 01. D101–D104 are the original confirmed rooms; all additional room codes and equal-width layouts are an assumed pattern explicitly requested by the user. Their exact doors are not verified.
- Floor 2 includes the main corridor, side block corridors, connected Bochka platforms and a library upper-level branch.
- A muted structural footprint from the original map gives orientation context below the outlined floor-2 paths. It is not a second-floor facility catalogue or a claim that every pale area is walkable. No first-floor POI markers are copied onto floor 2.
- Staircases 3, 4, 5, 8, the D end stairs and the spiral staircase link floors 1 and 2. D/F/H lifts also connect them.
- Staircase 6 goes directly from floor 1 to the floor-3 canteen, without a floor-2 landing. New canteen stairs connect floor 2 to that terminal. There is no full third-floor map and no invented lift connection to the canteen.
- Other unpositioned stair landings remain unpositioned, even where served floors are known.

## Routing and accessibility

The graph stores node floors and edge kinds: corridor, stairs or lift. Dijkstra selects routes using schematic drawing-unit costs, with explicit synthetic transfer costs (stairs 80, lift 200) for path ranking. These are NOT measured metres or walking times. Normal routing can use stairs or lifts; the user's saved accessibility preference removes every stairs edge and rejects staircase endpoints. Floor-1-to-floor-2 classroom routes consequently use a D/F/H lift. A canteen-floor-3 request with stairs excluded returns no route instead of inventing an accessible connection.

Responses include per-floor drawable segments and explicit transfer instructions. The app lets users choose floors 1/2 and displays only the route segments for the selected floor. The directions sheet provides floor-switch buttons. Searches can open rooms on either floor; favourites and starts/destinations refer to separate floor-specific catalogue records.

All approaches remain schematic, so `accessibility_verified` stays false and walking time/distance remain null. This is not a safety-certified or surveyed indoor-navigation system.

## Regeneration

`python3 scripts/import_campus_map.py docs/map-source` uses the original source facts, the floor-1 draft and `scripts/compile_upper_floor.py` to regenerate both catalogues and the floor-2 vector geometry. The upper-floor compiler encodes the user's sketch corrections separately, rather than claiming they were in the original supplied YAML. Generated assets should not be edited independently.
