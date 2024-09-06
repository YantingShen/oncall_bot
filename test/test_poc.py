import os
import json
import requests
from typing import Dict, List
from flask import Flask, request, jsonify
from transformers import pipeline

class OnCallBot:
    def __init__(self, confluence_base_url: str, confluence_page_id: str, confluence_api_key: str, pagerduty_api_key: str):
        self.confluence_base_url = confluence_base_url
        self.confluence_page_id = confluence_page_id
        self.confluence_api_key = confluence_api_key
        self.pagerduty_api_key = pagerduty_api_key
        self.team_contacts = self.fetch_team_contacts()
        self.runbooks = self.fetch_runbooks_from_confluence()
        self.nlp = pipeline("text2text-generation", model="t5-base")

    def fetch_team_contacts(self) -> Dict[str, str]:
        url = 'https://api.pagerduty.com/teams'
        headers = {
            'Authorization': f'Token token={self.pagerduty_api_key}',
            'Accept': 'application/vnd.pagerduty+json;version=2'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            teams = response.json().get('teams', [])
            team_contacts = {}
            for team in teams:
                team_id = team['id']
                team_name = team['summary']
                contact = self.fetch_team_contact(team_id)
                if contact:
                    team_contacts[team_name] = contact
            return team_contacts
        else:
            print(f"Failed to fetch PagerDuty teams: {response.status_code}")
            return {}

    def fetch_team_contact(self, team_id: str) -> str:
        url = f'https://api.pagerduty.com/teams/{team_id}/users'
        headers = {
            'Authorization': f'Token token={self.pagerduty_api_key}',
            'Accept': 'application/vnd.pagerduty+json;version=2'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            users = response.json().get('users', [])
            if users:
                return users[0].get('email', 'unknown@example.com')
        else:
            print(f"Failed to fetch users for team {team_id}: {response.status_code}")
        return 'unknown@example.com'

    def fetch_runbooks_from_confluence(self) -> List[Dict]:
        url = f'{self.confluence_base_url}/rest/api/content/{self.confluence_page_id}/child/page'
        headers = {
            'Authorization': f'Bearer {self.confluence_api_key}',
            'Accept': 'application/json'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            pages = response.json().get('results', [])
            runbooks = []
            for page in pages:
                runbook = self.fetch_runbook_content(page['id'])
                if runbook:
                    runbooks.append(runbook)
            return runbooks
        else:
            print(f"Failed to fetch Confluence pages: {response.status_code}")
            return []

    def fetch_runbook_content(self, page_id: str) -> Dict:
        url = f'{self.confluence_base_url}/rest/api/content/{page_id}?expand=body.storage'
        headers = {
            'Authorization': f'Bearer {self.confluence_api_key}',
            'Accept': 'application/json'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = response.json().get('body', {}).get('storage', {}).get('value', '')
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                print(f"Failed to decode JSON content for page {page_id}")
                return {}
        else:
            print(f"Failed to fetch Confluence page content: {response.status_code}")
            return {}

    def fetch_runbook_from_link(self, runbook_link: str) -> Dict:
        headers = {
            'Authorization': f'Bearer {self.confluence_api_key}',
            'Accept': 'application/json'
        }
        response = requests.get(runbook_link, headers=headers)
        if response.status_code == 200:
            content = response.json().get('body', {}).get('storage', {}).get('value', '')
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                print(f"Failed to decode JSON content from link {runbook_link}")
                return {}
        else:
            print(f"Failed to fetch runbook content from link: {response.status_code}")
            return {}

    def handle_alert(self, alert: Dict):
        runbook_link = alert.get('runbook_link')
        if runbook_link:
            runbook = self.fetch_runbook_from_link(runbook_link)
        else:
            runbook = self.find_relevant_runbook(alert)
        
        if runbook:
            self.execute_runbook(runbook, alert)
        else:
            self.notify_team("No relevant runbook found", alert)

    def find_relevant_runbook(self, alert: Dict) -> Dict:
        alert_type = alert.get('type')
        for runbook in self.runbooks:
            if runbook.get('alert_type') == alert_type:
                return runbook
        return None

    def execute_runbook(self, runbook: Dict, alert: Dict):
        steps = runbook.get('steps', [])
        for step in steps:
            action = self.nlp(step['action'])[0]['generated_text']
            if 'resolve the alert' in action:
                self.resolve_alert(alert)
            elif 'check' in action and 'metric' in action:
                metric = self.extract_metric(action)
                threshold = self.extract_threshold(action)
                self.check_metric(metric, threshold)
            elif 'restart' in action and 'service' in action:
                service_name = self.extract_service_name(action)
                self.restart_service(service_name)
            elif 'notify' in action and 'team' in action:
                message = self.extract_message(action)
                self.notify_team(message, alert)
            else:
                print(f"Unknown action: {action}")

    def resolve_alert(self, alert: Dict):
        incident_id = alert.get('id')
        url = f'https://api.pagerduty.com/incidents/{incident_id}'
        headers = {
            'Authorization': f'Token token={self.pagerduty_api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/vnd.pagerduty+json;version=2'
        }
        payload = {
            'incident': {
                'type': 'incident_reference',
                'status': 'resolved'
            }
        }
        response = requests.put(url, headers=headers, json=payload)
        if response.status_code == 200:
            print(f"Alert {incident_id} resolved successfully.")
        else:
            print(f"Failed to resolve alert {incident_id}: {response.status_code} - {response.text}")

    def extract_metric(self, action: str) -> str:
        # Extract metric from the action string
        # Example: "check CPU usage metric" -> "CPU usage"
        return action.split('metric')[0].strip()

    def extract_threshold(self, action: str) -> float:
        # Extract threshold from the action string
        # Example: "check CPU usage metric if above 90%" -> 90.0
        words = action.split()
        for word in words:
            if word.replace('.', '', 1).isdigit():
                return float(word)
        return 0.0

    def extract_service_name(self, action: str) -> str:
        # Extract service name from the action string
        # Example: "restart the database service" -> "database"
        return action.split('service')[0].strip()

    def extract_message(self, action: str) -> str:
        # Extract message from the action string
        # Example: "notify the team with message 'Service down'" -> "Service down"
        if 'message' in action:
            return action.split('message')[1].strip().strip("'\"")
        return "No message provided"

    def check_metric(self, metric: str, threshold: float):
        # Implement metric checking logic here
        print(f"Checking metric {metric} with threshold {threshold}")

    def restart_service(self, service_name: str):
        # Implement service restart logic here
        print(f"Restarting service {service_name}")

    def notify_team(self, message: str, alert: Dict):
        team = alert.get('team')
        if team in self.team_contacts:
            contact = self.team_contacts[team]
            # Implement notification logic here (e.g., send email, Slack message, etc.)
            print(f"Notifying {team} at {contact}: {message}")
        else:
            print(f"No contact found for team: {team}")

    def update_esc_tickets(self):
        url = 'https://api.pagerduty.com/incidents'
        headers = {
            'Authorization': f'Token token={self.pagerduty_api_key}',
            'Accept': 'application/vnd.pagerduty+json;version=2'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            incidents = response.json().get('incidents', [])
            for incident in incidents:
                # Check if the incident is within SLA
                sla_breached = self.check_sla_breach(incident)
                if sla_breached:
                    self.escalate_ticket(incident)
        else:
            print(f"Failed to fetch PagerDuty incidents: {response.status_code}")

    def check_sla_breach(self, incident: Dict) -> bool:
        # Implement SLA breach checking logic here
        # For example, check if the incident duration exceeds a certain threshold
        return False

    def escalate_ticket(self, incident: Dict):
        # Implement ticket escalation logic here
        print(f"Escalating ticket for incident: {incident['id']}")

# Flask app to handle webhooks
app = Flask(__name__)
bot = OnCallBot(
    confluence_base_url='https://your-confluence-instance.atlassian.net/wiki',
    confluence_page_id='your_confluence_page_id',
    confluence_api_key='your_confluence_api_key',
    pagerduty_api_key='your_pagerduty_api_key'
)

@app.route('/webhook', methods=['POST'])
def webhook():
    alert = request.json
    bot.handle_alert(alert)
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(port=5000)