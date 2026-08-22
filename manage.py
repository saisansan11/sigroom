#!/usr/bin/env python
"""จุดเริ่มต้นคำสั่ง Django ทั้งหมด — ใช้ผ่าน `uv run manage.py <คำสั่ง>`"""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
