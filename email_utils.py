from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from dotenv import load_dotenv
import os

load_dotenv()

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,      
    MAIL_SSL_TLS=False,      
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)

async def send_otp_email(email: str, otp: str):
    message = MessageSchema(
        subject="Your Task Manager OTP Verification Code",
        recipients=[email],
        body=f"Your OTP code is: {otp}\n\nIt expires in 10 minutes.",
        subtype="plain"
    )
    fm = FastMail(conf)
    await fm.send_message(message)
