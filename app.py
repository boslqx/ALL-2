from flask import Flask, render_template
from db import db
from db.models import User, Product, StockAlert, Transaction, TransactionDetails
from routes.login import login_bp
from routes.admin import admin_bp
from routes.manager import manager_bp
from routes.cashier import cashier_bp
from routes.register import register_bp
from extensions import mail  
import os

# Path to templates folder
template_dir = os.path.abspath('templates')

# app setup
app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'your_secret_key'

# Database 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email Config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'killerpill585@gmail.com'  # Your Gmail
app.config['MAIL_PASSWORD'] = 'fsjc efmx pzqm pcfx'  # Use App Password, not regular password
app.config['MAIL_DEFAULT_SENDER'] = 'killerpill585@gmail.com'

# Initialize extensions
db.init_app(app)
mail.init_app(app) 

# Register blueprints
app.register_blueprint(login_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(manager_bp)
app.register_blueprint(cashier_bp)
app.register_blueprint(register_bp)

@app.route('/')
def home():
    return render_template("login.html")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)


