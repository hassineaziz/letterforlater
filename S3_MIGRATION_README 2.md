# AWS S3 Media Storage Migration

This document describes the complete migration of the Legacy Letter application from local file storage to AWS S3 cloud storage for improved scalability, security, and reliability.

## Overview

The migration replaces the previous dual storage system (session-based and local database-backed files) with a unified AWS S3 solution that provides:

- **Scalable cloud storage** in the `letterforlater` S3 bucket
- **Organized folder structure** by user and letter
- **Secure access** using presigned URLs
- **Database metadata tracking** for all files
- **Automatic cleanup** of temporary files
- **Production-ready security** and validation

## Architecture

### S3 Folder Organization

```
s3://letterforlater/
├── [user_id]/
│   ├── temp/                    # Temporary uploads
│   │   └── [media_id].[ext]
│   └── [letter_id]/            # Permanent letter attachments
│       └── [media_id].[ext]
├── blog/                       # Blog post images
│   └── [filename]_[timestamp].[ext]
└── legacy/                     # Migrated legacy files
    └── [original_filename]
```

### Database Schema Updates

The `MediaAttachment` model has been enhanced with S3-specific fields:

```python
class MediaAttachment(db.Model):
    # ... existing fields ...
    is_s3_stored = db.Column(db.Boolean, default=True)  # True for S3 files
    s3_bucket = db.Column(db.String(100), nullable=True)  # S3 bucket name
    s3_etag = db.Column(db.String(100), nullable=True)  # S3 ETag for integrity
```

## Implementation Components

### 1. S3 Configuration (`website/s3_config.py`)

- AWS S3 client setup and connection testing
- Presigned URL generation for uploads and downloads
- File organization and path management
- Bucket operations and cleanup utilities

### 2. S3 Media Handler (`website/s3_media_handler.py`)

- Complete media upload/download workflow
- File validation and security checks
- Database metadata management
- Temporary file cleanup and maintenance

### 3. Frontend Integration (`website/static/js/s3-media-handler.js`)

- Direct S3 upload using presigned URLs
- Progress tracking and error handling
- File validation and type detection
- Blog image upload integration

### 4. API Endpoints

**New S3-based endpoints:**

- `POST /upload-media-url` - Generate presigned upload URL
- `POST /confirm-upload` - Confirm successful S3 upload
- `GET /media/<id>/download` - Get presigned download URL
- `POST /admin/upload-image-url` - Blog image upload URL

**Legacy endpoints removed:**

- `POST /upload-media` - Replaced with presigned URL workflow
- `POST /record-media` - Replaced with presigned URL workflow

## Migration Process

### Step 1: Install Dependencies

```bash
pip install boto3 python-dotenv
```

### Step 2: Configure Environment

Ensure your `.env` file contains:

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=eu-north-1
S3_BUCKET=letterforlater
SIGNED_URL_EXPIRY=600
```

### Step 3: Run Database Migration

```bash
# Apply the S3 schema changes
python -c "
from website import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
    print('Database updated with S3 fields')
"
```

### Step 4: Migrate Existing Files

```bash
# Preview migration (dry run)
python migrate_to_s3.py --dry-run

# Perform actual migration
python migrate_to_s3.py

# Clean up local files after successful migration
python migrate_to_s3.py --cleanup
```

### Step 5: Update Templates

Include the S3 media handler in your templates:

```html
<!-- For letter creation -->
<script src="{{ url_for('static', filename='js/s3-media-handler.js') }}"></script>

<!-- For blog editing -->
<script src="{{ url_for('static', filename='js/s3-media-handler.js') }}"></script>
```

## Usage Examples

### Frontend File Upload

```javascript
// Upload a file to S3
const file = document.getElementById("fileInput").files[0];
const result = await s3MediaUploader.uploadFile(file, "image");

if (result.success) {
  console.log("File uploaded:", result.media_id);
} else {
  console.error("Upload failed:", result.error);
}
```

### Backend Media Management

```python
from website.s3_media_handler import s3_media_handler

# Generate upload URL
response = s3_media_handler.generate_upload_url(user_id, filename, 'image')

# Confirm upload
response = s3_media_handler.confirm_upload(media_id, user_id, file_size)

# Get download URL
response = s3_media_handler.generate_download_url(media_id, user_id)
```

## Security Features

### File Validation

- File type validation (images, videos, audio)
- File size limits (100MB default)
- Filename sanitization to prevent path traversal
- MIME type verification

### Access Control

- Presigned URLs with expiration (10 minutes default)
- User-based access control
- No public file access
- Secure S3 bucket policies

### Data Integrity

- S3 ETag storage for file integrity verification
- Database-S3 consistency checks
- Automatic cleanup of orphaned files

## Maintenance and Monitoring

### Cleanup Utilities

```bash
# Clean up expired temporary files
python s3_maintenance.py --cleanup-expired

# Verify S3 integrity
python s3_maintenance.py --verify-integrity

# Get storage statistics
python s3_maintenance.py --storage-stats

# Clean up orphaned files
python s3_maintenance.py --cleanup-orphaned

# Generate user report
python s3_maintenance.py --user-report [user_id]
```

### Automated Cleanup

The system includes automatic cleanup of:

- Expired temporary files (24 hours default)
- Orphaned S3 files without database records
- Failed uploads and incomplete transfers

## Performance Optimizations

### Direct S3 Uploads

- Files upload directly to S3, bypassing server
- Reduced server bandwidth usage
- Faster upload speeds
- Better scalability

### Presigned URLs

- Temporary access without authentication
- Reduced server load for file serving
- CDN-ready architecture
- Configurable expiration times

### Database Optimization

- Efficient indexing on S3 fields
- Batch operations for cleanup
- Optimized queries for file metadata

## Troubleshooting

### Common Issues

1. **S3 Connection Errors**

   - Verify AWS credentials in `.env`
   - Check bucket permissions
   - Ensure region is correct

2. **Upload Failures**

   - Check file size limits
   - Verify file type is allowed
   - Ensure presigned URL hasn't expired

3. **Migration Issues**
   - Run with `--dry-run` first
   - Check file permissions
   - Verify S3 bucket access

### Monitoring

Monitor the following metrics:

- Upload success/failure rates
- S3 storage usage
- Presigned URL generation frequency
- Cleanup operation results

## Future Enhancements

### CDN Integration

- CloudFront distribution for faster delivery
- Global edge locations
- Automatic cache invalidation

### Advanced Features

- Image resizing and optimization
- Video thumbnail generation
- Audio waveform generation
- Bulk operations API

### Monitoring

- CloudWatch integration
- Custom metrics and alarms
- Cost optimization recommendations

## Rollback Plan

If rollback is needed:

1. **Stop new uploads** to S3
2. **Revert to local storage** endpoints
3. **Download critical files** from S3
4. **Update database** to mark files as local
5. **Restore local storage** handlers

## Support

For issues or questions:

1. Check the maintenance utilities output
2. Review S3 bucket logs
3. Verify database consistency
4. Test with small files first

The S3 migration provides a robust, scalable foundation for media storage that will support the application's growth while maintaining security and performance.
