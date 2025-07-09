import unittest
from unittest.mock import patch
from io import BytesIO
from app import app


class TestProductRegistration(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

        # Simulate admin login session
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'admin'
            session['_fresh'] = True

    @patch('sqlite3.connect')  # ✅ Patch SQLite directly since it's used in the route
    def test_product_registration(self, mock_sqlite):
        mock_conn = mock_sqlite.return_value
        mock_cursor = mock_conn.cursor.return_value

        # simulate insert returning last row id
        mock_cursor.lastrowid = 123

        test_data = {
            'category': 'Food',
            'brand': 'Test Brand',
            'product': 'Test Product',
            'price': '10.99',
            'quantity': '100',
            'image': (BytesIO(b"dummy image data"), 'test.jpg')
        }

        response = self.client.post('/register-container',
                                    data=test_data,
                                    content_type='multipart/form-data',
                                    follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Product registered successfully', response.data)
        mock_conn.commit.assert_called_once()

    def test_missing_fields(self):
        response = self.client.post('/register-container',
                                    data={},  # no data
                                    content_type='multipart/form-data',
                                    follow_redirects=True)

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Missing required fields', response.data)


if __name__ == '__main__':
    unittest.main()
