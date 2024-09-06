import requests

def trigger_pagerduty_alert(api_key, service_id, title, details):
    url = 'https://api.pagerduty.com/incidents'
    headers = {
        'Authorization': f'Token token={api_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/vnd.pagerduty+json;version=2'
    }
    payload = {
        'incident': {
            'type': 'incident',
            'title': title,
            'service': {
                'id': service_id,
                'type': 'service_reference'
            },
            'body': {
                'type': 'incident_body',
                'details': details
            }
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        print('Alert triggered successfully.')
    else:
        print(f'Failed to trigger alert: {response.status_code} - {response.text}')

# Example usage
api_key = 'your_pagerduty_api_key'
service_id = 'your_pagerduty_service_id'
title = 'Test Alert'
details = 'This is a test alert for end-to-end testing of OnCallBot.'
trigger_pagerduty_alert(api_key, service_id, title, details)