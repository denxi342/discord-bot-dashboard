#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Update DM send endpoint to support attachments"""

web_file = r'C:\Users\kompd\.gemini\antigravity\scratch\discord_bot\web.py'

with open(web_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Update the validation to allow messages with only attachments
old_validation = '''    data = request.json
    content = data.get('content', '').strip()
    reply_to_id = data.get('reply_to_id')  # ID сообщения на которое отвечаем
    if not content:
        return jsonify({'success': False, 'error': 'Empty message'}), 400'''

new_validation = '''    data = request.json
    content = data.get('content', '').strip()
    reply_to_id = data.get('reply_to_id')  # ID сообщения на которое отвечаем
    attachments = data.get('attachments')  # JSON string of file metadata
    
    # Require either content or attachments
    if not content and not attachments:
        return jsonify({'success': False, 'error': 'Empty message'}), 400'''

content = content.replace(old_validation, new_validation)

# Update INSERT query to include attachments
old_insert = '''        execute_query(\'\'\'
            INSERT INTO dm_messages (dm_id, author_id, content, timestamp, reply_to_id)
            VALUES (%s, %s, %s, %s, %s)
        \'\'\', (dm_id, my_id, content, timestamp, reply_to_id), commit=True)'''

new_insert = '''        execute_query(\'\'\'
            INSERT INTO dm_messages (dm_id, author_id, content, timestamp, reply_to_id, attachments)
            VALUES (%s, %s, %s, %s, %s, %s)
        \'\'\', (dm_id, my_id, content, timestamp, reply_to_id, attachments), commit=True)'''

content = content.replace(old_insert, new_insert)

# Update socket payload to include attachments
old_payload = '''    payload = {
        'dm_id': dm_id,
        'author': username,
        'avatar': avatar,
        'content': content,
        'timestamp': timestamp
    }'''

new_payload = '''    payload = {
        'dm_id': dm_id,
        'author': username,
        'avatar': avatar,
        'content': content,
        'timestamp': timestamp,
        'attachments': attachments
    }'''

content = content.replace(old_payload, new_payload)

# Update return payload
old_return = '''    return jsonify({
        'success': True, 
        'message': {
            'dm_id': dm_id,
            'author': username,
            'avatar': avatar,
            'content': content,
            'timestamp': timestamp
        }
    })'''

new_return = '''    return jsonify({
        'success': True, 
        'message': {
            'dm_id': dm_id,
            'author': username,
            'avatar': avatar,
            'content': content,
            'timestamp': timestamp,
            'attachments': attachments
        }
    })'''

content = content.replace(old_return, new_return)

with open(web_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: Updated DM send endpoint to support attachments")
