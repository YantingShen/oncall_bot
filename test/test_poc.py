import unittest
from unittest.mock import patch, MagicMock
from poc import OnCallBot, app

class TestOnCallBot(unittest.TestCase):
    def setUp(self):
        self.confluence_base_url = 'https://your-confluence-instance.atlassian.net/wiki'
        self.confluence_page_id = 'test_confluence_page_id'
        self.confluence_api_key = 'test_confluence_api_key'
        self.pagerduty_api_key = 'test_pagerduty_api_key'
        self.bot = OnCallBot(self.confluence_base_url, self.confluence_page_id, self.confluence_api_key, self.pagerduty_api_key)
        self.app = app.test_client()

    @patch('oncall_bot.requests.get')
    def test_fetch_team_contacts(self, mock_get):
        mock_response_teams = MagicMock()
        mock_response_teams.status_code = 200
        mock_response_teams.json.return_value = {
            'teams': [
                {'id': 'team_1', 'summary': 'frontend'},
                {'id': 'team_2', 'summary': 'backend'}
            ]
        }
        mock_response_users = MagicMock()
        mock_response_users.status_code = 200
        mock_response_users.json.return_value = {
            'users': [{'email': 'frontend-oncall@example.com'}]
        }
        mock_get.side_effect = [mock_response_teams, mock_response_users, mock_response_users]

        team_contacts = self.bot.fetch_team_contacts()
        self.assertEqual(team_contacts['frontend'], 'frontend-oncall@example.com')
        self.assertEqual(team_contacts['backend'], 'frontend-oncall@example.com')

    @patch('oncall_bot.requests.get')
    def test_fetch_team_contact(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'users': [{'email': 'frontend-oncall@example.com'}]
        }
        mock_get.return_value = mock_response

        contact = self.bot.fetch_team_contact('team_1')
        self.assertEqual(contact, 'frontend-oncall@example.com')

    @patch('oncall_bot.requests.get')
    def test_fetch_runbooks_from_confluence(self, mock_get):
        mock_response_pages = MagicMock()
        mock_response_pages.status_code = 200
        mock_response_pages.json.return_value = {
            'results': [
                {'id': 'page_1'},
                {'id': 'page_2'}
            ]
        }
        mock_response_content = MagicMock()
        mock_response_content.status_code = 200
        mock_response_content.json.return_value = {
            'body': {
                'storage': {
                    'value': json.dumps({
                        'alert_type': 'high_cpu_usage',
                        'steps': [{'action': 'notify_team', 'message': 'High CPU usage detected'}]
                    })
                }
            }
        }
        mock_get.side_effect = [mock_response_pages, mock_response_content, mock_response_content]

        runbooks = self.bot.fetch_runbooks_from_confluence()
        self.assertEqual(len(runbooks), 2)
        self.assertEqual(runbooks[0]['alert_type'], 'high_cpu_usage')

    @patch('oncall_bot.requests.get')
    def test_fetch_runbook_content(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'body': {
                'storage': {
                    'value': json.dumps({
                        'alert_type': 'high_cpu_usage',
                        'steps': [{'action': 'notify_team', 'message': 'High CPU usage detected'}]
                    })
                }
            }
        }
        mock_get.return_value = mock_response

        runbook = self.bot.fetch_runbook_content('page_1')
        self.assertEqual(runbook['alert_type'], 'high_cpu_usage')

    @patch('oncall_bot.requests.get')
    def test_fetch_runbook_from_link(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'body': {
                'storage': {
                    'value': json.dumps({
                        'alert_type': 'high_cpu_usage',
                        'steps': [{'action': 'notify_team', 'message': 'High CPU usage detected'}]
                    })
                }
            }
        }
        mock_get.return_value = mock_response

        runbook = self.bot.fetch_runbook_from_link('https://your-confluence-instance.atlassian.net/wiki/rest/api/content/page_1?expand=body.storage')
        self.assertEqual(runbook['alert_type'], 'high_cpu_usage')

    @patch('oncall_bot.requests.get')
    def test_fetch_pagerduty_alerts(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'incidents': [
                {
                    'type': 'high_cpu_usage',
                    'teams': [{'summary': 'infrastructure'}],
                    'summary': 'CPU usage exceeded 90% for 5 minutes'
                }
            ]
        }
        mock_get.return_value = mock_response

        alerts = self.bot.fetch_pagerduty_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['type'], 'high_cpu_usage')
        self.assertEqual(alerts[0]['team'], 'infrastructure')
        self.assertEqual(alerts[0]['details'], 'CPU usage exceeded 90% for 5 minutes')

    @patch('oncall_bot.OnCallBot.find_relevant_runbook')
    @patch('oncall_bot.OnCallBot.execute_runbook')
    @patch('oncall_bot.OnCallBot.notify_team')
    def test_handle_alert_with_runbook_link(self, mock_notify_team, mock_execute_runbook, mock_find_relevant_runbook):
        alert = {
            'type': 'high_cpu_usage',
            'team': 'infrastructure',
            'details': 'CPU usage exceeded 90% for 5 minutes',
            'runbook_link': 'https://your-confluence-instance.atlassian.net/wiki/rest/api/content/page_1?expand=body.storage'
        }
        runbook = {
            'alert_type': 'high_cpu_usage',
            'steps': [
                {'action': 'notify_team', 'message': 'High CPU usage detected'}
            ]
        }
        with patch.object(self.bot, 'fetch_runbook_from_link', return_value=runbook):
            self.bot.handle_alert(alert)

        self.bot.fetch_runbook_from_link.assert_called_once_with(alert['runbook_link'])
        mock_execute_runbook.assert_called_once_with(runbook, alert)
        mock_notify_team.assert_not_called()

    @patch('oncall_bot.OnCallBot.find_relevant_runbook')
    @patch('oncall_bot.OnCallBot.execute_runbook')
    @patch('oncall_bot.OnCallBot.notify_team')
    def test_handle_alert_without_runbook_link(self, mock_notify_team, mock_execute_runbook, mock_find_relevant_runbook):
        alert = {
            'type': 'high_cpu_usage',
            'team': 'infrastructure',
            'details': 'CPU usage exceeded 90% for 5 minutes'
        }
        runbook = {
            'alert_type': 'high_cpu_usage',
            'steps': [
                {'action': 'notify_team', 'message': 'High CPU usage detected'}
            ]
        }
        mock_find_relevant_runbook.return_value = runbook

        self.bot.handle_alert(alert)

        mock_find_relevant_runbook.assert_called_once_with(alert)
        mock_execute_runbook.assert_called_once_with(runbook, alert)
        mock_notify_team.assert_not_called()

    @patch('oncall_bot.OnCallBot.find_relevant_runbook')
    @patch('oncall_bot.OnCallBot.notify_team')
    def test_handle_alert_without_runbook(self, mock_notify_team, mock_find_relevant_runbook):
        alert = {
            'type': 'unknown_alert',
            'team': 'infrastructure',
            'details': 'An unknown alert occurred'
        }
        mock_find_relevant_runbook.return_value = None

        self.bot.handle_alert(alert)

        mock_find_relevant_runbook.assert_called_once_with(alert)
        mock_notify_team.assert_called_once_with("No relevant runbook found", alert)

    @patch('oncall_bot.requests.get')
    @patch('oncall_bot.OnCallBot.check_sla_breach')
    @patch('oncall_bot.OnCallBot.escalate_ticket')
    def test_update_esc_tickets(self, mock_escalate_ticket, mock_check_sla_breach, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'incidents': [
                {
                    'id': 'incident_1',
                    'type': 'high_cpu_usage',
                    'teams': [{'summary': 'infrastructure'}],
                    'summary': 'CPU usage exceeded 90% for 5 minutes'
                }
            ]
        }
        mock_get.return_value = mock_response
        mock_check_sla_breach.return_value = True

        self.bot.update_esc_tickets()

        mock_get.assert_called_once()
        mock_check_sla_breach.assert_called_once()
        mock_escalate_ticket.assert_called_once_with(mock_response.json.return_value['incidents'][0])

    @patch('oncall_bot.OnCallBot.handle_alert')
    def test_webhook(self, mock_handle_alert):
        alert = {
            'type': 'high_cpu_usage',
            'team': 'infrastructure',
            'details': 'CPU usage exceeded 90% for 5 minutes'
        }
        response = self.app.post('/webhook', json=alert)
        self.assertEqual(response.status_code, 200)
        mock_handle_alert.assert_called_once_with(alert)

if __name__ == '__main__':
    unittest.main()