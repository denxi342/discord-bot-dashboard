import requests
import json

try:
    url = "http://127.0.0.1:5000/api/arizona/helper"
    payload = {"question": "что будет за дм"}
    print(f"Sending POST to {url} with {payload}")
    
    # We might need to mock a session or login if it requires auth, 
    # but the code in web.py for api_arizona_helper DOES NOT seem to check for 'user' in session explicitly 
    # compared to other endpoints. Let's check web.py content again.
    # Lines 420: def api_arizona_helper(): ... no check for session['user'].
    # So it should work without auth.
    
    r = requests.post(url, json=payload, timeout=5)
    print(f"Status: {r.status_code}")
    print("Response JSON:")
    try:
        data = r.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        print(r.text)

except Exception as e:
    print(f"Test failed: {e}")
