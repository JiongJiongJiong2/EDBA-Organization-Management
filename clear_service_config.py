import sqlite3
from typing import List, Tuple

def clear_service_configurations(organization_id: int, exclude_types: List[str] = ['M']) -> None:
    """
    Clear service configurations for an organization while preserving specified service types.
    
    Args:
        organization_id (int): The ID of the organization to update
        exclude_types (List[str]): List of service types to exclude from clearing (default: ['M'])
    """
    try:
        # Connect to the database
        conn = sqlite3.connect('instance/EDBA.db')
        cursor = conn.cursor()

        def print_service_config():
            cursor.execute('''
                SELECT service_type, url, path, method, input_data, output_data, status, cost
                FROM services
                WHERE organization_id = ? AND service_type != 'M'
                ORDER BY service_type
            ''', (organization_id,))
            
            results = cursor.fetchall()
            print('\nService Configurations:')
            print('-' * 50)
            for svc in results:
                print(f'\nService Type: {svc[0]}')
                print(f'URL: {svc[1]}')
                print(f'Path: {svc[2]}')
                print(f'Method: {svc[3]}')
                print(f'Input Data: {svc[4]}')
                print(f'Output Data: {svc[5]}')
                print(f'Status: {svc[6]}')
                print(f'Cost: {svc[7]}')
                print('-' * 50)

        # Create placeholders for the excluded types
        placeholders = ','.join('?' for _ in exclude_types)
        
        # Print current configuration
        print("BEFORE UPDATE:")
        print_service_config()

        # Clear configurations for non-excluded services
        cursor.execute(f'''
            UPDATE services 
            SET url = NULL,
                path = NULL,
                method = NULL,
                input_data = NULL,
                output_data = NULL,
                status = 0
            WHERE organization_id = ?
            AND service_type NOT IN ({placeholders})
        ''', [organization_id] + exclude_types)

        # Commit the changes
        conn.commit()

        # Print updated configuration
        print("\nAFTER UPDATE:")
        print_service_config()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise
    
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Clear configurations for organization 1, preserving M service
    clear_service_configurations(organization_id=1)
