from flask import Blueprint, render_template, session, current_app, jsonify, request
from datetime import datetime, timedelta
from db.models import User, Product, StockAlert, Transaction, TransactionDetails, Product
from db import db
import cv2 #pip install opencv-python, then pip install opencv-contrib-python
import numpy as np
import pyzbar as pyzbar

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
    # Get all categories for the sidebar
    categories = db.session.query(Product.Category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    # Get initial products (all or filtered by first category)
    products = Product.query.order_by(Product.ProductName).all()
    
    return render_template(
        'new_transaction.html',
        categories=categories,
        products=products,
        active_tab='new_transaction'
    )

@cashier_bp.route('/cashier/search-products')
def search_products():
    query = request.args.get('query', '')
    category = request.args.get('category', '')
    sort_by = request.args.get('sort_by', 'name')
    stock_filter = request.args.get('stock_filter', 'all')
    
    # Base query
    products_query = Product.query
    
    # Apply filters
    if query:
        products_query = products_query.filter(Product.ProductName.ilike(f'%{query}%'))
    
    if category:
        products_query = products_query.filter_by(Category=category)
    
    if stock_filter == 'low':
        products_query = products_query.filter(Product.StockQuantity < 10)
    elif stock_filter == 'out':
        products_query = products_query.filter(Product.StockQuantity == 0)
    
    # Apply sorting
    if sort_by == 'name':
        products_query = products_query.order_by(Product.ProductName)
    elif sort_by == 'price_low':
        products_query = products_query.order_by(Product.Price)
    elif sort_by == 'price_high':
        products_query = products_query.order_by(Product.Price.desc())
    elif sort_by == 'stock_low':
        products_query = products_query.order_by(Product.StockQuantity)
    elif sort_by == 'stock_high':
        products_query = products_query.order_by(Product.StockQuantity.desc())
    
    products = products_query.all()
    
    # Convert to dictionary for JSON response
    products_data = [{
        'id': p.ProductID,
        'name': p.ProductName,
        'category': p.Category,
        'price': p.Price,
        'stock': p.StockQuantity,
        'brand': p.ProductBrand,
        'qrcode': p.QRcode
    } for p in products]
    
    return jsonify(products_data)

@cashier_bp.route('/cashier/scan-qr', methods=['POST'])
def scan_qr():
    # Get the image data from the request
    image_data = request.files['image'].read()
    
    # Convert to numpy array
    nparr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Decode QR codes
    decoded_objects = pyzbar.decode(img)
    
    product_ids = []
    for obj in decoded_objects:
        try:
            # Assuming QR code contains product ID
            product_id = int(obj.data.decode('utf-8'))
            product_ids.append(product_id)
        except:
            continue
    
    # Get product details
    products = Product.query.filter(Product.ProductID.in_(product_ids)).all()
    
    products_data = [{
        'id': p.ProductID,
        'name': p.ProductName,
        'price': p.Price,
        'stock': p.StockQuantity
    } for p in products]
    
    return jsonify(products_data)