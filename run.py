# run.py
import sys

import pymysql
from sqlalchemy.engine.url import make_url


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app import create_app, db


def ensure_database_exists(database_uri):
    url = make_url(database_uri)
    database_name = url.database

    if not database_name:
        raise RuntimeError("Database name is missing in SQLALCHEMY_DATABASE_URI")

    connection = pymysql.connect(
        host=url.host or "localhost",
        port=url.port or 3306,
        user=url.username,
        password=url.password or "",
        charset="utf8mb4",
        autocommit=True,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        print(f"Database ready: {database_name}")
    finally:
        connection.close()

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        ensure_database_exists(app.config["SQLALCHEMY_DATABASE_URI"])
        db.create_all()
        print("Database tables ready.")
    app.run(debug=True, port=5000)
