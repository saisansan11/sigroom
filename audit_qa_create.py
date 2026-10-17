import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
import psycopg
from psycopg import sql
cfg = settings.DATABASES['default']
assert cfg['HOST'] in ('127.0.0.1', 'localhost'), 'QA requires local PostgreSQL'
qa_name = 'sigroom_audit_qa_20261003'
with psycopg.connect(dbname='postgres', user=cfg['USER'], password=cfg['PASSWORD'], host=cfg['HOST'], port=cfg['PORT'], autocommit=True) as conn:
    conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(qa_name)))
print('Created isolated local QA database')
