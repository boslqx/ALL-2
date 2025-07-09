import unittest
import os
import sys
from werkzeug.security import generate_password_hash
from datetime import datetime

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from your app structure
from app import app, db
from db.models import User, Product, Transaction, TransactionDetails


class TestTransactions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure test app - runs once before all tests
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
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
        # Create test data for each test
        with app.app_context():
            # Clear any existing data
            db.session.query(TransactionDetails).delete()
            db.session.query(Transaction).delete()
            db.session.query(Product).delete()
            db.session.query(User).delete()

            # Create test cashier user
            self.cashier = User(
                Passcode="123456",
                Password=generate_password_hash("testpass"),
                Role="cashier",
                Name="Test Cashier",
                Email="cashier@test.com",
                IsActive=True
            )
            db.session.add(self.cashier)

            # Create test products
            self.product1 = Product(
                ProductName="Test Product 1",
                Category="Food & Beverages",
                Price=10.99,
                StockQuantity=100,
                QRcode="qr123"
            )
            self.product2 = Product(
                ProductName="Test Product 2",
                Category="Health & Personal",
                Price=5.99,
                StockQuantity=50,
                QRcode="qr456"
            )
            db.session.add_all([self.product1, self.product2])
            db.session.commit()

            # Store IDs for later use
            self.cashier_id = self.cashier.UserID
            self.product1_id = self.product1.ProductID
            self.product2_id = self.product2.ProductID

    def login_cashier(self):
        # Helper method to log in as cashier
        with self.client.session_transaction() as session:
            session['user_id'] = self.cashier_id
            session['role'] = 'cashier'
            session['_fresh'] = True

    def test_new_transaction_page(self):
        """Test accessing the new transaction page"""
        self.login_cashier()
        response = self.client.get('/cashier/new-transaction')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'New Transaction', response.data)

    def test_get_product(self):
        """Test getting a single product by ID"""
        self.login_cashier()
        response = self.client.get(f'/cashier/get-product/{self.product1_id}')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['name'], "Test Product 1")
        self.assertEqual(data['price'], 10.99)

    def test_get_nonexistent_product(self):
        """Test getting a product that doesn't exist"""
        self.login_cashier()
        response = self.client.get('/cashier/get-product/9999')
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()