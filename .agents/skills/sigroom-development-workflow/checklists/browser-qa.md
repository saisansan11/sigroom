# Browser QA Checklist

For user-facing changes, use a real browser and interact with the UI.

Record what was actually tested:
- role/persona: Guest, Student lodging, Supervisor, Approver, Custodian as applicable
- viewport: include affected mobile and desktop sizes; UI refresh target set is 360, 390, 430, 768, 1280, 1440 px
- route/page
- click/navigation/form interaction
- focus/keyboard behavior where applicable
- loading/empty/error states that can be exercised
- overflow, clipped text, overlap, touch target, contrast, layout shift
- console/runtime errors

A screenshot is evidence of appearance only, not interaction correctness. If Browser QA reveals a bug, fix it and rerun the relevant automated tests and affected browser path.
