Fix three booking-integrity defects: stale cancellation requests could overwrite current status/revision or bypass a changed cutoff; lodging cohort checks ignored preparation/cleanup buffers in one booking order; and rooms without ResourceRule bypassed blackouts/outages. The services now validate current locked state and apply the same reservation/closure rules consistently.

Validation: baseline 774 passed; new tests reproduced 9 failures before fixes; final suite 786 passed; Django check and migration drift clean. No schema changes. Search interactions passed in Edge desktop/mobile, including unavailable reasons and adjacent available slots.

Draft: browser automation stalled on cancellation confirmation and screenshot capture. Cancellation completion and student/supervisor buffer journeys still need browser verification. See docs/plans/2026-10-03-booking-integrity-handoff.md for evidence and limitations. No deployment or merge performed.
