#!/usr/bin/env python3
"""
S3 Media Maintenance Utilities
Handles cleanup, monitoring, and maintenance of S3 media files
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db
from website.models import MediaAttachment, User, Letter
from website.s3_config import s3_config
from website.s3_media_handler import s3_media_handler

class S3Maintenance:
    def __init__(self):
        self.app = create_app()
        self.app.app_context().push()
        
    def cleanup_expired_media(self, dry_run=False):
        """Clean up expired temporary media files"""
        print("=== Cleaning Up Expired Temporary Media ===")
        
        if dry_run:
            print("🔍 Dry run mode - no files will be deleted")
        
        try:
            cleaned_count = s3_media_handler.cleanup_expired_media()
            print(f"✅ Cleaned up {cleaned_count} expired media files")
            return cleaned_count
        except Exception as e:
            print(f"❌ Cleanup failed: {str(e)}")
            return 0
    
    def verify_s3_integrity(self):
        """Verify that all database records have corresponding S3 files"""
        print("=== Verifying S3 Integrity ===")
        
        s3_media = MediaAttachment.query.filter_by(is_s3_stored=True).all()
        missing_files = []
        corrupted_files = []
        
        print(f"Checking {len(s3_media)} S3-stored media files...")
        
        for media in s3_media:
            try:
                if not s3_config.file_exists(media.file_path):
                    missing_files.append({
                        'id': media.id,
                        'file_path': media.file_path,
                        'user_id': media.user_id,
                        'letter_id': media.letter_id
                    })
                else:
                    # Check file size matches
                    s3_metadata = s3_config.get_file_metadata(media.file_path)
                    if s3_metadata and s3_metadata['size'] != media.file_size:
                        corrupted_files.append({
                            'id': media.id,
                            'file_path': media.file_path,
                            'db_size': media.file_size,
                            's3_size': s3_metadata['size']
                        })
            except Exception as e:
                print(f"Error checking {media.file_path}: {str(e)}")
        
        print(f"✅ Found {len(s3_media) - len(missing_files) - len(corrupted_files)} valid files")
        
        if missing_files:
            print(f"❌ Missing files: {len(missing_files)}")
            for file_info in missing_files[:10]:  # Show first 10
                print(f"  - ID {file_info['id']}: {file_info['file_path']}")
            if len(missing_files) > 10:
                print(f"  ... and {len(missing_files) - 10} more")
        
        if corrupted_files:
            print(f"⚠️  Size mismatches: {len(corrupted_files)}")
            for file_info in corrupted_files[:10]:  # Show first 10
                print(f"  - ID {file_info['id']}: DB={file_info['db_size']}, S3={file_info['s3_size']}")
            if len(corrupted_files) > 10:
                print(f"  ... and {len(corrupted_files) - 10} more")
        
        return {
            'total_checked': len(s3_media),
            'missing_files': missing_files,
            'corrupted_files': corrupted_files
        }
    
    def get_storage_stats(self):
        """Get comprehensive storage statistics"""
        print("=== Storage Statistics ===")
        
        # Database stats
        total_media = MediaAttachment.query.count()
        s3_media = MediaAttachment.query.filter_by(is_s3_stored=True).count()
        local_media = MediaAttachment.query.filter_by(is_s3_stored=False).count()
        temp_media = MediaAttachment.query.filter_by(is_temporary=True).count()
        permanent_media = MediaAttachment.query.filter_by(is_temporary=False).count()
        
        # Size stats
        total_size = db.session.query(db.func.sum(MediaAttachment.file_size)).scalar() or 0
        s3_size = db.session.query(db.func.sum(MediaAttachment.file_size))\
            .filter_by(is_s3_stored=True).scalar() or 0
        
        # User stats
        users_with_media = db.session.query(db.func.count(db.func.distinct(MediaAttachment.user_id))).scalar()
        total_users = User.query.count()
        
        print(f"📊 Database Statistics:")
        print(f"  Total media files: {total_media}")
        print(f"  S3-stored files: {s3_media}")
        print(f"  Local files: {local_media}")
        print(f"  Temporary files: {temp_media}")
        print(f"  Permanent files: {permanent_media}")
        print(f"")
        print(f"💾 Storage Statistics:")
        print(f"  Total size: {self.format_size(total_size)}")
        print(f"  S3 size: {self.format_size(s3_size)}")
        print(f"  Local size: {self.format_size(total_size - s3_size)}")
        print(f"")
        print(f"👥 User Statistics:")
        print(f"  Users with media: {users_with_media}")
        print(f"  Total users: {total_users}")
        print(f"  Media adoption rate: {(users_with_media/total_users*100):.1f}%")
        
        return {
            'total_media': total_media,
            's3_media': s3_media,
            'local_media': local_media,
            'temp_media': temp_media,
            'permanent_media': permanent_media,
            'total_size': total_size,
            's3_size': s3_size,
            'users_with_media': users_with_media,
            'total_users': total_users
        }
    
    def cleanup_orphaned_files(self, dry_run=False):
        """Clean up S3 files that don't have database records"""
        print("=== Cleaning Up Orphaned S3 Files ===")
        
        if dry_run:
            print("🔍 Dry run mode - no files will be deleted")
        
        # Get all S3 files
        try:
            response = s3_config.s3_client.list_objects_v2(Bucket=s3_config.s3_bucket)
            s3_files = response.get('Contents', [])
        except Exception as e:
            print(f"❌ Failed to list S3 files: {str(e)}")
            return 0
        
        print(f"Found {len(s3_files)} files in S3")
        
        # Get all database file paths
        db_files = set()
        for media in MediaAttachment.query.filter_by(is_s3_stored=True).all():
            db_files.add(media.file_path)
        
        orphaned_files = []
        for s3_file in s3_files:
            if s3_file['Key'] not in db_files:
                orphaned_files.append(s3_file)
        
        print(f"Found {len(orphaned_files)} orphaned files")
        
        if not dry_run and orphaned_files:
            deleted_count = 0
            for s3_file in orphaned_files:
                try:
                    s3_config.s3_client.delete_object(
                        Bucket=s3_config.s3_bucket,
                        Key=s3_file['Key']
                    )
                    deleted_count += 1
                    print(f"Deleted: {s3_file['Key']}")
                except Exception as e:
                    print(f"Failed to delete {s3_file['Key']}: {str(e)}")
            
            print(f"✅ Deleted {deleted_count} orphaned files")
            return deleted_count
        else:
            print(f"Would delete {len(orphaned_files)} orphaned files")
            return len(orphaned_files)
    
    def generate_user_report(self, user_id):
        """Generate detailed report for a specific user"""
        user = User.query.get(user_id)
        if not user:
            print(f"❌ User {user_id} not found")
            return None
        
        print(f"=== User Report: {user.first_name} {user.last_name} ({user.email}) ===")
        
        # Get user's media
        user_media = MediaAttachment.query.filter_by(user_id=user_id).all()
        
        print(f"Total media files: {len(user_media)}")
        
        # Group by type
        by_type = {}
        total_size = 0
        
        for media in user_media:
            media_type = media.file_type
            if media_type not in by_type:
                by_type[media_type] = {'count': 0, 'size': 0}
            
            by_type[media_type]['count'] += 1
            by_type[media_type]['size'] += media.file_size
            total_size += media.file_size
        
        print(f"Total size: {self.format_size(total_size)}")
        print(f"")
        
        for media_type, stats in by_type.items():
            print(f"{media_type.title()} files:")
            print(f"  Count: {stats['count']}")
            print(f"  Size: {self.format_size(stats['size'])}")
            print(f"  Average size: {self.format_size(stats['size'] / stats['count'])}")
            print(f"")
        
        # Temporary vs permanent
        temp_count = sum(1 for m in user_media if m.is_temporary)
        perm_count = len(user_media) - temp_count
        
        print(f"Temporary files: {temp_count}")
        print(f"Permanent files: {perm_count}")
        
        return {
            'user': user,
            'total_files': len(user_media),
            'total_size': total_size,
            'by_type': by_type,
            'temp_count': temp_count,
            'perm_count': perm_count
        }
    
    def format_size(self, size_bytes):
        """Format size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"

def main():
    """Main maintenance function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='S3 Media Maintenance Utilities')
    parser.add_argument('--cleanup-expired', action='store_true', help='Clean up expired temporary media')
    parser.add_argument('--verify-integrity', action='store_true', help='Verify S3 file integrity')
    parser.add_argument('--storage-stats', action='store_true', help='Show storage statistics')
    parser.add_argument('--cleanup-orphaned', action='store_true', help='Clean up orphaned S3 files')
    parser.add_argument('--user-report', type=int, help='Generate report for specific user ID')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without making them')
    
    args = parser.parse_args()
    
    if not any([args.cleanup_expired, args.verify_integrity, args.storage_stats, 
                args.cleanup_orphaned, args.user_report]):
        parser.print_help()
        return
    
    try:
        maintenance = S3Maintenance()
        
        if args.cleanup_expired:
            maintenance.cleanup_expired_media(dry_run=args.dry_run)
        
        if args.verify_integrity:
            maintenance.verify_s3_integrity()
        
        if args.storage_stats:
            maintenance.get_storage_stats()
        
        if args.cleanup_orphaned:
            maintenance.cleanup_orphaned_files(dry_run=args.dry_run)
        
        if args.user_report:
            maintenance.generate_user_report(args.user_report)
        
    except Exception as e:
        print(f"Maintenance failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
