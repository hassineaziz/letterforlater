#!/usr/bin/env python3
"""
Unified script to encrypt all letters in the database.

This script:
1. Finds all letters with unencrypted data (regardless of is_encrypted flag)
2. Encrypts them properly
3. Updates the is_encrypted flag correctly
4. Handles all edge cases (marked encrypted but unencrypted, marked unencrypted but encrypted, etc.)

Usage:
    python encrypt_letters.py                    # Encrypt all unencrypted letters
    python encrypt_letters.py --dry-run           # Show what would be encrypted
    python encrypt_letters.py --diagnose          # Show status of all letters
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db
from website.models import Letter
from website.encryption import is_encrypted_text, get_encryption_key


def diagnose_letters():
    """Show encryption status of all letters - uses actual decryption to verify"""
    app = create_app()
    
    with app.app_context():
        from website.encryption import decrypt_text
        
        all_letters = Letter.query.all()
        print(f"\n🔍 Checking {len(all_letters)} total letters...\n")
        
        # Categorize letters
        properly_encrypted = []
        properly_unencrypted = []
        marked_encrypted_but_unencrypted = []
        marked_unencrypted_but_encrypted = []
        needs_encryption = []
        
        for letter in all_letters:
            # Actually try to decrypt to verify encryption (more reliable than is_encrypted_text)
            title_can_decrypt = True
            content_can_decrypt = True
            
            if letter.title:
                try:
                    # If it's encrypted, decrypt will work. If it's plain text, it will fail
                    decrypt_text(letter.title)
                    title_can_decrypt = True
                    title_is_encrypted = True
                except:
                    # Decryption failed - either it's plain text or corrupted
                    # Check if it looks like plain text (not base64-encoded)
                    title_is_encrypted = is_encrypted_text(letter.title)
                    title_can_decrypt = title_is_encrypted
            else:
                title_is_encrypted = True  # Empty is OK
            
            if letter.content:
                try:
                    # If it's encrypted, decrypt will work. If it's plain text, it will fail
                    decrypt_text(letter.content)
                    content_can_decrypt = True
                    content_is_encrypted = True
                except Exception as e:
                    # Decryption failed - either it's plain text or corrupted
                    # Check if it looks like plain text (not base64-encoded)
                    content_is_encrypted = is_encrypted_text(letter.content)
                    content_can_decrypt = content_is_encrypted
                    # Log the error for debugging (but don't show for every letter)
                    if letter.id == 1145:
                        print(f"   Debug: Letter 1145 content decryption failed: {e}")
                        print(f"   Content preview: {letter.content[:100] if letter.content else 'None'}...")
                        print(f"   is_encrypted_text check: {content_is_encrypted}")
            else:
                content_is_encrypted = True  # Empty is OK
            
            actually_encrypted = title_is_encrypted and content_is_encrypted
            
            if actually_encrypted and letter.is_encrypted:
                properly_encrypted.append(letter.id)
            elif not actually_encrypted and not letter.is_encrypted:
                properly_unencrypted.append(letter.id)
                needs_encryption.append(letter.id)
            elif actually_encrypted and not letter.is_encrypted:
                marked_unencrypted_but_encrypted.append(letter.id)
            elif not actually_encrypted and letter.is_encrypted:
                marked_encrypted_but_unencrypted.append(letter.id)
                needs_encryption.append(letter.id)
                # Show details for this problematic letter
                print(f"\n⚠️  Letter ID {letter.id} is marked encrypted but content is NOT encrypted!")
                print(f"   Title encrypted: {title_is_encrypted}")
                print(f"   Content encrypted: {content_is_encrypted}")
                print(f"   Title preview: {letter.title[:50] if letter.title else 'None'}...")
                print(f"   Content preview: {letter.content[:50] if letter.content else 'None'}...")
        
        print("📊 DIAGNOSIS RESULTS:")
        print(f"  ✅ Properly encrypted: {len(properly_encrypted)} letters")
        print(f"  ⚠️  Marked encrypted but actually unencrypted: {len(marked_encrypted_but_unencrypted)} letters")
        if marked_encrypted_but_unencrypted:
            print(f"     Letter IDs: {marked_encrypted_but_unencrypted}")
        print(f"  ⚠️  Marked unencrypted but actually encrypted: {len(marked_unencrypted_but_encrypted)} letters")
        if marked_unencrypted_but_encrypted:
            print(f"     Letter IDs: {marked_unencrypted_but_encrypted}")
        print(f"  📝 Properly unencrypted (needs encryption): {len(properly_unencrypted)} letters")
        if properly_unencrypted:
            print(f"     Letter IDs: {properly_unencrypted}")
        print(f"\n  🔧 Total letters needing encryption: {len(needs_encryption)}")
        if needs_encryption:
            print(f"     Letter IDs: {needs_encryption}")
        
        return needs_encryption


def encrypt_letters(letter_ids=None, dry_run=False):
    """
    Encrypt all letters that need encryption.
    
    Args:
        letter_ids: List of letter IDs to encrypt (None = encrypt all unencrypted)
        dry_run: If True, don't actually encrypt
    """
    app = create_app()
    
    with app.app_context():
        try:
            key = get_encryption_key()
            print("✅ Encryption key loaded successfully")
        except Exception as e:
            print(f"❌ ERROR: Encryption key not configured: {e}")
            return (0, 0, 1)
        
        if letter_ids:
            letters_to_encrypt = Letter.query.filter(Letter.id.in_(letter_ids)).all()
        else:
            # Find all letters that need encryption - actually try decrypting to verify
            from website.encryption import decrypt_text
            all_letters = Letter.query.all()
            letters_to_encrypt = []
            for letter in all_letters:
                title_enc = True
                content_enc = True
                
                if letter.title:
                    try:
                        decrypt_text(letter.title)
                        title_enc = True  # Successfully decrypted = encrypted
                    except Exception:
                        title_enc = False  # Decryption failed = not encrypted
                
                if letter.content:
                    try:
                        decrypt_text(letter.content)
                        content_enc = True  # Successfully decrypted = encrypted
                    except Exception:
                        content_enc = False  # Decryption failed = not encrypted
                
                if not title_enc or not content_enc:
                    letters_to_encrypt.append(letter)
        
        total_count = len(letters_to_encrypt)
        
        if total_count == 0:
            print("✅ No letters need encryption. All letters are already encrypted!")
            return (0, 0, 0)
        
        print(f"\n📊 Found {total_count} letters that need encryption")
        
        if dry_run:
            print("🔍 DRY RUN MODE: No letters will be encrypted\n")
            for letter in letters_to_encrypt:
                title_enc = is_encrypted_text(letter.title) if letter.title else True
                content_enc = is_encrypted_text(letter.content) if letter.content else True
                print(f"  Letter ID {letter.id}: title_enc={title_enc}, content_enc={content_enc}, is_encrypted={letter.is_encrypted}")
            return (total_count, 0, 0)
        
        print(f"🚀 Starting encryption process...")
        print(f"⏰ Started at: {datetime.now(timezone.utc)}\n")
        
        encrypted_count = 0
        failed_count = 0
        
        for letter in letters_to_encrypt:
            try:
                # Check current state by actually trying to decrypt
                title_enc = True
                content_enc = True
                
                if letter.title:
                    try:
                        decrypt_text(letter.title)
                        title_enc = True
                    except:
                        title_enc = is_encrypted_text(letter.title)
                
                if letter.content:
                    try:
                        decrypt_text(letter.content)
                        content_enc = True
                    except:
                        content_enc = is_encrypted_text(letter.content)
                
                # Store original content to verify encryption worked
                original_content = letter.content
                
                # Encrypt the letter
                success = letter.encrypt_fields()
                
                if success:
                    # Verify encryption actually worked by trying to decrypt
                    encryption_verified = True
                    
                    if letter.title:
                        try:
                            decrypt_text(letter.title)
                        except Exception:
                            encryption_verified = False
                            print(f"  ✗ Letter {letter.id}: Title encryption verification failed")
                    
                    if letter.content:
                        try:
                            decrypt_text(letter.content)
                        except Exception as e:
                            encryption_verified = False
                            print(f"  ✗ Letter {letter.id}: Content encryption verification failed: {e}")
                            print(f"    Original content preview: {original_content[:50] if original_content else 'None'}...")
                            print(f"    Content after encrypt_fields(): {letter.content[:50] if letter.content else 'None'}...")
                            print(f"    is_encrypted flag: {letter.is_encrypted}")
                    
                    if encryption_verified:
                        encrypted_count += 1
                        if encrypted_count % 10 == 0:
                            print(f"  ✓ Encrypted {encrypted_count}/{total_count} letters...")
                    else:
                        failed_count += 1
                        print(f"  ✗ Letter {letter.id}: encrypt_fields() returned True but verification failed")
                else:
                    failed_count += 1
                    print(f"  ✗ Failed to encrypt letter {letter.id}: encrypt_fields() returned False")
            
            except Exception as e:
                failed_count += 1
                print(f"  ✗ ERROR encrypting letter {letter.id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"\n✅ Committed all changes")
        except Exception as e:
            db.session.rollback()
            print(f"✗ ERROR committing changes: {e}")
            return (total_count, encrypted_count, failed_count + len(letters_to_encrypt))
        
        print(f"\n{'='*60}")
        print(f"📊 ENCRYPTION SUMMARY")
        print(f"{'='*60}")
        print(f"Total letters found:      {total_count}")
        print(f"Successfully encrypted:   {encrypted_count}")
        print(f"Failed:                   {failed_count}")
        print(f"⏰ Completed at: {datetime.now(timezone.utc)}")
        print(f"{'='*60}\n")
        
        # Verify encryption by actually trying to decrypt
        from website.encryption import decrypt_text
        remaining_unencrypted = []
        all_letters = Letter.query.all()
        for letter in all_letters:
            title_enc = True
            content_enc = True
            
            if letter.title:
                try:
                    decrypt_text(letter.title)
                    title_enc = True  # Successfully decrypted = encrypted
                except:
                    title_enc = False  # Decryption failed = not encrypted
            
            if letter.content:
                try:
                    decrypt_text(letter.content)
                    content_enc = True  # Successfully decrypted = encrypted
                except:
                    content_enc = False  # Decryption failed = not encrypted
            
            if not title_enc or not content_enc:
                remaining_unencrypted.append(letter.id)
        
        if remaining_unencrypted == []:
            print("✅ SUCCESS: All letters are now encrypted!")
        else:
            print(f"⚠️  WARNING: {len(remaining_unencrypted)} letters remain unencrypted")
            print(f"   Letter IDs: {remaining_unencrypted}")
        
        return (total_count, encrypted_count, failed_count)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Encrypt all unencrypted letters in the database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python encrypt_letters.py                    # Encrypt all unencrypted letters
  python encrypt_letters.py --dry-run          # Show what would be encrypted
  python encrypt_letters.py --diagnose         # Show status of all letters
        """
    )
    parser.add_argument('--dry-run', action='store_true', help='Show what would be encrypted without making changes')
    parser.add_argument('--diagnose', action='store_true', help='Show encryption status of all letters')
    parser.add_argument('--letter-ids', nargs='+', type=int, help='Specific letter IDs to encrypt')
    
    args = parser.parse_args()
    
    print("🔐 Letter Encryption Script")
    print("="*60)
    
    if args.diagnose:
        needs_encryption = diagnose_letters()
        if needs_encryption:
            print(f"\n💡 Tip: Run 'python encrypt_letters.py' to encrypt {len(needs_encryption)} letters")
    else:
        total, encrypted, failed = encrypt_letters(
            letter_ids=args.letter_ids,
            dry_run=args.dry_run
        )
        
        if failed > 0:
            sys.exit(1)
        else:
            sys.exit(0)

