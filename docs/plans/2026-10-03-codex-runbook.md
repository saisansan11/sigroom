# Runbook สำหรับ Codex: PR-A → PR-B → PR-C

เขียน 3 ต.ค. 2569 · ผู้ใช้สั่งให้ Codex ทำต่อเนื่องจนครบ 3 PR · Claude เป็นผู้ตรวจ
ทุกไฟล์แผนอยู่ใน branch `claude/cassette-pass-mockup` ให้ดึงไฟล์ในโฟลเดอร์ `docs/plans/` และ `docs/mockups/` มาใช้

## ลำดับงาน
| ลำดับ | แผน | branch ของงาน | แตกจาก | base ของ PR |
|---|---|---|---|---|
| 1 | `docs/plans/2026-10-03-pr-a-task-first-booking.md` | `feat/task-first-booking` | `origin/feat/lodging-v5-2` | `feat/lodging-v5-2` |
| 2 | `docs/plans/2026-10-03-pr-b-90s-cassette-pass.md` | `feat/theme-90s-cassette` | `feat/task-first-booking` | `feat/task-first-booking` |
| 3 | `docs/plans/2026-10-03-pr-c-teaching-pigeon.md` | `feat/teaching-pigeon` | `feat/theme-90s-cassette` | `feat/theme-90s-cassette` |

- ทำแบบ stacked: ไม่ต้องรอ merge ทำต่อได้เลย
- PR-A แก้ตามที่ผู้ตรวจขอเมื่อไร ให้ **merge** `feat/task-first-booking` เข้า `feat/theme-90s-cassette` แล้วต่อเข้า `feat/teaching-pigeon` (ใช้ merge commit **ห้าม rebase หรือ force-push** branch ที่เปิด PR แล้ว)
- **commit แรกของ PR-A:** คัดลอก `docs/plans/` ทั้ง 4 ไฟล์ และ `docs/mockups/` ทั้ง 3 ไฟล์ (lodging-cassette-pass, gateway-90s, teaching-pigeon) จาก `claude/cassette-pass-mockup` มาไว้ใน branch เพื่อให้ผู้ตรวจอ้างอิงได้
  ```
  git checkout origin/claude/cassette-pass-mockup -- docs/plans docs/mockups
  ```

## กติกาทุก PR
1. อ่าน `CLAUDE.md` และแผนของ PR นั้นให้จบก่อนเขียนโค้ด
2. เจอสิ่งที่ขัดกับแผนหรือไม่แน่ใจ: **อย่าเดา** ให้เลือกทางที่ปลอดภัยกว่าและไม่เปลี่ยนกฎธุรกิจ แล้วเขียนไว้ในหัวข้อ "ข้อสงสัย" ของ PR
3. ห้าม:
   - merge PR เอง
   - deploy หรือรัน `deploy-sigroom.cmd` / `gcloud`
   - แตะ PR #82
   - ลบหรือ skip test เดิม
   - แก้ข้อมูล production
   - push ไป `feat/lodging-v5-2`
4. ก่อนเปิดแต่ละ PR ต้องผ่าน:
   ```
   uv sync
   uv run pytest
   uv run manage.py check
   uv run manage.py makemigrations --check --dry-run   # PR-C: หลังสร้าง migration ของตัวเองแล้ว
   git diff --check
   ```
5. ข้อความ commit และ PR เป็นภาษาไทย (ชื่อ PR ใช้ตามแผน) แต่ละ commit ทำเรื่องเดียวตามหัวข้อในแผน
6. ภาพหน้าจอมือถือ (กว้าง 390px) แนบใน PR ตามรายการในแผน
   - ถ้าเปิดเบราว์เซอร์จริงไม่ได้ ให้เขียนว่าไม่ได้แนบเพราะอะไร **ห้ามแต่งภาพ**
7. จบแต่ละ PR: เขียนสรุปท้าย PR
   - test ผ่านกี่ข้อ
   - test เดิมที่แก้ (ไฟล์ + เหตุผล)
   - ข้อสงสัย
   - สิ่งที่ยังไม่ได้ทำ
   - วิธีดูผลด้วยตาตัวเอง

## เมื่อทำครบ 3 PR
ส่งรายการนี้ให้ผู้ใช้ เพื่อส่งต่อให้ Claude ตรวจ:
- เลข PR ทั้ง 3
- ผล `uv run pytest` ล่าสุดของแต่ละ branch
- รวมข้อสงสัยทั้งหมดไว้ในที่เดียว
