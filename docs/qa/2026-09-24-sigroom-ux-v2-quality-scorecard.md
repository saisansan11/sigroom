# SIGROOM UX V2 — Quality Scorecard

วันที่ประเมิน: 24 ก.ย. 2569
ฐาน: `48310a576155f37a5af0a6dea0356a340cf94c55`
สถานะ: local Quality Gate PASS — รอ PR/CI
หมายเหตุ: คะแนนเป็น engineering assessment จาก automated tests, browser inspection และ source review ไม่ใช่ Lighthouse score

| ด้าน | คะแนน /10 | หลักฐาน/เหตุผล |
|---|---:|---|
| Functional correctness | 9.6 | Full pytest 614/614 PASS; targeted UX/booking 42/42 PASS; UX32 tests 8/8 PASS; conflict/approval business rules ไม่ถูกย้ายไป client/template |
| Security | 9.5 | Production-like `check --deploy` ผ่านด้วย exact CI env; เหลือเฉพาะ W005/W021 allowlist เดิม; ไม่เปลี่ยน auth/permission rules |
| Privacy | 9.5 | `/about/` เป็น public static intro ไม่มี PII/operational secret; identity การจองยังมาจาก authenticated account; ไม่มีข้อมูลใหม่ใน client storage |
| Accessibility | 9.4 | Django/static accessibility subset 13/13 PASS; Playwright + axe WCAG A/AA 32/32 PASS ทั้ง desktop/mobile และรวม `/about/`; CTA/preset/disclosures หลัก >=44px |
| Mobile UX | 9.0 | Playwright axe mobile project PASS; responsive contracts one-column; native narrow-window QA inner ~500px no overflow; 360/390/430 layout rulesมี automated contract |
| Desktop UX | 9.3 | `/about/`, guest `/`, Booking V2 visual/DOM QA ไม่มี horizontal overflow; task hierarchy ชัด; time dropdowns ถูก progressive-disclosure |
| Performance | 8.7 | ไม่มี external dependency/media asset ใหม่; เพิ่ม CSS และ inline JS ขนาดเล็ก; ยังไม่มี Lighthouse/perf trace ใหม่ จึงไม่ให้คะแนนเกินหลักฐาน |
| Reliability | 9.6 | Full regression 614/614; `manage.py check` PASS; migration drift = No changes detected; reuse services/HTMX contracts เดิม |
| Maintainability | 9.2 | category map/constants อ่านง่าย; validation ยังอยู่ service; UX32 tests, bug register, phase plan และ axe route coverage ป้องกัน regression |
| Visual quality / hierarchy | 9.1 | task-first home cards, intro page, path switcher, numbered search blocks, collapsed advanced options; ใช้ design tokens เดิมไม่แตก visual system |

**คะแนนเฉลี่ยเชิงวิศวกรรม: 9.29 / 10**

## Local Quality Gate evidence

- Targeted booking/home regression: **42/42 PASS**
- UX32 feature tests: **8/8 PASS**
- Full pytest: **614/614 PASS**
- Accessibility/static subset: **13/13 PASS**
- Playwright + axe: **32/32 PASS** (desktop + mobile, รวม `/about/`)
- `manage.py check`: **PASS**
- `makemigrations --check --dry-run`: **No changes detected**
- `git diff --check`: **PASS**
- Production-like security check: exit 0; only `security.W005` / `security.W021` ตาม CI allowlist เดิม
- Browser QA: `/about/`, guest home และ authenticated Booking V2 local snapshot ไม่มี horizontal overflow; core touch targets 44px+

## Remaining gates

ก่อน merge:

1. GitHub PR `SIGROOM PR Safety` ต้อง SUCCESS ทุก job
2. PR ต้อง mergeable และ review diff ไม่มี unrelated files
3. post-merge `SIGROOM PR Safety` ต้อง SUCCESS

ก่อน Production deploy:

- `auto-deploy-sigroom` ต้องยัง disabled
- ต้องได้รับ Production deploy approval แยกจากผู้ใช้
- deploy exact merge commit เท่านั้น
- หลัง deployทำ read-only authenticated smoke ก่อนอนุญาต E2E booking write
