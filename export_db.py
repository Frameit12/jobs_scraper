"""
Run this to export your Railway database before shutting down.
Usage: python export_db.py "YOUR_DATABASE_PUBLIC_URL"
"""
import sys
import json
from datetime import datetime
from sqlalchemy import create_engine, text

if len(sys.argv) < 2:
    print("Usage: python export_db.py \"YOUR_DATABASE_PUBLIC_URL\"")
    sys.exit(1)

db_url = sys.argv[1]
engine = create_engine(db_url)

print("Connecting to database...")
with engine.connect() as conn:
    # Get all table names
    tables = conn.execute(text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)).fetchall()

    table_names = [t[0] for t in tables]
    print(f"Found {len(table_names)} tables: {', '.join(table_names)}")

    export = {}
    for table in table_names:
        rows = conn.execute(text(f"SELECT * FROM {table}")).fetchall()
        keys = conn.execute(text(f"SELECT * FROM {table} LIMIT 0")).keys()
        export[table] = [dict(zip(keys, row)) for row in rows]
        print(f"  {table}: {len(rows)} rows")

# Convert non-serializable types (dates, bytes) to strings
def default_serializer(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return f"<binary {len(obj)} bytes>"
    return str(obj)

filename = f"jobs_scraper_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(filename, 'w') as f:
    json.dump(export, f, indent=2, default=default_serializer)

print(f"\nDone! Backup saved to: {filename}")
