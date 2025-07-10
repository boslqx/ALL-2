import unittest
from unittest.mock import patch, MagicMock
from app import app


class TestTransactions(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['role'] = 'cashier'
            session['_fresh'] = True

    @patch('db.models.Product')
    def test_get_product(self, mock_product):
        mock_product_obj = MagicMock()
        mock_product_obj.ProductID = 1
        mock_product_obj.ProductName = "Chocolate Milk 1L"
        mock_product_obj.Price = 9.99
        mock_product_obj.StockQuantity = 10
        mock_product_obj.serialize.return_value = {
            'id': 1,
            'name': "Chocolate Milk 1L",
            'price': 9.99,
            'stock': 10
        }

        mock_product.query.get.return_value = mock_product_obj

        response = self.client.get('/cashier/get-product/1')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['id'], 1)
        self.assertEqual(data['name'], "Chocolate Milk 1L")

    @patch('db.models.Product')
    def test_get_nonexistent_product(self, mock_product):
        mock_product.query.get.return_value = None

        response = self.client.get('/cashier/get-product/999')
        self.assertEqual(response.status_code, 404)
        self.assertIn('error', response.get_json())


if __name__ == '__main__':
    unittest.main()
