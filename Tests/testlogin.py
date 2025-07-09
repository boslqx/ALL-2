import unittest
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash
from app import app


class TestLogin(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

        self.test_user = MagicMock()
        self.test_user.Email = "test@example.com"
        self.test_user.Password = generate_password_hash("correctpass")
        self.test_user.IsActive = True
        self.test_user.Role = "cashier"
        self.test_user.UserID = 1  # ✅ Required to avoid JSON error

    @patch('routes.login.User')
    def test_successful_login(self, mock_user):
        mock_user.query.filter_by.return_value.first.return_value = self.test_user

        response = self.client.post('/login', data={
            'email': 'test@example.com',
            'password': 'correctpass'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Cashier Dashboard', response.data)

    @patch('routes.login.User')
    def test_invalid_password(self, mock_user):
        mock_user.query.filter_by.return_value.first.return_value = self.test_user

        response = self.client.post('/login', data={
            'email': 'test@example.com',
            'password': 'wrongpass'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid email or password', response.data)


if __name__ == '__main__':
    unittest.main()
