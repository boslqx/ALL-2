from flask import Blueprint, render_template, session, current_app, request, redirect, url_for, flash, jsonify, send_file, send_from_directory
from flask.views import MethodView
import sqlite3, os
import secrets
import string
from datetime import datetime, timedelta
import base64
from extensions import mail, apply_role_protection
from flask_mail import Message
from io import BytesIO
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename


manager_bp = Blueprint('manager', __name__, template_folder='../templates')
apply_role_protection(manager_bp, 'manager')


# Utility Functions
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

def generate_temp_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_account_email(name, email, password, role):
    try:
        subject = "Your New Account Details"
        html = f"""
        <h2>Welcome to the System, {name}!</h2>
        <p>Your account has been created with the following details:</p>
        <ul>
            <li><strong>Email:</strong> {email}</li>
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

def send_registration_email(name, email, token, temp_password=None):
    try:
        subject = "Complete Your Account Registration"
        registration_url = url_for('register.register_with_token', token=token, _external=True)
        html = f"""
        <h2>Welcome to the System, {name}!</h2>
        <p>Your manager has created an account for you.</p>
        """
        if temp_password:
            html += f"<p>Your temporary password is: <strong>{temp_password}</strong></p>"
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

def log_activity(user_id, action_type, table_name, record_id, description):
    try:
        conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ActivityLog (UserID, ActionType, TableAffected, RecordID, Description, Timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            action_type,
            table_name,
            record_id,
            description,
            datetime.utcnow().isoformat()
        ))
        conn.commit()
    except Exception as e:
        current_app.logger.error(f"Failed to log activity: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

# Class-Based Views
class DashboardView(MethodView):
    def get(self):
        return render_template('manager_dashboard.html',
                            manager_name=get_manager_name(session.get('user_id')),
                            active_tab='Dashboard')

class ManagerProfileAPIView(MethodView):
    def get(self):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT UserID as id, Passcode, Name as name, Email as email, Role as role
                FROM User 
                WHERE UserID = ?
            """, (user_id,))
            
            user = cursor.fetchone()
            if not user:
                return jsonify({'error': 'User not found'}), 404
                
            return jsonify(dict(user))
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()

class ManagerDashboardStatsAPIView(MethodView):
    def get(self):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM Product")
            total_products = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM Product WHERE StockQuantity <= 5")
            low_stock_items = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM "Transaction" 
                WHERE Datetime >= DATE('now', '-7 days')
            """)
            recent_sales = cursor.fetchone()[0]

            cursor.execute("""
                SELECT A.Description, A.ActionType, A.Timestamp, 
                       COALESCE(U.Name, U.Passcode) AS Passcode
                FROM ActivityLog A
                LEFT JOIN User U ON A.UserID = U.UserID
                WHERE DATE(A.Timestamp) = DATE('now')
                ORDER BY A.Timestamp DESC
                LIMIT 5
            """)
            recent_activities = [dict(row) for row in cursor.fetchall()]

            return jsonify({
                'total_products': total_products,
                'low_stock_items': low_stock_items,
                'recent_sales': recent_sales,
                'recent_activities': recent_activities  # ✅
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()


class AllProductsView(MethodView):
    def get(self):
        return render_template('manager_allproducts.html',
                            manager_name=get_manager_name(session.get('user_id')),
                            active_tab='All Products')

class NewTransactionView(MethodView):
    def get(self):
        return render_template('manager_transaction.html',
                            manager_name=get_manager_name(session.get('user_id')),
                            active_tab='New Transaction')

class RegisterPageView(MethodView):
    def get(self):
        return render_template('manager_register.html',
                            manager_name=get_manager_name(session.get('user_id')),
                            active_tab='Register')

class ActivityPageView(MethodView):
    def get(self):
        return render_template('manager_activity.html',
                            manager_name=get_manager_name(session.get('user_id')),
                            active_tab='Activity')

class InventoryReportView(MethodView):
    def get(self):
        return render_template('manager_inventory.html',
                            manager_name=get_manager_name(session.get('user_id')),
                            active_tab='Inventory Report')

class SalesReportView(MethodView):
    def get(self):
        return render_template('manager_sales.html',
                            manager_name=get_manager_name(session.get('user_id')),
                            active_tab='Sales Report')

class EmployeeView(MethodView):
    def get(self):
        return render_template('manager_employee.html',
                            manager_name=get_manager_name(session.get('user_id')),
                            active_tab='Employee')

class ActivityLogsView(MethodView):
    def get(self):
        try:
            action_filter = request.args.get('action', 'all')
            user_filter = request.args.get('user', 'all')
            role_filter = request.args.get('role', 'all')
            date_from = request.args.get('from')
            date_to = request.args.get('to')
            
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT 
                    ActivityLog.*, 
                    User.Name as Name,
                    User.Role as Role,
                    User.Passcode as Passcode
                FROM ActivityLog 
                LEFT JOIN User ON ActivityLog.UserID = User.UserID
                WHERE 1=1
            """
            params = []
            
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

class AllUsersView(MethodView):
    def get(self):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT UserID, Name, Passcode, Email, Role 
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

class AddEmployeeView(MethodView):
    def post(self):
        try:
            data = request.get_json()
            name = data.get('name')
            email = data.get('email')
            role = data.get('role', 'cashier')

            if not all([name, email]):
                return jsonify({'error': 'Name and email are required'}), 400

            token = secrets.token_urlsafe(32)
            expiry = datetime.utcnow() + timedelta(hours=24)
            temp_password = generate_temp_password()
            
            # Generate a random 6-digit passcode
            passcode = ''.join(secrets.choice(string.digits) for _ in range(6))

            from werkzeug.security import generate_password_hash
            hashed_temp_password = generate_password_hash(temp_password)

            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            cursor = conn.cursor()

            # Check if passcode or email already exists
            cursor.execute("SELECT UserID FROM User WHERE Passcode = ? OR Email = ?", (passcode, email))
            if cursor.fetchone():
                return jsonify({'error': 'Passcode or email already exists'}), 400

            # Insert new employee
            cursor.execute("""
                INSERT INTO User (Name, Passcode, Email, Role, Password, registration_token, token_expiry, IsActive)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, passcode, email, role, hashed_temp_password, token, expiry, False))

            conn.commit()
            registration_url = url_for('register.register_with_token', token=token, _external=True)

            # Send registration email
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
                <p>Your passcode is: <strong>{passcode}</strong></p>
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
                    'temp_password': temp_password,
                    'passcode': passcode
                })

            return jsonify({'message': 'Employee added successfully. Registration email sent.'})
        except sqlite3.Error as e:
            return jsonify({'error': f'Database error: {str(e)}'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()

class GetEmployeesView(MethodView):
    def get(self):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT UserID, Name, Passcode, Email, Role, IsActive 
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

class RemoveEmployeeView(MethodView):
    def post(self):
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({'error': 'User ID is required'}), 400
                
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            cursor = conn.cursor()
            
            cursor.execute("SELECT Role FROM User WHERE UserID = ?", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
                
            if user[0] == 'manager':
                return jsonify({'error': 'Cannot remove manager accounts'}), 403
                
            cursor.execute("DELETE FROM User WHERE UserID = ?", (user_id,))
            conn.commit()
            
            return jsonify({'message': 'Employee removed successfully'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()

class ProductDetailsView(MethodView):
    def get(self, product_id):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM Product WHERE ProductID = ?", (product_id,))
            product = cursor.fetchone()
            
            if not product:
                flash('Product not found', 'error')
                return redirect(url_for('manager.all_products'))
                
            return render_template(
                'manager_productdetails.html',
                product=dict(product),
                manager_name=get_manager_name(session.get('user_id'))
            )
        except Exception as e:
            current_app.logger.error(f"Error fetching product: {str(e)}")
            flash('Error loading product', 'error')
            return redirect(url_for('manager.all_products'))
        finally:
            if 'conn' in locals():
                conn.close()

class UpdateProductView(MethodView):
    def post(self, product_id):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM Product WHERE ProductID = ?", (product_id,))
            old_product = cursor.fetchone()
            
            if not old_product:
                return jsonify({'success': False, 'message': 'Product not found'}), 404

            product_name = request.form['product_name']
            category = request.form['category']
            brand = request.form['brand']
            price = request.form['price']
            quantity = request.form['stock_quantity']

            image_filename = old_product['Image']
            if 'image' in request.files and request.files['image'].filename:
                file = request.files['image']
                if file.filename and '.' in file.filename:
                    filename = secure_filename(file.filename)
                    upload_dir = os.path.join(current_app.static_folder, 'product_image')
                    os.makedirs(upload_dir, exist_ok=True)
                    file.save(os.path.join(upload_dir, filename))
                    image_filename = filename
            elif 'remove_image' in request.form:
                if image_filename:
                    try:
                        os.remove(os.path.join(current_app.static_folder, 'product_image', image_filename))
                    except:
                        pass
                    image_filename = None

            qr_needs_update = (
                product_name != old_product['ProductName'] or
                category != old_product['Category'] or
                brand != old_product['ProductBrand'] or
                price != str(old_product['Price'])
            )

            if qr_needs_update:
                qr_data = f"Product ID: {product_id}\nName: {product_name}\nBrand: {brand}\nPrice: RM{float(price):.2f}"
                qr = qrcode.make(qr_data)
                buffered = BytesIO()
                qr.save(buffered, format="PNG")
                new_qr_base64 = base64.b64encode(buffered.getvalue()).decode()
            else:
                new_qr_base64 = old_product['QRcode']

            cursor.execute("""
                UPDATE Product SET 
                    ProductName = ?, 
                    Category = ?, 
                    ProductBrand = ?, 
                    Price = ?, 
                    StockQuantity = ?, 
                    QRcode = ?, 
                    Image = ?
                WHERE ProductID = ?
            """, (product_name, category, brand, price, quantity, new_qr_base64, image_filename, product_id))
            conn.commit()

            log_activity(
                user_id=session.get('user_id'),
                action_type='EDIT_PRODUCT',
                table_name='Product',
                record_id=product_id,
                description=f"Updated product information: {product_name}"
            )

            return jsonify({
                'success': True,
                'message': 'Product updated successfully',
                'new_qr_base64': new_qr_base64,
                'new_image_url': f"/static/product_image/{image_filename}" if image_filename else None
            })
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()

class DeleteProductView(MethodView):
    def post(self, product_id):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            cursor = conn.cursor()

            cursor.execute("SELECT ProductName, ProductBrand FROM Product WHERE ProductID = ?", (product_id,))
            result = cursor.fetchone()
            product_name = product_brand = "Unknown"

            if result:
                product_name, product_brand = result

            cursor.execute("DELETE FROM Product WHERE ProductID = ?", (product_id,))
            conn.commit()

            log_activity(
                user_id=session.get('user_id'),
                action_type='DELETE_PRODUCT',
                table_name='Product',
                record_id=product_id,
                description=f"Deleted product {product_brand} {product_name} ID: {product_id}"
            )

            return jsonify({'success': True, 'message': 'Product deleted'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()

class RestockProductView(MethodView):
    def post(self):
        try:
            data = request.get_json()
            product_id = data.get('productId')
            quantity = int(data.get('quantity', 0))

            if not product_id or quantity < 1:
                return jsonify({'success': False, 'message': 'Invalid product ID or quantity'}), 400

            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            cursor = conn.cursor()

            cursor.execute("""
                SELECT StockQuantity, ProductName, ProductBrand
                FROM Product
                WHERE ProductID = ?
            """, (product_id,))
            result = cursor.fetchone()

            if not result:
                return jsonify({'success': False, 'message': 'Product not found'}), 404

            current_stock, product_name, product_brand = result

            cursor.execute("""
                UPDATE Product
                SET StockQuantity = StockQuantity + ?
                WHERE ProductID = ?
            """, (quantity, product_id))
            conn.commit()

            cursor.execute("SELECT StockQuantity FROM Product WHERE ProductID = ?", (product_id,))
            new_quantity = cursor.fetchone()[0]

            log_activity(
                user_id=session.get('user_id'),
                action_type='UPDATE_STOCK',
                table_name='Product',
                record_id=product_id,
                description=f"Restocked {quantity} units for {product_brand} {product_name} - New total: {new_quantity}"
            )

            return jsonify({'success': True, 'newQuantity': new_quantity})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()

class ProductsAPIView(MethodView):
    def get(self):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

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

class RegisterProductView(MethodView):
    def get(self):
        return render_template('manager_register.html',
                            manager_name=get_manager_name(session.get('user_id')),
                            active_tab='Register')
    
    def post(self):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Not authenticated'}), 401

        required_fields = ['category', 'brand', 'product', 'price', 'quantity']
        if not all(field in request.form for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        try:
            category = request.form['category']
            if category == 'Other':
                category = request.form.get('other-category', category)
            brand = request.form['brand']
            product_name = request.form['product']
            price = float(request.form['price'])
            quantity = int(request.form['quantity'])

            image_filename = None
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    upload_dir = os.path.join(current_app.static_folder, 'product_image')
                    os.makedirs(upload_dir, exist_ok=True)
                    file.save(os.path.join(upload_dir, filename))
                    image_filename = filename

            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO Product 
                (ProductName, Category, Price, StockQuantity, QRcode, Image, ProductBrand)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (product_name, category, price, quantity, None, image_filename, brand))

            product_id = cursor.lastrowid

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr_data = f"Product ID: {product_id}\nName: {product_name}\nBrand: {brand}\nPrice: RM{price:.2f}"
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buffered = BytesIO()
            img.save(buffered, format="PNG")
            qr_code_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            cursor.execute("UPDATE Product SET QRcode = ? WHERE ProductID = ?", (qr_code_base64, product_id))

            cursor.execute("""
                INSERT INTO ActivityLog 
                (UserID, ActionType, TableAffected, RecordID, Description)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                'ADD_PRODUCT',
                'Product',
                product_id,
                f"Added {product_name} (Brand: {brand}, Price: RM{price:.2f})"
            ))

            conn.commit()

            return jsonify({
                'success': True,
                'product_id': product_id,
                'qr_image_url': f"data:image/png;base64,{qr_code_base64}",
                'message': 'Product registered successfully!'
            })
        except ValueError as e:
            return jsonify({'success': False, 'message': f'Invalid data: {str(e)}'}), 400
        except sqlite3.Error as e:
            conn.rollback()
            return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()

class PrintQRView(MethodView):
    def get(self, product_id):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            cursor = conn.cursor()
            cursor.execute("SELECT ProductID, ProductName, ProductBrand, QRcode FROM Product WHERE ProductID = ?", (product_id,))
            product = cursor.fetchone()
            conn.close()
            
            if not product:
                return "Product not found", 404

            product_id, product_name, product_brand, qr_base64 = product

            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            qr_img = ImageReader(BytesIO(base64.b64decode(qr_base64)))
            p.drawImage(qr_img, (width - 200) / 2, height - 300, width=200, height=200)

            p.setFont("Helvetica", 12)
            p.drawCentredString(width / 2, height - 80, f"Product ID: {product_id}")

            p.setFont("Helvetica-Bold", 14)
            p.drawCentredString(width / 2, height - 320, f"{product_brand} - {product_name}")

            p.setFont("Helvetica", 10)
            p.drawCentredString(width / 2, 30, "Scan this QR code for product details")

            p.showPage()
            p.save()

            buffer.seek(0)
            return send_file(
                buffer,
                as_attachment=True,
                download_name=f"{product_brand}_{product_name}_QR.pdf",
                mimetype='application/pdf'
            )
        except Exception as e:
            return str(e), 500

class SalesDataView(MethodView):
    def get(self):
        try:
            days = request.args.get('days')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            date_filter = ""
            params = []

            if days:
                date_filter = "WHERE t.Datetime >= DATE('now', ? || ' days')"
                params = [f'-{days}']
            elif start_date and end_date:
                date_filter = "WHERE DATE(t.Datetime) BETWEEN ? AND ?"
                params = [start_date, end_date]
            else:
                date_filter = "WHERE t.Datetime >= DATE('now', '-30 days')"

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

            period_total = sum(day['total_sales'] for day in daily_sales)
            period_transactions = sum(day['transaction_count'] for day in daily_sales)

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

class InventoryReportDataView(MethodView):
    def get(self):
        try:
            category_filter = request.args.get('category', 'all')
            stock_filter = request.args.get('stock', 'all')

            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
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

class ProductCategoriesView(MethodView):
    def get(self):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT Category FROM Product WHERE Category IS NOT NULL ORDER BY Category")
            categories = [row[0] for row in cursor.fetchall()]
            return jsonify(categories)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()

# Context Processor
@manager_bp.context_processor
def inject_manager_name():
    return {'manager_name': get_manager_name(session.get('user_id'))}

# Register Views
manager_bp.add_url_rule('/manager', view_func=DashboardView.as_view('manager'))
manager_bp.add_url_rule('/manager/dashboard', view_func=DashboardView.as_view('dashboard'))
manager_bp.add_url_rule('/manager/dashboard-data', view_func=ManagerDashboardStatsAPIView.as_view('dashboard_data'))
manager_bp.add_url_rule('/manager/api/profile', view_func=ManagerProfileAPIView.as_view('manager_profile_api'))
manager_bp.add_url_rule('/manager/api/dashboard-stats', view_func=ManagerDashboardStatsAPIView.as_view('manager_dashboard_stats'))
manager_bp.add_url_rule('/manager/all-products', view_func=AllProductsView.as_view('all_products'))
manager_bp.add_url_rule('/manager/new-transaction', view_func=NewTransactionView.as_view('new_transaction'))
manager_bp.add_url_rule('/manager/register', view_func=RegisterPageView.as_view('register_page'))
manager_bp.add_url_rule('/manager/activity-page', view_func=ActivityPageView.as_view('activity_page'))
manager_bp.add_url_rule('/manager/inventory-report', view_func=InventoryReportView.as_view('inventory_report'))
manager_bp.add_url_rule('/manager/sales-report', view_func=SalesReportView.as_view('sales_report'))
manager_bp.add_url_rule('/manager/employee', view_func=EmployeeView.as_view('employee'))
manager_bp.add_url_rule('/manager/activity-logs', view_func=ActivityLogsView.as_view('get_activity_logs'))
manager_bp.add_url_rule('/manager/get-all-users', view_func=AllUsersView.as_view('get_all_users'))
manager_bp.add_url_rule('/manager/add-employee', view_func=AddEmployeeView.as_view('add_employee'), methods=['POST'])
manager_bp.add_url_rule('/manager/get-employees', view_func=GetEmployeesView.as_view('get_employees'))
manager_bp.add_url_rule('/manager/remove-employee', view_func=RemoveEmployeeView.as_view('remove_employee'), methods=['POST'])
manager_bp.add_url_rule('/manager/product/<int:product_id>', view_func=ProductDetailsView.as_view('product_details'))
manager_bp.add_url_rule('/manager/update-product/<int:product_id>', view_func=UpdateProductView.as_view('update_product'), methods=['POST'])
manager_bp.add_url_rule('/manager/delete-product/<int:product_id>', view_func=DeleteProductView.as_view('delete_product'), methods=['POST'])
manager_bp.add_url_rule('/manager/api/products/restock', view_func=RestockProductView.as_view('restock_product_api'), methods=['POST'])
manager_bp.add_url_rule('/manager/api/products', view_func=ProductsAPIView.as_view('get_manager_products'))
manager_bp.add_url_rule('/manager/register-product', view_func=RegisterProductView.as_view('register_product'), methods=['GET', 'POST'])
manager_bp.add_url_rule('/manager/print-qr/<product_id>', view_func=PrintQRView.as_view('print_qr'))
manager_bp.add_url_rule('/manager/sales-data', view_func=SalesDataView.as_view('sales_data'))
manager_bp.add_url_rule('/manager/inventory-report-data', view_func=InventoryReportDataView.as_view('inventory_report_data'))
manager_bp.add_url_rule('/manager/api/product-categories', view_func=ProductCategoriesView.as_view('get_product_categories'))