from flask import Blueprint, render_template, session, current_app, request, jsonify, flash, redirect
import sqlite3, os
import secrets
import string
from datetime import datetime, timedelta
import base64
from extensions import mail
from flask import url_for
from flask_mail import Message


manager_bp = Blueprint('manager', __name__, template_folder='../templates')

def send_account_email(name, email, username, password, role):
    try:
        subject = "Your New Account Details"
        html = f"""
        <h2>Welcome to the System, {name}!</h2>
        <p>Your account has been created with the following details:</p>
        <ul>
            <li><strong>Username:</strong> {username}</li>
            <li><strong>Temporary Password:</strong> {password}</li>
            <li><strong>Role:</strong> {role.capitalize()}</li>
        </ul>
        <p>Please log in and change your password immediately.</p>
        <p>Login URL: {request.host_url}login</p>
        <p>Best regards,<br>The Management Team</p>
        """

        msg = Message(
            subject=subject,
            recipients=[email],
            html=html,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )

        mail.send(msg)
        current_app.logger.info(f"Account email sent to {email}")

    except Exception as e:
        current_app.logger.error(f"Error sending email to {email}: {str(e)}")
        # Don't fail the operation if email fails

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
    return render_template('manager_dashboard.html',
                         manager_name=get_manager_name(session.get('user_id')),
                         active_tab='Dashboard')

@manager_bp.route('/manager/dashboard-data')
def dashboard_data():
    try:
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get total products count
        cursor.execute("SELECT COUNT(*) FROM Product")
        total_products = cursor.fetchone()[0]

        # Get low stock items count (less than 10)
        cursor.execute("SELECT COUNT(*) FROM Product WHERE StockQuantity < 10")
        low_stock_items = cursor.fetchone()[0]

        # Get recent sales count (last 7 days)
        cursor.execute("""
            SELECT COUNT(*) FROM Sale 
            WHERE Timestamp >= DATE('now', '-7 days')
        """)
        recent_sales = cursor.fetchone()[0]

        return jsonify({
            'total_products': total_products,
            'low_stock_items': low_stock_items,
            'recent_sales': recent_sales
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()


@manager_bp.route('/manager/all-products')
def all_products():
    return render_template('manager_allproducts.html',
                         manager_name=get_manager_name(session.get('user_id')),
                         active_tab='All Products')

@manager_bp.route('/manager/activity-page')
def activity_page():
    return render_template('manager_activity.html',
                       manager_name=get_manager_name(session.get('user_id')),
                       active_tab='Activity')

@manager_bp.route('/manager/inventory-report')
def inventory_report():
    return render_template('manager_inventory.html',
                         manager_name=get_manager_name(session.get('user_id')),
                         active_tab='Inventory Report')

@manager_bp.route('/manager/sales-report')
def sales_report():
    return render_template('manager_sales.html',
                         manager_name=get_manager_name(session.get('user_id')),
                         active_tab='Sales Report')

@manager_bp.route('/manager/employee')
def employee():
    return render_template('manager_employee.html',
                         manager_name=get_manager_name(session.get('user_id')),
                         active_tab='Employee')

@manager_bp.route('/manager/activity-logs')
def get_activity_logs():
    try:
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get filter parameters
        action_filter = request.args.get('action', 'all')
        user_filter = request.args.get('user', 'all')
        role_filter = request.args.get('role', 'all')
        date_from = request.args.get('from')
        date_to = request.args.get('to')

        # Build query
        query = """
            SELECT 
                ActivityLog.*, 
                User.Name as UserName,
                User.Role as Role,
                User.Username as Username
            FROM ActivityLog 
            LEFT JOIN User ON ActivityLog.UserID = User.UserID
            WHERE 1=1
        """
        params = []

        # Add filters
        if action_filter != 'all':
            query += " AND ActionType = ?"
            params.append(action_filter)
        
        if user_filter != 'all':
            query += " AND ActivityLog.UserID = ?"
            params.append(user_filter)
        
        if role_filter != 'all':
            query += " AND User.Role = ?"
            params.append(role_filter)
        
        if date_from:
            query += " AND DATE(ActivityLog.Timestamp) >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND DATE(ActivityLog.Timestamp) <= ?"
            params.append(date_to)

        query += " ORDER BY ActivityLog.Timestamp DESC LIMIT 100"

        cursor.execute(query, params)
        logs = [dict(log) for log in cursor.fetchall()]
        
        return jsonify(logs)

    except Exception as e:
        current_app.logger.error(f"Error fetching logs: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()
            
@manager_bp.route('/manager/get-all-users')
def get_all_users():
    try:
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all users, not just cashiers
        cursor.execute("""
            SELECT UserID, Name, Username, Email, Role 
            FROM User
            ORDER BY Name
        """)
        users = [dict(user) for user in cursor.fetchall()]
        return jsonify(users)

    except Exception as e:
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
        role = data.get('role', 'cashier')

        if not all([name, username, email]):
            return jsonify({'error': 'Name, username and email are required'}), 400

        # Generate token and expiry (24 hours from now)
        token = secrets.token_urlsafe(32)
        expiry = datetime.utcnow() + timedelta(hours=24)
        temp_password = generate_temp_password()

        # Hash the temporary password
        from werkzeug.security import generate_password_hash
        hashed_temp_password = generate_password_hash(temp_password)

        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if username or email exists
        cursor.execute("SELECT UserID FROM User WHERE Username = ? OR Email = ?", (username, email))
        if cursor.fetchone():
            return jsonify({'error': 'Username or email already exists'}), 400

        # Insert new employee with inactive status and hashed temp password
        cursor.execute("""
            INSERT INTO User (Name, Username, Email, Role, Password, registration_token, token_expiry, IsActive)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, username, email, role, hashed_temp_password, token, expiry, False))

        conn.commit()

        # Generate proper registration URL - UPDATED ENDPOINT NAME
        registration_url = url_for('register.register_with_token', token=token, _external=True)

        try:
            msg = Message(
                subject="Complete Your Account Registration",
                recipients=[email],
                sender=current_app.config['MAIL_DEFAULT_SENDER']
            )

            msg.html = f"""
            <h2>Welcome to the System, {name}!</h2>
            <p>Your manager has created an account for you.</p>
            <p>Your temporary password is: <strong>{temp_password}</strong></p>
            <p>Please complete your registration by clicking the link below:</p>
            <p><a href="{registration_url}">{registration_url}</a></p>
            <p>This link will expire in 24 hours.</p>
            <p>Best regards,<br>The Management Team</p>
            """

            mail.send(msg)
            current_app.logger.info(f"Registration email sent to {email}")
        except Exception as e:
            current_app.logger.error(f"Error sending email to {email}: {str(e)}")
            return jsonify({
                'message': 'Employee added but email could not be sent. Please provide them with this registration link manually.',
                'registration_url': registration_url,
                'temp_password': temp_password
            })

        return jsonify({
            'message': 'Employee added successfully. Registration email sent.'
        })

    except sqlite3.Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

def send_registration_email(name, email, token, temp_password=None):
    try:
        subject = "Complete Your Account Registration"
        # UPDATED ENDPOINT NAME
        registration_url = url_for('register.register_with_token', token=token, _external=True)

        html = f"""
        <h2>Welcome to the System, {name}!</h2>
        <p>Your manager has created an account for you.</p>
        """
        if temp_password:
            html += f"""
            <p>Your temporary password is: <strong>{temp_password}</strong></p>
            """
        html += f"""
        <p>Please complete your registration by clicking the link below:</p>
        <p><a href="{registration_url}">{registration_url}</a></p>
        <p>This link will expire in 24 hours.</p>
        <p>Best regards,<br>The Management Team</p>
        """

        msg = Message(
            subject=subject,
            recipients=[email],
            html=html,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )

        mail.send(msg)
        current_app.logger.info(f"Registration email sent to {email}")

    except Exception as e:
        current_app.logger.error(f"Error sending email to {email}: {str(e)}")
        
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
            WHERE Role != 'manager'
            ORDER BY Name
        """)
        return jsonify([dict(emp) for emp in cursor.fetchall()])

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@manager_bp.route('/manager/remove-employee', methods=['POST'])
def remove_employee():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400
            
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # First check if the user exists and is not a manager
        cursor.execute("SELECT Role FROM User WHERE UserID = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        if user[0] == 'manager':
            return jsonify({'error': 'Cannot remove manager accounts'}), 403
            
        # Delete the user
        cursor.execute("DELETE FROM User WHERE UserID = ?", (user_id,))
        conn.commit()
        
        return jsonify({'message': 'Employee removed successfully'})
        
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
        conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM Product WHERE ProductID = ?", (product_id,))
        result = cursor.fetchone()
        if not result:
            flash('Product not found', 'danger')
            return redirect(url_for('manager.all_products'))

        product = dict(result)

        return render_template('manager_productdetails.html', product=product)

    except Exception as e:
        current_app.logger.error(f"Error fetching product: {e}")
        flash('Error loading product', 'danger')
        return redirect(url_for('manager.all_products'))

@manager_bp.context_processor
def inject_manager_name():
    return {'manager_name': get_manager_name(session.get('user_id'))}


@manager_bp.route('/api/products')
def get_products():
    try:
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Simplified query without alert joins
        cursor.execute("""
            SELECT 
                ProductID, 
                ProductName, 
                Category, 
                Price, 
                StockQuantity, 
                ProductBrand,
                Image
            FROM Product
            ORDER BY ProductName
        """)

        products = [dict(product) for product in cursor.fetchall()]
        return jsonify(products)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()


def get_db():
    """Connect to the SQLite database"""
    conn = sqlite3.connect('site.db')
    conn.row_factory = sqlite3.Row  # Enable dictionary-style access
    return conn


@manager_bp.route('/manager/sales-data')
def sales_data():
    try:
        # Get date parameters
        days = request.args.get('days')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build the date filter part of the query
        date_filter = ""
        params = []

        if days:
            # Use relative day filter (last X days)
            date_filter = "WHERE t.Datetime >= DATE('now', ? || ' days')"
            params = [f'-{days}']
        elif start_date and end_date:
            # Use absolute date range filter
            date_filter = "WHERE DATE(t.Datetime) BETWEEN ? AND ?"
            params = [start_date, end_date]
        else:
            # Default to last 30 days if no filter specified
            date_filter = "WHERE t.Datetime >= DATE('now', '-30 days')"

        # Get daily sales data from Transaction table
        cursor.execute(f"""
            SELECT 
                DATE(t.Datetime) as sale_date,
                SUM(t.TotalAmount) as total_sales,
                COUNT(DISTINCT t.TransactionID) as transaction_count
            FROM "Transaction" t
            {date_filter}
            GROUP BY DATE(t.Datetime)
            ORDER BY sale_date
        """, params)

        daily_sales = [dict(row) for row in cursor.fetchall()]

        # Calculate period totals
        period_total = sum(day['total_sales'] for day in daily_sales)
        period_transactions = sum(day['transaction_count'] for day in daily_sales)

        # Get category sales data
        cursor.execute(f"""
            SELECT 
                p.Category,
                SUM(td.Quantity * td.Price) as total_sales,
                SUM(td.Quantity) as items_sold
            FROM TransactionDetails td
            JOIN Product p ON td.ProductID = p.ProductID
            JOIN "Transaction" t ON td.TransactionID = t.TransactionID
            {date_filter}
            GROUP BY p.Category
            ORDER BY total_sales DESC
        """, params)

        category_sales = [dict(row) for row in cursor.fetchall()]

        # Get top products
        cursor.execute(f"""
            SELECT 
                p.ProductName,
                SUM(td.Quantity) as total_quantity,
                SUM(td.Quantity * td.Price) as total_revenue
            FROM TransactionDetails td
            JOIN Product p ON td.ProductID = p.ProductID
            JOIN "Transaction" t ON td.TransactionID = t.TransactionID
            {date_filter}
            GROUP BY p.ProductID
            ORDER BY total_quantity DESC
            LIMIT 10
        """, params)

        top_products = [dict(row) for row in cursor.fetchall()]

        # Calculate total items sold
        total_items = sum(product['total_quantity'] for product in top_products)

        return jsonify({
            'daily_sales': daily_sales,
            'category_sales': category_sales,
            'top_products': top_products,
            'period_total': period_total,
            'period_transactions': period_transactions,
            'total_items': total_items,
            'date_filter': {
                'start_date': start_date if start_date else None,
                'end_date': end_date if end_date else None,
                'days': days if days else None
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching sales data: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()


@manager_bp.route('/manager/inventory-report-data')
def inventory_report_data():
    try:
        category_filter = request.args.get('category', 'all')
        stock_filter = request.args.get('stock', 'all')

        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT ProductID, ProductName, Category, Price, StockQuantity FROM Product WHERE 1=1"
        params = []

        if category_filter != 'all':
            query += " AND Category = ?"
            params.append(category_filter)

        if stock_filter == 'low':
            query += " AND StockQuantity > 0 AND StockQuantity < 10"
        elif stock_filter == 'out':
            query += " AND StockQuantity <= 0"
        elif stock_filter == 'sufficient':
            query += " AND StockQuantity >= 10"

        query += " ORDER BY StockQuantity ASC, ProductName"

        cursor.execute(query, params)
        products = [dict(product) for product in cursor.fetchall()]
        return jsonify(products)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@manager_bp.route('/api/product-categories')
def get_product_categories():
    try:
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT Category FROM Product WHERE Category IS NOT NULL ORDER BY Category")
        categories = [row[0] for row in cursor.fetchall()]
        return jsonify(categories)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()