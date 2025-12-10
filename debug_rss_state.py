import requests
import re
import xml.etree.ElementTree as ET

def find_group_id():
    url = "https://vk.com/arizonastaterp"
    print(f"Fetching HTML for: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {r.status_code}")
        
        # Regex to find group ID
        # often "owner_id":-12345 or "public12345" or "club12345"
        # or "group_id":12345
        
        match = re.search(r'"group_id":(\d+)', r.text)
        if match:
            print(f"Found group_id: {match.group(1)}")
            check_rss(match.group(1))
            return

        match = re.search(r'wall-(\d+)_', r.text)
        if match:
             print(f"Found wall ID: {match.group(1)}")
             check_rss(match.group(1))
             return

        print("Could not find ID in HTML.")
        print(r.text[:500])
            
    except Exception as e:
        print(f"Error: {e}")

def check_rss(group_id):
    rss_url = f"https://vk.com/rss.php?owner_id=-{group_id}"
    print(f"Checking RSS: {rss_url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        r = requests.get(rss_url, headers=headers, timeout=10)
        if '<channel>' in r.text:
            print("SUCCESS! RSS is valid.")
            root = ET.fromstring(r.content)
            print("Title:", root.find('.//title').text)
        else:
            print("RSS failed or empty.")
            print(r.text[:200])
    except Exception as e:
        print(f"RSS Error: {e}")

if __name__ == "__main__":
    find_group_id()
