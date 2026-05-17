"""
AWS S3 Media Handler for Legacy Letter Application
Handles all media operations using S3 with presigned URLs and database metadata
"""

import os
import uuid
import mimetypes
from datetime import datetime, timezone, timedelta
from flask import jsonify, request
from flask_login import current_user
from werkzeug.utils import secure_filename
from .models import MediaAttachment, db
from .s3_config import s3_config

class S3MediaHandler:
    """Production-ready S3 media handler with security and scalability"""
    
    def __init__(self):
        self.max_file_size = 100 * 1024 * 1024  # 100MB limit
        self.allowed_extensions = {
            'image': {'png', 'jpg', 'jpeg', 'gif', 'webp'},
            'video': {'mp4'},  # MP4 only for maximum browser compatibility
            'audio': {'mp3', 'wav', 'm4a'}  # MP3, WAV, and M4A for browser compatibility
        }
    
    def _validate_file(self, filename, content_type, file_size=None):
        """Validate uploaded file"""
        if not filename:
            return False, "No filename provided"
        
        # Check file size if provided
        if file_size and file_size > self.max_file_size:
            return False, f"File too large. Maximum size: {self.max_file_size // (1024*1024)}MB"
        
        # Check file extension
        filename = secure_filename(filename)
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        # Determine media type from extension
        media_type = None
        for mtype, extensions in self.allowed_extensions.items():
            if file_ext in extensions:
                media_type = mtype
                break
        
        if not media_type:
            return False, f"Invalid file type. Allowed: {', '.join(['.'.join(exts) for exts in self.allowed_extensions.values()])}"
        
        return True, {'media_type': media_type, 'file_ext': file_ext, 'filename': filename}
    
    def _determine_content_type(self, media_type, file_ext):
        """Determine proper MIME type"""
        mime_types = {
            'image': {
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'gif': 'image/gif',
                'webp': 'image/webp'
            },
            'video': {
                'mp4': 'video/mp4'
            },
            'audio': {
                'mp3': 'audio/mpeg',
                'wav': 'audio/wav',
                'm4a': 'audio/mp4'
            }
        }
        
        return mime_types.get(media_type, {}).get(file_ext, 'application/octet-stream')
    
    def generate_upload_url(self, user_id, filename, media_type, letter_id):
        """Generate presigned URL for direct S3 upload - requires letter_id for permanent storage"""
        try:
            # Validate letter_id is provided
            if not letter_id:
                return jsonify({'success': False, 'error': 'Letter ID is required for media upload'}), 400
            
            # Validate file extension matches the provided media type
            if not filename:
                return jsonify({'success': False, 'error': 'No filename provided'}), 400
            
            filename = secure_filename(filename)
            file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            
            if not file_ext:
                return jsonify({'success': False, 'error': 'No file extension found'}), 400
            
            # Check if the file extension matches the provided media type
            if media_type not in self.allowed_extensions:
                return jsonify({'success': False, 'error': f'Invalid media type: {media_type}'}), 400
            
            if file_ext not in self.allowed_extensions[media_type]:
                return jsonify({'success': False, 'error': f'File extension .{file_ext} does not match media type {media_type}'}), 400
            
            validation_data = {
                'media_type': media_type,
                'file_ext': file_ext,
                'filename': filename
            }
            
            # Generate unique filename
            file_id = str(uuid.uuid4())
            file_ext = validation_data['file_ext']
            unique_filename = f"{file_id}.{file_ext}"
            
            # Use permanent letter folder only
            folder_path = s3_config.get_letter_folder(user_id, letter_id)
            s3_key = s3_config.get_file_key(folder_path, unique_filename)
            
            # Determine content type
            content_type = self._determine_content_type(validation_data['media_type'], file_ext)
            
            # Generate presigned URL
            presigned_data = s3_config.generate_presigned_upload_url(s3_key, content_type)
            
            # Create permanent database record
            media_attachment = MediaAttachment(
                user_id=user_id,
                letter_id=letter_id,
                file_name=validation_data['filename'],
                file_path=s3_key,  # Store S3 key as file_path
                file_type=validation_data['media_type'],
                mime_type=content_type,
                file_size=0  # Will be updated after upload
            )
            
            db.session.add(media_attachment)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'media_id': media_attachment.id,
                'upload_url': presigned_data['url'],
                'upload_fields': presigned_data['fields'],
                'file_name': validation_data['filename'],
                'file_type': validation_data['media_type'],
                's3_key': s3_key
            }), 200
            
        except Exception as e:
            print(f"Error generating upload URL: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Failed to generate upload URL'}), 500
    
    def confirm_upload(self, media_id, user_id, file_size):
        """Confirm successful upload and update metadata"""
        try:
            media = MediaAttachment.query.filter_by(id=media_id, user_id=user_id).first()
            if not media:
                return jsonify({'success': False, 'error': 'Media not found'}), 404
            
            # Update file size
            media.file_size = file_size
            
            # Verify file exists in S3 (with a small retry for eventual consistency)
            import time
            exists = False
            for _ in range(3):
                if s3_config.file_exists(media.file_path):
                    exists = True
                    break
                time.sleep(0.5)
            
            if not exists:
                print(f"ERROR: File {media.file_path} not found in S3 after 3 retries")
                return jsonify({'success': False, 'error': 'File not found in S3 - please try again in a moment'}), 404
            
            # Get additional metadata from S3
            s3_metadata = s3_config.get_file_metadata(media.file_path)
            if s3_metadata:
                # If S3 detected the wrong content type, fix it
                if s3_metadata['content_type'] == 'binary/octet-stream':
                    # Set the correct content type based on file extension
                    correct_content_type = self._determine_content_type(media.file_type, media.file_path.split('.')[-1])
                    try:
                        # Update the S3 object with correct content type
                        s3_config.s3_client.copy_object(
                            Bucket=s3_config.s3_bucket,
                            CopySource={'Bucket': s3_config.s3_bucket, 'Key': media.file_path},
                            Key=media.file_path,
                            MetadataDirective='REPLACE',
                            ContentType=correct_content_type
                        )
                        media.mime_type = correct_content_type
                        print(f"Updated S3 content type to: {correct_content_type}")
                    except Exception as e:
                        print(f"Failed to update S3 content type: {e}")
                        media.mime_type = s3_metadata['content_type']
                else:
                    # Use the detected content type from S3
                    media.mime_type = s3_metadata['content_type']
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'media_id': media_id,
                'file_size': file_size
            }), 200
            
        except Exception as e:
            print(f"Error confirming upload: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Failed to confirm upload'}), 500
    
    def generate_download_url(self, media_id, user_id):
        """Generate presigned URL for file download"""
        try:
            from .models import RecipientInvite
            
            # First check if user owns the media
            media = MediaAttachment.query.filter_by(id=media_id, user_id=user_id).first()
            
            # If not owned by user, check if they have access as a recipient
            if not media:
                # Check if user is a recipient of a letter containing this media
                media = MediaAttachment.query.get(media_id)
                if media:
                    # Check if current user is a recipient of the letter containing this media
                    recipient_access = RecipientInvite.query.filter(
                        RecipientInvite.letter_id == media.letter_id,
                        RecipientInvite.recipient_user_id == user_id,
                        RecipientInvite.registered_at.isnot(None)
                    ).first()
                    
                    if not recipient_access:
                        media = None  # No access
            
            if not media:
                return jsonify({'error': 'Media not found'}), 404
            
            # Check if file exists in S3
            if not s3_config.file_exists(media.file_path):
                return jsonify({'error': 'File not found'}), 404
            
            # Generate presigned download URL
            download_url = s3_config.generate_presigned_download_url(media.file_path)
            
            return jsonify({
                'success': True,
                'download_url': download_url,
                'file_name': media.file_name,
                'mime_type': media.mime_type
            }), 200
            
        except Exception as e:
            print(f"Error generating download URL: {str(e)}")
            return jsonify({'error': 'Failed to generate download URL'}), 500
    
    def delete_letter_media(self, letter_id, user_id):
        """Delete all media associated with a letter"""
        try:
            # Get all media for this letter
            media_files = MediaAttachment.query.filter_by(
                letter_id=letter_id,
                user_id=user_id
            ).all()
            
            if not media_files:
                return jsonify({'success': True, 'deleted_count': 0})
            
            deleted_count = 0
            for media in media_files:
                try:
                    # Delete from S3
                    if s3_config.file_exists(media.file_path):
                        s3_config.delete_file(media.file_path)
                    
                    # Delete thumbnail if exists
                    if media.thumbnail_path and s3_config.file_exists(media.thumbnail_path):
                        s3_config.delete_file(media.thumbnail_path)
                    
                    # Delete from database
                    db.session.delete(media)
                    deleted_count += 1
                    
                except Exception as e:
                    print(f"Error deleting media {media.id}: {str(e)}")
                    continue
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            print(f"Error deleting letter media: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Failed to delete letter media'}), 500
    
    def delete_media(self, media_id, user_id):
        """Delete media file and database record"""
        try:
            media = MediaAttachment.query.filter_by(id=media_id, user_id=user_id).first()
            if not media:
                return jsonify({'error': 'Media not found'}), 404
            
            # Delete file from S3
            if s3_config.file_exists(media.file_path):
                s3_config.delete_file(media.file_path)
            
            # Delete thumbnail if exists
            if media.thumbnail_path and s3_config.file_exists(media.thumbnail_path):
                s3_config.delete_file(media.thumbnail_path)
            
            # Delete from database
            db.session.delete(media)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Media deleted'})
            
        except Exception as e:
            print(f"Error deleting media: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Failed to delete media'}), 500
    
    
    def get_user_media_stats(self, user_id):
        """Get media statistics for a user"""
        try:
            total_media = MediaAttachment.query.filter_by(user_id=user_id).count()
            
            total_size = db.session.query(db.func.sum(MediaAttachment.file_size))\
                .filter_by(user_id=user_id).scalar() or 0
            
            return {
                'total_media': total_media,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            print(f"Error getting user media stats: {str(e)}")
            return None
    
    def generate_blog_upload_url(self, filename):
        """Generate presigned URL for blog image upload"""
        try:
            # Validate file
            is_valid, result = self._validate_file(filename, None)
            if not is_valid:
                return jsonify({'success': False, 'error': result}), 400
            
            validation_data = result
            
            # Only allow images for blog
            if validation_data['media_type'] != 'image':
                return jsonify({'success': False, 'error': 'Only images allowed for blog posts'}), 400
            
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_ext = validation_data['file_ext']
            unique_filename = f"{validation_data['filename'].rsplit('.', 1)[0]}_{timestamp}.{file_ext}"
            
            # Get S3 key
            folder_path = s3_config.get_blog_folder()
            s3_key = s3_config.get_file_key(folder_path, unique_filename)
            
            # Determine content type
            content_type = self._determine_content_type('image', file_ext)
            
            # Generate presigned URL
            presigned_data = s3_config.generate_presigned_upload_url(s3_key, content_type)
            
            # Generate URL that will be served by our Flask route
            blog_image_url = f"/blog-images/{unique_filename}"
            
            return jsonify({
                'success': True,
                'upload_url': presigned_data['url'],
                'upload_fields': presigned_data['fields'],
                'file_name': validation_data['filename'],
                's3_key': s3_key,
                'image_url': blog_image_url  # Use Flask route that redirects to S3
            })
            
        except Exception as e:
            print(f"Error generating blog upload URL: {str(e)}")
            return jsonify({'success': False, 'error': 'Failed to generate upload URL'}), 500

    def upload_blog_image(self, file, filename):
        """Upload blog image directly to S3"""
        try:
            # Validate file
            is_valid, result = self._validate_file(filename, file.content_type, len(file.read()))
            file.seek(0)  # Reset file pointer
            if not is_valid:
                return {'success': False, 'error': result}
            
            validation_data = result
            
            # Only allow images for blog
            if validation_data['media_type'] != 'image':
                return {'success': False, 'error': 'Only images allowed for blog posts'}
            
            # Get S3 key
            folder_path = s3_config.get_blog_folder()
            s3_key = s3_config.get_file_key(folder_path, filename)
            
            # Determine content type
            content_type = self._determine_content_type('image', validation_data['file_ext'])
            
            # Upload to S3
            success = s3_config.upload_file_to_s3(file, s3_key, content_type)
            
            if success:
                # Generate public URL
                public_url = s3_config.get_public_url(s3_key)
                return {
                    'success': True,
                    'url': public_url,
                    's3_key': s3_key,
                    'filename': filename
                }
            else:
                return {'success': False, 'error': 'Failed to upload to S3'}
                
        except Exception as e:
            print(f"Error uploading blog image: {str(e)}")
            return {'success': False, 'error': 'Upload failed'}

# Global S3 media handler instance
s3_media_handler = S3MediaHandler()
