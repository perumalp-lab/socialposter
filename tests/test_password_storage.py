"""Test password hashing and verification across sessions."""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from socialposter.web.app import create_app
from socialposter.web.models import User, db


def test_password_storage_and_verification():
    """Test that passwords are stored correctly and can be verified."""
    app = create_app()
    print(f"✓ App created with config: {app.config.get('SQLALCHEMY_DATABASE_URI', 'SQLite')[:50]}")
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✓ Database tables created")
        
        # Test 1: Create a new user and store password
        print("\n--- Test 1: Password Storage ---")
        test_email = "test_pwd_storage@example.com"
        test_password = "test6"  # Just 5 chars for easy testing
        
        # Clean up any existing test user
        existing = User.query.filter_by(email=test_email).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
        
        user = User(email=test_email, display_name="Test User")
        user.set_password(test_password)
        print(f"✓ Password hash generated: length={len(user.password_hash)}")
        print(f"  Hash preview: {user.password_hash[:50]}...")
        
        db.session.add(user)
        db.session.commit()
        print(f"✓ User stored in database")
        
        # Verify the hash length in database
        db.session.refresh(user)
        print(f"✓ User refreshed from database: hash_length={len(user.password_hash)}")
        
        # Test 2: Verify password immediately after save
        print("\n--- Test 2: Password Verification (Same Session) ---")
        is_correct = user.check_password(test_password)
        print(f"✓ Password verification (correct): {is_correct}")
        assert is_correct, "Password verification failed immediately after save!"
        
        is_wrong = user.check_password("WrongPassword123!")
        print(f"✓ Wrong password rejected: {not is_wrong}")
        assert not is_wrong, "Wrong password was accepted!"
        
        # Test 3: Query user and verify password in new session
        print("\n--- Test 3: Password Verification (New Session) ---")
        user_id = user.id
        db.session.expunge_all()  # Simulate new session
        
        user2 = User.query.filter_by(email=test_email).first()
        assert user2, f"User not found by email: {test_email}"
        print(f"✓ User queried from database: id={user2.id}, email={user2.email}")
        print(f"  Stored hash length: {len(user2.password_hash)}")
        print(f"  Stored hash preview: {user2.password_hash[:50]}...")
        
        is_correct2 = user2.check_password(test_password)
        print(f"✓ Password verification (new session): {is_correct2}")
        assert is_correct2, f"Password verification failed in new session! Hash length={len(user2.password_hash)}"
        
        # Test 4: Verify database column size
        print("\n--- Test 4: Database Column Size ---")
        from sqlalchemy import inspect, MetaData
        
        inspector = inspect(db.engine)
        columns = inspector.get_columns("users")
        password_col = next((c for c in columns if c["name"] == "password_hash"), None)
        
        if password_col:
            col_type = password_col.get("type")
            col_type_str = str(col_type)
            col_length = col_type.length if hasattr(col_type, "length") else None
            print(f"✓ password_hash column type: {col_type_str}")
            print(f"  Column length: {col_length}")
            # Note: Scrypt hashes are ~162 chars, so varchar(255) should be sufficient
            # but we expand to 500 for safety and future compatibility
            if col_length and col_length < 162:
                raise AssertionError(f"Column too small for scrypt hashes: {col_length}")
            print("✓ Column size is adequate for password hashes")
        
        # Clean up
        db.session.delete(user2)
        db.session.commit()
        print("\n✓ Test user cleaned up")
        
    print("\n✅ ALL TESTS PASSED - Password storage and verification working correctly!")


if __name__ == "__main__":
    test_password_storage_and_verification()
