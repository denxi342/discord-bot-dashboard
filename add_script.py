#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add attachments.js script to index.html"""

import os

html_file = r'C:\Users\kompd\.gemini\antigravity\scratch\discord_bot\templates\index.html'

with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the dashboard.js line and add attachments.js after it
old_line = '<script src="{{ url_for(\'static\', filename=\'js/dashboard.js\') }}?v=29"></script>'
new_lines = '''<script src="{{ url_for('static', filename='js/dashboard.js') }}?v=29"></script>
    <script src="{{ url_for('static', filename='js/attachments.js') }}"></script>'''

if old_line in content:
    content = content.replace(old_line, new_lines)
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK: Added attachments.js script to index.html")
else:
    print("ERROR: Could not find dashboard.js script line")
