import sqlite3
from typing import List, Tuple

def update_member_activation_status(organization_id: int, exclude_roles: List[str] = ['OC']) -> List[Tuple[str, int]]:
    """
    Update activation status for members in a specific organization, excluding specified roles.
    
    Args:
        organization_id (int): The ID of the organization to update
        exclude_roles (List[str]): List of role types to exclude from the update (default: ['OC'])
    
    Returns:
        List[Tuple[str, int]]: List of tuples containing (user_type, active_status) after update
    """
    try:
        # Connect to the database
        conn = sqlite3.connect('instance/EDBA.db')
        cursor = conn.cursor()

        # Create placeholders for the excluded roles
        placeholders = ','.join('?' for _ in exclude_roles)
        
        # Update non-excluded roles to inactive (0)
        cursor.execute(f'''
            UPDATE members 
            SET active_status = 0 
            WHERE organization_id = ?
            AND user_type NOT IN ({placeholders})
        ''', [organization_id] + exclude_roles)

        # Update excluded roles (OC) to active (1)
        cursor.execute(f'''
            UPDATE members 
            SET active_status = 1 
            WHERE organization_id = ?
            AND user_type IN ({placeholders})
        ''', [organization_id] + exclude_roles)

        # Commit the changes
        conn.commit()

        # Verify the changes
        cursor.execute('''
            SELECT user_type, active_status 
            FROM members 
            WHERE organization_id = ?
            ORDER BY user_type
        ''', (organization_id,))

        # Fetch and display results
        results = cursor.fetchall()
        print('Updated member statuses:')
        print('User Type | Active Status')
        print('-' * 25)
        for user_type, active_status in results:
            print(f'{user_type:<9} | {active_status}')

        return results

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise
    
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Example usage: Update organization 1, excluding OC roles
    update_member_activation_status(organization_id=1)
