#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Update handleInput to support file attachments"""

import re

js_file = r'C:\Users\kompd\.gemini\antigravity\scratch\discord_bot\static\js\dashboard.js'

with open(js_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace handleInput function
old_pattern = r'''handleInput: async \(\) => \{
        const input = document\.getElementById\('global-input'\);
        if \(!input\) \{
            console\.error\('global-input element not found!'\);
            return;
        \}

        const text = input\.value\.trim\(\);
        console\.log\('\[handleInput\] text:', text, 'currentChannel:', DiscordModule\.currentChannel, 'activeDM:', DiscordModule\.activeDM\);

        if \(!text\) return;
        input\.value = '';'''

new_code = '''handleInput: async () => {
        const input = document.getElementById('global-input');
        if (!input) {
            console.error('global-input element not found!');
            return;
        }

        const text = input.value.trim();
        console.log('[handleInput] text:', text, 'currentChannel:', DiscordModule.currentChannel, 'activeDM:', DiscordModule.activeDM);

        // Upload files first if any
        const attachments = await DiscordModule.uploadFiles();
        
        // Require either text or attachments  
        if (!text && attachments.length === 0) return;
        input.value = '';'''

content = re.sub(old_pattern, new_code, content)

# Also update the message sending calls to include attachments
# Update addMessage calls
content = content.replace(
    "author: 'You', avatar: DEFAULT_AVATAR, text: text\n            });",
    "author: 'You', avatar: DEFAULT_AVATAR, text: text, attachments: attachments\n            });"
)

# Update sendDMMessage call
content = content.replace(
    "DiscordModule.sendDMMessage(DiscordModule.activeDM, text);",
    "DiscordModule.sendDMMessage(DiscordModule.activeDM, text, attachments);"
)

# Update sendMessage call
content = content.replace(
    "DiscordModule.sendMessage(DiscordModule.currentChannel, text);",
    "DiscordModule.sendMessage(DiscordModule.currentChannel, text, attachments);"
)

with open(js_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: Updated handleInput to support attachments")
