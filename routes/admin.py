from flask import Blueprint, render_template, session, current_app, redirect, url_for
import sqlite3, os
from login import login_bp  # Import the login blueprint

admin_bp = Blueprint('admin', __name__, template_folder='../templates')

def get_admin_name():
    user_id = session.get('user_id')
    if not user_id:
        return 'Admin'
    
    try:
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT Name FROM User WHERE UserID = ?", (user_id,))
        result = cursor.fetchone()
        return f"Admin {result[0]}" if result else "Admin"
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return "Admin"
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