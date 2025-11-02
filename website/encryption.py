"""
Encryption utilities for letter content using Fernet (symmetric encryption).

This module provides functions to encrypt and decrypt letter titles and content.
Uses Fernet from the cryptography library for secure, authenticated encryption.

Environment Variables:
    ENCRYPTION_KEY: Base64-encoded Fernet key. Generate with:
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


def get_encryption_key():
    """
    Get or generate the encryption key from environment variable.
    
    Returns:
        Fernet key for encryption/decryption
        
    Raises:
        ValueError: If ENCRYPTION_KEY is not set and can't be generated
    """
    key_str = os.getenv('ENCRYPTION_KEY')
    
    if not key_str:
        raise ValueError(
            "ENCRYPTION_KEY environment variable is not set. "
            "Generate a key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    
    try:
        # Try to use the key directly (should be base64-encoded)
        return Fernet(key_str.encode())
    except Exception as e:
        raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")


def encrypt_text(text):
    """
    Encrypt a text string using Fernet.
    
    Args:
        text: Plain text string to encrypt
        
    Returns:
        Encrypted bytes (as base64-encoded string for database storage)
        
    Raises:
        ValueError: If encryption key is not configured
        Exception: If encryption fails
    """
    if not text:
        return None
    
    if not isinstance(text, str):
        text = str(text)
    
    try:
        key = get_encryption_key()
        encrypted_bytes = key.encrypt(text.encode('utf-8'))
        # Return as base64 string for database storage
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        print(f"Error encrypting text: {e}")
        raise


def decrypt_text(encrypted_text):
    """
    Decrypt a text string that was encrypted with Fernet.
    
    Args:
        encrypted_text: Encrypted text (base64-encoded string) to decrypt
        
    Returns:
        Decrypted plain text string
        
    Raises:
        ValueError: If decryption key is not configured
        Exception: If decryption fails (e.g., wrong key, corrupted data)
    """
    if not encrypted_text:
        return None
    
    if not isinstance(encrypted_text, str):
        # Try to convert to string if it's bytes
        encrypted_text = encrypted_text.decode('utf-8') if isinstance(encrypted_text, bytes) else str(encrypted_text)
    
    try:
        key = get_encryption_key()
        decrypted_bytes = key.decrypt(encrypted_text.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        print(f"Error decrypting text: {e}")
        raise


def is_encrypted_text(text):
    """
    Check if a text string appears to be encrypted (base64-encoded Fernet token).
    This is a heuristic check - not 100% reliable but useful for migration.
    
    Args:
        text: Text to check
        
    Returns:
        True if text appears to be encrypted, False otherwise
    """
    if not text:
        return False
    
    try:
        # Fernet tokens are base64-encoded and have a specific structure
        # They decode to bytes and have a minimum length
        decoded = base64.urlsafe_b64decode(text.encode('utf-8'))
        # Fernet tokens are typically 32+ bytes (with some padding)
        return len(decoded) >= 32
    except Exception:
        # If it can't be decoded as base64, it's probably plain text
        return False

