import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

print("🚀 Zendesk-Discord Integration Starting...")

# HARDCODED CONFIGURATION - REPLACE WITH YOUR ACTUAL VALUES
CONFIG = {
    'ZENDESK_SUBDOMAIN': 'btccexchange',  # ← REPLACE THIS (just the subdomain, not full URL)
    'ZENDESK_EMAIL': 'kevin.ezekiel@cloudsense.asia',      # ← REPLACE THIS
    'ZENDESK_API_TOKEN': 'KwMUBq32vDbPgYUCIWv6hLBrAvElR7CTWjMlyejs',  # ← REPLACE THIS
    'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/1438723422627692634/EDOAb93cPQGQDYru5HWfNtYLpCrvWr-X4fVfn7niIgkvYQdE_3rjqt3q474mTPoJlFD-'   # ← REPLACE THIS
}

print("🔧 Configuration check:")
for key, value in CONFIG.items():
    if 'YOUR_ACTUAL' not in value:
        print(f"   {key}: ✅ SET")
    else:
        print(f"   {key}: ❌ NEEDS TO BE UPDATED")

@app.route('/')
def home():
    return """
    <h1>🚀 Zendesk-Discord Integration</h1>
    <p><strong>Status:</strong> ✅ Running with hardcoded config</p>
    <p><strong>Note:</strong> Update credentials in app.py file</p>
    <h3>Available Endpoints:</h3>
    <ul>
        <li><a href="/health">/health</a> - Health check</li>
        <li><a href="/test">/test</a> - Test connections</li>
        <li>POST <a href="/create-ticket">/create-ticket</a> - Create ticket</li>
        <li>POST /zendesk-webhook - Zendesk webhook</li>
    </ul>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "zendesk-discord",
        "config": "hardcoded",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/test')
def test():
    """Test configuration and connections"""
    results = {
        "app": "✅ Running",
        "config_source": "hardcoded",
        "zendesk_configured": 'YOUR_ACTUAL' not in CONFIG['ZENDESK_API_TOKEN'],
        "discord_configured": 'YOUR_ACTUAL' not in CONFIG['DISCORD_WEBHOOK_URL'],
        "zendesk_subdomain": CONFIG['ZENDESK_SUBDOMAIN'],
        "zendesk_email": CONFIG['ZENDESK_EMAIL'][:3] + "***" if CONFIG['ZENDESK_EMAIL'] else "Not set"
    }
    
    # Test Zendesk if configured
    if results['zendesk_configured']:
        try:
            response = requests.get(
                f"https://{CONFIG['ZENDESK_SUBDOMAIN']}.zendesk.com/api/v2/tickets.json?per_page=1",
                auth=(f"{CONFIG['ZENDESK_EMAIL']}/token", CONFIG['ZENDESK_API_TOKEN']),
                timeout=10
            )
            results['zendesk_connection'] = response.status_code == 200
            results['zendesk_status'] = response.status_code
        except Exception as e:
            results['zendesk_connection'] = False
            results['zendesk_error'] = str(e)
    else:
        results['zendesk_connection'] = "Not configured"
    
    # Test Discord if configured
    if results['discord_configured']:
        try:
            response = requests.post(
                CONFIG['DISCORD_WEBHOOK_URL'],
                json={"content": "🔧 Test message from Railway deployment"},
                timeout=10
            )
            results['discord_connection'] = response.status_code in [200, 204]
            results['discord_status'] = response.status_code
        except Exception as e:
            results['discord_connection'] = False
            results['discord_error'] = str(e)
    else:
        results['discord_connection'] = "Not configured"
    
    return jsonify(results)

@app.route('/create-ticket', methods=['POST'])
def create_ticket():
    """Create a new Zendesk ticket"""
    try:
        data = request.get_json() or {}
        
        # Check if Zendesk is configured
        if 'YOUR_ACTUAL' in CONFIG['ZENDESK_API_TOKEN']:
            return jsonify({
                "status": "error",
                "message": "Zendesk not configured. Update ZENDESK_API_TOKEN in app.py file"
            }), 500
        
        subject = data.get('subject', 'Support Request')
        description = data.get('description', 'No description provided')
        user = data.get('user', 'Discord User')
        
        # Create Zendesk ticket
        ticket_data = {
            "ticket": {
                "subject": f"Discord: {subject}",
                "comment": {
                    "body": f"From: {user}\n\n{description}",
                    "public": True
                },
                "requester": {
                    "name": user,
                    "email": f"discord-{user}@company.com"
                },
                "tags": ["discord", "railway"]
            }
        }
        
        response = requests.post(
            f"https://{CONFIG['ZENDESK_SUBDOMAIN']}.zendesk.com/api/v2/tickets.json",
            json=ticket_data,
            auth=(f"{CONFIG['ZENDESK_EMAIL']}/token", CONFIG['ZENDESK_API_TOKEN']),
            timeout=30
        )
        
        if response.status_code == 201:
            ticket_id = response.json()['ticket']['id']
            
            # Notify Discord if configured
            if 'YOUR_ACTUAL' not in CONFIG['DISCORD_WEBHOOK_URL']:
                discord_data = {
                    "embeds": [{
                        "title": "🎫 New Ticket Created",
                        "description": f"**Ticket #{ticket_id}**\n**User:** {user}\n**Subject:** {subject}",
                        "color": 3066993,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }]
                }
                requests.post(CONFIG['DISCORD_WEBHOOK_URL'], json=discord_data)
            
            return jsonify({
                "status": "success",
                "ticket_id": ticket_id,
                "message": "Ticket created successfully"
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Zendesk API error: {response.status_code}",
                "details": response.text[:200] if response.text else 'No response body'
            }), 500
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/zendesk-webhook', methods=['POST'])
def zendesk_webhook():
    """Zendesk webhook endpoint"""
    try:
        data = request.get_json() or {}
        
        if 'YOUR_ACTUAL' in CONFIG['DISCORD_WEBHOOK_URL']:
            return jsonify({"status": "error", "message": "Discord not configured"}), 500
        
        ticket_id = data.get('ticket', {}).get('id')
        comment = data.get('ticket', {}).get('comment', {})
        
        if ticket_id and comment:
            body = comment.get('body', '')
            author = comment.get('author', {}).get('name', 'Support')
            
            if body and "discord-" not in author.lower():
                discord_data = {
                    "embeds": [{
                        "title": f"💬 Ticket #{ticket_id} Update",
                        "description": f"**From {author}:**\n{body}",
                        "color": 3447003,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }]
                }
                requests.post(CONFIG['DISCORD_WEBHOOK_URL'], json=discord_data)
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Starting server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)

@app.route('/test-webhook', methods=['POST', 'GET'])
def test_webhook():
    """Simple test to see if webhooks reach the app"""
    print("🎯 TEST WEBHOOK HIT!")
    
    if request.method == 'GET':
        return jsonify({"status": "ready", "message": "Test endpoint working"})
    
    # Handle POST
    print("📨 Test webhook received!")
    print("📨 Headers:", dict(request.headers))
    
    try:
        data = request.get_json()
        print("📨 Data received:", data)
        return jsonify({"status": "success", "message": "Test webhook received"})
    except:
        raw_data = request.get_data()
        print("📨 Raw data:", raw_data)
        return jsonify({"status": "success", "message": "Raw data received"})