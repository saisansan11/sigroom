"""
UX-17 Dormitory Showcase — server-side authoritative source for room data, rates, and facts.

Import this module in views and tests to prevent data drift.
No Django models, no DB queries — pure Python constants.
"""

# ---------------------------------------------------------------------------
# Floor 4
# ---------------------------------------------------------------------------
FLOOR4_AIR_ROOMS: list[int] = list(range(401, 408)) + list(range(411, 417)) + list(range(449, 461))
# 401-407 (7) + 411-416 (6) + 449-460 (12) = 25
FLOOR4_FAN_ROOMS: list[int] = list(range(417, 449))
# 417-448 = 32
FLOOR4_EXCLUDED: list[int] = [408, 409, 410]  # not lodging inventory

FLOOR4_LODGING_ROOMS: list[int] = sorted(FLOOR4_AIR_ROOMS + FLOOR4_FAN_ROOMS)
FLOOR4_ROOM_COUNT: int = len(FLOOR4_LODGING_ROOMS)   # 57
FLOOR4_BEDS_PER_ROOM: int = 2
FLOOR4_BED_COUNT: int = FLOOR4_ROOM_COUNT * FLOOR4_BEDS_PER_ROOM  # 114

# ---------------------------------------------------------------------------
# Floor 5
# ---------------------------------------------------------------------------
FLOOR5_AIR_ROOMS: list[int] = list(range(501, 531))
# 501-530 = 30
FLOOR5_FAN_ROOMS: list[int] = []
FLOOR5_LODGING_ROOMS: list[int] = sorted(FLOOR5_AIR_ROOMS)
FLOOR5_ROOM_COUNT: int = len(FLOOR5_LODGING_ROOMS)   # 30
FLOOR5_BEDS_PER_ROOM: int = 4
FLOOR5_BED_COUNT: int = FLOOR5_ROOM_COUNT * FLOOR5_BEDS_PER_ROOM  # 120

# ---------------------------------------------------------------------------
# Building totals
# ---------------------------------------------------------------------------
TOTAL_ROOMS: int = FLOOR4_ROOM_COUNT + FLOOR5_ROOM_COUNT   # 87
TOTAL_BEDS: int = FLOOR4_BED_COUNT + FLOOR5_BED_COUNT       # 234

# ---------------------------------------------------------------------------
# Shared facilities
# ---------------------------------------------------------------------------
FACILITIES_TEXT = {
    "bathrooms": "ห้องน้ำชั้น 4 และ 5 มี 2 ฝั่ง: โถปัสสาวะ 10, ห้องสุขา 10",
    "showers": "ห้องอาบน้ำชั้น 4 และ 5: ฝั่งละ 20 ห้อง",
}

# ---------------------------------------------------------------------------
# Rates
# ---------------------------------------------------------------------------
# Key: rate category label (Thai), value: dict with air/fan day/month
RATES: list[dict] = [
    {
        "category": "บุคคลภายนอก",
        "air_day": 150,
        "air_month": 2500,
        "fan_day": 100,
        "fan_month": 2000,
    },
    {
        "category": "นขต.กรม.สส.",
        "air_day": 100,
        "air_month": 2000,
        "fan_day": 70,
        "fan_month": 1500,
    },
    {
        "category": "นขต.รร.ส.สส.",
        "air_day": 50,
        "air_month": 1500,
        "fan_day": 40,
        "fan_month": 800,
    },
    {
        "category": "นายทหารนักเรียน",
        "air_day": 50,
        "air_month": 1500,
        "fan_day": 40,
        "fan_month": 800,
    },
    {
        "category": "นายสิบนักเรียน",
        "air_day": 40,
        "air_month": 1000,
        "fan_day": 30,
        "fan_month": 800,
    },
]

ELECTRICITY_AIR_BAHT_PER_UNIT: int = 5
ELECTRICITY_FAN_FLAT_BAHT_PER_MONTH: int = 200
MONTHLY_THRESHOLD_DAYS: int = 20  # 20+ days counted as 1 month
