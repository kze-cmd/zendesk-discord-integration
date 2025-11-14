import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

print("🚀 Starting Zendesk-Discord Integration...")

# Get configuration from environment with defaults
config = {
    'ZENDESK_SUBDOMAIN': os.environ.get('ZENDESK_SUBDOMAIN', 'yourcompany'),
    'ZENDESK_EMAIL': os.environ.get('ZENDESK_EMAIL', 'email@company.com'),
    'ZENDESK_API_TOKEN': os.environ.get('ZENDESK_API_TOKEN', 'your_token_here'),
    'DISCORD_WEBHOOK_URL': os.environ.get('DISCORD_WEBHOOK_URL', 'your_webhook_here')
}

print("🔧 Configuration loaded:")
for key, value in config.items():
    print(f"   {key}: {value if 'TOKEN' not in key else '***' if value != 'your_token_here' else 'NOT SET'}")

@app.route('/')
def home():
    return """
    <h1>🚀 Zendesk-Discord Integration</h1>
    <p><strong>Status:</strong> ✅ Running</p>
    <h3>Endpoints:</h3>
    <ul>
        <li><a href="/health">/health</a> - Health check</li>
        <li><a href="/test">/test</a> - Test connections</li>
        <li>POST /create-ticket - Create Zendesk ticket</li>
        <li>POST /zendesk-webhook - Zendesk webhook endpoint</li>
    </ul>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "zendesk-discord",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/test')
def test():
    """Test all connections"""
    results = {
        "flask_app": "✅ Running",
        "python_version": os.environ.get('PYTHON_VERSION', 'Unknown'),
        "zendesk_configured": "✅ Yes" if config['ZENDESK_API_TOKEN'] != 'your_token_here' else "❌ No",
        "discord_configured": "✅ Yes" if config['DISCORD_WEBHOOK_URL'] != 'your_webhook_here' else "❌ No"
    }
    
    # Test Zendesk connection if configured
    if config['ZENDESK_API_TOKEN'] != 'your_token_here':
        try:
            response = requests.get(
                f"https://{config['ZENDESK_SUBDOMAIN']}.zendesk.com/api/v2/tickets.json?per_page=1",
                auth=(f"{config['ZENDESK_EMAIL']}/token", config['ZENDESK_API_TOKEN']),
                timeout=10
            )
            results['zendesk_connection'] = f"✅ {response.status_code}" if response.status_code == 200 else f"❌ {response.status_code}"
        except Exception as e:
            results['zendesk_connection'] = f"❌ {str(e)}"
    else:
        results['zendesk_connection'] = "⚠️ Not configured"
    
    # Test Discord if configured
    if config['DISCORD_WEBHOOK_URL'] != 'your_webhook_here':
        try:
            response = requests.post(
                config['DISCORD_WEBHOOK_URL'],
                json={"content": "🔧 Test message - Zendesk-Discord integration is working!"},
                timeout=10
            )
            results['discord_connection'] = f"✅ {response.status_code}" if response.status_code in [200, 204] else f"❌ {response.status_code}"
        except Exception as e:
            results['discord_connection'] = f"❌ {str(e)}"
    else:
        results['discord_connection'] = "⚠️ Not configured"
    
    return jsonify(results)

@app.route('/create-ticket', methods=['POST'])
def create_ticket():
    """Create a new Zendesk ticket"""
    try:
        data = request.get_json() or {}
        
        # Check if Zendesk is configured
        if config['ZENDESK_API_TOKEN'] == 'your_token_here':
            return jsonify({
                "status": "error",
                "message": "Zendesk not configured. Set ZENDESK_API_TOKEN environment variable."
            }), 500
        
        subject = data.get('subject', 'Support Request from Discord')
        description = data.get('description', 'No description provided')
        user = data.get('user', 'Discord User')
        
        # Create ticket data
        ticket_data = {
            "ticket": {
                "subject": f"Discord: {subject}",
                "comment": {
                    "body": f"From Discord user: {user}\n\n{description}",
                    "public": True
                },
                "requester": {
                    "name": user,
                    "email": f"discord-{user}@company.com"
                },
                "tags": ["discord", "social_support"]
            }
        }
        
        # Send to Zendesk
        response = requests.post(
            f"https://{config['ZENDESK_SUBDOMAIN']}.zendesk.com/api/v2/tickets.json",
            json=ticket_data,
            auth=(f"{config['ZENDESK_EMAIL']}/token", config['ZENDESK_API_TOKEN']),
            timeout=30
        )
        
        if response.status_code == 201:
            ticket_id = response.json()['ticket']['id']
            
            # Send to Discord if configured
            if config['DISCORD_WEBHOOK_URL'] != 'your_webhook_here':
                discord_msg = {
                    "embeds": [{
                        "title": "🎫 Ticket Created",
                        "description": f"**Ticket #{ticket_id}** created successfully!\n**User:** {user}\n**Subject:** {subject}",
                        "color": 3066993,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }]
                }
                requests.post(config['DISCORD_WEBHOOK_URL'], json=discord_msg)
            
            return jsonify({
                "status": "success",
                "ticket_id": ticket_id,
                "message": "Ticket created successfully"
            })
        else:
            return jsonify({
                "status": "error", 
                "message": f"Zendesk API error: {response.status_code}",
                "details": response.text
            }), 500
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/zendesk-webhook', methods=['POST'])
def zendesk_webhook():
    """Receive webhooks from Zendesk"""
    try:
        data = request.get_json() or {}
        
        # Check if Discord is configured
        if config['DISCORD_WEBHOOK_URL'] == 'your_webhook_here':
            return jsonify({"status": "error", "message": "Discord not configured"}), 500
        
        ticket_id = data.get('ticket', {}).get('id')
        comment = data.get('ticket', {}).get('comment', {})
        
        if ticket_id and comment:
            comment_body = comment.get('body', '')
            author = comment.get('author', {}).get('name', 'Support Agent')
            
            if comment_body and "discord-" not in author.lower():
                discord_msg = {
                    "embeds": [{
                        "title": f"💬 Update on Ticket #{ticket_id}",
                        "description": f"**From {author}:**\n{comment_body}",
                        "color": 3447003,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }]
                }
                requests.post(config['DISCORD_WEBHOOK_URL'], json=discord_msg)
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Server starting on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)