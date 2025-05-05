from flask import Flask, render_template
from db import db
from db.models import User, Product, StockAlert, Transaction, TransactionDetails
from routes.login import login_bp  # Only this import
from routes.admin import admin_bp
from routes.manager import manager_bp
from routes.cashier import cashier_bp
import os

# Absolute path to templates folder
template_dir = os.path.abspath('templates')

# Flask app setup
app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'your_secret_key'  # Needed for session/flash messages

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize db
db.init_app(app)

# ✅ Register only the login blueprint for now
app.register_blueprint(login_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(manager_bp)
app.register_blueprint(cashier_bp)

@app.route('/')
def home():
    return render_template("login.html")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
