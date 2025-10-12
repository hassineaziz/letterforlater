#!/usr/bin/env python3
"""
Cleanup script for expired temporary media files.
Run this script periodically (e.g., via cron) to clean up orphaned media files.
"""

import os
import sys
from datetime import datetime, timezone, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app
from website.models import MediaAttachment, db

def cleanup_expired_media():
    """Clean up expired temporary media files"""
    app = create_app()
    
    with app.app_context():
        try:
            # Find expired temporary media
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            expired_media = MediaAttachment.query.filter(
                MediaAttachment.is_temporary == True,
                MediaAttachment.expires_at < cutoff_time
            ).all()
            
            if not expired_media:
                print("No expired media files found.")
                return 0
            
            print(f"Found {len(expired_media)} expired media files to clean up...")
            
            cleaned_count = 0
            for media in expired_media:
                try:
                    # Delete file from filesystem
                    if media.file_path and os.path.exists(media.file_path):
                        os.remove(media.file_path)
                        print(f"Deleted file: {media.file_path}")
                    
                    # Delete thumbnail if exists
                    if media.thumbnail_path and os.path.exists(media.thumbnail_path):
                        os.remove(media.thumbnail_path)
                        print(f"Deleted thumbnail: {media.thumbnail_path}")
                    
                    # Delete from database
                    db.session.delete(media)
                    cleaned_count += 1
                    
                except Exception as e:
                    print(f"Error cleaning up media {media.id}: {str(e)}")
                    continue
            
            db.session.commit()
            print(f"Successfully cleaned up {cleaned_count} expired media files.")
            
            return cleaned_count
            
        except Exception as e:
            print(f"Error in cleanup: {str(e)}")
            db.session.rollback()
            return 0

def cleanup_orphaned_files():
    """Clean up orphaned files that don't have database records"""
    app = create_app()
    
    with app.app_context():
        try:
            upload_dir = os.path.join(os.getcwd(), 'website', 'static', 'uploads')
            if not os.path.exists(upload_dir):
                print(f"Upload directory not found: {upload_dir}")
                return 0
            
            orphaned_count = 0
            
            # Walk through upload directory
            for root, dirs, files in os.walk(upload_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # Skip non-media files
                    if not any(file.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3', '.wav', '.m4a']):
                        continue
                    
                    # Check if file has database record
                    # Extract media ID from filename (assuming format: media_abc123.ext)
                    if file.startswith('media_'):
                        media_id = file.split('.')[0].replace('media_', '')
                        
                        # Check if media exists in database
                        media = MediaAttachment.query.filter(
                            MediaAttachment.file_path.like(f'%{file}%')
                        ).first()
                        
                        if not media:
                            try:
                                os.remove(file_path)
                                print(f"Deleted orphaned file: {file_path}")
                                orphaned_count += 1
                            except Exception as e:
                                print(f"Error deleting orphaned file {file_path}: {str(e)}")
            
            print(f"Cleaned up {orphaned_count} orphaned files.")
            return orphaned_count
            
        except Exception as e:
            print(f"Error in orphaned file cleanup: {str(e)}")
            return 0

def get_media_stats():
    """Get media statistics"""
    app = create_app()
    
    with app.app_context():
        try:
            total_media = MediaAttachment.query.count()
            temp_media = MediaAttachment.query.filter_by(is_temporary=True).count()
            permanent_media = total_media - temp_media
            
            total_size = db.session.query(db.func.sum(MediaAttachment.file_size)).scalar() or 0
            
            print("=== Media Statistics ===")
            print(f"Total media files: {total_media}")
            print(f"Temporary media: {temp_media}")
            print(f"Permanent media: {permanent_media}")
            print(f"Total size: {total_size / (1024*1024):.2f} MB")
            
            # Check for expired media
            expired_count = MediaAttachment.query.filter(
                MediaAttachment.is_temporary == True,
                MediaAttachment.expires_at < datetime.now(timezone.utc)
            ).count()
            
            print(f"Expired temporary media: {expired_count}")
            
        except Exception as e:
            print(f"Error getting media stats: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up expired temporary media files')
    parser.add_argument('--expired', action='store_true', help='Clean up expired temporary media')
    parser.add_argument('--orphaned', action='store_true', help='Clean up orphaned files')
    parser.add_argument('--stats', action='store_true', help='Show media statistics')
    parser.add_argument('--all', action='store_true', help='Run all cleanup operations')
    
    args = parser.parse_args()
    
    if args.all or args.expired:
        print("Cleaning up expired temporary media...")
        cleanup_expired_media()
    
    if args.all or args.orphaned:
        print("Cleaning up orphaned files...")
        cleanup_orphaned_files()
    
    if args.all or args.stats:
        get_media_stats()
    
    if not any([args.expired, args.orphaned, args.stats, args.all]):
        print("No operation specified. Use --help for usage information.")
        print("Recommended: python cleanup_expired_media.py --all")
