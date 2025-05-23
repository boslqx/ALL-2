from flask import Blueprint, render_template, session, current_app, request, redirect, url_for, flash, jsonify, send_file, send_from_directory
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

admin_bp = Blueprint('admin', __name__, template_folder='../templates')


# Utility function to get admin name
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


# Redirect /admin to /admin/dashboard
@admin_bp.route('/admin/dashboard')
def dashboard():
    admin_name = get_admin_name()
    return render_template('admin_dashboard.html', admin_name=admin_name)


@admin_bp.route('/admin/allproducts')
def all_products():
    admin_name = get_admin_name()
    return render_template('admin_allproducts.html', admin_name=admin_name)


@admin_bp.route('/admin/register')
def register():
    admin_name = get_admin_name()
    return render_template('admin_register.html', admin_name=admin_name)


@admin_bp.route('/admin/activity')
def activity():
    admin_name = get_admin_name()
    return render_template('admin_activity.html', admin_name=admin_name)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route('/admin/api/dashboard-stats')
def dashboard_stats():
    try:
        conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get total products count
        cursor.execute("SELECT COUNT(*) FROM Product")
        total_products = cursor.fetchone()[0]
        
        # Get low stock items (assuming low stock = quantity < 10)
        cursor.execute("SELECT COUNT(*) FROM Product WHERE StockQuantity < 10")
        low_stock_items = cursor.fetchone()[0]
        
        # Get today's activities
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT A.Description, A.ActionType, A.Timestamp, 
                   COALESCE(U.Name, U.Username) AS UserName
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

@admin_bp.route('/register-container', methods=['POST']) 
def register_product():
    if request.method == 'POST':
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Not authenticated'}), 401

        # Validate required fields
        required_fields = ['category', 'brand', 'product', 'price', 'quantity']
        if not all(field in request.form for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        try:
            # Get form data
            category = request.form['category']
            if category == 'Other':
                category = request.form.get('other-category', category)
            brand = request.form['brand']
            product_name = request.form['product']
            price = float(request.form['price'])
            quantity = int(request.form['quantity'])

            # Handle image upload
            image_filename = None
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    upload_dir = os.path.join(current_app.static_folder, 'product_image')
                    os.makedirs(upload_dir, exist_ok=True)
                    file.save(os.path.join(upload_dir, filename))
                    image_filename = filename

            # Database operations
            db_path = os.path.join(current_app.instance_path, 'site.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Insert product
            cursor.execute("""
                INSERT INTO Product 
                (ProductName, Category, Price, StockQuantity, QRcode, Image, ProductBrand)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (product_name, category, price, quantity, None, image_filename, brand))

            product_id = cursor.lastrowid

            # Generate QR code
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

            # Update with QR code
            cursor.execute("""
                UPDATE Product SET QRcode = ? WHERE ProductID = ?
            """, (qr_code_base64, product_id))

            # Log activity
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


@admin_bp.route('/print-qr/<product_id>')
def print_qr(product_id):
    try:
        # Get product data from database
        conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
        cursor = conn.cursor()
        cursor.execute("SELECT ProductID, ProductName, ProductBrand, QRcode FROM Product WHERE ProductID = ?", (product_id,))
        product = cursor.fetchone()
        conn.close()
        
        if not product:
            return "Product not found", 404

        product_id, product_name, product_brand, qr_base64 = product

        # Create PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Add QR code image (centered)
        qr_img = ImageReader(BytesIO(base64.b64decode(qr_base64)))
        p.drawImage(qr_img, (width - 200) / 2, height - 300, width=200, height=200)

        # Add Product ID above QR
        p.setFont("Helvetica", 12)
        p.drawCentredString(width / 2, height - 80, f"Product ID: {product_id}")

        # Add Brand + Product Name
        p.setFont("Helvetica-Bold", 14)
        p.drawCentredString(width / 2, height - 320, f"{product_brand} - {product_name}")

        # Footer message
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

    
def get_product_from_db(product_id):
    return Product.query.get(product_id)
    
@admin_bp.route('/print-view/<product_id>')
def print_view(product_id):
    product = get_product_from_db(product_id)  # Implement this
    return render_template('print.html', product=product)

@admin_bp.route('/api/products')
def get_products():
    try:
        conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get filter parameters from request
        category = request.args.get('category')
        brand_sort = request.args.get('brand_sort')
        price_sort = request.args.get('price_sort')

        # Base query
        query = "SELECT ProductID, ProductName, ProductBrand, Price, StockQuantity, Image, Category FROM Product"
        params = []

        # Add category filter if specified
        if category and category != 'all':
            query += " WHERE Category = ?"
            params.append(category)

        # Add sorting
        if brand_sort == 'a-z':
            query += " ORDER BY ProductBrand ASC"
        elif brand_sort == 'z-a':
            query += " ORDER BY ProductBrand DESC"
        elif price_sort == 'low-high':
            query += " ORDER BY Price ASC"
        elif price_sort == 'high-low':
            query += " ORDER BY Price DESC"
        else:
            query += " ORDER BY ProductName ASC"  # Default sorting

        cursor.execute(query, params)
        products = [dict(row) for row in cursor.fetchall()]
        return jsonify(products)
        
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {str(e)}")
        return jsonify({"error": "Database error"}), 500
    finally:
        if conn:
            conn.close()

@admin_bp.route('/uploads/products/<filename>')
def serve_product_image(filename):
    upload_dir = os.path.join(current_app.instance_path, 'uploads', 'products')
    return send_from_directory(upload_dir, filename)

# Product Details View
@admin_bp.route('/admin/product/<int:product_id>')
def product_details(product_id):
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
            product={},  # Empty fallback
            admin_name=get_admin_name()
        )
    finally:
        if 'conn' in locals():
            conn.close()

# Update Product
@admin_bp.route('/update-product/<int:product_id>', methods=['POST'])
def update_product(product_id):
    try:
        conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Fetch old product data
        cursor.execute("SELECT * FROM Product WHERE ProductID = ?", (product_id,))
        old_product = cursor.fetchone()
        if not old_product:
            return jsonify({'success': False, 'message': 'Product not found'}), 404

        # Extract new form values
        product_name = request.form['product_name']
        category = request.form['category']
        brand = request.form['brand']
        price = request.form['price']
        quantity = request.form['stock_quantity']

        # Handle image upload or removal
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
                image_filename = None  # remove reference from DB

        # Check if QR needs update
        qr_needs_update = (
            product_name != old_product['ProductName'] or
            category != old_product['Category'] or
            brand != old_product['ProductBrand'] or
            price != str(old_product['Price'])  # compare as string to avoid float mismatch
        )

        # Generate new QR if needed
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

        # Update product
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

        # Log the product update activity
        log_activity(
            user_id=session.get('user_id'),
            action_type='EDIT_PRODUCT',
            table_name='Product',
            record_id=product_id,
            description=f"Updated product: {product_name} (Price: RM{price}, Stock: {quantity})"
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


# Delete Product
@admin_bp.route('/delete-product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    try:
        conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
        cursor = conn.cursor()
        
        # Soft delete or hard delete based on your DB design
        cursor.execute("DELETE FROM Product WHERE ProductID = ?", (product_id,))
        conn.commit()

        # Log the deletion activity
        log_activity(
            user_id=session.get('user_id'),
            action_type='DELETE_PRODUCT',
            table_name='Product',
            record_id=product_id,
            description=f"Deleted product ID {product_id}"
        )
        
        return jsonify({'success': True, 'message': 'Product deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_bp.route('/api/products/restock', methods=['POST'])
def restock_product():
    try:
        data = request.get_json()
        product_id = data.get('productId')
        quantity = int(data.get('quantity', 0))

        if not product_id or quantity < 1:
            return jsonify({'success': False, 'message': 'Invalid product ID or quantity'}), 400

        conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
        cursor = conn.cursor()

        # Make sure the product exists
        cursor.execute("SELECT StockQuantity FROM Product WHERE ProductID = ?", (product_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'success': False, 'message': 'Product not found'}), 404

        # Update stock quantity
        cursor.execute("""
            UPDATE Product
            SET StockQuantity = StockQuantity + ?
            WHERE ProductID = ?
        """, (quantity, product_id))
        conn.commit()

        # Return new quantity for confirmation
        cursor.execute("SELECT StockQuantity FROM Product WHERE ProductID = ?", (product_id,))
        new_quantity = cursor.fetchone()[0]

        # Log the restock activity
        log_activity(
            user_id=session.get('user_id'),
            action_type='UPDATE_STOCK',
            table_name='Product',
            record_id=product_id,
            description=f"Restocked {quantity} units (New total: {new_quantity})"
        )

        return jsonify({'success': True, 'newQuantity': new_quantity})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

    finally:
        if 'conn' in locals():
            conn.close()

@admin_bp.route('/admin/api/users')
def get_admin_users():
    try:
        conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Only select users with Role = 'admin'
        cursor.execute("SELECT UserID, Username, Name FROM User WHERE Role = 'admin'")
        rows = cursor.fetchall()

        users = []
        for row in rows:
            users.append({
                'UserID': row['UserID'],
                'Username': row['Username'],
                'Name': row['Name']
            })

        return jsonify(users)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        if 'conn' in locals():
            conn.close()


# Update activity logs endpoint
@admin_bp.route('/admin/activity-logs')
def admin_activity_logs():
    try:
        # Get filters
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
                COALESCE(U.Name, U.Username) AS UserName,
                A.ActionType,
                A.Description
            FROM ActivityLog A
            LEFT JOIN User U ON A.UserID = U.UserID
            WHERE 1=1
        """
        params = []
        
        # Apply filters
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
