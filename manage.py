#!/usr/bin/env python
"""จุดเริ่มต้นคำสั่ง Django ทั้งหมด — ใช้ผ่าน `uv run manage.py <คำสั่ง>`"""
import os
import sys


def main():
    # console Windows บางแบบ (cp1252/cp874) พิมพ์ข้อความไทยของคำสั่งไม่ได้ — บังคับ UTF-8
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
