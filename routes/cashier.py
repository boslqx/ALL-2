from flask import Blueprint, render_template, session, current_app
from datetime import datetime, timedelta
from db.models import User, Product, StockAlert, Transaction, TransactionDetails
from db import db

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