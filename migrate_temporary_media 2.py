#!/usr/bin/env python3
"""
Migration script to convert temporary media files to permanent storage
This script handles the transition from temporary to permanent media storage workflow.
"""

import os
import sys
from datetime import datetime, timezone

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db
from website.models import MediaAttachment, Letter
from website.s3_config import s3_config
from website.s3_media_handler import s3_media_handler

def migrate_temporary_media():
    """Migrate all temporary media files to permanent storage"""
    print("🔄 Starting migration of temporary media files...")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Find all media files (they are all permanent now)
            temp_media = MediaAttachment.query.all()
            
            if not temp_media:
                print("✅ No temporary media files found. Migration complete!")
                return True
            
            print(f"📁 Found {len(temp_media)} media files to verify...")
            
            migrated_count = 0
            error_count = 0
            
            for media in temp_media:
                try:
                    print(f"🔄 Migrating: {media.file_name} (ID: {media.id})")
                    
                    # Check if the file exists in S3
                    if not s3_config.file_exists(media.file_path):
                        print(f"⚠️  File not found in S3: {media.file_path}")
                        error_count += 1
                        continue
                    
                    # Create a draft letter for this media if it doesn't have one
                    if not media.letter_id:
                        draft_letter = Letter(
                            title=f"Migrated Letter for {media.file_name}",
                            content="This letter was created during migration to preserve media files.",
                            recipient_name="",
                            recipient_email="",
                            delivery_type="date",
                            status="draft",
                            user_id=media.user_id
                        )
                        db.session.add(draft_letter)
                        db.session.flush()  # Get the ID
                        media.letter_id = draft_letter.id
                        print(f"📝 Created draft letter {draft_letter.id} for media {media.id}")
                    
                    # Move file from temp folder to permanent letter folder
                    old_key = media.file_path
                    new_folder = s3_config.get_letter_folder(media.user_id, media.letter_id)
                    file_ext = old_key.split('.')[-1]
                    new_key = s3_config.get_file_key(new_folder, f"{media.id}.{file_ext}")
                    
                    # Copy file to new location
                    s3_config.s3_client.copy_object(
                        Bucket=s3_config.s3_bucket,
                        CopySource={'Bucket': s3_config.s3_bucket, 'Key': old_key},
                        Key=new_key
                    )
                    
                    # Delete old file
                    s3_config.delete_file(old_key)
                    
                    # Update database record
                    media.file_path = new_key
                    
                    migrated_count += 1
                    print(f"✅ Migrated: {media.file_name} -> {new_key}")
                    
                except Exception as e:
                    print(f"❌ Error migrating {media.file_name}: {str(e)}")
                    error_count += 1
                    continue
            
            # Commit all changes
            db.session.commit()
            
            print(f"\n🎉 Migration completed!")
            print(f"✅ Successfully migrated: {migrated_count} files")
            print(f"❌ Errors: {error_count} files")
            
            return error_count == 0
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            return False

def cleanup_orphaned_temp_files():
    """Clean up any orphaned temporary files in S3"""
    print("\n🧹 Cleaning up orphaned temporary files...")
    
    app = create_app()
    
    with app.app_context():
        try:
            # List all files in temp folders
            temp_prefixes = []
            for user_id in range(1, 1000):  # Check first 1000 users
                temp_prefix = f"{user_id}/temp/"
                temp_prefixes.append(temp_prefix)
            
            cleaned_count = 0
            for prefix in temp_prefixes:
                try:
                    # List objects with this prefix
                    response = s3_config.s3_client.list_objects_v2(
                        Bucket=s3_config.s3_bucket,
                        Prefix=prefix
                    )
                    
                    if 'Contents' in response:
                        for obj in response['Contents']:
                            # Check if this file has a database record
                            file_key = obj['Key']
                            media = MediaAttachment.query.filter_by(file_path=file_key).first()
                            
                            if not media:
                                # No database record, safe to delete
                                s3_config.delete_file(file_key)
                                cleaned_count += 1
                                print(f"🗑️  Deleted orphaned file: {file_key}")
                
                except Exception as e:
                    print(f"⚠️  Error checking prefix {prefix}: {str(e)}")
                    continue
            
            print(f"✅ Cleaned up {cleaned_count} orphaned files")
            return True
            
        except Exception as e:
            print(f"❌ Cleanup failed: {str(e)}")
            return False

def verify_migration():
    """Verify that the migration was successful"""
    print("\n🔍 Verifying migration...")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Check that all media has letter_id (already done in schema update)
            media_without_letter = MediaAttachment.query.filter_by(letter_id=None).all()
            
            if media_without_letter:
                print(f"❌ Found {len(media_without_letter)} media files without letter_id!")
                for media in media_without_letter:
                    print(f"   - {media.file_name} (ID: {media.id})")
                return False
            
            print("✅ Migration verification passed!")
            print("✅ All media files are now permanent and attached to letters")
            return True
            
        except Exception as e:
            print(f"❌ Verification failed: {str(e)}")
            return False

def main():
    """Main migration function"""
    print("🚀 Legacy Letter Media Migration Script")
    print("=" * 50)
    
    # Step 1: Migrate temporary media
    if not migrate_temporary_media():
        print("❌ Migration failed!")
        return False
    
    # Step 2: Clean up orphaned files
    if not cleanup_orphaned_temp_files():
        print("⚠️  Cleanup had issues, but continuing...")
    
    # Step 3: Verify migration
    if not verify_migration():
        print("❌ Migration verification failed!")
        return False
    
    print("\n🎉 Migration completed successfully!")
    print("✅ All temporary media has been converted to permanent storage")
    print("✅ Media files are now only deleted when their associated letter is deleted")
    print("✅ The new permanent storage workflow is now active")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
