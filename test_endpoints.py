import requests

BASE_URL = "http://localhost:5000"

def test_endpoint(method, endpoint, data=None):
    try:
        if method.upper() == 'GET':
            response = requests.get(f"{BASE_URL}{endpoint}")
        elif method.upper() == 'POST':
            response = requests.post(f"{BASE_URL}{endpoint}", json=data)
        
        print(f"{method} {endpoint}: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        print(f"❌ Error testing {method} {endpoint}: {e}")
        return None

print("🧪 Testing endpoints...")

# Test GET endpoints
test_endpoint('GET', '/')
test_endpoint('GET', '/health')
test_endpoint('GET', '/test-discord')

# Test POST endpoint
test_endpoint('POST', '/create-ticket', {
    "subject": "Test from Script",
    "description": "Testing the create-ticket endpoint",
    "requester_name": "Test Script",
    "discord_username": "testscript"
})

print("✅ Testing complete!")