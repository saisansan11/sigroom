# UX-26 — 3D Architectural Depth

## Goal
Make the lodging explorer read as a recognizable building/floor model instead of a grid of rotating rectangular blocks, while preserving the verified room truth, keyboard semantics, filters, mobile behavior, reduced motion, and lightweight SVG implementation.

## Design brief
- Keep the bright architectural light-table direction from UX-24.
- Add building-scale architectural cues: perimeter/parapet, corridor spine, entrance/core marker, room door/window details, and clearer vertical separation.
- Do not imply BIM accuracy or real dimensions.
- Do not introduce WebGL, remote engines, continuous animation, or heavy assets.
- Room controls remain the top faces and retain focus/selection behavior from UX-25.

## Acceptance gates
1. Floor model has a visible building envelope/perimeter and circulation spine.
2. Rooms show architectural door/window cues without adding interactive focus targets.
3. Depth remains correct under all four camera quarters.
4. Selected room remains visually dominant and accessible.
5. Existing UX-23/24/25 contracts pass.
6. Browser QA: 360/390/430/768/1280/1440, no horizontal overflow, rotate/zoom/filter/select/Escape work.
7. Reduced-motion and JS-disabled fallback remain valid.
8. Full regression + accessibility gate pass before PR.
