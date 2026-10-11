"""Real email delivery through Brevo's HTTPS API (works on Render's free plan, which blocks SMTP)."""
import json
import logging
import urllib.error
import urllib.request

log = logging.getLogger(__name__)
BREVO_URL = "https://api.brevo.com/v3/smtp/email"


class EmailDeliveryError(Exception):
    pass


def send_via_brevo(api_key, sender_email, sender_name, to, code, ttl_minutes=10, url=BREVO_URL, timeout=10):
    if not api_key or not sender_email:
        raise EmailDeliveryError("Email delivery isn't set up on the server yet. Please contact the administrator.")
    text = (f"Your College Academic Assistant verification code is {code}.\n"
            f"It expires in {ttl_minutes} minutes. If you didn't try to sign up, you can ignore this email.")
    html = (f"<p>Your College Academic Assistant verification code is:</p>"
            f"<p style=\"font-size:28px;font-weight:700;letter-spacing:6px\">{code}</p>"
            f"<p>It expires in {ttl_minutes} minutes. If you didn't try to sign up, you can ignore this email.</p>")
    body = json.dumps({
        "sender": {"name": sender_name or "College Academic Assistant", "email": sender_email},
        "to": [{"email": to}],
        "subject": "Your verification code",
        "textContent": text,
        "htmlContent": html,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "api-key": api_key, "accept": "application/json", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status not in (200, 201, 202):
                raise EmailDeliveryError("We couldn't send the verification email right now. Please try again in a minute.")
    except urllib.error.HTTPError as e:
        log.error("Brevo rejected the email: HTTP %s %s", e.code, e.read()[:300])
        raise EmailDeliveryError("We couldn't send the verification email right now. Please try again in a minute.")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        log.error("Brevo request failed: %s", e)
        raise EmailDeliveryError("We couldn't reach the email service. Please try again in a minute.")
