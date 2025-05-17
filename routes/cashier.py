from flask import Blueprint, render_template, session, current_app, request, jsonify
from datetime import datetime, timedelta
from db.models import User, Product, StockAlert, Transaction, TransactionDetails
from db import db
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib'))
import cv2


import numpy as np

cashier_bp = Blueprint('cashier', __name__, template_folder='../templates')

cashier_bp = Blueprint('cashier', __name__, template_folder='../templates')

@cashier_bp.route('/cashier')
def dashboard():
    user_id = session.get('user_id')
    cashier_name = 'Cashier'

    if user_id:
        user = User.query.get(user_id)
        if user:
            cashier_name = f"Cashier {user.Name}"

    # Get stock alerts (low stock items)
    stock_alerts = StockAlert.query.join(Product).filter(
        StockAlert.AlertStatus == 'Active'
    ).order_by(
        StockAlert.Timestamp.desc()
    ).limit(3).all()

    # Get recent transactions (last 4 hours)
    time_threshold = datetime.utcnow() - timedelta(hours=4)
    recent_transactions = Transaction.query.filter(
        Transaction.Datetime >= time_threshold
    ).order_by(
        Transaction.Datetime.desc()
    ).limit(4).all()

    return render_template(
        'cashier.html',
        cashier_name=cashier_name,
        stock_alerts=stock_alerts,
        recent_transactions=recent_transactions,
        active_tab='dashboard'
    )

@cashier_bp.route('/cashier/new-transaction')
def new_transaction():
    user_id = session.get('user_id')
    cashier_name = 'Cashier'

    if user_id:
        user = User.query.get(user_id)
        if user:
            cashier_name = f"Cashier {user.Name}"

    # Get all distinct categories
    categories = db.session.query(Product.Category).distinct().all()
    categories = [category[0] for category in categories]

    # Get initial products
    products = Product.query.order_by(Product.ProductName).limit(50).all()

    return render_template(
        'new_transaction.html',
        cashier_name=cashier_name,
        categories=categories,
        products=products,
        active_tab='new_transaction'
    )

@cashier_bp.route('/cashier/search-products')
def search_products():
    query = request.args.get('query', '').lower()  # Convert query to lowercase
    category = request.args.get('category', '')
    stock_filter = request.args.get('stock_filter', 'all')

    # Base query
    products_query = Product.query

    # Apply filters - now case insensitive for product name
    if query:
        products_query = products_query.filter(db.func.lower(Product.ProductName).contains(query))

    if category:
        products_query = products_query.filter_by(Category=category)

    if stock_filter == 'low':
        products_query = products_query.filter(Product.StockQuantity < 10)
    elif stock_filter == 'out':
        products_query = products_query.filter(Product.StockQuantity == 0)

    products = products_query.order_by(Product.ProductName).limit(50).all()

    # Prepare data for JSON response
    products_data = []
    for product in products:
        products_data.append({
            'id': product.ProductID,
            'name': product.ProductName,
            'brand': product.ProductBrand,
            'price': product.Price,
            'stock': product.StockQuantity,
            'category': product.Category
        })

    return jsonify(products_data)

@cashier_bp.route('/cashier/get-product/<int:product_id>')
def get_product(product_id):
    product = Product.query.get(product_id)
    if product:
        return jsonify({
            'id': product.ProductID,
            'name': product.ProductName,
            'price': product.Price,
            'stock': product.StockQuantity
        })
    return jsonify({'error': 'Product not found'}), 404

@cashier_bp.route('/cashier/checkout', methods=['POST'])
def checkout():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not logged in'}), 401

    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'error': 'Invalid request data'}), 400

    try:
        # Create new transaction
        new_transaction = Transaction(
            UserID=user_id,
            Datetime=datetime.utcnow(),
            TotalAmount=sum(item['price'] * item['quantity'] for item in data['items']),
            PaymentMethod=data.get('payment_method', 'Cash')
        )
        db.session.add(new_transaction)
        db.session.flush()  # To get the transaction ID

        # Add transaction details
        for item in data['items']:
            product = Product.query.get(item['id'])
            if not product:
                return jsonify({'error': f'Product {item["id"]} not found'}), 404
            
            if product.StockQuantity < item['quantity']:
                return jsonify({'error': f'Not enough stock for {product.ProductName}'}), 400
            
            detail = TransactionDetails(
                TransactionID=new_transaction.TransactionID,
                ProductID=item['id'],
                Quantity=item['quantity'],
                UnitPrice=item['price'],
                Subtotal=item['price'] * item['quantity']
            )
            db.session.add(detail)
            
            # Update product stock
            product.StockQuantity -= item['quantity']
            db.session.add(product)

        db.session.commit()
        return jsonify({
            'success': True,
            'transaction_id': new_transaction.TransactionID,
            'total_amount': new_transaction.TotalAmount
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Checkout error: {str(e)}')
        return jsonify({'error': 'Failed to process transaction'}), 500