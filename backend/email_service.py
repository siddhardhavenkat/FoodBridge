"""Email via Gmail App Password — pure smtplib, no Flask-Mail dependency."""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

log = logging.getLogger(__name__)

_cfg = {}

def init_mail(app):
    _cfg['user'] = (app.config.get("MAIL_USERNAME") or "").strip()
    _cfg['pwd']  = (app.config.get("MAIL_PASSWORD") or "").strip()
    _cfg['from'] = (app.config.get("MAIL_DEFAULT_SENDER") or _cfg['user']).strip()
    if _cfg['user'] and _cfg['pwd']:
        app.logger.info("✅ Email ready — Gmail: %s", _cfg['user'])
    else:
        app.logger.warning("⚠️  Email disabled — set MAIL_USERNAME and MAIL_PASSWORD (Gmail App Password) in .env")


def _build(to, subject, text_body, html_body=None):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"FoodBridge <{_cfg['from']}>"
    msg["To"]      = to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def _send(to, subject, text_body, html_body=None):
    if not _cfg.get('user') or not _cfg.get('pwd'):
        log.warning("Email skipped — credentials not configured")
        return
    msg = _build(to, subject, text_body, html_body)
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(_cfg['user'], _cfg['pwd'])
            s.sendmail(_cfg['from'], [to], msg.as_string())
        log.info("✅ Email sent to %s | %s", to, subject)
    except smtplib.SMTPAuthenticationError:
        log.error("❌ Gmail auth failed — make sure MAIL_PASSWORD is a 16-char App Password (not your Gmail password). Generate at: myaccount.google.com → Security → App passwords")
        raise
    except Exception as exc:
        log.error("❌ Email send error to %s: %s", to, exc)
        raise


# ── HTML email templates ──────────────────────────────────────────────────────
_HTML_WRAP = """<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f0fdf4;font-family:'Segoe UI',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px;">
<table width="560" style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08);">
<tr><td style="background:linear-gradient(135deg,#16a34a,#15803d);padding:28px 32px;text-align:center;">
  <h1 style="margin:0;color:#fff;font-size:26px;font-weight:900;">🌾 FoodBridge</h1>
  <p style="margin:6px 0 0;color:#bbf7d0;font-size:14px;">Connecting Surplus Food with Those Who Need It</p>
</td></tr>
<tr><td style="padding:32px;">{BODY}</td></tr>
<tr><td style="background:#f8fafc;padding:18px 32px;text-align:center;color:#94a3b8;font-size:12px;">
  © FoodBridge — Food Rescue Platform &nbsp;|&nbsp; <a href="http://127.0.0.1:5000" style="color:#16a34a">Open App</a>
</td></tr>
</table></td></tr></table></body></html>"""


def send_welcome_email(to_email: str, user_name: str, role: str):
    role_line = {
        "restaurant": "List surplus food in 30 seconds. Your pickup OTP will be auto-generated.",
        "ngo":        "Accept food donations from nearby restaurants and track runners live.",
        "runner":     "Accept delivery jobs, share your GPS, and confirm with OTP.",
    }.get(role, "Start using FoodBridge today.")
    text = f"Welcome to FoodBridge, {user_name}!\n\nYour {role.upper()} account is ready.\n\n{role_line}\n\nLogin: http://127.0.0.1:5000/login\n\n— FoodBridge Team"
    html = _HTML_WRAP.replace("{BODY}", f"""
      <h2 style="color:#0f172a;margin:0 0 8px">Welcome, {user_name}! 🎉</h2>
      <p style="color:#475569;margin:0 0 20px">Your <b>{role.upper()}</b> account on FoodBridge is ready.</p>
      <div style="background:#f0fdf4;border-left:4px solid #16a34a;border-radius:10px;padding:14px 18px;margin:0 0 24px;color:#166534;">{role_line}</div>
      <a href="http://127.0.0.1:5000/login" style="display:inline-block;background:linear-gradient(135deg,#16a34a,#15803d);color:#fff;padding:13px 28px;border-radius:12px;text-decoration:none;font-weight:700;font-size:15px;">Login to FoodBridge →</a>
    """)
    _send(to_email, "🌾 Welcome to FoodBridge!", text, html)


def send_reset_email(to_email: str, user_name: str, reset_link: str):
    text = f"Hello {user_name},\n\nReset your FoodBridge password:\n{reset_link}\n\nLink expires in 1 hour. Ignore if you did not request this.\n\n— FoodBridge Team"
    html = _HTML_WRAP.replace("{BODY}", f"""
      <h2 style="color:#0f172a;margin:0 0 8px">Reset Your Password 🔐</h2>
      <p style="color:#475569;margin:0 0 20px">Hello <b>{user_name}</b>, click below to set a new password. This link expires in <b>1 hour</b>.</p>
      <a href="{reset_link}" style="display:inline-block;background:linear-gradient(135deg,#dc2626,#b91c1c);color:#fff;padding:13px 28px;border-radius:12px;text-decoration:none;font-weight:700;font-size:15px;">Reset Password →</a>
      <p style="color:#94a3b8;font-size:13px;margin:20px 0 0;">If you did not request this, you can safely ignore this email.</p>
      <p style="color:#94a3b8;font-size:11px;word-break:break-all;margin:8px 0 0;">Link: {reset_link}</p>
    """)
    _send(to_email, "🔐 Reset Your FoodBridge Password", text, html)


def send_new_donation_email(ngo_email: str, donation: dict):
    items = donation.get("food_items") or [{"name": donation.get("food_type",""), "quantity": donation.get("quantity",""), "unit": donation.get("unit","portions")}]
    items_text  = "\n".join(f"  • {f['name']} — {f['quantity']} {f['unit']}" for f in items)
    items_html  = "".join(f"<li style='margin:4px 0'><b>{f['name']}</b> — {f['quantity']} {f['unit']}</li>" for f in items)
    text = f"New food available!\n\nRestaurant: {donation.get('restaurant_name')}\nFood:\n{items_text}\nLocation: {donation.get('location')}\nExpires in: {donation.get('expires_hours',4)} hours\n\nLogin to accept: http://127.0.0.1:5000/ngo/dashboard\n\n— FoodBridge"
    html = _HTML_WRAP.replace("{BODY}", f"""
      <h2 style="color:#0f172a;margin:0 0 8px">🍛 New Food Available!</h2>
      <p style="color:#475569;margin:0 0 16px"><b>{donation.get('restaurant_name')}</b> has listed food for pickup.</p>
      <div style="background:#f0fdf4;border-radius:12px;padding:16px 20px;margin:0 0 20px;">
        <p style="margin:0 0 8px;font-weight:700;color:#166534;">Food Items:</p>
        <ul style="margin:0;padding-left:18px;color:#0f172a;">{items_html}</ul>
        <p style="margin:12px 0 0;color:#475569;">📍 {donation.get('location')}&nbsp;&nbsp;⏱ Expires in {donation.get('expires_hours',4)} hours</p>
      </div>
      <a href="http://127.0.0.1:5000/ngo/dashboard" style="display:inline-block;background:linear-gradient(135deg,#16a34a,#15803d);color:#fff;padding:13px 28px;border-radius:12px;text-decoration:none;font-weight:700;font-size:15px;">Accept Now →</a>
    """)
    _send(ngo_email, f"🍛 New Food Available — {donation.get('food_type','Food')} | FoodBridge", text, html)
