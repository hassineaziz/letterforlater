#!/usr/bin/env python3
"""
Test script for the new permanent media storage workflow
This script tests the complete workflow from upload to deletion.
"""

import os
import sys
import requests
from io import BytesIO

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db
from website.models import MediaAttachment, Letter, User
from website.s3_config import s3_config
from website.s3_media_handler import s3_media_handler

def test_permanent_media_workflow():
    """Test the complete permanent media storage workflow"""
    print("🧪 Testing Permanent Media Storage Workflow")
    print("=" * 50)
    
    app = create_app()
    
    with app.app_context():
        try:
            # Test 1: Create a draft letter
            print("\n1️⃣ Testing draft letter creation...")
            draft_letter = Letter(
                title='Test Letter',
                content='Test content',
                recipient_name='Test Recipient',
                recipient_email='test@example.com',
                delivery_type='date',
                status='draft',
                user_id=1  # Assuming user ID 1 exists
            )
            db.session.add(draft_letter)
            db.session.commit()
            print(f"✅ Draft letter created: ID {draft_letter.id}")
            
            # Test 2: Upload media with letter_id
            print("\n2️⃣ Testing media upload with letter_id...")
            
            # Create test files
            test_files = {
                'image': ('test_image.png', b'fake_png_data', 'image/png'),
                'audio': ('test_audio.wav', b'fake_wav_data', 'audio/wav'),
                'video': ('test_video.mp4', b'fake_mp4_data', 'video/mp4')
            }
            
            uploaded_media = []
            
            for media_type, (filename, content, mime_type) in test_files.items():
                print(f"   Uploading {media_type}: {filename}")
                
                # Generate upload URL
                response = s3_media_handler.generate_upload_url(
                    user_id=1,
                    filename=filename,
                    media_type=media_type,
                    letter_id=draft_letter.id
                )
                
                if response[1] != 200:
                    print(f"❌ Failed to generate upload URL for {filename}: {response[1]}")
                    continue
                
                data = response[0].get_json()
                media_id = data['media_id']
                upload_url = data['upload_url']
                upload_fields = data['upload_fields']
                
                # Simulate file upload to S3
                files = {'file': (filename, content, mime_type)}
                form_data = {**upload_fields}
                
                upload_response = requests.post(upload_url, files=files, data=form_data)
                
                if upload_response.status_code != 204:
                    print(f"❌ Upload failed for {filename}: {upload_response.status_code}")
                    continue
                
                # Confirm upload
                confirm_response = s3_media_handler.confirm_upload(media_id, 1, len(content))
                
                if confirm_response[1] != 200:
                    print(f"❌ Confirm upload failed for {filename}: {confirm_response[1]}")
                    continue
                
                uploaded_media.append(media_id)
                print(f"   ✅ {filename} uploaded successfully")
            
            # Test 3: Verify media is permanent
            print(f"\n3️⃣ Testing permanent storage verification...")
            
            for media_id in uploaded_media:
                media = MediaAttachment.query.get(media_id)
                if not media:
                    print(f"❌ Media {media_id} not found in database")
                    continue
                
                if media.is_temporary:
                    print(f"❌ Media {media_id} is still marked as temporary")
                    continue
                
                if not media.letter_id:
                    print(f"❌ Media {media_id} has no letter_id")
                    continue
                
                if media.letter_id != draft_letter.id:
                    print(f"❌ Media {media_id} has wrong letter_id")
                    continue
                
                print(f"   ✅ Media {media_id} is properly permanent")
            
            # Test 4: Test media access
            print(f"\n4️⃣ Testing media access...")
            
            for media_id in uploaded_media:
                response = s3_media_handler.generate_download_url(media_id, 1)
                
                if response[1] != 200:
                    print(f"❌ Failed to generate download URL for media {media_id}")
                    continue
                
                data = response[0].get_json()
                download_url = data['download_url']
                
                # Test download
                try:
                    download_response = requests.head(download_url, timeout=5)
                    if download_response.status_code == 200:
                        print(f"   ✅ Media {media_id} is accessible")
                    else:
                        print(f"   ❌ Media {media_id} not accessible: {download_response.status_code}")
                except Exception as e:
                    print(f"   ❌ Media {media_id} download test failed: {e}")
            
            # Test 5: Test letter deletion with media cleanup
            print(f"\n5️⃣ Testing letter deletion with media cleanup...")
            
            # Count media before deletion
            media_before = MediaAttachment.query.filter_by(letter_id=draft_letter.id).count()
            print(f"   Media files before deletion: {media_before}")
            
            # Delete letter
            result = s3_media_handler.delete_letter_media(draft_letter.id, 1)
            
            if result.json.get('success'):
                deleted_count = result.json.get('deleted_count', 0)
                print(f"   ✅ Deleted {deleted_count} media files")
            else:
                print(f"   ❌ Failed to delete media: {result.json.get('error')}")
            
            # Verify media is deleted from database
            media_after = MediaAttachment.query.filter_by(letter_id=draft_letter.id).count()
            print(f"   Media files after deletion: {media_after}")
            
            if media_after == 0:
                print(f"   ✅ All media files deleted from database")
            else:
                print(f"   ❌ {media_after} media files still in database")
            
            # Clean up the draft letter
            db.session.delete(draft_letter)
            db.session.commit()
            
            print(f"\n🎉 All tests completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

def test_file_format_restrictions():
    """Test file format restrictions"""
    print("\n🔒 Testing file format restrictions...")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Test allowed formats
            allowed_files = [
                ('test.png', 'image'),
                ('test.jpg', 'image'),
                ('test.jpeg', 'image'),
                ('test.gif', 'image'),
                ('test.webp', 'image'),
                ('test.mp4', 'video'),
                ('test.mp3', 'audio'),
                ('test.wav', 'audio')
            ]
            
            # Test disallowed formats
            disallowed_files = [
                ('test.ogg', 'audio'),
                ('test.aac', 'audio'),
                ('test.mov', 'video'),
                ('test.avi', 'video')
            ]
            
            print("   Testing allowed formats...")
            for filename, media_type in allowed_files:
                response = s3_media_handler.generate_upload_url(
                    user_id=1,
                    filename=filename,
                    media_type=media_type,
                    letter_id=1  # Dummy letter ID for testing
                )
                
                if response[1] == 200:
                    print(f"   ✅ {filename} ({media_type}) - Allowed")
                else:
                    print(f"   ❌ {filename} ({media_type}) - Unexpectedly rejected")
            
            print("   Testing disallowed formats...")
            for filename, media_type in disallowed_files:
                response = s3_media_handler.generate_upload_url(
                    user_id=1,
                    filename=filename,
                    media_type=media_type,
                    letter_id=1  # Dummy letter ID for testing
                )
                
                if response[1] != 200:
                    print(f"   ✅ {filename} ({media_type}) - Correctly rejected")
                else:
                    print(f"   ❌ {filename} ({media_type}) - Should have been rejected")
            
            return True
            
        except Exception as e:
            print(f"❌ File format test failed: {str(e)}")
            return False

def main():
    """Main test function"""
    print("🚀 Permanent Media Storage Workflow Test Suite")
    print("=" * 60)
    
    # Run tests
    test1_passed = test_permanent_media_workflow()
    test2_passed = test_file_format_restrictions()
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    print(f"   Permanent Media Workflow: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"   File Format Restrictions: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All tests passed! The permanent media storage workflow is working correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
