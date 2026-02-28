import os
import sqlite3
import csv

def export_sqlite_to_dir(db_path, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    data_dir = os.path.join(output_dir, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Export schema (definition)
    # Get all schema objects except sqlite internal tables
    cur.execute("""
        SELECT type, name, tbl_name, sql FROM sqlite_master
        WHERE type IN ('table', 'index', 'trigger', 'view') AND name NOT LIKE 'sqlite_%'
    """)
    schema_objects = cur.fetchall()

    # Separate schema objects by type
    tables = [obj for obj in schema_objects if obj["type"] == "table"]
    indexes = [obj for obj in schema_objects if obj["type"] == "index"]
    triggers = [obj for obj in schema_objects if obj["type"] == "trigger"]
    views = [obj for obj in schema_objects if obj["type"] == "view"]

    # Sort each list by name for consistent ordering
    tables.sort(key=lambda x: x["name"])
    indexes.sort(key=lambda x: x["name"])
    triggers.sort(key=lambda x: x["name"])
    views.sort(key=lambda x: x["name"])

    # Write schema.sql in correct order: tables -> indexes -> triggers -> views
    schema_path = os.path.join(output_dir, "schema.sql")
    with open(schema_path, "w", encoding="utf-8") as f:
        for obj in tables + indexes + triggers + views:
            if obj["sql"]:
                f.write(obj["sql"].strip())
                f.write(";\n\n")

    # 2. Export data for each table
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    tables = [row["name"] for row in cur.fetchall()]

    for table in tables:
        cur.execute(f"PRAGMA table_info({table})")
        columns_info = cur.fetchall()
        columns = [col["name"] for col in columns_info]

        pk_columns = [col["name"] for col in columns_info if col["pk"] > 0]
        if not pk_columns:
            order_by = ", ".join([f'"{col}"' for col in columns])
        else:
            order_by = ", ".join([f'"{col}"' for col in pk_columns])

        cur.execute(f'SELECT * FROM "{table}" ORDER BY {order_by}')
        rows = cur.fetchall()

        data_path = os.path.join(data_dir, f"{table}.csv")
        with open(data_path, "w", encoding="utf-8", newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(columns)
            for row in rows:
                row_data = [str(item) if item is not None else "" for item in row]
                writer.writerow(row_data)

    conn.close()
    print(f"Export completed to directory: {output_dir}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export SQLite DB to directory with UTF-8 schema and data.")
    parser.add_argument("db_path", help="Path to the SQLite database file")
    parser.add_argument("output_dir", help="Directory to export schema and data")
    args = parser.parse_args()

    export_sqlite_to_dir(args.db_path, args.output_dir)
