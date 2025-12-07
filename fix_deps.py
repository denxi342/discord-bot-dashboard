import sys
import subprocess

def install(package):
    print(f"Installing {package}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"Successfully installed {package}")
    except subprocess.CalledProcessError as e:
        print(f"Error installing {package}: {e}")
    except Exception as e:
        print(f"Unknown error: {e}")

if __name__ == "__main__":
    # Install critical dependencies for web.py
    install("flask")
    install("flask-socketio")
    install("requests")
    install("psutil")
    print("Done.")
