import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime

print("🚀 Starting Zendesk-Discord Integration with py command...")

# Create Flask app
app = Flask(__name__)

# Configuration
CONFIG = {
    'ZENDESK_SUBDOMAIN': os.environ.get('ZENDESK_SUBDOMAIN'),
    'ZENDESK_EMAIL': os.environ.get('ZENDESK_EMAIL'),
    'ZENDESK_API_TOKEN': os.environ.get('ZENDESK_API_TOKEN'),
    'DISCORD_WEBHOOK_URL': os.environ.get('DISCORD_WEBHOOK_URL')
}

print("🔧 Configuration check:")
for key, value in CONFIG.items():
    if value:
        print(f"   {key}: ✅ SET")
    else:
        print(f"   {key}: ❌ NOT SET")

@app.route('/')
def home():
    return """
    <h1>🚀 Zendesk-Discord Integration</h1>
    <p><strong>Status:</strong> ✅ Running on Railway (py command)</p>
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
        "command": "py",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/test')
def test():
    """Test configuration and connections"""
    results = {
        "app": "✅ Running",
        "python_command": "py",
        "zendesk_configured": bool(CONFIG['ZENDESK_API_TOKEN']),
        "discord_configured": bool(CONFIG['DISCORD_WEBHOOK_URL'])
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
                json={"content": "🔧 Test from Railway deployment using py command"},
                timeout=10
            )
            results['discord_connection'] = response.status_code in [200, 204]
        except Exception as e:
            results['discord_connection'] = False
            results['discord_error'] = str(e)
    else:
        results['discord_connection'] = "Not configured"
    
    return jsonify(results)

@app.route('/create-ticket', methods=['GET', 'POST'])
def create_ticket():
    """Create ticket endpoint"""
    if request.method == 'GET':
        return """
        <h2>Create Test Ticket</h2>
        <p>Use POST method with JSON data. Example using curl:</p>
        <pre>
curl -X POST https://your-app.up.railway.app/create-ticket \\
  -H "Content-Type: application/json" \\
  -d '{
    "subject": "Test Ticket",
    "description": "Test description",
    "user": "TestUser"
  }'
        </pre>
        """
    
    # POST method
    try:
        data = request.get_json() or {}
        
        # Validate Zendesk config
        if not CONFIG['ZENDESK_API_TOKEN']:
            return jsonify({
                "status": "error",
                "message": "Zendesk not configured. Set ZENDESK_API_TOKEN environment variable."
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
            if CONFIG['DISCORD_WEBHOOK_URL']:
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
                "details": response.text[:200]
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
        
        if not CONFIG['DISCORD_WEBHOOK_URL']:
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
    print(f"🌐 Starting server on port {port} using py command...")
    app.run(host='0.0.0.0', port=port, debug=False)