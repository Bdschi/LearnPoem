import os
import sqlite3
import csv

def import_sqlite_from_dir(input_dir, db_path):
    schema_path = os.path.join(input_dir, "schema.sql")
    data_dir = os.path.join(input_dir, "data")

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Execute schema.sql
    with open(schema_path, "r", encoding="utf-8", errors="replace") as f:
        schema_sql = f.read()
    cur.executescript(schema_sql)

    # 2. Insert data from CSV files
    for filename in sorted(os.listdir(data_dir)):
        if not filename.endswith(".csv"):
            continue
        table = filename[:-4]  # remove .csv
        csv_path = os.path.join(data_dir, filename)

        with open(csv_path, "r", encoding="utf-8", errors="replace", newline='') as csvfile:
            reader = csv.reader(csvfile)
            columns = next(reader)  # header row

            placeholders = ", ".join(["?"] * len(columns))
            #insert_sql = f'INSERT INTO "{table}" ({", ".join(columns)}) VALUES ({placeholders})'
            quoted_columns = [f'"{col}"' for col in columns]
            insert_sql = f'INSERT INTO "{table}" ({", ".join(quoted_columns)}) VALUES ({placeholders})'
            rows = []
            for row in reader:
                # Convert empty strings back to None
                row_data = [col if col != "" else None for col in row]
                rows.append(row_data)

            cur.executemany(insert_sql, rows)
            conn.commit()

    conn.close()
    print(f"Import completed. Database created at: {db_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Import SQLite DB from directory with ASCII schema and data.")
    parser.add_argument("input_dir", help="Directory containing schema.sql and data/")
    parser.add_argument("db_path", help="Path to create the SQLite database file")
    args = parser.parse_args()

    import_sqlite_from_dir(args.input_dir, args.db_path)
