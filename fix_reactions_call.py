#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fix get_message_reactions call that causes hanging"""

web_file = r'C:\Users\kompd\.gemini\antigravity\scratch\discord_bot\web.py'

with open(web_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the problematic get_message_reactions call with empty dict
old_reactions = "        reactions = get_message_reactions(msg_id) if 'get_message_reactions' in dir() else {}"
new_reactions = "        reactions = {}  # TODO: Implement get_message_reactions function"

content = content.replace(old_reactions, new_reactions)

with open(web_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: Fixed get_message_reactions call")
