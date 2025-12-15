#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Update sendDMMessage to support attachments"""

import re

js_file = r'C:\Users\kompd\.gemini\antigravity\scratch\discord_bot\static\js\dashboard.js'

with open(js_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Update function signature and validation
old_signature = 'sendDMMessage: async (dmId, text) => {'
new_signature = 'sendDMMessage: async (dmId, text, attachments = []) => {'

content = content.replace(old_signature, new_signature)

# Update the validation - allow messages with only attachments
old_validation = '        if (!text) return;'
new_validation = '        if (!text && (!attachments || attachments.length === 0)) return;'

content = content.replace(old_validation, new_validation)

# Update the payload to include attachments
old_payload = '''            const payload = { content: text };
            if (DiscordModule.replyingTo) {
                payload.reply_to_id = DiscordModule.replyingTo.id;
                DiscordModule.cancelReply(); // Clear reply state
            }'''

new_payload = '''            const payload = { content: text };
            if (attachments && attachments.length > 0) {
                payload.attachments = JSON.stringify(attachments);
            }
            if (DiscordModule.replyingTo) {
                payload.reply_to_id = DiscordModule.replyingTo.id;
                DiscordModule.cancelReply(); // Clear reply state
            }'''

content = content.replace(old_payload, new_payload)

# Update optimistic UI rendering to include attachments
old_optimistic = '''            box.innerHTML += `
            <div class="dm-bubble own sending" id="${tempId}">
                <div class="dm-bubble-content">
                    <div class="dm-bubble-text">${Utils.escapeHtml(text)}</div>
                    <div class="dm-bubble-time"><i class="fa-solid fa-circle-notch fa-spin"></i></div>
                </div>
            </div>`;'''

new_optimistic = '''            // Render attachments for optimistic UI
            let attachmentHTML = '';
            if (attachments && attachments.length > 0) {
                attachmentHTML = DiscordModule.renderAttachments(attachments);
            }
            
            box.innerHTML += `
            <div class="dm-bubble own sending" id="${tempId}">
                <div class="dm-bubble-content">
                    ${text ? `<div class="dm-bubble-text">${Utils.escapeHtml(text)}</div>` : ''}
                    ${attachmentHTML}
                    <div class="dm-bubble-time"><i class="fa-solid fa-circle-notch fa-spin"></i></div>
                </div>
            </div>`;'''

content = content.replace(old_optimistic, new_optimistic)

with open(js_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: Updated sendDMMessage to support attachments")
