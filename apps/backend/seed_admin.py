#!/usr/bin/env python3
"""
Seed script to create admin user
Usage: python seed_admin.py
"""

import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bcrypt
from app.core.database import SessionLocal
from app.models.user import User


def create_admin_user():
    db = SessionLocal()
    try:
        # Check if admin already exists
        existing = db.query(User).filter(User.username == "admin").first()
        if existing:
            print("Admin user already exists")
            return

        # Create admin user with bcrypt directly
        password = b"signalvault2024"
        hashed = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
        
        admin = User(
            username="admin",
            email="admin@signalvault.local",
            hashed_password=hashed,
            name="Administrator"
        )

        db.add(admin)
        db.commit()
        print("✓ Admin user created successfully")
        print(f"  Username: admin")
        print(f"  Password: signalvault2024")

    except Exception as e:
        db.rollback()
        print(f"✗ Error creating admin user: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_admin_user()
