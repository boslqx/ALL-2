from flask import Blueprint, render_template, session, current_app, request, jsonify
import sqlite3, os
import secrets
import string
from datetime import datetime
import base64

manager_bp = Blueprint('manager', __name__, template_folder='../templates')

def get_manager_name(user_id):
    manager_name = 'manager'
    if user_id:
        try:
            db_path = os.path.join(current_app.instance_path, 'site.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT Name FROM User WHERE UserID = ?", (user_id,))
            result = cursor.fetchone()
            if result:
                manager_name = f"manager {result[0]}"
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        finally:
            if 'conn' in locals():
                conn.close()
    return manager_name

@manager_bp.route('/manager')
@manager_bp.route('/manager/dashboard')
def dashboard():
    return render_template('manager.html',
                         manager_name=get_manager_name(session.get('user_id')),
                         active_tab='Dashboard')

@manager_bp.route('/manager/all-products')
def all_products():
    return render_template('manager.html',
                         manager_name=get_manager_name(session.get('user_id')),
                         active_tab='All Products')

@manager_bp.route('/manager/inventory-report')
def inventory_report():
    return render_template('manager.html',
                         manager_name=get_manager_name(session.get('user_id')),
                         active_tab='Inventory Report')

@manager_bp.route('/manager/sales-report')
def sales_report():
    return render_template('manager.html',
                         manager_name=get_manager_name(session.get('user_id')),
                         active_tab='Sales Report')

@manager_bp.route('/manager/employee')
def employee():
    return render_template('manager.html',
                         manager_name=get_manager_name(session.get('user_id')),
                         active_tab='Employee')

@manager_bp.route('/manager/activity-logs')
def get_activity_logs():
    try:
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        action_filter = request.args.get('action', 'all')
        query = """
            SELECT ActivityLog.*, User.Name as UserName 
            FROM ActivityLog 
            LEFT JOIN User ON ActivityLog.UserID = User.UserID
        """
        params = []
        if action_filter != 'all':
            query += " WHERE ActionType = ?"
            params.append(action_filter)
        query += " ORDER BY Timestamp DESC LIMIT 100"

        cursor.execute(query, params)
        return jsonify([dict(log) for log in cursor.fetchall()])

    except Exception as e:
        print(f"Error fetching logs: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@manager_bp.route('/manager/add-employee', methods=['POST'])
def add_employee():
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        username = data.get('username')

        if not all([name, username]):
            return jsonify({'error': 'Name and username are required'}), 400

        temp_password = generate_temp_password()
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT UserID FROM User WHERE Username = ?", (username,))
        if cursor.fetchone():
            return jsonify({'error': 'Username already exists'}), 400

        cursor.execute("""
            INSERT INTO User (Name, Username, Email, PasswordHash, Role, IsActive, MustChangePassword)
            VALUES (?, ?, ?, ?, 'cashier', 1, 1)
        """, (name, username, email, temp_password))

        conn.commit()
        return jsonify({
            'message': 'Employee added successfully',
            'temp_password': temp_password
        })

    except sqlite3.Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@manager_bp.route('/manager/get-employees')
def get_employees():
    try:
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT UserID, Name, Username, Email, Role, IsActive 
            FROM User 
            WHERE Role = 'cashier'
            ORDER BY Name
        """)
        return jsonify([dict(emp) for emp in cursor.fetchall()])

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

def generate_temp_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@manager_bp.route('/manager/product/<int:product_id>')
def product_details(product_id):
    try:
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Fetch product from Product table (removed AlertThreshold)
        cursor.execute("""
            SELECT 
                ProductID, 
                ProductName, 
                Category, 
                Price, 
                StockQuantity, 
                ProductBrand,
                Image,
                QrCode
            FROM Product
            WHERE ProductID = ?
        """, (product_id,))

        product = cursor.fetchone()

        if not product:
            return "Product not found", 404

        # Convert to dict and handle binary data (e.g., QR code)
        product_data = dict(product)
        if product_data.get('QrCode'):
            product_data['QrCode'] = base64.b64encode(product_data['QrCode']).decode('utf-8')

        return render_template('manager_productdetails.html', product=product_data)

    except Exception as e:
        return f"Error loading product: {str(e)}", 500
    finally:
        if conn:
            conn.close()

