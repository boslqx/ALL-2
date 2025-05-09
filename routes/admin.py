from flask import Blueprint, render_template, session, current_app
import sqlite3, os

admin_bp = Blueprint('admin', __name__, template_folder='../templates')

@admin_bp.route('/admin')
def dashboard():
    user_id = session.get('user_id')
    admin_name = 'Admin'

    if user_id:
        try:
            # This will automatically point to your instance folder
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

@admin_bp.route('/admin/dashboard')
def admin_dashboard():
    return render_template('admin/dashboard.html',
                           admin_name=get_admin_name(),
                           active_tab='dashboard')

@admin_bp.route('/admin/products')
def admin_products():
    return render_template('admin/products.html',
                           admin_name=get_admin_name(),
                           active_tab='products')

@admin_bp.route('/admin/register')
def admin_register():
    return render_template('admin/register.html',
                           admin_name=get_admin_name(),
                           active_tab='register')

@admin_bp.route('/admin/activity')  # Added missing route
def admin_activity():
    return render_template('admin/activity.html',
                         admin_name=get_admin_name(),
                         active_tab='activity')

@admin_bp.route('/logout')  # Changed from login_bp
def logout():
    session.clear()
    return redirect(url_for('login.login'))