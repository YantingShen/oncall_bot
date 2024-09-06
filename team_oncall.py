import os
import json
import requests
from typing import Dict, List
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from poc import OnCallBot

class TeamOnCall(OnCallBot):
    def __init__(self, team_name: str, confluence_base_url: str, confluence_page_id: str, confluence_api_key: str, pagerduty_api_key: str, slack_bot_token: str, codebase_path: str):
        super().__init__(confluence_base_url, confluence_page_id, confluence_api_key, pagerduty_api_key)
        self.team_name = team_name
        self.slack_client = WebClient(token=slack_bot_token)
        self.codebase_path = codebase_path

    def handle_alert(self, alert: Dict):
        assigned_team = alert.get('assigned_team')
        if assigned_team == self.team_name:
            super().handle_alert(alert)
        else:
            print(f"Alert not assigned to {self.team_name}. Ignoring alert.")

    def handle_slack_tag(self, event: Dict):
        channel = event['channel']
        user = event['user']
        text = event['text']

        if self.is_business_logic_question(text):
            evidence = self.check_codebase_for_evidence(text)
            if evidence:
                self.reply_in_slack(channel, user, evidence)
            else:
                self.reply_in_slack(channel, user, "No relevant information found in the codebase.")
        else:
            self.reply_in_slack(channel, user, "Could you please provide more details about your question?")

    def is_business_logic_question(self, text: str) -> bool:
        # Implement logic to determine if the question is related to business logic
        # For example, check for keywords or phrases that indicate a business logic question
        return "feature" in text or "support" in text

    def check_codebase_for_evidence(self, text: str) -> str:
        # Implement logic to check the codebase for evidence related to the question
        # For example, search for relevant files or comments in the codebase
        evidence = []
        for root, dirs, files in os.walk(self.codebase_path):
            for file in files:
                if file.endswith('.py') or file.endswith('.java') or file.endswith('.js'):
                    with open(os.path.join(root, file), 'r') as f:
                        content = f.read()
                        if text in content:
                            evidence.append(f"Found in {file}: {content}")
        return "\n".join(evidence) if evidence else None

    def reply_in_slack(self, channel: str, user: str, message: str):
        try:
            response = self.slack_client.chat_postMessage(
                channel=channel,
                text=f"<@{user}> {message}"
            )
        except SlackApiError as e:
            print(f"Error posting message to Slack: {e.response['error']}")

# Usage example
team_oncall = TeamOnCall(
    team_name='opt',
    confluence_base_url='https://your-confluence-instance.atlassian.net/wiki',
    confluence_page_id='your_confluence_page_id',
    confluence_api_key='your_confluence_api_key',
    pagerduty_api_key='your_pagerduty_api_key',
    slack_bot_token='your_slack_bot_token',
    codebase_path='/path/to/codebase'
)

# Simulated alert
alert = {
    'assigned_team': 'opt',
    'type': 'high_cpu_usage',
    'details': 'CPU usage exceeded 90% for 5 minutes'
}

# Handle the alert
team_oncall.handle_alert(alert)

# Simulated Slack event
slack_event = {
    'channel': 'C12345678',
    'user': 'U12345678',
    'text': 'Does service A support feature X?'
}

# Handle the Slack tag
team_oncall.handle_slack_tag(slack_event)