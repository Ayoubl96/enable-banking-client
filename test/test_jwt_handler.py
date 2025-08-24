#!/usr/bin/env python3
"""
Simple test script for JWTHandler functionality
"""
import sys
import os
sys.path.append('src')

import jwt as pyjwt
from datetime import datetime, timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import tempfile


def test_jwt_handler():
    """Test JWTHandler functionality"""
    print("🧪 Testing JWTHandler...")

    try:
        # Mock settings for testing
        from config.settings import settings

        # Set variables value
        settings.enable_banking_private_key_path = settings.enable_banking_private_key_path
        settings.enable_banking_application_id = settings.enable_banking_application_id

        # Import and test JWTHandler
        from utils.jwt_handler import JWTHandler

        # Create JWT handler
        jwt_handler = JWTHandler()
        print("✅ JWTHandler initialized successfully")

        # Generate token
        token = jwt_handler.generate_enable_baking_token()
        print("✅ JWT token generated successfully")
        print(f"Token length: {len(token)} characters")

        # Decode token (skip audience validation for testing)
        decoded = pyjwt.decode(token, algorithms=['RS256'], options={'verify_signature': False})
        print("✅ JWT token decoded successfully")

        # Verify token structure
        expected_fields = ['iss', 'aud', 'iat', 'exp']
        for field in expected_fields:
            if field not in decoded:
                print(f"❌ Missing field: {field}")
                return False
            else:
                print(f"✅ Field '{field}': {decoded[field]}")

        # Check header
        header = pyjwt.get_unverified_header(token)
        if 'kid' in header and header['kid'] == settings.enable_banking_application_id:
            print(f"✅ Header 'kid': {header['kid']}")
        else:
            print(f"❌ Invalid or missing 'kid' in header: {header}")
            return False

        # Check expiry
        exp_time = datetime.fromtimestamp(decoded['exp'], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(decoded['iat'], tz=timezone.utc)
        duration = (exp_time - iat_time).total_seconds() / 60

        if abs(duration - 60) < 1:  # Allow 1 minute tolerance
            print(f"✅ Token expiry duration: {duration:.1f} minutes")
        else:
            print(f"❌ Unexpected token expiry duration: {duration:.1f} minutes (expected ~60)")
            return False

        print("\n🎉 All JWT tests passed! Your JWTHandler is working correctly.")
        return True

    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_jwt_handler()
    sys.exit(0 if success else 1)
