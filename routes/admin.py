from flask import Blueprint, render_template, session, current_app, request, redirect, url_for, flash, jsonify, send_file,send_from_directory
import sqlite3, os
from werkzeug.utils import secure_filename
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from io import BytesIO
import base64
from db.models import Product

admin_bp = Blueprint('admin', __name__, template_folder='../templates')

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route('/admin')
def dashboard():
    user_id = session.get('user_id')
    admin_name = 'Admin'

    if user_id:
        try:
            db_path = os.path.join(current_app.instance_path, 'site.db')

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT Name FROM User WHERE UserID = ?", (user_id,))
            result = cursor.fetchone()

            if result:
                admin_name = f"Admin {result[0]}"

        except sqlite3.Error as e:
            print(f"Database error: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

    return render_template('admin.html', admin_name=admin_name, active_tab='dashboard')


@admin_bp.route('/register-product', methods=['POST'])
def register_product():
    if request.method == 'POST':
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Not authenticated'}), 401

        # Get form data
        category = request.form.get('category')
        if category == 'Other':
            category = request.form.get('other-category')
        brand = request.form.get('brand')
        product_name = request.form.get('product')
        price = request.form.get('price')
        quantity = request.form.get('quantity')

        # Handle image upload
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Save to static/product_image
                upload_dir = os.path.join(current_app.static_folder, 'product_image')
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, filename))
                image_filename = filename 

        try:
            db_path = os.path.join(current_app.instance_path, 'site.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Insert product without QR code first
            cursor.execute("""
                INSERT INTO Product 
                (ProductName, Category, Price, StockQuantity, QRcode, Image, ProductBrand)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (product_name, category, price, quantity, None, image_filename, brand))

            # Get Product ID
            product_id = cursor.lastrowid

            # Now generate QR code using product_id
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr_data = (
                f"Product ID: {product_id}\n"
                f"Category: {category}\n"
                f"Product: {product_name}\n"
                f"Brand: {brand}\n"
                f"Price: RM{price}\n"
                f"Stock Quantity: {quantity}"
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buffered = BytesIO()
            img.save(buffered, format="PNG")
            qr_code_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            # Update product with QR code
            cursor.execute("""
                UPDATE Product
                SET QRcode = ?
                WHERE ProductID = ?
            """, (qr_code_base64, product_id))

            # Log the activity
            cursor.execute("""
                INSERT INTO ActivityLog 
                (UserID, ActionType, TableAffected, RecordID, Description)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                'ADD_PRODUCT',
                'Product',
                product_id,
                f"Added new product: {product_name} (Brand: {brand}, Price: RM{price}, Qty: {quantity})"
            ))

            conn.commit()

            return jsonify({
                'success': True,
                'product_id': product_id,
                'qr_code': qr_code_base64,
                'qr_image_url': f"data:image/png;base64,{qr_code_base64}",
                'message': 'Product saved successfully!'
            })

        except sqlite3.Error as e:
            conn.rollback()
            return jsonify({'success': False, 'message': f'Database error: {e}'}), 500
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
        conn.row_factory = sqlite3.Row  # This allows accessing columns by name
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ProductID, ProductName, ProductBrand, 
                   Price, StockQuantity, Image 
            FROM Product
            ORDER BY ProductName
        """)
        
        products = [dict(row) for row in cursor.fetchall()]
        return jsonify(products)
        
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {str(e)}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "Server error"}), 500
    finally:
        if conn:
            conn.close()

@admin_bp.route('/uploads/products/<filename>')
def serve_product_image(filename):
    upload_dir = os.path.join(current_app.instance_path, 'uploads', 'products')
    return send_from_directory(upload_dir, filename)