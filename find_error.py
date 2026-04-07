import ast
import traceback
import sys

path = 'web.py'
try:
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()
    ast.parse(source)
    print("SUCCESS: VALID")
except SyntaxError as e:
    print(f"FAILED: LINE: {e.lineno}, MSG: {e.msg}")
    if e.text:
        print(f"OFFENDING TEXT: {e.text.strip()}")
except Exception as e:
    print(f"FAILED: OTHER: {str(e)}")
    traceback.print_exc(file=sys.stdout)
