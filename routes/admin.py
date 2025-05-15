from flask import Blueprint, render_template, session, current_app, request, redirect, url_for, flash, jsonify
import sqlite3, os
from werkzeug.utils import secure_filename
import qrcode
from io import BytesIO
import base64

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
                # Save file (in production you'd save to filesystem or cloud storage)
                # For demo, we'll just store the filename
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr_data = f"Product: {product_name}\nBrand: {brand}\nPrice: RM{price}"
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
            
            cursor.execute("""
                INSERT INTO Product 
                (ProductName, Category, Price, StockQuantity, QRcode, Image, ProductBrand)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (product_name, category, price, quantity, qr_code_base64, image, brand))  # Changed qr_code to qr_code_base64
            
            conn.commit()
            
            # Return success with QR code data
            return jsonify({
                'success': True,
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