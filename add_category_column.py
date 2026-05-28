"""
One-shot migration: adds 'category' column to the products table.
Safe to run multiple times (checks if column already exists).
"""
import sys
import codecs
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("products")]

    if "category" in columns:
        print("Column 'category' already exists – nothing to do.")
    else:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE products ADD COLUMN category VARCHAR(100)"))
            conn.commit()
        print("SUCCESS: Column 'category' added to products table.")
