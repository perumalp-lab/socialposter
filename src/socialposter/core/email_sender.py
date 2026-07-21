from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Literal

logger = logging.getLogger("socialposter")

TEMPLATE_CONTENT: dict[str, tuple[str, str]] = {
    "confirmation_email_purchase": ("Purchase Confirmation", "Your purchase has been confirmed. Thank you for your order!"),
    "reminder_email_purchase_dropoff": ("Complete Your Purchase", "You have items in your cart. Complete your purchase now."),
    "reminder_email_failed_purchase": ("Payment Failed", "Your recent payment attempt failed. Please update your payment details."),
    "reminder_email_one_day_before_expiry": ("Subscription Expiring Soon", "Your subscription expires tomorrow. Renew now to avoid interruption."),
    "notification_email_new_post": ("New Post Published", "A new post has been published on your account."),
    "notification_email_post_comment": ("New Comment on Your Post", "Someone commented on your post."),
    "notification_email_comment_like": ("Comment Liked", "Someone liked your comment."),
    "notification_email_comment_reply": ("New Reply to Your Comment", "Someone replied to your comment."),
    "notification_email_tagging_comment": ("You Were Tagged in a Comment", "Someone tagged you in a comment."),
    "promotional_email_creation": ("New Promotion Created", "A new promotion has been created."),
    "notification_email_single_workshop": ("Workshop Created", "Your single workshop has been created successfully."),
    "notification_email_recurring_workshop": ("Recurring Workshop Created", "Your recurring workshop has been scheduled."),
    "notification_email_reschedule_workshop": ("Workshop Rescheduled", "Your workshop has been rescheduled."),
    "notification_email_workshop_cancellation": ("Workshop Cancelled", "Your workshop has been cancelled."),
    "reminder_email_24h_before_workshop": ("Workshop Tomorrow", "Your workshop starts in 24 hours."),
    "reminder_email_30m_before_workshop": ("Workshop Starting Soon", "Your workshop starts in 30 minutes."),
    "reminder_email_15m_before_workshop": ("Workshop Starting Soon", "Your workshop starts in 15 minutes."),
    "post_workshop_email_15m_after": ("Workshop Follow-Up", "Thanks for attending the workshop. Here's a summary."),
    "notification_email_subscription_expired": ("Subscription Expired", "Your subscription has expired."),
    "notification_email_10pct_course": ("10% Course Complete", "Great start! You've completed 10% of your course."),
    "notification_email_50pct_course": ("Halfway Through Course", "You're halfway through your course. Keep going!"),
    "notification_email_100pct_course": ("Course Complete", "Congratulations! You've completed your course."),
    "confirmation_email_1on1_consultation": ("Consultation Booked", "Your 1-on-1 consultation has been booked."),
    "reminder_email_30m_before_1on1": ("Consultation Starting Soon", "Your 1-on-1 consultation starts in 30 minutes."),
    "cancellation_email_1on1_consultation": ("Consultation Cancelled", "Your 1-on-1 consultation has been cancelled."),
}


def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    from_name: str,
    from_addr: str,
    reply_to: str,
    to_addr: str,
    subject: str,
    body_text: str,
    *,
    use_tls: bool = True,
) -> dict:
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to

    html = (
        "<html><body style='font-family:sans-serif;padding:20px;'>"
        f"<p>{body_text}</p>"
        "<hr style='margin-top:30px;color:#ccc;'>"
        "<p style='font-size:12px;color:#888;'>Sent via Kryptams</p>"
        "</body></html>"
    )
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        if use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.starttls(context=context)
                if smtp_username:
                    server.login(smtp_username, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
                if smtp_username:
                    server.login(smtp_username, smtp_password)
                server.send_message(msg)
        logger.info("Email sent to %s — subject=%s", to_addr, subject)
        return {"ok": True}
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending to %s: %s", to_addr, e)
        return {"ok": False, "error": str(e)}
    except OSError as e:
        logger.error("Connection error sending to %s: %s", to_addr, e)
        return {"ok": False, "error": str(e)}


def test_connection(
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    *,
    use_tls: bool = True,
) -> dict:
    try:
        if use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls(context=context)
                if smtp_username:
                    server.login(smtp_username, smtp_password)
                server.quit()
        else:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as server:
                if smtp_username:
                    server.login(smtp_username, smtp_password)
                server.quit()
        return {"ok": True}
    except smtplib.SMTPException as e:
        return {"ok": False, "error": str(e)}
    except OSError as e:
        return {"ok": False, "error": str(e)}
