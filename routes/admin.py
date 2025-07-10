from flask import Blueprint, render_template, session, current_app, request, redirect, url_for, flash, jsonify, send_file, send_from_directory
from flask.views import MethodView
import sqlite3, os
from werkzeug.utils import secure_filename
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from io import BytesIO
import base64
from db.models import Product
from datetime import datetime
from extensions import admin_required, apply_role_protection, role_required


# Initialize blueprint and role based access
admin_bp = Blueprint('admin', __name__, template_folder='../templates')
apply_role_protection(admin_bp, 'admin')

# Utility functions
def get_admin_name():
    user_id = session.get('user_id')
    admin_name = "Admin"

    if user_id:
        try:
            db_path = os.path.join(current_app.instance_path, 'site.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT Name FROM User WHERE UserID = ?", (user_id,))
            result = cursor.fetchone()
            if result:
                admin_name = f"Admin {result[0]}"
        except:
            pass
        finally:
            if 'conn' in locals():
                conn.close()

    return admin_name

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_product_from_db(product_id):
    return Product.query.get(product_id)

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

# Admin Main
class DashboardView(MethodView):
    def get(self):
        admin_name = get_admin_name()
        return render_template('admin_dashboard.html', admin_name=admin_name)

class AllProductsView(MethodView):
    def get(self):
        admin_name = get_admin_name()
        return render_template('admin_allproducts.html', admin_name=admin_name)

class RegisterView(MethodView):
    def get(self):
        admin_name = get_admin_name()
        return render_template('admin_register.html', admin_name=admin_name)

class ActivityView(MethodView):
    def get(self):
        admin_name = get_admin_name()
        return render_template('admin_activity.html', admin_name=admin_name)

class ProfileAPIView(MethodView):
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

class DashboardStatsAPIView(MethodView):
    def get(self):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM Product")
            total_products = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM Product WHERE StockQuantity <= 5")
            low_stock_items = cursor.fetchone()[0]
            
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT A.Description, A.ActionType, A.Timestamp, 
                       COALESCE(U.Name, U.Passcode) AS Passcode
                FROM ActivityLog A
                LEFT JOIN User U ON A.UserID = U.UserID
                WHERE DATE(A.Timestamp) = ?
                ORDER BY A.Timestamp DESC
                LIMIT 5
            """, (today,))
            recent_activities = [dict(row) for row in cursor.fetchall()]
            
            return jsonify({
                'total_products': total_products,
                'low_stock_items': low_stock_items,
                'recent_activities_count': len(recent_activities),
                'recent_activities': recent_activities
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()

class RegisterProductView(MethodView):
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

            db_path = os.path.join(current_app.instance_path, 'site.db')
            conn = sqlite3.connect(db_path)
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

            cursor.execute("""
                UPDATE Product SET QRcode = ? WHERE ProductID = ?
            """, (qr_code_base64, product_id))

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

# Generate PDF
class PrintQRView(MethodView):
    decorators = [role_required('manager')]
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

class PrintView(MethodView):
    def get(self, product_id):
        product = get_product_from_db(product_id)
        return render_template('print.html', product=product)

# View Peoduct with filtering options
class ProductsAPIView(MethodView):
    decorators = [role_required('admin', 'manager')]
    def get(self):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            category = request.args.get('category')
            brand_sort = request.args.get('brand_sort')
            price_sort = request.args.get('price_sort')

            query = "SELECT ProductID, ProductName, ProductBrand, Price, StockQuantity, Image, Category FROM Product"
            params = []

            if category and category != 'all':
                query += " WHERE Category = ?"
                params.append(category)

            if brand_sort == 'a-z':
                query += " ORDER BY ProductBrand ASC"
            elif brand_sort == 'z-a':
                query += " ORDER BY ProductBrand DESC"
            elif price_sort == 'low-high':
                query += " ORDER BY Price ASC"
            elif price_sort == 'high-low':
                query += " ORDER BY Price DESC"
            else:
                query += " ORDER BY ProductName ASC"

            cursor.execute(query, params)
            products = [dict(row) for row in cursor.fetchall()]
            return jsonify(products)
            
        except sqlite3.Error as e:
            current_app.logger.error(f"Database error: {str(e)}")
            return jsonify({"error": "Database error"}), 500
        finally:
            if conn:
                conn.close()

class ProductImageView(MethodView):
    def get(self, filename):
        upload_dir = os.path.join(current_app.instance_path, 'uploads', 'products')
        return send_from_directory(upload_dir, filename)

class ProductDetailsView(MethodView):
    def get(self, product_id):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM Product 
                WHERE ProductID = ?
            """, (product_id,))
            
            product = cursor.fetchone()
            if not product:
                flash('Product not found', 'error')
                return redirect(url_for('admin.all_products'))
                
            return render_template(
                'admin_productdetails.html',
                product=dict(product),
                admin_name=get_admin_name()
            )
            
        except Exception as e:
            current_app.logger.error(f"Error fetching product: {str(e)}")
            flash('Error loading product', 'error')
            return render_template(
                'admin_productdetails.html',
                product={},
                admin_name=get_admin_name()
            )
        finally:
            if 'conn' in locals():
                conn.close()

class UpdateProductView(MethodView):
    decorators = [role_required('admin', 'manager')]
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
                    file_path = os.path.join(upload_dir, filename)
                    file.save(file_path)
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
                qr_data = (
                    f"Product ID: {product_id}\n"
                    f"Name: {product_name}\n"
                    f"Brand: {brand}\n"
                    f"Price: RM{float(price):.2f}"
                )
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
    decorators = [role_required('admin', 'manager')]
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
    decorators = [role_required('admin', 'manager')]
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

class AdminUsersAPIView(MethodView):
    def get(self):
        try:
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT UserID, Passcode, Name FROM User WHERE Role = 'admin'")
            rows = cursor.fetchall()

            users = []
            for row in rows:
                users.append({
                    'UserID': row['UserID'],
                    'Passcode': row['Passcode'],
                    'Name': row['Name']
                })

            return jsonify(users)

        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()

class ActivityLogsAPIView(MethodView):
    def get(self):
        try:
            action_filter = request.args.get('action', 'all')
            user_filter = request.args.get('user', 'all')
            date_from = request.args.get('from')
            date_to = request.args.get('to')
            
            conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT 
                    A.Timestamp,
                    U.UserID,
                    COALESCE(U.Name, U.Passcode) AS Passcode,
                    A.ActionType,
                    A.Description
                FROM ActivityLog A
                LEFT JOIN User U ON A.UserID = U.UserID
                WHERE 1=1
            """
            params = []
            
            if action_filter != 'all':
                query += " AND A.ActionType = ?"
                params.append(action_filter)
                
            if user_filter != 'all':
                query += " AND A.UserID = ?"
                params.append(user_filter)
                
            if date_from:
                query += " AND DATE(A.Timestamp) >= ?"
                params.append(date_from)
                
            if date_to:
                query += " AND DATE(A.Timestamp) <= ?"
                params.append(date_to)

            query += " ORDER BY A.Timestamp DESC LIMIT 200"
            
            cursor.execute(query, params)
            logs = [dict(row) for row in cursor.fetchall()]
            return jsonify(logs)
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()

# Register views with the blueprint
admin_bp.add_url_rule('/admin/dashboard', view_func=DashboardView.as_view('dashboard'))
admin_bp.add_url_rule('/admin/allproducts', view_func=AllProductsView.as_view('all_products'))
admin_bp.add_url_rule('/admin/register', view_func=RegisterView.as_view('register'))
admin_bp.add_url_rule('/admin/activity', view_func=ActivityView.as_view('activity'))
admin_bp.add_url_rule('/admin/api/profile', view_func=ProfileAPIView.as_view('get_profile'))
admin_bp.add_url_rule('/admin/api/dashboard-stats', view_func=DashboardStatsAPIView.as_view('dashboard_stats'))
admin_bp.add_url_rule('/register-container', view_func=RegisterProductView.as_view('register_product'), methods=['POST'])
admin_bp.add_url_rule('/print-qr/<product_id>', view_func=PrintQRView.as_view('print_qr'))
admin_bp.add_url_rule('/print-view/<product_id>', view_func=PrintView.as_view('print_view'))
admin_bp.add_url_rule('/api/products', view_func=ProductsAPIView.as_view('get_products'))
admin_bp.add_url_rule('/uploads/products/<filename>', view_func=ProductImageView.as_view('serve_product_image'))
admin_bp.add_url_rule('/admin/product/<int:product_id>', view_func=ProductDetailsView.as_view('product_details'))
admin_bp.add_url_rule('/update-product/<int:product_id>', view_func=UpdateProductView.as_view('update_product'), methods=['POST'])
admin_bp.add_url_rule('/delete-product/<int:product_id>', view_func=DeleteProductView.as_view('delete_product'), methods=['POST'])
admin_bp.add_url_rule('/api/products/restock', view_func=RestockProductView.as_view('restock_product'), methods=['POST'])
admin_bp.add_url_rule('/admin/api/users', view_func=AdminUsersAPIView.as_view('get_admin_users'))
admin_bp.add_url_rule('/admin/activity-logs', view_func=ActivityLogsAPIView.as_view('admin_activity_logs'))