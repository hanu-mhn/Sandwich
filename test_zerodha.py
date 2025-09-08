#!/usr/bin/env python3
"""
Test Zerodha Broker Import

Simple test to verify the Zerodha broker can be imported and initialized.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

def test_zerodha_import():
    """Test importing Zerodha broker"""
    try:
        from src.brokers.zerodha_broker import ZerodhaBroker
        print("✅ ZerodhaBroker imported successfully")
        
        # Test with mock config
        config = {
            'name': 'zerodha',
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'access_token': 'test_token'
        }
        
        broker = ZerodhaBroker(config)
        print("✅ ZerodhaBroker initialized successfully")
        print(f"   API Key: {broker.api_key}")
        print(f"   Connected: {broker.is_connected}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Initialization error: {e}")
        return False

def test_kiteconnect_direct():
    """Test kiteconnect import directly"""
    try:
        from kiteconnect import KiteConnect
        print("✅ KiteConnect imported successfully")
        
        # Test initialization (without credentials)
        try:
            kite = KiteConnect(api_key="test")
            print("✅ KiteConnect instance created")
        except Exception as e:
            print(f"⚠️  KiteConnect instance creation failed (expected): {e}")
        
        return True
        
    except ImportError as e:
        print(f"❌ KiteConnect import failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Zerodha Broker Implementation")
    print("=" * 50)
    
    print("\n1. Testing KiteConnect import:")
    kite_ok = test_kiteconnect_direct()
    
    print("\n2. Testing ZerodhaBroker import:")
    broker_ok = test_zerodha_import()
    
    print("\n" + "=" * 50)
    if kite_ok and broker_ok:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
