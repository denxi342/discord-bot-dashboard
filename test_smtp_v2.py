import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USER = "octavesup@outlook.com"
SMTP_PASSWORD = "Tt0pn3n4d022672267^^"

def test_email():
    try:
        print(f"[*] Attempting to connect to {SMTP_SERVER}:{SMTP_PORT}...")
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = SMTP_USER # Send to self
        msg['Subject'] = "SMTP Test"
        msg.attach(MIMEText("This is a test message.", 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.set_debuglevel(1) # See full conversation
        server.starttls()
        print("[*] Starting TLS...")
        server.login(SMTP_USER, SMTP_PASSWORD)
        print("[+] Login successful!")
        server.send_message(msg)
        print("[+] Message sent!")
        server.quit()
    except Exception as e:
        print(f"[!] SMTP Error: {e}")

if __name__ == "__main__":
    test_email()
