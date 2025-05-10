import sqlite3
import os
import sys
from tabulate import tabulate

DB_PATH = 'instance/EDBA.db'

class DBManager:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.backup = {}

    def connect(self):
        try:
            self.conn = sqlite3.connect(DB_PATH)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            sys.exit(1)

    def close(self):
        if self.conn:
            self.conn.close()

    def get_tables(self):
        self.cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT IN ('sqlite_master', 'sqlite_sequence')
        """)
        return [row['name'] for row in self.cursor.fetchall()]

    def get_table_info(self, table_name):
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        return self.cursor.fetchall()

    def view_table(self, table_name):
        try:
            self.cursor.execute(f"SELECT * FROM {table_name}")
            rows = self.cursor.fetchall()
            if not rows:
                print(f"\nNo data in {table_name}")
                return

            # Get column names
            columns = [description[0] for description in self.cursor.description]
            
            # Convert rows to list format
            data = [[row[col] for col in columns] for row in rows]
            
            print(f"\nTable: {table_name}")
            print(tabulate(data, headers=columns, tablefmt="grid"))
        except sqlite3.Error as e:
            print(f"Error viewing table: {e}")

    def backup_data(self):
        """备份所有表的数据"""
        tables = self.get_tables()
        for table in tables:
            try:
                self.cursor.execute(f"SELECT * FROM {table}")
                columns = [description[0] for description in self.cursor.description]
                rows = self.cursor.fetchall()
                self.backup[table] = {
                    'columns': columns,
                    'rows': [dict(row) for row in rows]
                }
                print(f"Backed up {len(rows)} records from {table}")
            except sqlite3.Error as e:
                print(f"Error backing up table {table}: {e}")

    def restore_data(self):
        """恢复备份的数据"""
        for table, data in self.backup.items():
            try:
                if not data['rows']:
                    continue
                
                columns = data['columns']
                placeholders = ','.join(['?' for _ in columns])
                column_names = ','.join(columns)
                query = f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})"
                
                for row in data['rows']:
                    values = [row[col] for col in columns]
                    try:
                        self.cursor.execute(query, values)
                    except sqlite3.Error as e:
                        print(f"Error restoring row in {table}: {e}")
                        continue
                
                self.conn.commit()
                print(f"Restored {len(data['rows'])} records to {table}")
            except sqlite3.Error as e:
                print(f"Error restoring table {table}: {e}")
                self.conn.rollback()

    def recreate_database(self):
        """重新创建数据库表"""
        try:
            print("Backing up existing data...")
            self.backup_data()
            
            print("\nDropping existing tables...")
            tables = self.get_tables()
            for table in tables:
                try:
                    self.cursor.execute(f"DROP TABLE IF EXISTS {table}")
                    print(f"Dropped table: {table}")
                except sqlite3.Error as e:
                    print(f"Error dropping table {table}: {e}")
            
            print("\nCreating new tables...")
            # 从models.py读取并创建新表
            from models import db
            import app
            with app.app.app_context():
                db.create_all()
                print("Created all new tables")
            
            print("\nRestoring data...")
            self.restore_data()
            
            print("\nDatabase recreation completed successfully!")
        except Exception as e:
            print(f"Error recreating database: {e}")
            self.conn.rollback()

    def add_record(self, table_name):
        try:
            columns = self.get_table_info(table_name)
            values = []
            
            print(f"\nAdding new record to {table_name}")
            print("Enter values (press Enter for NULL on optional fields):")
            
            for col in columns:
                name = col['name']
                type_name = col['type']
                not_null = col['notnull']
                is_pk = col['pk']
                
                if is_pk:
                    self.cursor.execute(f"SELECT MAX({name}) FROM {table_name}")
                    max_id = self.cursor.fetchone()[0]
                    next_id = 1 if max_id is None else max_id + 1
                    values.append(next_id)
                    print(f"{name}: {next_id} (auto-generated)")
                    continue
                
                while True:
                    value = input(f"{name} ({type_name}): ").strip()
                    if not value and not_null:
                        print("This field cannot be NULL. Please enter a value.")
                        continue
                    if not value:
                        values.append(None)
                    else:
                        values.append(value)
                    break

            placeholders = ','.join(['?' for _ in columns])
            query = f"INSERT INTO {table_name} VALUES ({placeholders})"
            self.cursor.execute(query, values)
            self.conn.commit()
            print("Record added successfully!")
            
        except sqlite3.Error as e:
            print(f"Error adding record: {e}")
            self.conn.rollback()

    def update_record(self, table_name):
        try:
            columns = self.get_table_info(table_name)
            pk_col = next(col['name'] for col in columns if col['pk'])
            
            self.view_table(table_name)
            
            record_id = input(f"\nEnter {pk_col} of record to update: ")
            self.cursor.execute(f"SELECT * FROM {table_name} WHERE {pk_col} = ?", (record_id,))
            record = self.cursor.fetchone()
            
            if not record:
                print("Record not found!")
                return
            
            print("\nCurrent values:")
            for col in columns:
                name = col['name']
                print(f"{name}: {record[name]}")
            
            print("\nEnter new values (press Enter to keep current value):")
            updates = []
            values = []
            
            for col in columns:
                name = col['name']
                if col['pk']:
                    continue
                    
                new_value = input(f"{name}: ").strip()
                if new_value:
                    updates.append(f"{name} = ?")
                    values.append(new_value)
            
            if updates:
                values.append(record_id)
                query = f"UPDATE {table_name} SET {', '.join(updates)} WHERE {pk_col} = ?"
                self.cursor.execute(query, values)
                self.conn.commit()
                print("Record updated successfully!")
            else:
                print("No changes made.")
                
        except sqlite3.Error as e:
            print(f"Error updating record: {e}")
            self.conn.rollback()

    def delete_record(self, table_name):
        try:
            columns = self.get_table_info(table_name)
            pk_col = next(col['name'] for col in columns if col['pk'])
            
            self.view_table(table_name)
            
            record_id = input(f"\nEnter {pk_col} of record to delete: ")
            self.cursor.execute(f"SELECT * FROM {table_name} WHERE {pk_col} = ?", (record_id,))
            record = self.cursor.fetchone()
            
            if not record:
                print("Record not found!")
                return
            
            confirm = input(f"Are you sure you want to delete this record? (y/N): ")
            if confirm.lower() == 'y':
                self.cursor.execute(f"DELETE FROM {table_name} WHERE {pk_col} = ?", (record_id,))
                self.conn.commit()
                print("Record deleted successfully!")
            else:
                print("Deletion cancelled.")
                
        except sqlite3.Error as e:
            print(f"Error deleting record: {e}")
            self.conn.rollback()

def main():
    db = DBManager()
    db.connect()

    while True:
        print("\n=== Database Manager ===")
        print("1. View table")
        print("2. Add record")
        print("3. Update record")
        print("4. Delete record")
        print("5. Recreate database")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '6':
            break
            
        if choice in ['1', '2', '3', '4']:
            # Show available tables
            tables = db.get_tables()
            print("\nAvailable tables:")
            for i, table in enumerate(tables, 1):
                print(f"{i}. {table}")
            
            try:
                table_choice = int(input("\nSelect table number: "))
                if 1 <= table_choice <= len(tables):
                    table_name = tables[table_choice - 1]
                    
                    if choice == '1':
                        db.view_table(table_name)
                    elif choice == '2':
                        db.add_record(table_name)
                    elif choice == '3':
                        db.update_record(table_name)
                    elif choice == '4':
                        db.delete_record(table_name)
                else:
                    print("Invalid table number!")
            except ValueError:
                print("Invalid input! Please enter a number.")
        elif choice == '5':
            confirm = input("Are you sure you want to recreate the database? This will rebuild all tables. (y/N): ")
            if confirm.lower() == 'y':
                db.recreate_database()
            else:
                print("Operation cancelled.")
        else:
            print("Invalid choice! Please enter a number between 1 and 6.")

    db.close()
    print("\nGoodbye!")

if __name__ == "__main__":
    main()

'''
    用户类型  
    Admin role:
        O-Convener:     OC 
        T-admin:        TT
        E-admin:        EE 
        Senior E-admin: SE 
    
    Normal user role:
        Data provider:          PP 
        Public data consumer:   PC
        Private data consumer:  CC 

    'S': thesis search, 
    'P': PDF download, 
    'C': course info, 
    'A': student anthendicate, 
    'R': student GPA record and year info, 
    'M': transfer money
'''
