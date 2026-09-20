# UX28 — lodging entry and operations

Approved flow: general visitors submit requests for staff approval; course students can self-book after allocation/publication, or authorized staff assign a bed. Staff should work from one date/cohort/room workspace, with reusable course choices and private occupant details. Public showcase retains one rates table and a collapsed original; add an illustrative isometric locality map with navigation link.

Base: local UX27 8687ab3, stacked on UX26 PR50. Preserve debug.log. GitHub discovery currently returns HTTP401; public push previously denied pending explicit publication approval. No merge/deploy or authentication changes.

Implementation sequence: consolidate public content; shared transactional bed assignment with locked state revalidation and staff permissions; staff room workspace and searchable course choices; general request flow reusing approval constraints; illustrative locality map. No real occupant data in public views. No guessed location or guaranteed room views.

Verify permissions, closed/released cohorts, duplicate normalized phone/bed, stale state, regular-booking conflicts, public privacy, validation redisplay; Django checks, full pytest, desktop/mobile interactions, final diff and handoff. Completion requires every requested flow and gate, not just changed labels.
