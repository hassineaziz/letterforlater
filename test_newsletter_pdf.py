#!/usr/bin/env python3
"""
Test script for newsletter download page functionality
Run this to test the newsletter subscription with download page
"""

import os
import sys
import requests
from datetime import datetime

def test_newsletter_subscription():
    """Test the newsletter subscription endpoint"""
    
    # Test email (use a test email address)
    test_email = "test@example.com"
    
    # Get the base URL (adjust if running on different port)
    base_url = "http://localhost:5000"  # Adjust if your Flask app runs on different port
    
    print("🧪 Testing Newsletter Subscription with Download Page")
    print("=" * 60)
    
    # Test data
    data = {
        'email': test_email,
        'source': 'test_script'
    }
    
    try:
        # Make POST request to newsletter subscription endpoint
        print(f"📧 Subscribing email: {test_email}")
        response = requests.post(f"{base_url}/newsletter/subscribe", data=data, allow_redirects=False)
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 302:  # Redirect response
            print("✅ Newsletter subscription successful!")
            print("📧 Welcome email should have been sent with download link")
            print(f"🔗 Redirect location: {response.headers.get('Location', 'Unknown')}")
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            print(f"Response content: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the Flask application")
        print("💡 Make sure your Flask app is running on localhost:5000")
        print("   Run: python main.py")
    except Exception as e:
        print(f"❌ Error testing newsletter subscription: {e}")

def test_download_page():
    """Test the download page accessibility"""
    print("\n🌐 Testing Download Page")
    print("=" * 30)
    
    base_url = "http://localhost:5000"
    
    try:
        # Test the download page
        print("📄 Testing download page...")
        response = requests.get(f"{base_url}/download/legacy-template")
        
        if response.status_code == 200:
            print("✅ Download page is accessible")
            if "Legacy Letter Template" in response.text:
                print("✅ Download page content looks correct")
            else:
                print("⚠️ Download page content may be missing")
        else:
            print(f"❌ Download page returned status: {response.status_code}")
            
        # Test the PDF download
        print("\n📥 Testing PDF download...")
        pdf_response = requests.get(f"{base_url}/download/legacy-template.pdf")
        
        if pdf_response.status_code == 200:
            print("✅ PDF download is working")
            if pdf_response.headers.get('content-type') == 'application/pdf':
                print("✅ Correct content type (PDF)")
            else:
                print(f"⚠️ Unexpected content type: {pdf_response.headers.get('content-type')}")
        else:
            print(f"❌ PDF download returned status: {pdf_response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the Flask application")
        print("💡 Make sure your Flask app is running on localhost:5000")
    except Exception as e:
        print(f"❌ Error testing download page: {e}")

def test_pdf_file():
    """Test if the PDF file exists and is readable"""
    print("\n🔍 Testing PDF File")
    print("=" * 30)
    
    pdf_path = os.path.join(os.path.dirname(__file__), 'website', 'static', 'Legacy_Letter_Template_LetterForLater.pdf')
    
    if os.path.exists(pdf_path):
        file_size = os.path.getsize(pdf_path)
        print(f"✅ PDF file found: {pdf_path}")
        print(f"📏 File size: {file_size:,} bytes")
        
        # Try to read the file
        try:
            with open(pdf_path, 'rb') as f:
                content = f.read(100)  # Read first 100 bytes
                if content.startswith(b'%PDF'):
                    print("✅ PDF file appears to be valid (starts with %PDF)")
                else:
                    print("⚠️ PDF file may be corrupted (doesn't start with %PDF)")
        except Exception as e:
            print(f"❌ Error reading PDF file: {e}")
    else:
        print(f"❌ PDF file not found: {pdf_path}")
        print("💡 Make sure the PDF file is in website/static/")

if __name__ == "__main__":
    print("🚀 Newsletter Download Page Test Suite")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test PDF file
    test_pdf_file()
    
    # Test download page
    test_download_page()
    
    # Test newsletter subscription
    test_newsletter_subscription()
    
    print("\n✨ Test completed!")
    print("\n📝 Notes:")
    print("- Check your email server logs for email sending status")
    print("- The welcome email now contains a link to the download page")
    print("- Only new subscribers receive the welcome email")
    print("- The download page encourages users to sign up for accounts")
