#!/usr/bin/env python3
"""
MoltBot Backend API Testing Suite
Tests all backend APIs for the MoltBot AI assistant application
"""

import requests
import json
import time
from typing import Dict, Any, Optional

# Backend URL from frontend .env
BACKEND_URL = "https://native-agent.preview.emergentagent.com/api"

class MoltBotTester:
    def __init__(self):
        self.session = requests.Session()
        self.conversation_id = None
        self.test_results = []
        self.test_snapshot_id = None
        
    def log_test(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "response_data": response_data,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        if response_data and not success:
            print(f"   Response: {response_data}")
    
    def test_health_check(self):
        """Test GET /api/health"""
        try:
            response = self.session.get(f"{BACKEND_URL}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy" and "llm_key_configured" in data:
                    self.log_test("Health Check API", True, 
                                f"Status: {data['status']}, LLM Key: {data['llm_key_configured']}")
                else:
                    self.log_test("Health Check API", False, 
                                "Invalid response format", data)
            else:
                self.log_test("Health Check API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Health Check API", False, f"Exception: {str(e)}")
    
    def test_providers_api(self):
        """Test GET /api/providers"""
        try:
            response = self.session.get(f"{BACKEND_URL}/providers", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    # Check if we have the expected providers
                    provider_ids = [p.get("id") for p in data]
                    expected_providers = ["openai", "anthropic", "gemini"]
                    
                    if all(provider in provider_ids for provider in expected_providers):
                        self.log_test("Providers API", True, 
                                    f"Found {len(data)} providers: {provider_ids}")
                    else:
                        self.log_test("Providers API", False, 
                                    f"Missing expected providers. Found: {provider_ids}")
                else:
                    self.log_test("Providers API", False, 
                                "Empty or invalid provider list", data)
            else:
                self.log_test("Providers API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Providers API", False, f"Exception: {str(e)}")
    
    def test_settings_get(self):
        """Test GET /api/settings"""
        try:
            response = self.session.get(f"{BACKEND_URL}/settings", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["active_provider", "active_model"]
                
                if all(field in data for field in required_fields):
                    self.log_test("Settings GET API", True, 
                                f"Provider: {data['active_provider']}, Model: {data['active_model']}")
                    return data
                else:
                    self.log_test("Settings GET API", False, 
                                "Missing required fields", data)
            else:
                self.log_test("Settings GET API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Settings GET API", False, f"Exception: {str(e)}")
        
        return None
    
    def test_settings_put(self):
        """Test PUT /api/settings"""
        try:
            # Test updating to anthropic
            update_data = {
                "active_provider": "anthropic",
                "active_model": "claude-4-sonnet-20250514"
            }
            
            response = self.session.put(f"{BACKEND_URL}/settings", 
                                      json=update_data, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if (data.get("active_provider") == "anthropic" and 
                    data.get("active_model") == "claude-4-sonnet-20250514"):
                    self.log_test("Settings PUT API", True, 
                                f"Updated to {data['active_provider']}/{data['active_model']}")
                    
                    # Test switching back to OpenAI
                    reset_data = {
                        "active_provider": "openai",
                        "active_model": "gpt-5.2"
                    }
                    reset_response = self.session.put(f"{BACKEND_URL}/settings", 
                                                    json=reset_data, timeout=10)
                    if reset_response.status_code == 200:
                        self.log_test("Settings PUT API (Reset)", True, "Reset to OpenAI/gpt-5.2")
                    else:
                        self.log_test("Settings PUT API (Reset)", False, 
                                    f"Failed to reset: HTTP {reset_response.status_code}")
                else:
                    self.log_test("Settings PUT API", False, 
                                "Settings not updated correctly", data)
            else:
                self.log_test("Settings PUT API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Settings PUT API", False, f"Exception: {str(e)}")
    
    def test_chat_api(self):
        """Test POST /api/chat"""
        try:
            # Test chat without conversation_id (should create new conversation)
            chat_data = {
                "content": "Hello! Can you tell me a short joke about robots?"
            }
            
            response = self.session.post(f"{BACKEND_URL}/chat", 
                                       json=chat_data, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if ("message" in data and "conversation_id" in data and 
                    data["message"].get("role") == "assistant"):
                    
                    self.conversation_id = data["conversation_id"]
                    ai_response = data["message"]["content"]
                    
                    self.log_test("Chat API (New Conversation)", True, 
                                f"Got AI response: '{ai_response[:50]}...' (Conv: {self.conversation_id[:8]})")
                    
                    # Test follow-up message in same conversation
                    followup_data = {
                        "content": "That's funny! Tell me another one.",
                        "conversation_id": self.conversation_id
                    }
                    
                    followup_response = self.session.post(f"{BACKEND_URL}/chat", 
                                                        json=followup_data, timeout=30)
                    
                    if followup_response.status_code == 200:
                        followup_data_resp = followup_response.json()
                        if followup_data_resp.get("conversation_id") == self.conversation_id:
                            self.log_test("Chat API (Follow-up)", True, 
                                        f"Follow-up response in same conversation")
                        else:
                            self.log_test("Chat API (Follow-up)", False, 
                                        "Conversation ID mismatch in follow-up")
                    else:
                        self.log_test("Chat API (Follow-up)", False, 
                                    f"Follow-up failed: HTTP {followup_response.status_code}")
                else:
                    self.log_test("Chat API (New Conversation)", False, 
                                "Invalid response format", data)
            else:
                self.log_test("Chat API (New Conversation)", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Chat API (New Conversation)", False, f"Exception: {str(e)}")
    
    def test_conversations_get(self):
        """Test GET /api/conversations"""
        try:
            response = self.session.get(f"{BACKEND_URL}/conversations", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    if len(data) > 0:
                        # Check if our test conversation is in the list
                        conv_ids = [conv.get("id") for conv in data]
                        if self.conversation_id and self.conversation_id in conv_ids:
                            self.log_test("Conversations GET API", True, 
                                        f"Found {len(data)} conversations including test conversation")
                        else:
                            self.log_test("Conversations GET API", True, 
                                        f"Found {len(data)} conversations (test conv not found)")
                    else:
                        self.log_test("Conversations GET API", True, "No conversations found (empty list)")
                else:
                    self.log_test("Conversations GET API", False, 
                                "Response is not a list", data)
            else:
                self.log_test("Conversations GET API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Conversations GET API", False, f"Exception: {str(e)}")
    
    def test_conversations_post(self):
        """Test POST /api/conversations"""
        try:
            # Create a new conversation
            conv_data = {
                "title": "Test Conversation for API Testing",
                "provider": "openai",
                "model": "gpt-5.2"
            }
            
            response = self.session.post(f"{BACKEND_URL}/conversations", 
                                       json=conv_data, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if ("id" in data and "title" in data and 
                    data["title"] == conv_data["title"]):
                    
                    self.test_conversation_id = data["id"]
                    self.log_test("Conversations POST API", True, 
                                f"Created conversation: {data['title']} (ID: {data['id'][:8]})")
                    return data["id"]
                else:
                    self.log_test("Conversations POST API", False, 
                                "Invalid response format", data)
            else:
                self.log_test("Conversations POST API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Conversations POST API", False, f"Exception: {str(e)}")
        
        return None
    
    def test_conversation_messages(self, conversation_id: str):
        """Test GET /api/conversations/{id}/messages"""
        try:
            response = self.session.get(f"{BACKEND_URL}/conversations/{conversation_id}/messages", 
                                      timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_test("Conversation Messages API", True, 
                                f"Retrieved {len(data)} messages for conversation")
                else:
                    self.log_test("Conversation Messages API", False, 
                                "Response is not a list", data)
            else:
                self.log_test("Conversation Messages API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Conversation Messages API", False, f"Exception: {str(e)}")
    
    def test_conversation_delete(self, conversation_id: str):
        """Test DELETE /api/conversations/{id}"""
        try:
            response = self.session.delete(f"{BACKEND_URL}/conversations/{conversation_id}", 
                                         timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    self.log_test("Conversation DELETE API", True, 
                                f"Deleted conversation: {data['message']}")
                else:
                    self.log_test("Conversation DELETE API", True, 
                                "Conversation deleted successfully")
            else:
                self.log_test("Conversation DELETE API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Conversation DELETE API", False, f"Exception: {str(e)}")
    
    def test_provider_switching(self):
        """Test switching providers and using chat with different providers"""
        providers_to_test = [
            ("anthropic", "claude-4-sonnet-20250514"),
            ("gemini", "gemini-2.5-pro")
        ]
        
        for provider, model in providers_to_test:
            try:
                # Switch provider
                update_data = {
                    "active_provider": provider,
                    "active_model": model
                }
                
                settings_response = self.session.put(f"{BACKEND_URL}/settings", 
                                                   json=update_data, timeout=10)
                
                if settings_response.status_code == 200:
                    # Test chat with new provider
                    chat_data = {
                        "content": f"Hello from {provider}! Just say 'Hi from {provider}' to confirm you're working."
                    }
                    
                    chat_response = self.session.post(f"{BACKEND_URL}/chat", 
                                                    json=chat_data, timeout=30)
                    
                    if chat_response.status_code == 200:
                        chat_data_resp = chat_response.json()
                        ai_response = chat_data_resp["message"]["content"]
                        self.log_test(f"Provider Switch Test ({provider})", True, 
                                    f"Chat successful with {provider}: '{ai_response[:50]}...'")
                    else:
                        self.log_test(f"Provider Switch Test ({provider})", False, 
                                    f"Chat failed with {provider}: HTTP {chat_response.status_code}")
                else:
                    self.log_test(f"Provider Switch Test ({provider})", False, 
                                f"Failed to switch to {provider}: HTTP {settings_response.status_code}")
                    
            except Exception as e:
                self.log_test(f"Provider Switch Test ({provider})", False, f"Exception: {str(e)}")
        
        # Reset to OpenAI
        try:
            reset_data = {"active_provider": "openai", "active_model": "gpt-5.2"}
            self.session.put(f"{BACKEND_URL}/settings", json=reset_data, timeout=10)
        except:
            pass
    
    def test_heal_status(self):
        """Test GET /api/heal/status"""
        try:
            response = self.session.get(f"{BACKEND_URL}/heal/status", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["enabled", "monitoring", "last_health"]
                
                if all(field in data for field in required_fields):
                    self.log_test("Heal Status API", True, 
                                f"Enabled: {data['enabled']}, Monitoring: {data['monitoring']}")
                else:
                    self.log_test("Heal Status API", False, 
                                "Missing required fields", data)
            else:
                self.log_test("Heal Status API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Heal Status API", False, f"Exception: {str(e)}")
    
    def test_heal_check(self):
        """Test GET /api/heal/check"""
        try:
            response = self.session.get(f"{BACKEND_URL}/heal/check", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["score", "overall_status", "checks"]
                
                if all(field in data for field in required_fields):
                    self.log_test("Heal Check API", True, 
                                f"Score: {data['score']}, Status: {data['overall_status']}, Components: {len(data['checks'])}")
                else:
                    self.log_test("Heal Check API", False, 
                                "Missing required fields", data)
            else:
                self.log_test("Heal Check API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Heal Check API", False, f"Exception: {str(e)}")
    
    def test_heal_config_get(self):
        """Test GET /api/heal/config"""
        try:
            response = self.session.get(f"{BACKEND_URL}/heal/config", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["enabled", "auto_recover", "health_threshold", "storage_type", "storage_path"]
                
                if all(field in data for field in required_fields):
                    self.log_test("Heal Config GET API", True, 
                                f"Storage: {data['storage_type']}, Auto-recover: {data['auto_recover']}")
                    return data
                else:
                    self.log_test("Heal Config GET API", False, 
                                "Missing required fields", data)
            else:
                self.log_test("Heal Config GET API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Heal Config GET API", False, f"Exception: {str(e)}")
        
        return None
    
    def test_heal_config_put(self):
        """Test PUT /api/heal/config"""
        try:
            # Test updating auto_recover to true
            update_data = {"auto_recover": True}
            
            response = self.session.put(f"{BACKEND_URL}/heal/config", 
                                      json=update_data, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("auto_recover") == True:
                    self.log_test("Heal Config PUT API", True, 
                                f"Updated auto_recover to {data['auto_recover']}")
                    
                    # Test switching back to false
                    reset_data = {"auto_recover": False}
                    reset_response = self.session.put(f"{BACKEND_URL}/heal/config", 
                                                    json=reset_data, timeout=10)
                    if reset_response.status_code == 200:
                        self.log_test("Heal Config PUT API (Reset)", True, "Reset auto_recover to false")
                    else:
                        self.log_test("Heal Config PUT API (Reset)", False, 
                                    f"Failed to reset: HTTP {reset_response.status_code}")
                else:
                    self.log_test("Heal Config PUT API", False, 
                                "Config not updated correctly", data)
            else:
                self.log_test("Heal Config PUT API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Heal Config PUT API", False, f"Exception: {str(e)}")
    
    def test_heal_snapshot_create(self):
        """Test POST /api/heal/snapshot"""
        try:
            snapshot_data = {
                "name": "test_snap",
                "description": "Test snapshot for API testing"
            }
            
            response = self.session.post(f"{BACKEND_URL}/heal/snapshot", 
                                       json=snapshot_data, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["id", "name", "size_mb", "file_count", "checksum"]
                
                if all(field in data for field in required_fields):
                    self.test_snapshot_id = data["id"]
                    self.log_test("Heal Snapshot Create API", True, 
                                f"Created snapshot: {data['name']} (ID: {data['id'][:8]}, Size: {data['size_mb']}MB, Files: {data['file_count']})")
                    return data["id"]
                else:
                    self.log_test("Heal Snapshot Create API", False, 
                                "Missing required fields", data)
            else:
                self.log_test("Heal Snapshot Create API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Heal Snapshot Create API", False, f"Exception: {str(e)}")
        
        return None
    
    def test_heal_snapshots_list(self):
        """Test GET /api/heal/snapshots"""
        try:
            response = self.session.get(f"{BACKEND_URL}/heal/snapshots", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    # Check if our test snapshot is in the list
                    if self.test_snapshot_id:
                        snap_ids = [snap.get("id") for snap in data]
                        if self.test_snapshot_id in snap_ids:
                            self.log_test("Heal Snapshots List API", True, 
                                        f"Found {len(data)} snapshots including test snapshot")
                        else:
                            self.log_test("Heal Snapshots List API", True, 
                                        f"Found {len(data)} snapshots (test snapshot not found)")
                    else:
                        self.log_test("Heal Snapshots List API", True, 
                                    f"Found {len(data)} snapshots")
                else:
                    self.log_test("Heal Snapshots List API", False, 
                                "Response is not a list", data)
            else:
                self.log_test("Heal Snapshots List API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Heal Snapshots List API", False, f"Exception: {str(e)}")
    
    def test_heal_evolution(self):
        """Test GET /api/heal/evolution"""
        try:
            response = self.session.get(f"{BACKEND_URL}/heal/evolution", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_test("Heal Evolution API", True, 
                                f"Retrieved {len(data)} evolution events")
                else:
                    self.log_test("Heal Evolution API", False, 
                                "Response is not a list", data)
            else:
                self.log_test("Heal Evolution API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Heal Evolution API", False, f"Exception: {str(e)}")
    
    def test_heal_growth(self):
        """Test GET /api/heal/growth"""
        try:
            response = self.session.get(f"{BACKEND_URL}/heal/growth", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["total_events", "snapshots_created", "is_growing"]
                
                if all(field in data for field in required_fields):
                    self.log_test("Heal Growth API", True, 
                                f"Events: {data['total_events']}, Snapshots: {data['snapshots_created']}, Growing: {data['is_growing']}")
                else:
                    self.log_test("Heal Growth API", False, 
                                "Missing required fields", data)
            else:
                self.log_test("Heal Growth API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Heal Growth API", False, f"Exception: {str(e)}")
    
    def test_heal_verify(self):
        """Test POST /api/heal/verify"""
        try:
            response = self.session.post(f"{BACKEND_URL}/heal/verify", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["passed", "health_score", "components"]
                
                if all(field in data for field in required_fields):
                    self.log_test("Heal Verify API", True, 
                                f"Passed: {data['passed']}, Score: {data['health_score']}, Components: {len(data['components'])}")
                else:
                    self.log_test("Heal Verify API", False, 
                                "Missing required fields", data)
            else:
                self.log_test("Heal Verify API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Heal Verify API", False, f"Exception: {str(e)}")
    
    def test_heal_storage(self):
        """Test GET /api/heal/storage"""
        try:
            response = self.session.get(f"{BACKEND_URL}/heal/storage", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("type") == "local":
                    self.log_test("Heal Storage API", True, 
                                f"Storage type: {data['type']}, Path: {data.get('base_path', 'N/A')}")
                else:
                    self.log_test("Heal Storage API", False, 
                                f"Unexpected storage type: {data.get('type')}", data)
            else:
                self.log_test("Heal Storage API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Heal Storage API", False, f"Exception: {str(e)}")
    
    def test_heal_snapshot_delete(self, snapshot_id: str):
        """Test DELETE /api/heal/snapshot/{snapshot_id}"""
        try:
            response = self.session.delete(f"{BACKEND_URL}/heal/snapshot/{snapshot_id}", 
                                         timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") == True:
                    self.log_test("Heal Snapshot Delete API", True, 
                                f"Deleted snapshot: {snapshot_id[:8]}")
                else:
                    self.log_test("Heal Snapshot Delete API", True, 
                                "Snapshot deleted successfully")
            else:
                self.log_test("Heal Snapshot Delete API", False, 
                            f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_test("Heal Snapshot Delete API", False, f"Exception: {str(e)}")

    def run_all_tests(self):
        """Run all backend API tests"""
        print("=" * 60)
        print("MoltBot Backend API Testing Suite")
        print("=" * 60)
        print(f"Testing backend at: {BACKEND_URL}")
        print()
        
        # Core API tests
        self.test_health_check()
        self.test_providers_api()
        self.test_settings_get()
        self.test_settings_put()
        
        # Chat and conversation tests
        self.test_chat_api()
        self.test_conversations_get()
        
        # Test conversation creation and management
        new_conv_id = self.test_conversations_post()
        
        # Test messages retrieval
        if self.conversation_id:
            self.test_conversation_messages(self.conversation_id)
        
        # Test provider switching
        self.test_provider_switching()
        
        # Clean up - delete test conversation
        if new_conv_id:
            self.test_conversation_delete(new_conv_id)
        
        print("\n" + "=" * 60)
        print("SELF-HEALING API TESTS")
        print("=" * 60)
        
        # Self-healing API tests in order as requested
        self.test_heal_status()
        self.test_heal_check()
        self.test_heal_config_get()
        self.test_heal_config_put()
        
        # Create test snapshot
        test_snap_id = self.test_heal_snapshot_create()
        
        # List snapshots
        self.test_heal_snapshots_list()
        
        # Evolution and growth
        self.test_heal_evolution()
        self.test_heal_growth()
        
        # Verification
        self.test_heal_verify()
        
        # Storage info
        self.test_heal_storage()
        
        # Clean up - delete test snapshot
        if test_snap_id:
            self.test_heal_snapshot_delete(test_snap_id)
        
        # Print summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if total - passed > 0:
            print("\nFAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  ❌ {result['test']}: {result['details']}")
        
        return passed == total

if __name__ == "__main__":
    tester = MoltBotTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed!")
        exit(0)
    else:
        print("\n💥 Some tests failed!")
        exit(1)