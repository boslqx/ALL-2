from flask import Blueprint, render_template, session, current_app, request, jsonify, send_from_directory
from datetime import datetime, timedelta
from db.models import User, Product, StockAlert, Transaction, TransactionDetails
from db import db
import sys
import os 
    
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from io import BytesIO
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

    products_data = []
    for product in products:
        products_data.append({
            'id': product.ProductID,
            'name': product.ProductName,
            'brand': product.Brand if hasattr(product, 'Brand') else '',
            'price': product.Price,
            'stock': product.StockQuantity,
            'category': product.Category,
            'image': product.Image if hasattr(product, 'Image') else None  # Add image path
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
    
@cashier_bp.route('/static/product_image/<filename>')
def serve_product_image(filename):
    return send_from_directory(os.path.join(current_app.static_folder, 'product_image'), filename)

@cashier_bp.route('/cashier/checkout-page')
def checkout_page():
    user_id = session.get('user_id')
    cashier_name = 'Cashier'

    if user_id:
        user = User.query.get(user_id)
        if user:
            cashier_name = f"Cashier {user.Name}"

    # Get cart items from session or request (you'll need to implement this)
    # For now, we'll just pass empty data
    return render_template(
        'checkout.html',
        cashier_name=cashier_name,
        active_tab='new_transaction',
        cart_items=[],
        total=0
    )

@cashier_bp.route('/cashier/complete-transaction', methods=['POST'])
def complete_transaction():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not logged in'}), 401

    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'error': 'Invalid request data'}), 400

    try:
        # Get cashier name
        cashier = User.query.get(user_id)
        cashier_name = cashier.Name if cashier else "Unknown"

        # Create new transaction
        new_transaction = Transaction(
            CashierID=user_id,
            TotalAmount=data['totalAmount'],
            Datetime=datetime.utcnow()
        )
        db.session.add(new_transaction)
        db.session.flush()  # To get the transaction ID

        # Add transaction details and update stock
        details = []
        for item in data['items']:
            product = Product.query.get(item['productId'])
            if not product:
                return jsonify({'error': f'Product {item["productId"]} not found'}), 404
            
            if product.StockQuantity < item['quantity']:
                return jsonify({'error': f'Not enough stock for {product.ProductName}'}), 400
            
            detail = TransactionDetails(
                TransactionID=new_transaction.TransactionID,
                ProductID=item['productId'],
                Quantity=item['quantity'],
                Price=item['price']
            )
            db.session.add(detail)
            details.append(detail)
            
            # Update product stock
            product.StockQuantity -= item['quantity']
            db.session.add(product)

        db.session.commit()

        # Generate PDF receipt
        pdf_buffer = generate_receipt(new_transaction, details, cashier_name)
        
        # Save PDF to server (optional)
        receipt_dir = os.path.join(current_app.static_folder, 'receipts')
        os.makedirs(receipt_dir, exist_ok=True)
        receipt_path = os.path.join(receipt_dir, f'receipt_{new_transaction.TransactionID}.pdf')
        with open(receipt_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())

        # Return both JSON response and PDF
        response = jsonify({
            'success': True,
            'transactionId': new_transaction.TransactionID,
            'totalAmount': new_transaction.TotalAmount,
            'receiptUrl': f'/static/receipts/receipt_{new_transaction.TransactionID}.pdf'
        })
        
        return response

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Transaction error: {str(e)}')
        return jsonify({'error': 'Failed to process transaction'}), 500
    

def generate_receipt(transaction, transaction_details, cashier_name):
    # Create a buffer for the PDF
    buffer = BytesIO()
    
    # Create the PDF object
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Set up receipt styling
    p.setFont("Helvetica-Bold", 16)
    p.drawString(1*inch, height-1*inch, "Your Store Name")
    p.setFont("Helvetica", 12)
    p.drawString(1*inch, height-1.25*inch, "123 Store Address")
    p.drawString(1*inch, height-1.5*inch, "Phone: (123) 456-7890")
    
    # Draw a line
    p.line(1*inch, height-1.6*inch, width-1*inch, height-1.6*inch)
    
    # Transaction info
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1*inch, height-2*inch, f"Receipt #: {transaction.TransactionID}")
    p.setFont("Helvetica", 12)
    p.drawString(1*inch, height-2.25*inch, f"Date: {transaction.Datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    p.drawString(1*inch, height-2.5*inch, f"Cashier: {cashier_name}")
    
    # Items header
    p.line(1*inch, height-2.7*inch, width-1*inch, height-2.7*inch)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(1*inch, height-2.9*inch, "Item")
    p.drawString(4*inch, height-2.9*inch, "Qty")
    p.drawString(5*inch, height-2.9*inch, "Price")
    p.drawString(6.5*inch, height-2.9*inch, "Total")
    p.line(1*inch, height-3*inch, width-1*inch, height-3*inch)
    
    # Items list
    y_position = height - 3.2*inch
    p.setFont("Helvetica", 10)
    
    for item in transaction_details:
        product = Product.query.get(item.ProductID)
        p.drawString(1*inch, y_position, product.ProductName)
        p.drawString(4*inch, y_position, str(item.Quantity))
        p.drawString(5*inch, y_position, f"RM{item.Price:.2f}")
        p.drawString(6.5*inch, y_position, f"RM{item.Price * item.Quantity:.2f}")
        y_position -= 0.25*inch
        
        # New page if we're running out of space
        if y_position < 1*inch:
            p.showPage()
            y_position = height - 1*inch
    
    # Totals
    p.line(1*inch, y_position-0.1*inch, width-1*inch, y_position-0.1*inch)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(5*inch, y_position-0.3*inch, "Subtotal:")
    p.drawString(6.5*inch, y_position-0.3*inch, f"RM{transaction.TotalAmount/1.06:.2f}")
    p.drawString(5*inch, y_position-0.6*inch, "Tax (6%):")
    p.drawString(6.5*inch, y_position-0.6*inch, f"RM{transaction.TotalAmount*0.06:.2f}")
    p.drawString(5*inch, y_position-0.9*inch, "Total:")
    p.drawString(6.5*inch, y_position-0.9*inch, f"RM{transaction.TotalAmount:.2f}")
    
    # Thank you message
    p.setFont("Helvetica", 10)
    p.drawString(1*inch, y_position-1.5*inch, "Thank you for shopping with us!")
    
    # Save the PDF
    p.showPage()
    p.save()
    
    # Get PDF content from buffer
    buffer.seek(0)
    return buffer

@cashier_bp.route('/static/receipts/<filename>')
def serve_receipt(filename):
    return send_from_directory(os.path.join(current_app.static_folder, 'receipts'), filename)