import sqlite3
import os

def run_migration():
    try:
        # Get the absolute path to the database file
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance', 'EDBA.db'))
        
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Read and execute the SQL migration script
        with open(os.path.join(os.path.dirname(__file__), 'add_question_fields.sql'), 'r') as f:
            sql_script = f.read()
            
        # Execute migration script
        cursor.executescript(sql_script)
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    run_migration()
