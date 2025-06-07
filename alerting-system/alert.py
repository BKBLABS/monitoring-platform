import smtplib


def send_alert(subject, body):
    msg = f"Subject: {subject}\n\n{body}"
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login("your_email@gmail.com", "your_password")
    server.sendmail("your_email@gmail.com", "target@example.com", msg)
    server.quit()
