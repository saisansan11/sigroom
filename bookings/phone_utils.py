def normalize_phone(raw_phone: str) -> str:
    """คืนเบอร์โทรเป็นตัวเลขล้วน เพื่อให้รูปแบบต่างกันถือเป็นคนเดียวกัน"""
    return "".join(character for character in (raw_phone or "") if character.isdigit())
