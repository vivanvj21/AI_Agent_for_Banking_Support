import sqlite3

conn = sqlite3.connect('db/bank.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = cursor.fetchall()

print('\n✓ Database Tables Found:')
for table in tables:
    print(f'  - {table[0]}')

# Verify memory tables
print('\n✓ Verifying Memory Tables:')
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions';")
if cursor.fetchone():
    print('  ✓ sessions table exists')
else:
    print('  ✗ sessions table MISSING')

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages';")
if cursor.fetchone():
    print('  ✓ messages table exists')
else:
    print('  ✗ messages table MISSING')

# Verify banking tables
print('\n✓ Verifying Banking Tables:')
banking_tables = ['users', 'accounts', 'cards', 'transactions']
for table_name in banking_tables:
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
    if cursor.fetchone():
        print(f'  ✓ {table_name} table exists')
    else:
        print(f'  ✗ {table_name} table MISSING')

# Count records
print('\n✓ Record Counts:')
tables_to_count = ['users', 'accounts', 'cards', 'transactions', 'sessions', 'messages']
for table_name in tables_to_count:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        print(f'  {table_name}: {count} records')
    except:
        print(f'  {table_name}: (table may not exist)')

conn.close()
print('\n✓ Database Verification Complete')
