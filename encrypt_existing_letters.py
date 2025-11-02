#!/usr/bin/env python3
"""
Migration script to encrypt all existing unencrypted letters in the database.

This script:
1. Finds all letters where is_encrypted = False
2. Encrypts their title and content fields
3. Sets is_encrypted = True
4. Processes in batches to avoid timeouts
5. Logs progress and errors

Usage:
    python encrypt_existing_letters.py

Requirements:
    - ENCRYPTION_KEY environment variable must be set
    - Database connection must be configured
    - All dependencies must be installed
"""

import os
import sys
from datetime import datetime, timezone

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db
from website.models import Letter


def encrypt_existing_letters(batch_size=100, dry_run=False):
    """
    Encrypt all existing unencrypted letters in the database.
    
    Args:
        batch_size: Number of letters to process in each batch (default: 100)
        dry_run: If True, only count letters without encrypting (default: False)
    
    Returns:
        tuple: (total_count, encrypted_count, failed_count)
    """
    app = create_app()
    
    with app.app_context():
        try:
            # Get encryption key to verify it's configured
            from website.encryption import get_encryption_key
            key = get_encryption_key()
            print(f"✅ Encryption key loaded successfully")
        except Exception as e:
            print(f"❌ ERROR: Encryption key not configured: {e}")
            print("\nPlease set ENCRYPTION_KEY environment variable:")
            print("  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
            return (0, 0, 1)
        
        # Count total unencrypted letters
        total_count = Letter.query.filter_by(is_encrypted=False).count()
        
        if total_count == 0:
            print("✅ No unencrypted letters found. All letters are already encrypted.")
            return (0, 0, 0)
        
        print(f"\n📊 Found {total_count} unencrypted letters to encrypt")
        
        if dry_run:
            print("🔍 DRY RUN MODE: No letters will be encrypted")
            return (total_count, 0, 0)
        
        print(f"🚀 Starting encryption process (batch size: {batch_size})...")
        print(f"⏰ Started at: {datetime.now(timezone.utc)}\n")
        
        encrypted_count = 0
        failed_count = 0
        
        # Process in batches
        offset = 0
        while True:
            # Get next batch of unencrypted letters
            letters = Letter.query.filter_by(is_encrypted=False).limit(batch_size).offset(offset).all()
            
            if not letters:
                break
            
            batch_start = offset + 1
            batch_end = offset + len(letters)
            
            print(f"📦 Processing batch {batch_start}-{batch_end} of {total_count}...")
            
            for letter in letters:
                try:
                    # Encrypt the letter fields
                    letter.encrypt_fields()
                    encrypted_count += 1
                    
                    if encrypted_count % 10 == 0:
                        print(f"  ✓ Encrypted {encrypted_count}/{total_count} letters...")
                
                except Exception as e:
                    failed_count += 1
                    print(f"  ✗ ERROR encrypting letter {letter.id}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # Commit this batch
            try:
                db.session.commit()
                print(f"  ✅ Committed batch {batch_start}-{batch_end}")
            except Exception as e:
                db.session.rollback()
                print(f"  ✗ ERROR committing batch {batch_start}-{batch_end}: {e}")
                failed_count += len(letters)
            
            offset += batch_size
            
            # Safety check
            if offset >= total_count:
                break
        
        print(f"\n{'='*60}")
        print(f"📊 ENCRYPTION SUMMARY")
        print(f"{'='*60}")
        print(f"Total letters found:      {total_count}")
        print(f"Successfully encrypted:   {encrypted_count}")
        print(f"Failed:                   {failed_count}")
        print(f"⏰ Completed at: {datetime.now(timezone.utc)}")
        print(f"{'='*60}\n")
        
        # Verify encryption
        remaining_unencrypted = Letter.query.filter_by(is_encrypted=False).count()
        if remaining_unencrypted == 0:
            print("✅ SUCCESS: All letters are now encrypted!")
        else:
            print(f"⚠️  WARNING: {remaining_unencrypted} letters remain unencrypted")
        
        return (total_count, encrypted_count, failed_count)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Encrypt existing unencrypted letters in the database')
    parser.add_argument('--batch-size', type=int, default=100, help='Number of letters to process per batch (default: 100)')
    parser.add_argument('--dry-run', action='store_true', help='Count letters without encrypting them')
    
    args = parser.parse_args()
    
    print("🔐 Letter Encryption Migration Script")
    print("="*60)
    
    total, encrypted, failed = encrypt_existing_letters(
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )
    
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

