import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USER = "octavesup@outlook.com"
SMTP_PASSWORD = "fpesftmxocnbhsfl"

def test_email():
    try:
        print(f"[*] Connecting to {SMTP_SERVER}:{SMTP_PORT}...")
        msg = MIMEMultipart()
        msg['From'] = f"Octave <{SMTP_USER}>"
        msg['To'] = SMTP_USER
        msg['Subject'] = "Final SMTP Test"
        msg.attach(MIMEText("Test message content.", 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.set_debuglevel(1)
        server.starttls()
        print("[*] Performing login...")
        server.login(SMTP_USER, SMTP_PASSWORD)
        print("[SUCCESS] Logged in!")
        server.send_message(msg)
        print("[SUCCESS] Message sent!")
        server.quit()
    except Exception as e:
        print(f"[ERROR] SMTP Failed: {e}")

if __name__ == "__main__":
    test_email()
