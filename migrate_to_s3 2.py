#!/usr/bin/env python3
"""
Migration script to move existing media files from local storage to AWS S3
This script handles both legacy session-based files and database-backed files
"""

import os
import sys
import shutil
import mimetypes
from datetime import datetime
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db
from website.models import MediaAttachment, User, Letter
from website.s3_config import s3_config

class MediaMigration:
    def __init__(self):
        self.app = create_app()
        self.app.app_context().push()
        
        self.local_uploads_path = os.path.join(os.getcwd(), 'website', 'static', 'uploads')
        self.migrated_count = 0
        self.failed_count = 0
        self.errors = []
        
    def migrate_all_files(self, dry_run=False):
        """Migrate all existing media files to S3"""
        print(f"Starting media migration to S3 bucket: {s3_config.s3_bucket}")
        print(f"Dry run: {dry_run}")
        print("-" * 50)
        
        # Migrate database-backed files
        self.migrate_database_files(dry_run)
        
        # Migrate legacy session files
        self.migrate_legacy_files(dry_run)
        
        # Migrate blog images
        self.migrate_blog_images(dry_run)
        
        # Print summary
        self.print_summary()
        
    def migrate_database_files(self, dry_run=False):
        """Migrate files that have database records"""
        print("\n=== Migrating Database-Backed Files ===")
        
        # Get all media attachments that are not S3 stored
        media_files = MediaAttachment.query.filter_by(is_s3_stored=False).all()
        
        print(f"Found {len(media_files)} database-backed files to migrate")
        
        for media in media_files:
            try:
                local_path = media.file_path
                
                # Check if file exists locally
                if not os.path.exists(local_path):
                    print(f"⚠️  File not found: {local_path}")
                    self.failed_count += 1
                    continue
                
                # Determine S3 key based on user and letter
                if media.letter_id:
                    s3_key = s3_config.get_file_key(
                        s3_config.get_letter_folder(media.user_id, media.letter_id),
                        f"{media.id}.{self.get_file_extension(local_path)}"
                    )
                else:
                    s3_key = s3_config.get_file_key(
                        s3_config.get_temp_folder(media.user_id),
                        f"{media.id}.{self.get_file_extension(local_path)}"
                    )
                
                print(f"Migrating: {local_path} -> s3://{s3_config.s3_bucket}/{s3_key}")
                
                if not dry_run:
                    # Upload to S3
                    s3_config.s3_client.upload_file(
                        local_path,
                        s3_config.s3_bucket,
                        s3_key
                    )
                    
                    # Update database record
                    media.file_path = s3_key
                    media.is_s3_stored = True
                    media.s3_bucket = s3_config.s3_bucket
                    
                    # Get S3 metadata
                    s3_metadata = s3_config.get_file_metadata(s3_key)
                    if s3_metadata:
                        media.s3_etag = s3_metadata['etag']
                        media.file_size = s3_metadata['size']
                        media.mime_type = s3_metadata['content_type']
                
                self.migrated_count += 1
                
            except Exception as e:
                error_msg = f"Failed to migrate {media.file_path}: {str(e)}"
                print(f"❌ {error_msg}")
                self.errors.append(error_msg)
                self.failed_count += 1
        
        if not dry_run:
            db.session.commit()
            print(f"✅ Updated {self.migrated_count} database records")
    
    def migrate_legacy_files(self, dry_run=False):
        """Migrate legacy session-based files"""
        print("\n=== Migrating Legacy Session Files ===")
        
        # Find all media_*.ext files in the root uploads directory
        legacy_files = []
        for filename in os.listdir(self.local_uploads_path):
            if filename.startswith('media_') and os.path.isfile(os.path.join(self.local_uploads_path, filename)):
                legacy_files.append(filename)
        
        print(f"Found {len(legacy_files)} legacy files to migrate")
        
        for filename in legacy_files:
            try:
                local_path = os.path.join(self.local_uploads_path, filename)
                
                # Try to determine user from file metadata or use a default
                # For legacy files, we'll put them in a special folder
                s3_key = s3_config.get_file_key('legacy/', filename)
                
                print(f"Migrating: {local_path} -> s3://{s3_config.s3_bucket}/{s3_key}")
                
                if not dry_run:
                    # Upload to S3
                    s3_config.s3_client.upload_file(
                        local_path,
                        s3_config.s3_bucket,
                        s3_key
                    )
                
                self.migrated_count += 1
                
            except Exception as e:
                error_msg = f"Failed to migrate legacy file {filename}: {str(e)}"
                print(f"❌ {error_msg}")
                self.errors.append(error_msg)
                self.failed_count += 1
    
    def migrate_blog_images(self, dry_run=False):
        """Migrate blog images"""
        print("\n=== Migrating Blog Images ===")
        
        blog_path = os.path.join(self.local_uploads_path, 'blog')
        if not os.path.exists(blog_path):
            print("No blog images directory found")
            return
        
        blog_files = []
        for filename in os.listdir(blog_path):
            if os.path.isfile(os.path.join(blog_path, filename)):
                blog_files.append(filename)
        
        print(f"Found {len(blog_files)} blog images to migrate")
        
        for filename in blog_files:
            try:
                local_path = os.path.join(blog_path, filename)
                s3_key = s3_config.get_file_key(s3_config.get_blog_folder(), filename)
                
                print(f"Migrating: {local_path} -> s3://{s3_config.s3_bucket}/{s3_key}")
                
                if not dry_run:
                    # Upload to S3
                    s3_config.s3_client.upload_file(
                        local_path,
                        s3_config.s3_bucket,
                        s3_key
                    )
                
                self.migrated_count += 1
                
            except Exception as e:
                error_msg = f"Failed to migrate blog image {filename}: {str(e)}"
                print(f"❌ {error_msg}")
                self.errors.append(error_msg)
                self.failed_count += 1
    
    def get_file_extension(self, file_path):
        """Get file extension from path"""
        return os.path.splitext(file_path)[1][1:]  # Remove the dot
    
    def cleanup_local_files(self, dry_run=False):
        """Remove local files after successful migration"""
        if dry_run:
            print("\n=== Cleanup Preview (Dry Run) ===")
            print("Would remove local files after migration")
            return
        
        print("\n=== Cleaning Up Local Files ===")
        
        # Remove database-backed files that are now in S3
        s3_media = MediaAttachment.query.filter_by(is_s3_stored=True).all()
        
        for media in s3_media:
            if media.file_path.startswith('/') or '\\' in media.file_path:  # Local path
                local_path = media.file_path
                if os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                        print(f"Removed: {local_path}")
                    except Exception as e:
                        print(f"Failed to remove {local_path}: {str(e)}")
        
        # Remove legacy files
        for filename in os.listdir(self.local_uploads_path):
            if filename.startswith('media_'):
                local_path = os.path.join(self.local_uploads_path, filename)
                try:
                    os.remove(local_path)
                    print(f"Removed legacy file: {local_path}")
                except Exception as e:
                    print(f"Failed to remove {local_path}: {str(e)}")
        
        # Remove blog images
        blog_path = os.path.join(self.local_uploads_path, 'blog')
        if os.path.exists(blog_path):
            for filename in os.listdir(blog_path):
                local_path = os.path.join(blog_path, filename)
                try:
                    os.remove(local_path)
                    print(f"Removed blog image: {local_path}")
                except Exception as e:
                    print(f"Failed to remove {local_path}: {str(e)}")
    
    def print_summary(self):
        """Print migration summary"""
        print("\n" + "=" * 50)
        print("MIGRATION SUMMARY")
        print("=" * 50)
        print(f"✅ Successfully migrated: {self.migrated_count} files")
        print(f"❌ Failed migrations: {self.failed_count} files")
        
        if self.errors:
            print("\nErrors encountered:")
            for error in self.errors:
                print(f"  - {error}")
        
        print(f"\nTotal files processed: {self.migrated_count + self.failed_count}")
        print("=" * 50)

def main():
    """Main migration function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate media files to AWS S3')
    parser.add_argument('--dry-run', action='store_true', help='Preview migration without making changes')
    parser.add_argument('--cleanup', action='store_true', help='Remove local files after migration')
    
    args = parser.parse_args()
    
    try:
        migration = MediaMigration()
        
        # Run migration
        migration.migrate_all_files(dry_run=args.dry_run)
        
        # Cleanup if requested
        if args.cleanup and not args.dry_run:
            migration.cleanup_local_files(dry_run=False)
        
        if args.dry_run:
            print("\n🔍 This was a dry run. No files were actually migrated.")
            print("Run without --dry-run to perform the actual migration.")
        
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
