import sys
import os

# Add parent directory to path so we can import from database and models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from database.connection import engine, create_all_tables

def reset_database():
    print("Connecting to the database...")
    with engine.connect() as conn:
        # Get all table names in the 'public' schema
        print("Fetching all tables in the public schema...")
        result = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        tables = result.fetchall()
        
        if not tables:
            print("No tables found. Schema is already clean.")
        else:
            for table in tables:
                table_name = table[0]
                print(f"Dropping table: {table_name}")
                # Use CASCADE to drop any dependent objects
                conn.execute(text(f"DROP TABLE IF EXISTS \"{table_name}\" CASCADE"))
        
        conn.commit()
        print("All tables dropped successfully!")

        # Also drop custom enum types so they get recreated with latest values
        print("Dropping custom enum types...")
        result = conn.execute(text(
            "SELECT typname FROM pg_type WHERE typtype = 'e' "
            "AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')"
        ))
        enums = result.fetchall()
        for e in enums:
            print(f"  Dropping enum type: {e[0]}")
            conn.execute(text(f'DROP TYPE IF EXISTS "{e[0]}" CASCADE'))
        conn.commit()
        print("Enum types cleaned up!")
        
    print("\nRecreating database schema (creating fresh tables)...")
    create_all_tables()
    print("Base tables created successfully!")

if __name__ == "__main__":
    print("WARNING: This will drop ALL tables in your Supabase database.")
    confirm = input("Are you sure you want to proceed? (yes/no): ")
    if confirm.lower() == 'yes':
        reset_database()
    else:
        print("Aborted.")
