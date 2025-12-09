import requests
import xml.etree.ElementTree as ET

def debug_state_rss():
    # User's provided group
    domain = "arizonastaterp" 
    url = f"https://vk.com/rss.php?domain={domain}"
    
    print(f"Testing RSS for: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {r.status_code}")
        print(f"Content Length: {len(r.content)}")
        print(f"Start of content: {r.text[:200]}")
        
        if r.status_code == 200:
            if '<channel>' not in r.text and '<item>' not in r.text:
                print("WARNING: XML seems empty or invalid content.")
            else:
                root = ET.fromstring(r.content)
                items = root.findall('.//item')
                print(f"Items found: {len(items)}")
        else:
            print("Failed to fetch RSS.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_state_rss()
