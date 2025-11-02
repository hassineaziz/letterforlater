#!/usr/bin/env python3
"""
Script to find and fix letters that are marked as encrypted (is_encrypted=True)
but actually have unencrypted data.

This script:
1. Finds letters where is_encrypted=True but the data isn't actually encrypted
2. Either encrypts them properly OR marks is_encrypted=False
3. Logs all findings
"""

import os
import sys
from datetime import datetime, timezone

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db
from website.models import Letter
from website.encryption import is_encrypted_text, encrypt_text


def fix_unencrypted_letters(dry_run=False, fix_mode='encrypt'):
    """
    Find letters marked as encrypted but with unencrypted data.
    
    Args:
        dry_run: If True, only report findings without making changes
        fix_mode: 'encrypt' to encrypt the data, 'unmark' to set is_encrypted=False
    """
    app = create_app()
    
    with app.app_context():
        try:
            # Get encryption key to verify it's configured
            from website.encryption import get_encryption_key
            key = get_encryption_key()
            print("✅ Encryption key loaded successfully")
        except Exception as e:
            print(f"❌ ERROR: Encryption key not configured: {e}")
            print("\nPlease set ENCRYPTION_KEY environment variable:")
            print("  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
            return (0, 0, 1)
        
        # Find all letters marked as encrypted
        encrypted_letters = Letter.query.filter_by(is_encrypted=True).all()
        
        print(f"\n🔍 Checking {len(encrypted_letters)} letters marked as encrypted...")
        
        broken_letters = []
        valid_letters = 0
        
        for letter in encrypted_letters:
            title_is_encrypted = not letter.title or is_encrypted_text(letter.title)
            content_is_encrypted = not letter.content or is_encrypted_text(letter.content)
            
            if not title_is_encrypted or not content_is_encrypted:
                broken_letters.append(letter)
                print(f"\n⚠️  Letter ID {letter.id}:")
                print(f"   Title encrypted: {title_is_encrypted}")
                print(f"   Content encrypted: {content_is_encrypted}")
                print(f"   Title (first 50 chars): {repr(letter.title[:50]) if letter.title else 'None'}")
                if letter.title and not title_is_encrypted:
                    print(f"   ⚠️  Title is NOT encrypted but is_encrypted=True!")
                if letter.content and not content_is_encrypted:
                    print(f"   ⚠️  Content is NOT encrypted but is_encrypted=True!")
            else:
                valid_letters += 1
        
        if not broken_letters:
            print(f"\n✅ All {len(encrypted_letters)} letters are properly encrypted!")
            return (len(encrypted_letters), 0, 0)
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total letters marked as encrypted: {len(encrypted_letters)}")
        print(f"   Valid encrypted letters: {valid_letters}")
        print(f"   Broken letters (marked encrypted but not encrypted): {len(broken_letters)}")
        
        if dry_run:
            print(f"\n🔍 DRY RUN: Would fix {len(broken_letters)} letters (mode: {fix_mode})")
            return (len(encrypted_letters), 0, len(broken_letters))
        
        print(f"\n🔧 Fixing {len(broken_letters)} letters...")
        
        fixed_count = 0
        failed_count = 0
        
        for letter in broken_letters:
            try:
                if fix_mode == 'encrypt':
                    # Try to encrypt the data
                    if letter.title and not is_encrypted_text(letter.title):
                        letter.title = encrypt_text(letter.title)
                    if letter.content and not is_encrypted_text(letter.content):
                        letter.content = encrypt_text(letter.content)
                    
                    # Verify encryption worked
                    title_ok = not letter.title or is_encrypted_text(letter.title)
                    content_ok = not letter.content or is_encrypted_text(letter.content)
                    
                    if title_ok and content_ok:
                        letter.is_encrypted = True
                        fixed_count += 1
                        print(f"   ✅ Encrypted letter {letter.id}")
                    else:
                        letter.is_encrypted = False
                        failed_count += 1
                        print(f"   ❌ Failed to encrypt letter {letter.id} - marking as unencrypted")
                else:  # fix_mode == 'unmark'
                    # Just mark as unencrypted
                    letter.is_encrypted = False
                    fixed_count += 1
                    print(f"   ✅ Marked letter {letter.id} as unencrypted")
                
                db.session.add(letter)
                
            except Exception as e:
                failed_count += 1
                print(f"   ❌ ERROR fixing letter {letter.id}: {e}")
                # Mark as unencrypted if encryption failed
                letter.is_encrypted = False
                db.session.add(letter)
        
        try:
            db.session.commit()
            print(f"\n✅ Successfully fixed {fixed_count} letters, {failed_count} failed")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERROR committing changes: {e}")
            return (len(encrypted_letters), 0, len(broken_letters))
        
        return (len(encrypted_letters), fixed_count, failed_count)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix letters marked as encrypted but with unencrypted data')
    parser.add_argument('--dry-run', action='store_true', help='Only report findings without making changes')
    parser.add_argument('--fix-mode', choices=['encrypt', 'unmark'], default='encrypt',
                       help='How to fix: "encrypt" to encrypt the data, "unmark" to set is_encrypted=False')
    
    args = parser.parse_args()
    
    print("🔐 Letter Encryption Fix Script")
    print("="*60)
    
    total, fixed, failed = fix_unencrypted_letters(
        dry_run=args.dry_run,
        fix_mode=args.fix_mode
    )
    
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

