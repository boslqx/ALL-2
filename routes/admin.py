from flask import Blueprint, render_template, session, current_app, request, redirect, url_for, flash, jsonify, send_file
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
        image = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                image = filename

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr_data = f"Category: {category}\n Product: {product_name}\n Brand: {brand}\n Price: RM{price}\n Stock Quantity: {quantity}"
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # Save to database
        try:
            db_path = os.path.join(current_app.instance_path, 'site.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Insert product
            cursor.execute("""
                INSERT INTO Product 
                (ProductName, Category, Price, StockQuantity, QRcode, Image, ProductBrand)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (product_name, category, price, quantity, qr_code_base64, image, brand))

            # Get the ID of the newly inserted product
            product_id = cursor.lastrowid

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
            return jsonify({
                'success': False,
                'message': f'Database error: {e}'
            }), 500
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500
        finally:
            if 'conn' in locals():
                conn.close()

@admin_bp.route('/print-qr/<product_id>')
def print_qr(product_id):
    try:
        # Get product data from database
        conn = sqlite3.connect(os.path.join(current_app.instance_path, 'site.db'))
        cursor = conn.cursor()
        cursor.execute("SELECT ProductName, QRcode FROM Product WHERE ProductID = ?", (product_id,))
        product = cursor.fetchone()
        
        if not product:
            return "Product not found", 404
            
        # Create PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Add QR code (centered)
        qr_img = ImageReader(BytesIO(base64.b64decode(product[1])))
        p.drawImage(qr_img, (width-200)/2, height-250, width=200, height=200)
        
        # Add product name
        p.setFont("Helvetica-Bold", 16)
        p.drawCentredString(width/2, height-270, product[0])
        
        # Add footer
        p.setFont("Helvetica", 10)
        p.drawCentredString(width/2, 30, "Scan this QR code for product details")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{product[0]}_QR.pdf",
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