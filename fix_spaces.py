import os
path = r'c:\Users\kompd\.gemini\antigravity\scratch\discord_bot\static\js\dashboard.js'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('getElementById(`dm - messages - ${dmId} `)', 'getElementById(`dm-messages-${dmId}`)')
content = content.replace('fetch(`/ api / dms / by_id / ${dmId}/send`', 'fetch(`/api/dms/by_id/${dmId}/send`')

# Also fix the weird HTML replacements
content = content.replace('< div class="dm-bubble own sending', '<div class="dm-bubble own sending')
content = content.replace('id = "${tempId}" oncontextmenu = "return false;" >', 'id="${tempId}" oncontextmenu="return false;">')
content = content.replace('</div >', '</div>')
content = content.replace('< div class="dm-bubble-reply" >', '<div class="dm-bubble-reply">')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Patched successfully')
