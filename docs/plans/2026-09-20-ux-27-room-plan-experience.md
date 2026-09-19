# UX-27 — Room plan experience

## Verified base
PR #50 is OPEN at 568b2f23b08af419649ce27dcdbdbbaa73b88c6f; base feat/lodging-v5-2.
Stack this phase on feat/ux-26-3d-architectural-depth in feat/ux-27-room-plan-experience.

## Scope and direction
Replace index-based room packing with explicit coordinates transcribed from the supplied floor plans. Start with a readable overhead plan; selecting a room raises a small architectural volume. Preserve an optional perspective view, room filters, keyboard access and focus restoration.
Floor 4: rear row, two paired central blocks, front row interrupted by stairs, side bathrooms and service spaces. Floor 5: two rear wings, interrupted front row and side bathrooms/service rooms. Preserve 57/30 student rooms; 408–410 remain non-student spaces.
Rear rooms 401–416 and 501–516 face the swimming-pool side; front rooms 449–460 and 517–530 face the front of the building. Distinguish building-side orientation from a guaranteed unobstructed window view. Do not invent compass bearings or views for central rooms.
Use a strong room-number card, capacity/cooling and contextual orientation. Keep original plans as expandable references with full-size links, rather than repeating large image cards. Add a restrained site-context guide based on the supplied aerial reference.

## Non-goals
No booking, allocation, privacy, schema, authentication, deployment or merge changes. No invented room-specific photos or unverified room views. Coordinates convey topology, not measured architectural dimensions.

## Gates
Review room ordering, service/stair gaps and orientation against supplied plans. Add executable layout tests and interaction tests. Run targeted Django tests, system/migration checks, full regression, accessibility and real browser checks at 360/390/430/768/1280/1440. Review final diff, commit scoped files, push stacked PR, inspect CI, write handoff.
