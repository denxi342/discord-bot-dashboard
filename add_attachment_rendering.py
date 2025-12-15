#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add attachment rendering to DM messages"""

import re

js_file = r'C:\Users\kompd\.gemini\antigravity\scratch\discord_bot\static\js\dashboard.js'

with open(js_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the DM message rendering code and add attachments
old_dm_rendering = r'''box\.innerHTML \+= `
                        <div class="dm-bubble other">
                            <img src="\$\{data\.avatar\}" onerror="this\.onerror=null;this\.src=window\.DEFAULT_AVATAR" class="dm-bubble-avatar">
                            <div class="dm-bubble-content">
                                <div class="dm-bubble-text">\$\{Utils\.escapeHtml\(data\.content\)\}</div>
                                <div class="dm-bubble-time">\$\{new Date\(data\.timestamp \* 1000\)\.toLocaleTimeString\(\[\], \{ hour: '2-digit', minute: '2-digit' \}\)\}</div>
                            </div>
                        </div>`;'''

new_dm_rendering = r'''// Render attachments if present
                    let attachmentHTML = '';
                    if (data.attachments) {
                        const attachments = typeof data.attachments === 'string' ? JSON.parse(data.attachments) : data.attachments;
                        attachmentHTML = DiscordModule.renderAttachments(attachments);
                    }
                    
                    box.innerHTML += `
                        <div class="dm-bubble other">
                            <img src="${data.avatar}" onerror="this.onerror=null;this.src=window.DEFAULT_AVATAR" class="dm-bubble-avatar">
                            <div class="dm-bubble-content">
                                <div class="dm-bubble-text">${Utils.escapeHtml(data.content)}</div>
                                ${attachmentHTML}
                                <div class="dm-bubble-time">${new Date(data.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                            </div>
                        </div>`;'''

# Try to replace with regex
content = re.sub(old_dm_rendering, new_dm_rendering, content, flags=re.MULTILINE)

# Also update the part where we send our own messages 
# Find where own messages are rendered optimistically
# This is typically in sendDMMessage or similar

with open(js_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: Added attachment rendering to DM messages")
