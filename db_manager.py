import sqlite3
import os
import sys
import pandas as pd
from tabulate import tabulate
from datetime import datetime

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

    def restore_data(self, preserve_specific_records=False):
        """恢复备份的数据，可选择保留特定记录"""
        for table, data in self.backup.items():
            try:
                if not data['rows']:
                    continue
                
                # 如果需要保留特定记录，且是members表或organizations表，则跳过那些记录
                if preserve_specific_records and table == 'members':
                    filtered_rows = [row for row in data['rows'] if row['user_id'] != 7]
                    print(f"Filtered out user_id=7 from {table} restoration")
                    data['rows'] = filtered_rows
                elif preserve_specific_records and table == 'organizations':
                    filtered_rows = [row for row in data['rows'] if row['organization_id'] != 0]
                    print(f"Filtered out organization_id=0 from {table} restoration")
                    data['rows'] = filtered_rows
                
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

    def recreate_database_preserve_specific(self):
        """重建数据库，仅保留 user_id=7 和 organization_id=0 的记录"""
        try:
            print("Backing up specific records...")

            user_record = None
            org_record = None

            # 备份指定的记录
            try:
                self.cursor.execute("SELECT * FROM members WHERE user_id = 7")
                user_record = self.cursor.fetchone()

                self.cursor.execute("SELECT * FROM organizations WHERE organization_id = 0")
                org_record = self.cursor.fetchone()

                if not user_record:
                    print("Warning: User with user_id=7 not found.")
                if not org_record:
                    print("Warning: Organization with organization_id=0 not found.")
            except sqlite3.Error as e:
                print(f"Error querying specific records: {e}")
                return

            print("\nDropping existing tables...")
            tables = self.get_tables()
            for table in tables:
                try:
                    self.cursor.execute(f"DROP TABLE IF EXISTS {table}")
                    print(f"Dropped table: {table}")
                except sqlite3.Error as e:
                    print(f"Error dropping table {table}: {e}")

            print("\nCreating new tables...")
            try:
                from models import db
                import app
                with app.app.app_context():
                    db.create_all()
                    print("Created all new tables")
            except Exception as e:
                print(f"Error creating tables: {e}")
                raise

            print("\nInserting preserved records...")

            try:
                if user_record:
                    columns = user_record.keys()
                    values = [user_record[col] for col in columns]
                    
                    # Find the index of active_status column and set it to 1
                    try:
                        active_status_index = list(columns).index('active_status')
                        values[active_status_index] = 1
                    except ValueError:
                        pass  # In case active_status column doesn't exist
                        
                    placeholders = ','.join(['?' for _ in columns])
                    column_names = ','.join(columns)

                    self.cursor.execute(f"INSERT INTO members ({column_names}) VALUES ({placeholders})", values)
                    print("Preserved user with user_id=7")


                if org_record:
                    columns = org_record.keys()
                    values = [org_record[col] for col in columns]
                    placeholders = ','.join(['?' for _ in columns])
                    column_names = ','.join(columns)

                    self.cursor.execute(f"INSERT INTO organizations ({column_names}) VALUES ({placeholders})", values)
                    print("Preserved organization with organization_id=0")

                # Initialize M-type service for organization_id=0
                money_service = {
                    'organization_id': 0,
                    'service_type': 'M',
                    'status': 2,  # Configured
                    'url': 'http://172.16.160.88:8001',
                    'path': '/hw/bank/transfer',
                    'method': 'POST',
                    'input_data': '{}',
                    'output_data': '{}',
                    'cost': 0
                }

                self.cursor.execute("""
                    INSERT INTO services (organization_id, service_type, status, url, path, method, input_data, output_data, cost)
                    VALUES (:organization_id, :service_type, :status, :url, :path, :method, :input_data, :output_data, :cost)
                """, money_service)
                print("Created M-type service for organization_id=0")

                self.conn.commit()
                print("\nDatabase reset successfully with preserved records!")
            except Exception as e:
                print(f"Error inserting preserved records: {e}")
                self.conn.rollback()

        except Exception as e:
            print(f"Error during reset process: {e}")
            self.conn.rollback()


    def export_member_table(self):
        """导出members表数据到Excel文件，按组织分别导出"""
        try:
            # 获取所有组织信息
            self.cursor.execute("SELECT organization_id, name FROM organizations")
            organizations = {row['organization_id']: row['name'] for row in self.cursor.fetchall()}
            
            if not organizations:
                print("No organizations found in the database")
                return
            
            # 获取所有成员数据
            self.cursor.execute("SELECT user_id, email, user_type, fund, organization_id FROM members")
            all_members = self.cursor.fetchall()
            
            if not all_members:
                print("No data in members table to export")
                return
            
            # 创建输出目录（如果不存在）
            os.makedirs("exports", exist_ok=True)
            
            # 按组织ID分组
            members_by_org = {}
            for member in all_members:
                org_id = member['organization_id']
                if org_id not in members_by_org:
                    members_by_org[org_id] = []
                
                # 创建一个带有修改后fund值的成员记录
                member_dict = dict(member)
                member_dict['fund'] = 100  # 将fund统一设置为100
                members_by_org[org_id].append(member_dict)
            
            # 使用当前时间创建时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 为每个组织创建Excel文件
            exported_files = []
            for org_id, members in members_by_org.items():
                # 获取组织名称，如果不存在则使用ID
                org_name = organizations.get(org_id, f"Unknown_Org_{org_id}")
                
                # 创建文件名（替换非法字符）
                safe_org_name = ''.join(c if c.isalnum() or c in ['-', '_'] else '_' for c in org_name)
                filename = f"exports/members_{safe_org_name}_{timestamp}.xlsx"
                
                # 只保留需要的列
                df = pd.DataFrame(members)[['email', 'user_type', 'fund']]
                
                # 导出到Excel
                df.to_excel(filename, index=False)
                exported_files.append((org_name, filename, len(members)))
            
            # 输出导出结果
            print("\nExport Results:")
            for org_name, filename, count in exported_files:
                print(f"Organization: {org_name}")
                print(f"File: {filename}")
                print(f"Records: {count}")
                print("-" * 40)
            
            print(f"\nTotal organizations exported: {len(exported_files)}")
            
        except sqlite3.Error as e:
            print(f"Error exporting members table: {e}")
        except Exception as e:
            print(f"Error during export process: {e}")
            import traceback
            traceback.print_exc()
            
        except sqlite3.Error as e:
            print(f"Error exporting member table: {e}")
        except Exception as e:
            print(f"Error during export process: {e}")

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
        print("6. Reset database (preserve specific records)")
        print("7. Export members table to Excel")
        print("8. Exit")
        
        choice = input("\nEnter your choice (1-8): ")
        
        if choice == '8':
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
        elif choice == '6':
            confirm = input("Are you sure you want to reset the database? This will rebuild all tables but preserve specific records. (y/N): ")
            if confirm.lower() == 'y':
                db.recreate_database_preserve_specific()
            else:
                print("Operation cancelled.")
        elif choice == '7':
            db.export_member_table()
        else:
            print("Invalid choice! Please enter a number between 1 and 8.")

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
