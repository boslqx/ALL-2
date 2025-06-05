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
        role = data.get('role', 'cashier')

        if not all([name, username, email]):
            return jsonify({'error': 'Name, username and email are required'}), 400

        # Generate token and expiry (24 hours from now)
        token = secrets.token_urlsafe(32)
        expiry = datetime.utcnow() + timedelta(hours=24)
        temp_password = generate_temp_password()

        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if username or email exists
        cursor.execute("SELECT UserID FROM User WHERE Username = ? OR Email = ?", (username, email))
        if cursor.fetchone():
            return jsonify({'error': 'Username or email already exists'}), 400

        # Insert new employee with inactive status and temp password
        cursor.execute("""
            INSERT INTO User (Name, Username, Email, Role, Password, registration_token, token_expiry, IsActive)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, username, email, role, temp_password, token, expiry, False))

        conn.commit()

        # Generate proper registration URL
        registration_url = url_for('register.register', token=token, _external=True)

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
        registration_url = url_for('register.register', token=token, _external=True)

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


@manager_bp.route('/manager/sales-data')
def get_sales_data():
    try:
        days = request.args.get('days', '30')
        try:
            days = int(days)
        except ValueError:
            days = 30

        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get sales data by date
        cursor.execute("""
            SELECT 
                DATE(Sale.Timestamp) as sale_date,
                SUM(SaleItem.Quantity * SaleItem.PriceAtSale) as total_sales,
                COUNT(DISTINCT Sale.SaleID) as transaction_count,
                SUM(SaleItem.Quantity) as items_sold
            FROM Sale
            JOIN SaleItem ON Sale.SaleID = SaleItem.SaleID
            WHERE Sale.Timestamp >= DATE('now', ? || ' days')
            GROUP BY DATE(Sale.Timestamp)
            ORDER BY sale_date DESC
        """, (f'-{days}',))
        daily_sales = [dict(row) for row in cursor.fetchall()]

        # Get top selling products
        cursor.execute("""
            SELECT 
                Product.ProductName,
                SUM(SaleItem.Quantity) as total_quantity,
                SUM(SaleItem.Quantity * SaleItem.PriceAtSale) as total_revenue
            FROM SaleItem
            JOIN Product ON SaleItem.ProductID = Product.ProductID
            GROUP BY Product.ProductID
            ORDER BY total_quantity DESC
            LIMIT 10
        """)
        top_products = [dict(row) for row in cursor.fetchall()]

        # Get sales by category
        cursor.execute("""
            SELECT 
                Product.Category,
                SUM(SaleItem.Quantity * SaleItem.PriceAtSale) as total_sales,
                SUM(SaleItem.Quantity) as items_sold
            FROM SaleItem
            JOIN Product ON SaleItem.ProductID = Product.ProductID
            GROUP BY Product.Category
            ORDER BY total_sales DESC
        """)
        category_sales = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            'daily_sales': daily_sales,
            'top_products': top_products,
            'category_sales': category_sales
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()