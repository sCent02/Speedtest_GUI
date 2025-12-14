import requests
import sys
import json
from datetime import datetime
from pathlib import Path

class SpeedtestAPITester:
    def __init__(self, base_url="https://netspeed-capture.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.errors = []

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                error_msg = f"Expected {expected_status}, got {response.status_code}"
                print(f"❌ Failed - {error_msg}")
                print(f"   Response: {response.text[:200]}...")
                self.errors.append(f"{name}: {error_msg}")
                return False, {}

        except requests.exceptions.Timeout:
            error_msg = f"Request timeout after {timeout}s"
            print(f"❌ Failed - {error_msg}")
            self.errors.append(f"{name}: {error_msg}")
            return False, {}
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"❌ Failed - {error_msg}")
            self.errors.append(f"{name}: {error_msg}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root Endpoint", "GET", "", 200)

    def test_status_endpoints(self):
        """Test status check endpoints"""
        # Test GET status
        success1, _ = self.run_test("Get Status Checks", "GET", "status", 200)
        
        # Test POST status
        success2, response = self.run_test(
            "Create Status Check", 
            "POST", 
            "status", 
            200,
            data={"client_name": f"test_client_{datetime.now().strftime('%H%M%S')}"}
        )
        
        return success1 and success2

    def test_speedtest_validation(self):
        """Test speedtest URL validation"""
        # Test with empty URLs
        success1, _ = self.run_test(
            "Empty URLs Validation",
            "POST",
            "process-speedtest",
            400,
            data={"urls": []}
        )

        # Test with invalid URLs
        success2, _ = self.run_test(
            "Invalid URLs Validation",
            "POST",
            "process-speedtest", 
            400,
            data={"urls": ["https://google.com", "invalid-url"]}
        )

        return success1 and success2

    def test_valid_speedtest_processing(self):
        """Test processing valid speedtest URLs"""
        # Use sample URLs from the frontend
        sample_urls = [
            "https://www.speedtest.net/my-result/a/11295159508",
            "https://www.speedtest.net/my-result/a/11295160960"
        ]
        
        # This test might take longer due to screenshot capture
        success, response = self.run_test(
            "Valid Speedtest Processing",
            "POST",
            "process-speedtest",
            200,
            data={"urls": sample_urls},
            timeout=120  # Longer timeout for screenshot capture
        )
        
        if success and response:
            # Verify response structure
            required_fields = ['success', 'message', 'file_path']
            for field in required_fields:
                if field not in response:
                    print(f"❌ Missing field in response: {field}")
                    self.errors.append(f"Valid Speedtest Processing: Missing {field} in response")
                    return False
            
            # Check if file_path is provided
            if not response.get('file_path'):
                print(f"❌ No file_path in response")
                self.errors.append("Valid Speedtest Processing: No file_path provided")
                return False
                
            print(f"✅ Response contains required fields")
            print(f"   File path: {response.get('file_path')}")
            return True
        
        return success

    def test_download_endpoint(self):
        """Test file download endpoint - this requires a file to exist"""
        # This test will likely fail if no file exists, which is expected
        success, _ = self.run_test(
            "Download Endpoint (Test File)",
            "GET",
            "download/test_file.xlsx",
            404  # Expecting 404 since file doesn't exist
        )
        return success

def main():
    print("🚀 Starting Speedtest API Backend Tests")
    print("=" * 50)
    
    tester = SpeedtestAPITester()
    
    # Run all tests
    test_results = []
    
    print("\n📡 Testing Basic Endpoints...")
    test_results.append(("Root Endpoint", tester.test_root_endpoint()[0]))
    test_results.append(("Status Endpoints", tester.test_status_endpoints()))
    
    print("\n🔍 Testing Validation...")
    test_results.append(("URL Validation", tester.test_speedtest_validation()))
    
    print("\n📸 Testing Screenshot Processing...")
    test_results.append(("Speedtest Processing", tester.test_valid_speedtest_processing()))
    
    print("\n📥 Testing Download...")
    test_results.append(("Download Endpoint", tester.test_download_endpoint()))
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    for test_name, success in test_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nTotal Tests: {tester.tests_run}")
    print(f"Passed: {tester.tests_passed}")
    print(f"Failed: {tester.tests_run - tester.tests_passed}")
    
    if tester.errors:
        print(f"\n❌ ERRORS FOUND:")
        for error in tester.errors:
            print(f"   • {error}")
    
    # Return exit code
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())