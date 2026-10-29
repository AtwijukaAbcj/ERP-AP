import os
import sqlite3

path = os.path.join(os.path.dirname(__file__), os.pardir, 'db.sqlite3')
path = os.path.abspath(path)
conn = sqlite3.connect(path)
cur = conn.cursor()
print('accounts_permission schema:')
for row in cur.execute('PRAGMA table_info("accounts_permission")'):
    print(row)
print('\nmigrations table exists?')
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='django_migrations'"):
    print(row)
print('\nlast accounts migration entries:')
for row in cur.execute("SELECT id, app, name FROM django_migrations WHERE app='accounts' ORDER BY id DESC LIMIT 10"):
    print(row)
conn.close()
