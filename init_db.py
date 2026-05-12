#!/usr/bin/env python
# init_db.py - Database initialization script

"""
This script initializes the database with the required tables and 
creates a default organization with a default admin user.
"""

import os
import sys

# Ensure the instance directory exists
instance_dir = os.path.join(os.path.dirname(__file__), 'instance')
os.makedirs(instance_dir, exist_ok=True)

# Create proof_documents subdirectory
proof_documents_dir = os.path.join(instance_dir, 'proof_documents')
os.makedirs(proof_documents_dir, exist_ok=True)

# Create policies subdirectory
policies_dir = os.path.join(instance_dir, 'policies')
os.makedirs(policies_dir, exist_ok=True)

from app import app
from models import db, Member, Organization, Service

def init_database():
    """Initialize the database with tables and default data."""
    with app.app_context():
        # Create all tables
        print("Creating database tables...")
        db.create_all()
        print("Tables created successfully!")
        
        # Check if default organization exists
        default_org = db.session.execute(
            db.select(Organization).filter_by(organization_id=0)
        ).scalar_one_or_none()
        
        if not default_org:
            # Create default organization
            print("Creating default organization...")
            default_org = Organization(
                organization_id=0,
                name='System Organization'
            )
            db.session.add(default_org)
            db.session.commit()
            print("Default organization created!")
        
        # Check if default admin exists
        default_admin = db.session.execute(
            db.select(Member).filter_by(user_id=0)
        ).scalar_one_or_none()
        
        if not default_admin:
            # Create default SE admin
            print("Creating default admin user...")
            default_admin = Member(
                user_id=0,
                email='admin@example.com',
                user_type='SE',
                fund=100,
                organization_id=0,
                active_status=1
            )
            db.session.add(default_admin)
            db.session.commit()
            print("Default admin user created!")
            print("Default admin email: admin@example.com")
            print("Please update the email in the database for your actual admin user.")
        
        # Check if default M-type service exists
        default_service = db.session.execute(
            db.select(Service).filter_by(organization_id=0, service_type='M')
        ).scalar_one_or_none()
        
        if not default_service:
            # Create default M-type service
            print("Creating default M-type service...")
            default_service = Service(
                organization_id=0,
                service_type='M',
                status=2,
                url=os.environ.get('BANK_SERVICE_URL', 'http://localhost:8001'),
                path='/hw/bank/transfer',
                method='POST',
                input_data='{}',
                output_data='{}',
                cost=0
            )
            db.session.add(default_service)
            db.session.commit()
            print("Default M-type service created!")
        
        print("\nDatabase initialization complete!")
        print("\nDefault data created:")
        print("- Organization: System Organization (ID: 0)")
        print("- Admin User: admin@example.com (Type: SE)")
        print("- Service: M-type Money Transfer service")
        
        # Print all tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"\nCreated tables: {', '.join(tables)}")


def reset_database():
    """Reset the database (drop all tables and reinitialize)."""
    with app.app_context():
        print("WARNING: This will delete all data!")
        confirm = input("Are you sure you want to reset the database? (y/N): ")
        
        if confirm.lower() == 'y':
            print("Dropping all tables...")
            db.drop_all()
            print("Tables dropped.")
            
            print("Reinitializing database...")
            init_database()
        else:
            print("Operation cancelled.")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        reset_database()
    else:
        init_database()