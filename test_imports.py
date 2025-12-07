
try:
    import discord
    print("discord: OK")
except ImportError as e:
    print(f"discord: FAIL ({e})")

try:
    from dotenv import load_dotenv
    print("dotenv: OK")
except ImportError as e:
    print(f"dotenv: FAIL ({e})")

try:
    import cryptography
    print("cryptography: OK")
except ImportError as e:
    print(f"cryptography: FAIL ({e})")

try:
    import matplotlib
    print("matplotlib: OK")
except ImportError as e:
    print(f"matplotlib: FAIL ({e})")
