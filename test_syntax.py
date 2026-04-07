import py_compile
try:
    py_compile.compile('web.py', doraise=True)
    print("VALID")
except Exception as e:
    print(str(e))
