#!/usr/bin/env python3
"""
MoltBot Backend Quick Health Check
Quick verification of 4 core endpoints as requested by user.
"""

import requests
import json
import sys

# Backend URL from frontend .env
BACKEND_URL = "https://native-agent.preview.emergentagent.com/api"

def test_health_endpoint():
    """Test GET /api/health - should return {status: "healthy"}"""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        print(f"✅ Health Check: Status {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data}")
            if data.get("status") == "healthy":
                return True, "Health endpoint working correctly"
            else:
                return False, f"Unexpected response format: {data}"
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"Request failed: {str(e)}"

def test_providers_endpoint():
    """Test GET /api/providers - should return list of providers"""
    try:
        response = requests.get(f"{BACKEND_URL}/providers", timeout=10)
        print(f"✅ Providers: Status {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Found {len(data)} providers: {[p.get('name', 'unknown') for p in data]}")
            if isinstance(data, list) and len(data) > 0:
                return True, f"Providers endpoint working - {len(data)} providers available"
            else:
                return False, f"Expected non-empty list, got: {data}"
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"Request failed: {str(e)}"

def test_settings_endpoint():
    """Test GET /api/settings - should return settings with active_provider and active_model"""
    try:
        response = requests.get(f"{BACKEND_URL}/settings", timeout=10)
        print(f"✅ Settings: Status {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Active Provider: {data.get('active_provider')}")
            print(f"   Active Model: {data.get('active_model')}")
            
            if "active_provider" in data and "active_model" in data:
                return True, "Settings endpoint working correctly"
            else:
                return False, f"Missing required fields in response: {data}"
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"Request failed: {str(e)}"

def test_conversations_endpoint():
    """Test GET /api/conversations - should return list of conversations"""
    try:
        response = requests.get(f"{BACKEND_URL}/conversations", timeout=10)
        print(f"✅ Conversations: Status {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Found {len(data)} conversations")
            if isinstance(data, list):
                return True, f"Conversations endpoint working - {len(data)} conversations found"
            else:
                return False, f"Expected list, got: {type(data)}"
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"Request failed: {str(e)}"

def main():
    """Run health check on all 4 requested endpoints"""
    print("🔍 MoltBot Backend Health Check")
    print(f"Testing backend at: {BACKEND_URL}")
    print("=" * 50)
    
    tests = [
        ("Health Check API", test_health_endpoint),
        ("Providers API", test_providers_endpoint), 
        ("Settings API", test_settings_endpoint),
        ("Conversations API", test_conversations_endpoint)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Testing {test_name}...")
        success, message = test_func()
        results.append((test_name, success, message))
        
        if success:
            print(f"   ✅ PASS: {message}")
        else:
            print(f"   ❌ FAIL: {message}")
    
    print("\n" + "=" * 50)
    print("📊 HEALTH CHECK SUMMARY:")
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for test_name, success, message in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status}: {test_name}")
        if not success:
            print(f"      Error: {message}")
    
    print(f"\n🎯 Overall: {passed}/{total} endpoints working")
    
    if passed == total:
        print("🎉 All endpoints healthy!")
        return 0
    else:
        print("⚠️  Some endpoints have issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())