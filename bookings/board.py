"""ตัวช่วยแสดงผล "ทะเบียนห้องวันนี้" บนหน้าแรก (ธีม A Ledger)

ไฟล์นี้เป็น presentation logic ล้วน ไม่ใช่กฎธุรกิจ: ช่วงว่างที่คำนวณได้เป็นเพียง "คำแนะนำ"
ให้ผู้ใช้แตะไปฟอร์มจองพร้อมเติมวัน/เวลาให้ — ฟอร์มและ ExclusionConstraint ที่ฐานข้อมูล
ยังเป็นผู้ตัดสินสุดท้ายเสมอ (SRS FR-09/35)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable


@dataclass(frozen=True)
class FreeGap:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


def _ceil_to_step(value: datetime, step_minutes: int) -> datetime:
    """ปัดเวลาขึ้นเป็นช่วง step นาที (เช่น 10.07 → 10.15) ให้ลิงก์จองเริ่มที่เวลาที่เลือกได้ในฟอร์ม"""
    base = value.replace(second=0, microsecond=0)
    if base < value:
        base += timedelta(minutes=1)
    remainder = base.minute % step_minutes
    if remainder:
        base += timedelta(minutes=step_minutes - remainder)
    return base


def _floor_to_step(value: datetime, step_minutes: int) -> datetime:
    base = value.replace(second=0, microsecond=0)
    return base - timedelta(minutes=base.minute % step_minutes)


def free_gaps(
    busy: Iterable[tuple[datetime, datetime]],
    window_start: datetime,
    window_end: datetime,
    *,
    now: datetime | None = None,
    pad: timedelta = timedelta(0),
    min_minutes: int = 30,
    step_minutes: int = 15,
) -> list[FreeGap]:
    """คืนช่วงว่างในกรอบ [window_start, window_end) เรียงตามเวลา

    - busy: ช่วงที่ไม่ว่าง (การจองที่ถือครอง, งดใช้ ฯลฯ) ซ้อนกันได้ ไม่ต้องเรียง
    - now: ถ้าให้มา ช่วงว่างจะเริ่มไม่ก่อนเวลานี้ (ไม่ชวนจองเวลาที่ผ่านไปแล้ว)
    - pad: ระยะกันชนที่ขยายรอบช่วงไม่ว่างทั้งสองด้าน (buffer ของห้อง) — ใช้เพื่อแสดงผลเท่านั้น
    - ขอบช่วงว่างถูกปัดเข้าใน (เริ่มปัดขึ้น จบปัดลง) เป็นทุก step นาที ให้ตรงกับตัวเลือกเวลาในฟอร์ม
    - ช่วงที่สั้นกว่า min_minutes หลังปัดแล้วจะถูกตัดทิ้ง
    """
    start = window_start
    if now is not None and now > start:
        start = now
    if start >= window_end:
        return []

    intervals = sorted(
        (max(s - pad, window_start), min(e + pad, window_end))
        for s, e in busy
        if e > s and s - pad < window_end and e + pad > window_start
    )
    merged: list[list[datetime]] = []
    for s, e in intervals:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    gaps: list[FreeGap] = []
    cursor = start
    for s, e in merged + [[window_end, window_end]]:
        if s > cursor:
            gap_start = _ceil_to_step(cursor, step_minutes)
            gap_end = _floor_to_step(s, step_minutes)
            if gap_end - gap_start >= timedelta(minutes=min_minutes):
                gaps.append(FreeGap(gap_start, gap_end))
        cursor = max(cursor, e)
    return gaps
