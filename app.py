print("🎯 Starting Zendesk-Discord Integration...")

from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
print("✅ Environment variables loaded")

app = Flask(__name__)

# Configuration from environment variables
ZENDESK_SUBDOMAIN = os.environ.get('ZENDESK_SUBDOMAIN')
ZENDESK_EMAIL = os.environ.get('ZENDESK_EMAIL')
ZENDESK_API_TOKEN = os.environ.get('ZENDESK_API_TOKEN')
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')

print(f"🔧 Config: Zendesk Subdomain = {ZENDESK_SUBDOMAIN}")
if DISCORD_WEBHOOK_URL:
    print(f"🔧 Config: Discord Webhook URL = {DISCORD_WEBHOOK_URL[:50]}...")
else:
    print("❌ Discord Webhook URL not set")

# Store ticket mappings
ticket_mappings = {}

class ZendeskAPI:
    def __init__(self):
        self.base_url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"
        self.auth = (f"{ZENDESK_EMAIL}/token", ZENDESK_API_TOKEN)
        print(f"🔧 Zendesk API configured: {self.base_url}")
    
    def create_ticket(self, subject, description, requester_name, discord_username):
        """Create a ticket in Zendesk from Discord"""
        print(f"📝 Creating ticket for {requester_name}")
        
        # Validate credentials
        if not all([ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN]):
            print("❌ Zendesk credentials missing")
            return None
        
        data = {
            "ticket": {
                "subject": f"Discord: {subject}",
                "comment": {
                    "body": f"From Discord user: {discord_username}\n\n{description}",
                    "public": True
                },
                "requester": {
                    "name": requester_name,
                    "email": f"discord-{discord_username}@yourcompany.com"
                },
                "tags": ["discord", "social_support"]
            }
        }
        
        try:
            print(f"🔧 Sending request to Zendesk API...")
            response = requests.post(
                f"{self.base_url}/tickets.json",
                json=data,
                auth=self.auth,
                timeout=30
            )
            
            print(f"🔧 Zendesk response: {response.status_code}")
            
            if response.status_code == 201:
                ticket_id = response.json()['ticket']['id']
                ticket_mappings[ticket_id] = discord_username
                print(f"✅ Ticket #{ticket_id} created for {discord_username}")
                return ticket_id
            else:
                print(f"❌ Zendesk API Error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating Zendesk ticket: {e}")
            return None
    
    def add_comment(self, ticket_id, comment, public=True):
        """Add a comment to an existing Zendesk ticket"""
        data = {
            "ticket": {
                "comment": {
                    "body": comment,
                    "public": public
                }
            }
        }
        
        try:
            response = requests.put(
                f"{self.base_url}/tickets/{ticket_id}.json",
                json=data,
                auth=self.auth,
                timeout=30
            )
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error adding comment to ticket #{ticket_id}: {e}")
            return False

def send_discord_message(message, ticket_id=None):
    """Send message to Discord via webhook"""
    if not DISCORD_WEBHOOK_URL:
        print("❌ Discord webhook URL not configured")
        return False
        
    print(f"📨 Sending message to Discord: {message[:50]}...")
    
    if ticket_id:
        embed = {
            "title": f"🎫 Ticket #{ticket_id}",
            "description": message,
            "color": 3447003,  # Blue
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    else:
        embed = {
            "title": "💬 Support Update",
            "description": message,
            "color": 3066993,  # Green
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    data = {
        "embeds": [embed],
        "username": "Zendesk Support Bot"
    }
    
    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=data,
            timeout=30
        )
        if response.status_code == 204:
            print("✅ Discord message sent successfully")
            return True
        else:
            print(f"❌ Discord API Error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending Discord message: {e}")
        return False

# Initialize Zendesk API
zendesk = ZendeskAPI()

@app.route('/')
def home():
    return """
    🚀 Zendesk-Discord Integration is Running!
    
    <h3>Available Endpoints:</h3>
    <ul>
    <li>GET <a href="/health">/health</a> - Health check</li>
    <li>GET <a href="/test-discord">/test-discord</a> - Test Discord webhook</li>
    <li>GET <a href="/test-zendesk">/test-zendesk</a> - Test Zendesk connection</li>
    <li>POST /create-ticket - Create a new ticket (use Postman)</li>
    <li>POST /zendesk-webhook - Zendesk webhook endpoint</li>
    </ul>
    
    <p>Use POST requests with JSON body for creating tickets.</p>
    """

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy", 
        "service": "Zendesk-Discord",
        "timestamp": datetime.now().isoformat(),
        "environment": "production"
    })

@app.route('/create-ticket', methods=['POST'])
def create_ticket():
    """Create a new Zendesk ticket"""
    print("📨 Received create-ticket request")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data provided'}), 400
            
        print(f"📦 Request data: {json.dumps(data, indent=2)}")
        
        subject = data.get('subject', 'Support Request from Discord')
        description = data.get('description', '')
        requester_name = data.get('requester_name', 'Discord User')
        discord_username = data.get('discord_username', 'unknown')
        
        if not description:
            return jsonify({'status': 'error', 'message': 'Description is required'}), 400
        
        # Create Zendesk ticket
        ticket_id = zendesk.create_ticket(subject, description, requester_name, discord_username)
        
        if ticket_id:
            # Send confirmation to Discord
            success_message = f"""**Ticket Created Successfully!**

**Ticket ID:** #{ticket_id}
**Subject:** {subject}
**Requester:** {requester_name}

Our team will respond shortly. You'll receive updates here when we reply to your ticket."""
            
            send_discord_message(success_message, ticket_id)
            
            return jsonify({
                'status': 'success', 
                'ticket_id': ticket_id,
                'message': 'Ticket created successfully'
            })
        else:
            error_message = "❌ Failed to create support ticket. Please check your Zendesk credentials and try again."
            send_discord_message(error_message)
            return jsonify({'status': 'error', 'message': 'Failed to create ticket. Check Zendesk credentials.'}), 500
    
    except Exception as e:
        print(f"❌ Error in create-ticket: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/zendesk-webhook', methods=['POST'])
def zendesk_webhook():
    """Receive webhooks from Zendesk and send updates to Discord"""
    print("📨 Received Zendesk webhook")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data provided'}), 400
            
        print(f"📦 Webhook data: {json.dumps(data, indent=2)}")
        
        if 'ticket' in data:
            ticket_id = data['ticket']['id']
            current_comment = data.get('ticket', {}).get('comment', {})
            
            if current_comment:
                comment_body = current_comment.get('body', '')
                comment_author = current_comment.get('author', {}).get('name', 'Support Agent')
                is_public = current_comment.get('public', True)
                
                # Only send public comments
                if is_public and comment_body:
                    # Don't send if it's from a Discord user
                    if "discord-" not in comment_author.lower():
                        formatted_message = f"""**Update from {comment_author}:**

{comment_body}

_Reply in Zendesk to continue the conversation._"""
                        
                        send_discord_message(formatted_message, ticket_id)
        
        return jsonify({'status': 'success'})
    
    except Exception as e:
        print(f"❌ Error in Zendesk webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/test-discord', methods=['GET'])
def test_discord():
    """Test Discord webhook connection"""
    print("🧪 Testing Discord webhook...")
    success = send_discord_message("🔧 **Test Message**\n\nThis is a test message from your Zendesk-Discord integration. If you can see this, Discord webhook is working!")
    return jsonify({'status': 'success' if success else 'error'})

@app.route('/test-zendesk', methods=['GET'])
def test_zendesk():
    """Test Zendesk connection"""
    print("🧪 Testing Zendesk connection...")
    try:
        # Test by listing recent tickets (lightweight request)
        response = requests.get(
            f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets.json?per_page=1",
            auth=(f"{ZENDESK_EMAIL}/token", ZENDESK_API_TOKEN),
            timeout=30
        )
        if response.status_code == 200:
            return jsonify({
                'status': 'success', 
                'message': 'Zendesk connection successful',
                'account': ZENDESK_SUBDOMAIN
            })
        else:
            return jsonify({
                'status': 'error', 
                'message': f'Zendesk API error: {response.status_code}',
                'details': response.text[:200] if response.text else 'No response body'
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/debug', methods=['GET'])
def debug():
    """Debug endpoint to check configuration"""
    config_status = {
        'zendesk_subdomain': ZENDESK_SUBDOMAIN if ZENDESK_SUBDOMAIN else 'MISSING',
        'zendesk_email': ZENDESK_EMAIL if ZENDESK_EMAIL else 'MISSING',
        'zendesk_token': 'SET' if ZENDESK_API_TOKEN else 'MISSING',
        'discord_webhook': 'SET' if DISCORD_WEBHOOK_URL else 'MISSING',
        'ticket_mappings_count': len(ticket_mappings)
    }
    return jsonify(config_status)

if __name__ == '__main__':
    # Use PORT provided by Railway or default to 5000 for local development
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting server on port {port}...")
    print(f"🌐 Access at: http://localhost:{port}")
    print("📋 Available endpoints:")
    print("  GET  /               - Home page with links")
    print("  GET  /health         - Health check")
    print("  GET  /test-discord   - Test Discord webhook")
    print("  GET  /test-zendesk   - Test Zendesk connection")
    print("  GET  /debug          - Debug configuration")
    print("  POST /create-ticket  - Create a new ticket")
    print("  POST /zendesk-webhook - Zendesk webhook endpoint")
    print("")
    print("🔧 Configuration Status:")
    print(f"  Zendesk: {'✅ Configured' if ZENDESK_SUBDOMAIN and ZENDESK_EMAIL and ZENDESK_API_TOKEN else '❌ Missing credentials'}")
    print(f"  Discord:  {'✅ Configured' if DISCORD_WEBHOOK_URL else '❌ Missing webhook URL'}")
    
    # Run the app - debug=False for production
    app.run(host='0.0.0.0', port=port, debug=False)