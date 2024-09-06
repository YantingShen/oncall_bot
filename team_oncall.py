import os
import json
import requests
from typing import Dict, List

class TeamOnCall:
    def __init__(self, team_name: str, runbook_directory: str, confluence_base_url: str, confluence_page_id: str, confluence_api_key: str, support_api_key: str):
        self.team_name = team_name
        self.runbook_directory = runbook_directory
        self.confluence_base_url = confluence_base_url
        self.confluence_page_id = confluence_page_id
        self.confluence_api_key = confluence_api_key
        self.support_api_key = support_api_key
        self.runbooks = self.fetch_runbooks_from_confluence()

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

    def handle_ticket(self, ticket: Dict):
        runbook = self.find_relevant_runbook(ticket)
        if runbook:
            related = self.check_ticket_relevance(runbook, ticket)
            if related:
                self.reply_to_ticket(ticket, "This issue is related to our team. We will handle it.")
            else:
                evidence = self.gather_evidence(runbook, ticket)
                self.reply_to_ticket(ticket, f"This issue is not related to our team. Evidence: {evidence}")
                self.tag_relevant_team(ticket, runbook)
        else:
            self.reply_to_ticket(ticket, "No relevant runbook found for this issue.")

    def find_relevant_runbook(self, ticket: Dict) -> Dict:
        issue_type = ticket.get('issue_type')
        for runbook in self.runbooks:
            if runbook.get('issue_type') == issue_type:
                return runbook
        return None

    def check_ticket_relevance(self, runbook: Dict, ticket: Dict) -> bool:
        # Implement logic to check if the ticket is related to the team according to the runbook
        # For example, check specific conditions or metrics mentioned in the runbook
        return False

    def gather_evidence(self, runbook: Dict, ticket: Dict) -> str:
        # Implement logic to gather evidence why the ticket is not related to the team
        # For example, check logs, metrics, or other data sources
        return "Evidence details here"

    def reply_to_ticket(self, ticket: Dict, message: str):
        url = f'https://api.supportsystem.com/tickets/{ticket["id"]}/reply'
        headers = {
            'Authorization': f'Bearer {self.support_api_key}',
            'Content-Type': 'application/json'
        }
        data = {
            'message': message
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            print(f"Replied to ticket {ticket['id']} successfully.")
        else:
            print(f"Failed to reply to ticket {ticket['id']}: {response.status_code}")

    def tag_relevant_team(self, ticket: Dict, runbook: Dict):
        relevant_team = runbook.get('relevant_team')
        if relevant_team:
            url = f'https://api.supportsystem.com/tickets/{ticket["id"]}/tag'
            headers = {
                'Authorization': f'Bearer {self.support_api_key}',
                'Content-Type': 'application/json'
            }
            data = {
                'team': relevant_team
            }
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                print(f"Tagged relevant team {relevant_team} in ticket {ticket['id']} successfully.")
            else:
                print(f"Failed to tag relevant team {relevant_team} in ticket {ticket['id']}: {response.status_code}")

# Usage example
team_oncall = TeamOnCall(
    team_name='frontend',
    runbook_directory='/path/to/runbooks',
    confluence_base_url='https://your-confluence-instance.atlassian.net/wiki',
    confluence_page_id='your_confluence_page_id',
    confluence_api_key='your_confluence_api_key',
    support_api_key='your_support_api_key'
)

# Simulated ticket
ticket = {
    'id': 'ticket_123',
    'issue_type': 'high_cpu_usage',
    'details': 'CPU usage exceeded 90% for 5 minutes'
}

# Handle the ticket
team_oncall.handle_ticket(ticket)