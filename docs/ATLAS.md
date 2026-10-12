# Atlas / Marble docs hub (imported 2026-10-12)

Full index: https://docs.worldlabs.ai/llms.txt (complete page list).
API: https://api.worldlabs.ai — generate /marble/v1/worlds:generate,
poll operations, export splats (.spz/.ply, free) or GLB mesh (~$2.80).
World ≈ $1.20 (1,500 credits), draft ≈ $0.12, min top-up $5, credits don't
expire. NO video export via API — flythroughs record in the web app only.

## Pages that matter for trains/planes (journeys)

- Record (camera animation + Enhance + MP4):
  https://docs.worldlabs.ai/marble/create/studio-tools/record.md
  Keyframes on a timeline (F=add, Space=preview), Enhance = built-in
  lighting/color post, export MP4. WARNINGS: trajectory does NOT persist
  (lose keyframes leaving the page); timeline runs past 8s.
- Compose (stitch worlds):
  https://docs.worldlabs.ai/marble/create/studio-tools/compose.md
  Multi-room pattern: generate each carriage separately, align floors,
  match lighting, walk room to room. = our train: sleeper + corridor +
  dining car as composed worlds. Splat budget 500K/2M shown live.
- Pano edit (restyle in place):
  https://docs.worldlabs.ai/marble/edit/pano-edit.md
  Same cabin, dawn/storm/night moods without regenerating geometry.
- Variations: same scene, new conditions. = mood episodes cheap.
- Rendering SPZ (scale metadata — required for correct compositing):
  https://docs.worldlabs.ai/api/rendering-spz.md

## Post-effects doctrine (our side)

Marble/Atlas = base pass (geometry + camera). Everything temporal and
graded happens in OUR compositor (FFmpeg, existing render.py pattern):

1. **In-app Enhance** for base lighting/color where the web app suffices.
2. **Our grade**: dawn shift, night dim, storm desat, grain — LUT-style
   FFmpeg filters per episode mood. Same world, many grades.
3. **Outside events as layers**: passing station lights (streak overlays),
   rain on glass, tunnel blacks, dawn bloom — composited over the window
   region, timed to the journey script (station list = event timeline).
4. **Audio bed**: rail hum + announcements (rail-announcements banks) +
   narration. Audio carries sleep; video carries place.

Rule: never regenerate a world for a lighting change. Worlds are geometry;
moods are post. One cabin, infinite nights.
