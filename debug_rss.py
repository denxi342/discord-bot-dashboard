import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime

def debug_rss():
    url = "https://vk.com/rss.php?domain=arizona_rp"
    print(f"Fetching {url}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {r.status_code}")
        print(f"Encoding (detected): {r.encoding}")
        print(f"Content Start: {r.text[:200]}")
        
        # Try finding channel
        try:
            # Check for encoding declaration in XML
            if 'encoding="windows-1251"' in r.text:
                print("Detected windows-1251 declaration.")
                # If requests didn't auto-detect, force it.
                # But let's see if ET parses it naturally from bytes if we pass bytes.
                pass
            
            root = ET.fromstring(r.content) # Use bytes for ET to handle encoding
            channel = root.find('channel')
            
            if not channel:
                print("ERROR: No <channel> found in XML")
                return

            items = channel.findall('item')
            print(f"Found {len(items)} items.")
            
            for i, item in enumerate(items[:1]):
                title = item.find('title').text
                desc = item.find('description').text
                print(f"Item {i+1}: {title}")
                print(f"Description snippet: {desc[:100]}...")
                
        except ET.ParseError as e:
            print(f"XML PARSE ERROR: {e}")
            
    except Exception as e:
        print(f"REQUEST ERROR: {e}")

if __name__ == "__main__":
    debug_rss()
