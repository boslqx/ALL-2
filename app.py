from flask import Flask, render_template
from db import db  # import from your db folder
from db.models import User, Product, StockAlert, Transaction, TransactionDetails
import os

# Absolute path to templates folder
template_dir = os.path.abspath('templates')

# Flask app setup
app = Flask(__name__, template_folder=template_dir)

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'  # this will create site.db in root
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize db
db.init_app(app)

# Routes
@app.route('/')
def home():
    print("Rendering index.html from:", template_dir)
    return render_template("index.html")

# Only run create_all if this script is being run directly
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # This will create all tables in site.db if they don't exist
    app.run(debug=True)
