import unittest
from unittest.mock import patch, MagicMock
from team_oncall import TeamOnCall

class TestTeamOnCall(unittest.TestCase):
    def setUp(self):
        self.opt_team_oncall = TeamOnCall(
            team_name='opt',
            runbook_directory='/path/to/runbooks',
            confluence_base_url='https://your-confluence-instance.atlassian.net/wiki',
            confluence_page_id='opt_confluence_page_id',
            confluence_api_key='opt_confluence_api_key',
            support_api_key='opt_support_api_key'
        )
        self.serving_team_oncall = TeamOnCall(
            team_name='serving',
            runbook_directory='/path/to/runbooks',
            confluence_base_url='https://your-confluence-instance.atlassian.net/wiki',
            confluence_page_id='serving_confluence_page_id',
            confluence_api_key='serving_confluence_api_key',
            support_api_key='serving_support_api_key'
        )

    @patch('team_oncall.requests.get')
    @patch('team_oncall.requests.post')
    def test_handle_ticket_not_related(self, mock_post, mock_get):
        # Mocking the Confluence API responses
        mock_response_pages = MagicMock()
        mock_response_pages.status_code = 200
        mock_response_pages.json.return_value = {
            'results': [
                {'id': 'page_1'}
            ]
        }
        mock_response_content = MagicMock()
        mock_response_content.status_code = 200
        mock_response_content.json.return_value = {
            'body': {
                'storage': {
                    'value': json.dumps({
                        'issue_type': 'service_a_not_working',
                        'steps': [
                            {'action': 'check_logs', 'log_link': 'https://logs.example.com/service_a'},
                            {'action': 'notify_team', 'message': 'Service A issue should be handled by the serving team.'}
                        ],
                        'relevant_team': 'serving-oncall'
                    })
                }
            }
        }
        mock_get.side_effect = [mock_response_pages, mock_response_content]

        # Mocking the support system API responses
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post.return_value = mock_post_response

        # Simulated ticket
        ticket = {
            'id': 'ticket_123',
            'issue_type': 'service_a_not_working',
            'details': 'Service A is not working due to some issue.'
        }

        # Handle the ticket
        self.opt_team_oncall.handle_ticket(ticket)

        # Check that the correct API calls were made
        mock_get.assert_any_call(
            'https://your-confluence-instance.atlassian.net/wiki/rest/api/content/opt_confluence_page_id/child/page',
            headers={
                'Authorization': 'Bearer opt_confluence_api_key',
                'Accept': 'application/json'
            }
        )
        mock_get.assert_any_call(
            'https://your-confluence-instance.atlassian.net/wiki/rest/api/content/page_1?expand=body.storage',
            headers={
                'Authorization': 'Bearer opt_confluence_api_key',
                'Accept': 'application/json'
            }
        )
        mock_post.assert_any_call(
            'https://api.supportsystem.com/tickets/ticket_123/reply',
            headers={
                'Authorization': 'Bearer opt_support_api_key',
                'Content-Type': 'application/json'
            },
            json={
                'message': 'This issue is not related to our team. Evidence: Service A issue should be handled by the serving team. Check logs here: https://logs.example.com/service_a'
            }
        )
        mock_post.assert_any_call(
            'https://api.supportsystem.com/tickets/ticket_123/tag',
            headers={
                'Authorization': 'Bearer opt_support_api_key',
                'Content-Type': 'application/json'
            },
            json={
                'team': 'serving-oncall'
            }
        )

if __name__ == '__main__':
    unittest.main()