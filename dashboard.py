from flask import Flask, render_template, jsonify, request, redirect, url_for
import utils
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Simple auth (you should use proper auth in production)
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'admin123')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def api_stats():
    """Get overall statistics"""
    accounts = utils.get_all_accounts()
    monitors = utils.get_monitors()
    
    stats = {
        'total_accounts': len(accounts),
        'total_monitors': len(monitors),
        'monitors_online': len([m for m in monitors if m['status'] == 'online']),
        'monitors_offline': len([m for m in monitors if m['status'] == 'offline']),
        'top_users': utils.get_user_stats()
    }
    return jsonify(stats)

@app.route('/api/accounts')
def api_accounts():
    """Get all accounts (without content for security)"""
    accounts = utils.get_all_accounts()
    # Don't expose full content in API, only metadata
    safe_accounts = [{
        'id': acc['id'],
        'added_by': acc.get('added_by', 'Unknown'),
        'timestamp': acc.get('timestamp', ''),
        'preview': acc['content'][:30] + '...' if len(acc['content']) > 30 else acc['content']
    } for acc in accounts]
    return jsonify(safe_accounts)

@app.route('/api/monitors')
def api_monitors():
    """Get all monitors"""
    monitors = utils.get_monitors()
    return jsonify(monitors)

@app.route('/api/monitors/add', methods=['POST'])
def api_add_monitor():
    """Add new monitor"""
    data = request.json
    url = data.get('url')
    name = data.get('name')
    
    if not url:
        return jsonify({'error': 'URL required'}), 400
    
    success, result = utils.add_monitor(url, name)
    if success:
        return jsonify({'success': True, 'monitor': result})
    else:
        return jsonify({'error': result}), 400

@app.route('/api/monitors/remove/<monitor_id>', methods=['DELETE'])
def api_remove_monitor(monitor_id):
    """Remove monitor"""
    success = utils.remove_monitor(monitor_id)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Monitor not found'}), 404

@app.route('/api/accounts/<int:account_id>')
def api_get_account(account_id):
    """Get full account content by ID"""
    accounts = utils.get_all_accounts()
    account = next((acc for acc in accounts if acc['id'] == account_id), None)
    if account:
        return jsonify(account)
    else:
        return jsonify({'error': 'Account not found'}), 404

@app.route('/api/accounts/<int:account_id>', methods=['DELETE'])
def api_delete_account(account_id):
    """Delete account by ID"""
    success = utils.delete_account(account_id)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Account not found'}), 404

@app.route('/api/export')
def api_export():
    """Export all accounts as JSON"""
    accounts = utils.get_all_accounts()
    return jsonify(accounts)


if __name__ == '__main__':
    print("Dashboard starting at http://localhost:5000")
    print(f"Password: {DASHBOARD_PASSWORD}")
    app.run(host='0.0.0.0', port=5000, debug=True)
