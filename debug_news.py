import requests
import json
from datetime import datetime

def test_news():
    token = '5c8059f45c8059f45c8059f47c5fbdb09955c805c8059f435b61029f3a0276425bc525b'
    group_domain = 'arizona_rp'
    version = '5.131'
    
    print(f"Testing VK API for domain: {group_domain}")
    
    try:
        url = f"https://api.vk.com/method/wall.get?domain={group_domain}&count=5&access_token={token}&v={version}"
        r = requests.get(url, timeout=10)
        data = r.json()
        
        if 'error' in data:
            print("VK API Error:")
            print(json.dumps(data['error'], indent=2, ensure_ascii=False))
        else:
            print("Success! Found items:", len(data.get('response', {}).get('items', [])))
            # Print first item title/text
            items = data.get('response', {}).get('items', [])
            if items:
                print("First item text preview:", items[0].get('text', '')[:100])
                
    except Exception as e:
        print(f"Request Exception: {e}")

if __name__ == "__main__":
    test_news()
