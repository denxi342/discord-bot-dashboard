#!/usr/bin/env python3
"""Fix the addLogEntry function in templates/index.html"""

import re

# Read the file
with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the correct function
correct_function = """function addLogEntry(log) {
                    const container = document.getElementById('log-container');
                    const entry = document.createElement('div');
                    entry.className = 'log-entry';
                    entry.innerHTML = `
                <span class="log-time">${log.timestamp}</span>
                <span class="log-level ${log.level}">[${log.level.toUpperCase()}]</span>
                <span>${log.message}</span>
            `;
                    container.insertBefore(entry, container.firstChild);

                    // Keep only last 50 entries
                    while (container.children.length > 50) {
                        container.removeChild(container.lastChild);
                    }
                }"""

# Pattern to match the problematic function
# We'll match from "function addLogEntry(log)" to the closing "}" that belongs to it
pattern = r'function addLogEntry\(log\) \{[\s\S]*?container\.insertBefore\(entry, container\.firstChild\);[\s\S]*?while \(container\.children\.length > 50\) \{[\s\S]*?\}[\s\S]*?\n                \}'

# Replace
new_content = re.sub(pattern, correct_function, content, count=1)

# Check if replacement was made
if new_content == content:
    print("WARNING: No changes made - pattern not found!")
    print("Let's try a simpler approach...")
    
    # Find the start of the function
    start_marker = "function addLogEntry(log) {"
    start_pos = content.find(start_marker)
    
    if start_pos == -1:
        print("ERROR: Could not find addLogEntry function!")
        exit(1)
    
    # Find the end - we need to find the matching closing brace
    # The function ends after the second closing brace after "container.insertBefore"
    insertBefore_pos = content.find("container.insertBefore(entry, container.firstChild);", start_pos)
    
    if insertBefore_pos == -1:
        print("ERROR: Could not find insertBefore statement!")
        exit(1)
    
    # Now find the end of the function by counting braces
    brace_count = 0
    in_function = False
    end_pos = start_pos
    
    for i in range(start_pos, len(content)):
        if content[i] == '{':
            brace_count += 1
            in_function = True
        elif content[i] == '}':
            brace_count -= 1
            if in_function and brace_count == 0:
                end_pos = i + 1
                break
    
    # Replace the old function with the new one
    # Preserve indentation
    indent = "                "
    new_content = content[:start_pos] + indent + correct_function + content[end_pos:]

# Write the fixed content
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ File fixed successfully!")
print("Changes made:")
print("- Removed misplaced Arizona news loading code from addLogEntry()")
print("- Function now only adds log entries and removes old ones")
