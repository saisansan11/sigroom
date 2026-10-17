from config.settings import *  # noqa: F401,F403

DATABASES["default"]["NAME"] = "ogn_room_pr7_browserqa"
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
AUTHENTICATION_BACKENDS = ["qa_auth_backend.QABackend"] + list(AUTHENTICATION_BACKENDS)
