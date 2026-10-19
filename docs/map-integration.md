# Current campus map integration

The active React frontend (`web/src/MapWorkspace.tsx`) and legacy Flutter frontend reuse the same generated assets and explicit graph. Current source facts and floor-2 corrections are documented in [floor-2-integration.md](floor-2-integration.md).

## Sources and regeneration

- `docs/map-source/campus.yaml`: supplied catalogue/floor-1 facts.
- `docs/map-source/floor-1.svg`: supplied geometry.
- `docs/map-source/routing-draft.yaml`: traced floor-1 centreline graph and approximate endpoints.
- `docs/map-source/floor-2-user-sketch.png`: supplied annotated upper-floor sketch.
- `scripts/import_campus_map.py` and `scripts/compile_upper_floor.py`: reproducible compilation.
- `assets/maps/campus.json` and `backend/app/data/campus.json`: identical generated 103-place catalogues.
- `assets/maps/floor-{1,2}-background.svg`: transparent backgrounds with interactive room/POI content removed.

Regenerate with `python3 scripts/import_campus_map.py docs/map-source` (PyYAML needed in the importing environment). This migration does not change generated assets, graph nodes/edges or stable IDs.

## Web rendering and routing

React loads the map metadata from `/campus-map`, then overlays current database location details from `/locations`. Geometry uses the original 765 × 1280 coordinate system. The SVG is transformed as one canvas; rooms/markers are added once. Pan/pinch plus visible zoom/fit controls work on desktop and mobile. Searches and saved places focus the correct location/floor. Unpositioned places remain searchable without an invented pin. New admin catalogue records have no graph attachment until explicitly mapped.

Dijkstra stays in `backend/app/routing.py`. `/routes` applies the signed-in account's stored accessibility preference in the backend. With stairs excluded, every stairs edge is removed; normal routing may use lifts or stairs. Responses retain floor-specific segments, approximate terminal flags, ordered instructions and transfers. React frames the selected floor's route, draws its segments only, and exposes transfer-floor buttons. Identical endpoints, missing attachments, disconnected or restricted destinations return explanatory states. Distance/time remain null.

## Facts that must remain preserved

- Floors 1/2 are schematic; floor 2 has connected main/side corridors, Bochka upper platforms and a library branch over a muted building footprint. The pale footprint is context, not confirmed walkability.
- S1 is absent. Stair identifiers 3, 4, 5, 6 and 8 remain. S6 connects 1 → 3, skipping 2. The separate canteen stairs near S5 connect 2 → 3.
- Floor 3 has only the canteen terminal. No full floor-3 or basement layout is invented.
- D/F/H lifts record service to −1/1/2/3, but route edges exist only for actual mapped landing approaches (currently 1/2). The stairs-excluded floor-3 canteen request returns no route.
- D101–D104 are original confirmed room records. Additional four-room D–H patterns and equal-width/door positions are explicitly schematic assumptions requested by the user.
- Library internal stairs/lift and unknown block-end landings remain unpositioned/unconnected when the source lacks an approach.
- No live indoor positioning, measured scale, verified step-free access, invented opening hours or contacts.

The web E2E suite verifies D201 floor switching, manual entrance-to-floor-2 routing, lift-only transfers after preference persistence, guest restrictions and mobile controls. Backend tests retain the original graph regression assertions.
