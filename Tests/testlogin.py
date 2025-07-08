# testlogin.py
import unittest
import os
import sys
from werkzeug.security import generate_password_hash

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from your app structure
from app import app, db
from db.models import User


class TestLogin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure test app - runs once before all tests
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        # Create test client
        cls.client = app.test_client()

        # Create test database
        with app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        # Clean up after all tests
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def setUp(self):
        # Create test user for each test
        with app.app_context():
            # Clear any existing data
            db.session.query(User).delete()

            # Create test user
            self.test_user = User(
                Passcode="123456",
                Password=generate_password_hash("correctpass"),
                Role="cashier",
                Name="Test User",
                Email="test@example.com",
                IsActive=True
            )
            db.session.add(self.test_user)
            db.session.commit()

    def test_successful_login(self):
        """Test login with correct credentials"""
        response = self.client.post('/login',
                                    data={
                                        'email': 'test@example.com',
                                        'password': 'correctpass'
                                    },
                                    follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Cashier Dashboard', response.data)

    def test_invalid_password(self):
        """Test login with wrong password"""
        response = self.client.post('/login',
                                    data={
                                        'email': 'test@example.com',
                                        'password': 'wrongpass'
                                    },
                                    follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid email or password', response.data)


if __name__ == '__main__':
    unittest.main()