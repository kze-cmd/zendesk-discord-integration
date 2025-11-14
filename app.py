"""
Secure Flask app for forwarding Zendesk ticket comments to Discord.

Features:
- Uses environment variables for secrets (no hardcoding)
- Optional Zendesk webhook HMAC verification (if ZENDESK_WEBHOOK_SECRET set)
- Safe logging (truncates sensitive data)
- Robust JSON parsing and validation
- Accepts Discord 200/204 responses as success
- Minimal leakage of PII in logs

Usage:
1. Set environment variables (example):
   export ZENDESK_SUBDOMAIN=your_subdomain
   export ZENDESK_EMAIL=you@example.com
   export ZENDESK_API_TOKEN=xxxxx
   export DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
   export ZENDESK_WEBHOOK_SECRET=optional_shared_secret

2. Run:
   pip install flask requests python-dotenv
   flask run

This file intentionally avoids printing or storing secrets.
"""

import os
import json
import hmac
import hashlib
import logging
from datetime import datetime
from typing import Optional

import requests
from flask import Flask, request, jsonify, abort

# --- Configuration ---
# Read critical values from environment variables
ZENDESK_SUBDOMAIN = os.getenv('ZENDESK_SUBDOMAIN')
ZENDESK_EMAIL = os.getenv('ZENDESK_EMAIL')
ZENDESK_API_TOKEN = os.getenv('ZENDESK_API_TOKEN')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
ZENDESK_WEBHOOK_SECRET = os.getenv('ZENDESK_WEBHOOK_SECRET')  # optional

# Quick safety check: ensure required values are present
REQUIRED = {
    'ZENDESK_SUBDOMAIN': ZENDESK_SUBDOMAIN,
    'ZENDESK_EMAIL': ZENDESK_EMAIL,
    'ZENDESK_API_TOKEN': ZENDESK_API_TOKEN,
    'DISCORD_WEBHOOK_URL': DISCORD_WEBHOOK_URL,
}

missing = [k for k, v in REQUIRED.items() if not v]

# --- Logging ---
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger('zendesk-discord')

if missing:
    logger.warning('Missing environment variables: %s', ', '.join(missing))

app = Flask(__name__)

# --- Utilities ---

def truncate(s: Optional[str], length: int = 200) -> str:
    if s is None:
        return ''
    s = str(s)
    return (s[:length] + '...') if len(s) > length else s


def verify_zendesk_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify Zendesk webhook signature (if provided). Zendesk uses HMAC-SHA256.
    The header may look like: "sha256=..."
    """
    if not signature_header or not secret:
        return False

    try:
        if signature_header.startswith('sha256='):
            signature = signature_header.split('=', 1)[1]
        else:
            signature = signature_header

        mac = hmac.new(secret.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
        computed = mac.hexdigest()
        # Use hmac.compare_digest to avoid timing attacks
        return hmac.compare_digest(computed, signature)
    except Exception:
        return False


def is_discord_success(status_code: int) -> bool:
    return status_code in (200, 204)


def safe_post_discord(payload: dict, timeout: int = 15) -> requests.Response:
    """Post to Discord webhook and return response. Exceptions bubble up to caller."""
    headers = {'Content-Type': 'application/json'}
    return requests.post(DISCORD_WEBHOOK_URL, json=payload, headers=headers, timeout=timeout)


# --- Routes ---

@app.route('/')
def home():
    status = {
        'service': 'zendesk-discord-forwarder',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'configured': not bool(missing),
    }
    return jsonify(status)


@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'configured': not bool(missing),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })


@app.route('/test')
def test():
    """Lightweight connectivity tests for configured services. Does not log secrets."""
    if missing:
        return jsonify({'status': 'error', 'message': 'Missing environment variables', 'missing': missing}), 400

    results = {'app': 'running', 'timestamp': datetime.utcnow().isoformat() + 'Z'}

    # Zendesk test - small, safe GET for 1 ticket (doesn't expose token in logs)
    try:
        url = f'https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets.json?per_page=1'
        resp = requests.get(url, auth=(f'{ZENDESK_EMAIL}/token', ZENDESK_API_TOKEN), timeout=10)
        results['zendesk'] = {'status_code': resp.status_code, 'ok': resp.status_code == 200}
    except Exception as e:
        logger.exception('Zendesk connectivity test failed')
        results['zendesk'] = {'ok': False, 'error': str(e)}

    # Discord test - send a safe minimal message
    try:
        payload = {'content': '🔧 Test message (no sensitive data)'}
        resp = safe_post_discord(payload)
        results['discord'] = {'status_code': getattr(resp, 'status_code', None), 'ok': is_discord_success(getattr(resp, 'status_code', 0))}
    except Exception as e:
        logger.exception('Discord connectivity test failed')
        results['discord'] = {'ok': False, 'error': str(e)}

    return jsonify(results)


@app.route('/create-ticket', methods=['POST'])
def create_ticket():
    """Create a Zendesk ticket from provided JSON. Expects subject, description, user(optional)."""
    if missing:
        return jsonify({'status': 'error', 'message': 'Service not fully configured', 'missing': missing}), 400

    try:
        data = request.get_json(silent=True) or {}
        subject = data.get('subject', 'Support Request')
        description = data.get('description', 'No description provided')
        user = data.get('user', 'discord-user')

        requester_email = f'discord-{user}@example.com'

        ticket_data = {
            'ticket': {
                'subject': f'Discord: {truncate(subject, 120)}',
                'comment': {'body': truncate(description, 4000), 'public': True},
                'requester': {'name': truncate(user, 120), 'email': requester_email},
                'tags': ['discord']
            }
        }

        url = f'https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets.json'
        resp = requests.post(url, json=ticket_data, auth=(f'{ZENDESK_EMAIL}/token', ZENDESK_API_TOKEN), timeout=30)

        if resp.status_code == 201:
            ticket_id = resp.json().get('ticket', {}).get('id')
            # Notify Discord
            try:
                embed = {
                    'embeds': [{
                        'title': '🎫 New Ticket Created',
                        'description': f'**Ticket #{ticket_id}**\n**User:** {truncate(user, 80)}\n**Subject:** {truncate(subject, 200)}',
                        'timestamp': datetime.utcnow().isoformat() + 'Z'
                    }]
                }
                discord_resp = safe_post_discord(embed)
                if not is_discord_success(discord_resp.status_code):
                    logger.warning('Discord webhook returned non-success for ticket notification: %s', discord_resp.status_code)
            except Exception:
                logger.exception('Failed to notify Discord about created ticket')

            return jsonify({'status': 'success', 'ticket_id': ticket_id}), 201

        logger.warning('Zendesk API returned non-201 when creating ticket: %s', resp.status_code)
        return jsonify({'status': 'error', 'message': 'Zendesk API error', 'status_code': resp.status_code}), 500

    except Exception as e:
        logger.exception('Unexpected error in create_ticket')
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/zendesk-webhook', methods=['POST', 'GET'])
def zendesk_webhook():
    """Endpoint to receive Zendesk webhook events and forward comments to Discord.

    If ZENDESK_WEBHOOK_SECRET is set, verify the X-Zendesk-Webhook-Signature header.
    """
    if request.method == 'GET':
        return jsonify({'status': 'ready', 'message': 'zendesk webhook endpoint active'})

    # Only accept JSON-like payloads. Keep raw body for signature verification.
    payload_body = request.get_data()  # bytes

    # Verify signature if secret provided
    signature_header = request.headers.get('X-Zendesk-Webhook-Signature') or request.headers.get('X-Zendesk-Signature')
    if ZENDESK_WEBHOOK_SECRET:
        ok = verify_zendesk_signature(payload_body, signature_header or '', ZENDESK_WEBHOOK_SECRET)
        if not ok:
            logger.warning('Zendesk webhook signature verification failed. Header present: %s', bool(signature_header))
            return jsonify({'status': 'error', 'message': 'signature verification failed'}), 401

    # Parse JSON safely
    data = None
    try:
        if request.is_json:
            data = request.get_json(silent=True)
        else:
            # best-effort: try to parse
            data = json.loads(payload_body.decode('utf-8')) if payload_body else {}
    except Exception:
        logger.exception('Failed to parse webhook payload as JSON')
        return jsonify({'status': 'error', 'message': 'invalid json payload'}), 400

    # Extract comment and author robustly while avoiding KeyErrors
    ticket_id = None
    comment_body = None
    author_name = 'Support Agent'

    try:
        if isinstance(data, dict) and 'ticket' in data:
            ticket = data.get('ticket') or {}
            ticket_id = ticket.get('id')
            comment = ticket.get('comment') or {}
            comment_body = comment.get('body') or comment.get('value')
            author_info = comment.get('author') or {}
            author_name = author_info.get('name') or author_info.get('author_name') or author_name
        elif isinstance(data, dict):
            ticket_id = data.get('ticket_id') or data.get('id')
            comment_body = data.get('body') or data.get('comment') or data.get('latest_comment') or data.get('value')
            author_name = data.get('author_name') or data.get('author') or author_name
    except Exception:
        logger.exception('Error while extracting fields from webhook payload')

    if not comment_body:
        logger.info('No comment body found in webhook payload (ticket: %s). Ignoring.', truncate(ticket_id, 40))
        return jsonify({'status': 'ignored', 'message': 'no comment body'}), 200

    # Prevent loops: ignore comments that appear to originate from Discord sender pattern
    if isinstance(author_name, str) and 'discord-' in author_name.lower():
        logger.info('Ignoring comment from Discord-origin author: %s', truncate(author_name, 80))
        return jsonify({'status': 'ignored', 'message': 'discord-origin comment'}), 200

    # Prepare Discord payload
    discord_payload = {
        'embeds': [{
            'title': f'💬 Update on Ticket #{ticket_id or "Unknown"}',
            'description': f'**From {truncate(author_name, 80)}:**\n\n{truncate(comment_body, 2000)}',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'footer': {'text': 'Zendesk'}
        }]
    }

    try:
        resp = safe_post_discord(discord_payload)
        if is_discord_success(resp.status_code):
            logger.info('Forwarded Zendesk comment to Discord (ticket=%s).', truncate(ticket_id, 40))
            return jsonify({'status': 'success', 'message': 'forwarded to discord'}), 200
        else:
            logger.warning('Discord webhook returned error status: %s; body=%s', resp.status_code, truncate(resp.text, 500))
            return jsonify({'status': 'error', 'message': 'discord webhook error', 'status_code': resp.status_code}), 502
    except Exception:
        logger.exception('Failed to send message to Discord')
        return jsonify({'status': 'error', 'message': 'failed to post to discord'}), 500


@app.route('/test-webhook', methods=['POST', 'GET'])
def test_webhook():
    if request.method == 'GET':
        return jsonify({'status': 'ready', 'message': 'test webhook endpoint active'})

    try:
        payload_body = request.get_data(as_text=True)
        logger.info('Test webhook received (truncated): %s', truncate(payload_body, 500))
        return jsonify({'status': 'success', 'message': 'received', 'truncated_body': truncate(payload_body, 200)}), 200
    except Exception as e:
        logger.exception('Error in test_webhook')
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    # When running locally for development, ensure debug is off by default unless explicitly enabled
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=debug_mode)
