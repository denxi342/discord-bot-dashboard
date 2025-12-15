#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Update api_dm_messages_by_id to return attachments"""

web_file = r'C:\Users\kompd\.gemini\antigravity\scratch\discord_bot\web.py'

with open(web_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Update SELECT query to include attachments
old_select = '''    rows = execute_query("""
        SELECT dm.id, dm.content, dm.timestamp, u.username, u.avatar, 
               dm.is_pinned, dm.edited_at, dm.reply_to_id, u.id as author_id
        FROM dm_messages dm
        JOIN users u ON u.id = dm.author_id
        WHERE dm.dm_id = %s
        ORDER BY dm.timestamp ASC
    """, (dm_id,), fetch_all=True)'''

new_select = '''    rows = execute_query("""
        SELECT dm.id, dm.content, dm.timestamp, u.username, u.avatar, 
               dm.is_pinned, dm.edited_at, dm.reply_to_id, u.id as author_id, dm.attachments
        FROM dm_messages dm
        JOIN users u ON u.id = dm.author_id
        WHERE dm.dm_id = %s
        ORDER BY dm.timestamp ASC
    """, (dm_id,), fetch_all=True)'''

content = content.replace(old_select, new_select)

# Update message dict to include attachments
old_append = '''        messages.append({
            'id': msg_id,
            'content': r[1],
            'timestamp': r[2],
            'username': r[3],
            'avatar': r[4] if r[4] else DEFAULT_AVATAR,
            'is_pinned': bool(r[5]),
            'edited_at': r[6],
            'reply_to': reply_preview,
            'author_id': r[8],
            'reactions': reactions
        })'''

new_append = '''        messages.append({
            'id': msg_id,
            'content': r[1],
            'timestamp': r[2],
            'username': r[3],
            'avatar': r[4] if r[4] else DEFAULT_AVATAR,
            'is_pinned': bool(r[5]),
            'edited_at': r[6],
            'reply_to': reply_preview,
            'author_id': r[8],
            'reactions': reactions,
            'attachments': r[9]  # JSON string of attachments
        })'''

content = content.replace(old_append, new_append)

with open(web_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: Updated api_dm_messages_by_id to return attachments")
