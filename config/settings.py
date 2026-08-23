"""
การตั้งค่า Django ของระบบจองห้อง
ค่าที่เปลี่ยนตามเครื่อง/หน่วยงานอ่านจากไฟล์ .env (ดู .env.example) — ห้ามเขียน secret ในไฟล์นี้
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --- พื้นฐาน ---------------------------------------------------------------
SITE_NAME = "SIGROOM"
SITE_NAME_TH = "ระบบจองห้อง รร.ส.สส."
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django_htmx",
    # แอปของระบบ (modular monolith — SRS NF-15)
    "accounts",
    "resources",
    "bookings",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- ฐานข้อมูล: PostgreSQL เท่านั้น (ต้องมี extension btree_gist — SRS FR-09) ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "ogn_room"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "OPTIONS": {"connect_timeout": 3},  # ไม่ให้คำสั่งค้างนานเมื่อฐานข้อมูลยังไม่เปิด
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- ผู้ใช้ -----------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
ALLOWED_EMAIL_DOMAIN = os.environ.get("ALLOWED_EMAIL_DOMAIN", "signalschool.ac.th")
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},  # SR-05
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",  # SR-12
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# --- ภาษา/เวลา (SRS NF-07) --------------------------------------------------
LANGUAGE_CODE = "th"
TIME_ZONE = "Asia/Bangkok"
USE_I18N = True
USE_TZ = True

# --- ไฟล์ static -----------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- ความปลอดภัย session/cookie (SRS SR-11) ----------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 12 * 60 * 60  # 12 ชั่วโมง (SR-05)
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000

# --- กฎการจองค่าเริ่มต้น (SRS ข้อ 5; ค่ารายห้องอยู่ใน ResourceRule) ------------
BOOKING_SLOT_MINUTES = 15  # ช่วงเวลาขั้นต่ำของการเลือกเวลา (SRS 12.2)
