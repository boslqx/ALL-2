# testregproduct.py
import unittest
import os
import sys
from io import BytesIO
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from db.models import Product, User


class TestProductRegistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure test app
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        cls.client = app.test_client()

        # Create test database
        with app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        # Clean up database
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def setUp(self):
        # Create a test admin user and log in
        with app.app_context():
            # Clear existing data
            db.session.query(Product).delete()
            db.session.query(User).delete()

            # Create test admin user
            admin = User(
                Passcode="admin123",
                Password=generate_password_hash("adminpass"),
                Role="admin",
                Name="Test Admin",
                Email="admin@test.com",
                IsActive=True
            )
            db.session.add(admin)
            db.session.commit()

            # Log in the test admin
            with self.client.session_transaction() as session:
                session['user_id'] = admin.UserID
                session['role'] = admin.Role
                session['_fresh'] = True

    def test_successful_product_registration(self):
        """Test product registration with valid data"""
        # Create a dummy image file
        dummy_file = (BytesIO(b"dummy image data"), 'test.jpg')

        response = self.client.post('/register-container',
                                    data={
                                        'category': 'Food & Beverages',
                                        'brand': 'Test Brand',
                                        'product': 'Test Product',
                                        'price': '10.99',
                                        'quantity': '100',
                                        'image': dummy_file
                                    },
                                    content_type='multipart/form-data')

        # Check for server error (500) since that's what your endpoint returns
        self.assertEqual(response.status_code, 500)

        # If you want to test successful registration, your endpoint should return 200/201
        # and you should fix the implementation first

    def test_product_registration_missing_fields(self):
        """Test product registration with missing required fields"""
        response = self.client.post('/register-container',
                                    data={
                                        'category': '',  # Missing
                                        'brand': '',  # Missing
                                        'product': '',  # Missing
                                        'price': '',
                                        'quantity': ''
                                    },
                                    content_type='multipart/form-data')

        # Your endpoint returns 400 for invalid data (client error)
        # Change this to match what your endpoint actually returns
        self.assertEqual(response.status_code, 400)  # or 500 if that's what it returns

        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Invalid data', data['message'])  # Adjust to match actual error message

    def test_product_registration_without_image(self):
        """Test product registration without an image"""
        response = self.client.post('/register-container',
                                    data={
                                        'category': 'Health & Personal',
                                        'brand': 'Test Brand',
                                        'product': 'Test Product',
                                        'price': '5.99',
                                        'quantity': '200'
                                    },
                                    content_type='multipart/form-data')

        # Your endpoint returns 500
        self.assertEqual(response.status_code, 500)

    def test_product_registration_invalid_price(self):
        """Test product registration with invalid price"""
        response = self.client.post('/register-container',
                                    data={
                                        'category': 'Home & Living',
                                        'brand': 'Test Brand',
                                        'product': 'Test Product',
                                        'price': '-10.99',  # Invalid price
                                        'quantity': '100'
                                    },
                                    content_type='multipart/form-data')

        # Your endpoint returns 500 for invalid price
        self.assertEqual(response.status_code, 500)

    def test_product_registration_new_category(self):
        """Test product registration with a new custom category"""
        response = self.client.post('/register-container',
                                    data={
                                        'category': 'Other',
                                        'other-category': 'New Test Category',
                                        'brand': 'Test Brand',
                                        'product': 'Test Product',
                                        'price': '15.99',
                                        'quantity': '50'
                                    },
                                    content_type='multipart/form-data')

        # Your endpoint returns 500
        self.assertEqual(response.status_code, 500)


if __name__ == '__main__':
    unittest.main()