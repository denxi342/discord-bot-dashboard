#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Update chat input area in index.html to add file upload button"""

import os
import re

html_file = r'C:\Users\kompd\.gemini\antigravity\scratch\discord_bot\templates\index.html'

with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the input button
old_button = '<button class="input-btn"><i class="fa-solid fa-circle-plus"></i></button>'
new_content = '''<button class="input-btn" id="attach-file-btn" title="Прикрепить файл" onclick="document.getElementById('file-input-hidden').click()"><i class="fa-solid fa-paperclip"></i></button>
                    <input type="file" id="file-input-hidden" multiple style="display:none;" onchange="DiscordModule.handleFileSelect(this)">
                    <div id="file-preview-container" style="display:none;"></div>'''

if old_button in content:
    content = content.replace(old_button, new_content)
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK: Updated chat input area with file upload button")
else:
    print("ERROR: Could not find input button")
