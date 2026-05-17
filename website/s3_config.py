"""
AWS S3 Configuration for Legacy Letter Application
Handles S3 client setup, bucket configuration, and environment variables
"""

import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class S3Config:
    """S3 configuration and client management"""
    
    def __init__(self):
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_REGION', 'eu-north-1')
        self.s3_bucket = os.getenv('S3_BUCKET', 'letterforlater')
        self.signed_url_expiry = int(os.getenv('SIGNED_URL_EXPIRY', '600'))  # 10 minutes default
        
        # Validate required credentials
        if not all([self.aws_access_key_id, self.aws_secret_access_key]):
            raise ValueError("AWS credentials not found in environment variables")
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region
        )
        
        # Test connection
        self._test_connection()
    
    def _test_connection(self):
        """Test S3 connection and bucket access"""
        try:
            # Check if bucket exists and is accessible
            self.s3_client.head_bucket(Bucket=self.s3_bucket)
            print(f"S3 connection successful. Bucket: {self.s3_bucket}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"WARNING: S3 bucket '{self.s3_bucket}' not found")
            elif error_code == '403':
                print(f"WARNING: Access denied to S3 bucket '{self.s3_bucket}'. Could be missing s3:ListBucket permission.")
            else:
                print(f"WARNING: S3 connection error: {str(e)}")
        except NoCredentialsError:
            print("WARNING: AWS credentials not configured properly")
        except Exception as e:
            print(f"WARNING: Unexpected S3 connection error: {str(e)}")
    
    def get_user_folder(self, user_id):
        """Get S3 folder path for a user"""
        return f"{user_id}/"
    
    def get_temp_folder(self, user_id):
        """Get S3 temp folder path for a user"""
        return f"{user_id}/temp/"
    
    def get_letter_folder(self, user_id, letter_id):
        """Get S3 folder path for a specific letter"""
        return f"{user_id}/{letter_id}/"
    
    def get_blog_folder(self):
        """Get S3 folder path for blog images"""
        return "blog/"
    
    def get_file_key(self, folder_path, filename):
        """Get full S3 key for a file"""
        return f"{folder_path}{filename}"
    
    def generate_presigned_upload_url(self, key, content_type, expires_in=None):
        """Generate presigned URL for file upload"""
        if expires_in is None:
            expires_in = self.signed_url_expiry
        
        try:
            # Standard fields for the POST
            fields = {'success_action_status': '201'}
            
            response = self.s3_client.generate_presigned_post(
                Bucket=self.s3_bucket,
                Key=key,
                Fields=fields,
                Conditions=[
                    # Only enforce file size limits, let S3 detect content type from file
                    ['content-length-range', 1, 100 * 1024 * 1024],  # 1 byte to 100MB
                    {'success_action_status': '201'}
                ],
                ExpiresIn=expires_in
            )
            return response
        except ClientError as e:
            print(f"Error generating presigned upload URL: {str(e)}")
            raise
    
    def generate_presigned_download_url(self, key, expires_in=None):
        """Generate presigned URL for file download"""
        if expires_in is None:
            expires_in = self.signed_url_expiry
        
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.s3_bucket, 'Key': key},
                ExpiresIn=expires_in
            )
            return response
        except ClientError as e:
            print(f"Error generating presigned download URL: {str(e)}")
            raise
    
    def delete_file(self, key):
        """Delete a file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.s3_bucket, Key=key)
            return True
        except ClientError as e:
            print(f"Error deleting file {key}: {str(e)}")
            return False
    
    def file_exists(self, key):
        """Check if a file exists in S3"""
        try:
            self.s3_client.head_object(Bucket=self.s3_bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    def get_file_metadata(self, key):
        """Get file metadata from S3"""
        try:
            response = self.s3_client.head_object(Bucket=self.s3_bucket, Key=key)
            return {
                'size': response['ContentLength'],
                'last_modified': response['LastModified'],
                'content_type': response.get('ContentType', 'application/octet-stream'),
                'etag': response['ETag']
            }
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            raise
    
    def list_user_files(self, user_id, prefix=None):
        """List files for a user"""
        folder_prefix = self.get_user_folder(user_id)
        if prefix:
            folder_prefix += prefix
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_bucket,
                Prefix=folder_prefix
            )
            return response.get('Contents', [])
        except ClientError as e:
            current_app.logger.error(f"Error listing files for user {user_id}: {str(e)}")
            return []
    
    def cleanup_temp_files(self, user_id, older_than_hours=24):
        """Clean up temporary files older than specified hours"""
        from datetime import datetime, timedelta
        
        temp_files = self.list_user_files(user_id, 'temp/')
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        
        cleaned_count = 0
        for file_obj in temp_files:
            if file_obj['LastModified'].replace(tzinfo=None) < cutoff_time:
                if self.delete_file(file_obj['Key']):
                    cleaned_count += 1
        
        return cleaned_count

# Global S3 configuration instance
s3_config = S3Config()
