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

@app.route('/zendesk-webhook', methods=['POST', 'GET'])
def zendesk_webhook():
    """Zendesk webhook endpoint with full debugging"""
    print("=" * 60)
    print("🎯 MAIN ZENDESK WEBHOOK ENDPOINT HIT!")
    print("=" * 60)
    
    if request.method == 'GET':
        return jsonify({
            "status": "ready",
            "message": "Zendesk webhook endpoint is active",
            "endpoint": "/zendesk-webhook"
        })
    
    # Handle POST requests
    print("📨 MAIN: Webhook received via POST!")
    print("📨 MAIN: Headers:", dict(request.headers))
    print("📨 MAIN: Content-Type:", request.content_type)
    print("📨 MAIN: Method:", request.method)
    
    try:
        # Try to get JSON data
        if request.is_json:
            data = request.get_json()
            print("📨 MAIN: JSON data received:")
            print(json.dumps(data, indent=2))
        else:
            # Try to force JSON parsing
            try:
                data = request.get_json(force=True, silent=True)
                if data:
                    print("📨 MAIN: Forced JSON parsing worked:")
                    print(json.dumps(data, indent=2))
                else:
                    raw_data = request.get_data(as_text=True)
                    print("📨 MAIN: Raw data (not JSON):", raw_data)
                    data = {"raw_data": raw_data}
            except Exception as e:
                raw_data = request.get_data(as_text=True)
                print("📨 MAIN: Raw data (parse error):", raw_data)
                data = {"raw_data": raw_data, "error": str(e)}
        
        # Check Discord configuration
        if 'YOUR_ACTUAL' in CONFIG['DISCORD_WEBHOOK_URL']:
            print("❌ MAIN: Discord webhook not configured in app.py")
            return jsonify({
                "status": "error", 
                "message": "Discord webhook URL not configured. Update CONFIG in app.py"
            }), 500
        
        print("🔧 MAIN: Discord webhook is configured")
        
        # Try to extract ticket and comment data
        ticket_id = None
        comment_body = None
        author_name = "Support Agent"
        
        # Method 1: Standard Zendesk structure
        if isinstance(data, dict) and 'ticket' in data:
            ticket = data['ticket']
            ticket_id = ticket.get('id')
            comment = ticket.get('comment', {})
            comment_body = comment.get('body') or comment.get('value')
            author_info = comment.get('author', {})
            author_name = author_info.get('name') or author_info.get('author_name', 'Support Agent')
            print(f"🔧 MAIN: Using standard ticket structure")
        
        # Method 2: Direct fields
        elif isinstance(data, dict):
            ticket_id = data.get('ticket_id') or data.get('id')
            comment_body = data.get('body') or data.get('comment') or data.get('latest_comment') or data.get('value')
            author_name = data.get('author_name') or data.get('author') or 'Support Agent'
            print(f"🔧 MAIN: Using direct field structure")
        
        print(f"🔧 MAIN: Extracted ticket_id: {ticket_id}")
        print(f"🔧 MAIN: Extracted author: {author_name}")
        print(f"🔧 MAIN: Extracted comment: {comment_body[:100] if comment_body else 'None'}")
        
        # Validate we have the necessary data
        if not comment_body:
            print("❌ MAIN: No comment body found in webhook data")
            return jsonify({
                "status": "error", 
                "message": "No comment text found in webhook data"
            }), 400
        
        if not ticket_id:
            print("⚠️ MAIN: No ticket ID found, using placeholder")
            ticket_id = "Unknown"
        
        # Don't send if it's from a Discord user (to avoid loops)
        if "discord-" in str(author_name).lower():
            print("✅ MAIN: Ignoring comment from Discord user (prevent loop)")
            return jsonify({
                "status": "success", 
                "message": "Ignored Discord user comment"
            })
        
        print("✅ MAIN: All checks passed! Sending to Discord...")
        
        # Prepare Discord message
        discord_message = {
            "embeds": [{
                "title": f"💬 Update on Ticket #{ticket_id}",
                "description": f"**From {author_name}:**\n\n{comment_body}",
                "color": 3447003,  # Blue color
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "footer": {
                    "text": "Zendesk Support"
                }
            }]
        }
        
        print(f"🔧 MAIN: Sending to Discord webhook...")
        response = requests.post(
            CONFIG['DISCORD_WEBHOOK_URL'], 
            json=discord_message, 
            timeout=30
        )
        
        print(f"🔧 MAIN: Discord API response: {response.status_code}")
        
        if response.status_code == 204:
            print("✅ MAIN: Successfully sent to Discord!")
            return jsonify({
                "status": "success", 
                "message": "Comment sent to Discord successfully"
            })
        else:
            print(f"❌ MAIN: Discord API error: {response.status_code} - {response.text}")
            return jsonify({
                "status": "error", 
                "message": f"Discord API returned {response.status_code}"
            }), 500
            
    except Exception as e:
        print(f"❌ MAIN: Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/test-webhook', methods=['POST', 'GET'])
def test_webhook():
    """Test endpoint to verify webhook connectivity"""
    print("🎯 TEST WEBHOOK ENDPOINT HIT!")
    
    if request.method == 'GET':
        return jsonify({
            "status": "ready", 
            "message": "Test webhook endpoint is working",
            "endpoint": "/test-webhook"
        })
    
    # Handle POST requests
    print("📨 TEST: Webhook received via POST!")
    print("📨 TEST: Headers:", dict(request.headers))
    print("📨 TEST: Content-Type:", request.content_type)
    
    try:
        if request.is_json:
            data = request.get_json()
            print("📨 TEST: JSON data received:", json.dumps(data, indent=2))
        else:
            raw_data = request.get_data(as_text=True)
            print("📨 TEST: Raw data received:", raw_data)
            
        return jsonify({
            "status": "success", 
            "message": "Test webhook received successfully",
            "data_received": True
        })
    except Exception as e:
        print("📨 TEST: Error:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500