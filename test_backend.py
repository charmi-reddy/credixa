import urllib.request
import json

base_url = "http://localhost:8000"

def post(url, data=None):
    req = urllib.request.Request(url, method="POST")
    if data:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(data).encode("utf-8")
    with urllib.request.urlopen(req, data=data) as f:
        return f.status, f.read().decode("utf-8")

def get(url):
    with urllib.request.urlopen(url) as f:
        return f.status, f.read().decode("utf-8")

def test_flow():
    # 1. Create Invoice
    print("Creating invoice...")
    try:
        status, resp = post(f"{base_url}/create_invoice", {"amount": 1000000})
        print(f"Status: {status}, Response: {resp}")
    except Exception as e:
        print(f"Error: {e}")
    
    # 2. Request Financing
    print("\nRequesting financing...")
    try:
        status, resp = post(f"{base_url}/request_financing")
        print(f"Status: {status}, Response: {resp}")
    except Exception as e:
        print(f"Error: {e}")
    
    # 3. Check Status
    print("\nChecking status...")
    try:
        status, resp = get(f"{base_url}/status")
        print(f"Status: {status}, Response: {resp}")
    except Exception as e:
        print(f"Error: {e}")
    
    # 4. Fund Invoice
    print("\nFunding invoice...")
    try:
        status, resp = post(f"{base_url}/fund_invoice")
        print(f"Status: {status}, Response: {resp}")
    except Exception as e:
        print(f"Error: {e}")
    
    # 5. Final Status
    print("\nFinal status...")
    try:
        status, resp = get(f"{base_url}/status")
        print(f"Status: {status}, Response: {resp}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_flow()
