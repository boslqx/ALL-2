# This file is to create database and table

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# User Table
class User(db.Model):
    __tablename__ = 'User'

    UserID = db.Column(db.Integer, primary_key=True)
    Username = db.Column(db.String(20), unique=True, nullable=False)
    Password = db.Column(db.String(20), nullable=False)
    Role = db.Column(db.String(15), nullable=False)
    Name = db.Column(db.String(50), nullable=False)
    Email = db.Column(db.String(50), unique=True, nullable=False)

    # Relationships
    transactions = db.relationship('Transaction', backref='cashier', lazy=True)

    def __repr__(self):
        return f"<User {self.Username}>"


# Product Table
class Product(db.Model):
    __tablename__ = 'Product'

    ProductID = db.Column(db.Integer, primary_key=True)  # FIXED: typo was `db.column`
    ProductName = db.Column(db.String(100), nullable=False)
    Category = db.Column(db.String(50), nullable=False)
    Price = db.Column(db.Float, nullable=False)
    StockQuantity = db.Column(db.Integer, nullable=False)
    QRcode = db.Column(db.String(255))

    # Relationships
    stock_alerts = db.relationship('StockAlert', backref='product', lazy=True)
    transaction_details = db.relationship('TransactionDetails', backref='product', lazy=True)

    def __repr__(self):
        return f"<Product {self.ProductName}>"


# Stock Alert Table
class StockAlert(db.Model):
    __tablename__ = 'StockAlert'

    StockAlertID = db.Column(db.Integer, primary_key=True)
    ProductID = db.Column(db.Integer, db.ForeignKey('Product.ProductID'), nullable=False)
    AlertType = db.Column(db.String(20), nullable=False)
    AlertStatus = db.Column(db.String(20), nullable=False)
    Timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<StockAlert {self.AlertType} for ProductID {self.ProductID}>"


# Transaction Table
class Transaction(db.Model):
    __tablename__ = 'Transaction'

    TransactionID = db.Column(db.Integer, primary_key=True)
    CashierID = db.Column(db.Integer, db.ForeignKey('User.UserID'), nullable=False)
    TotalAmount = db.Column(db.Float, nullable=False)
    Datetime = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    transaction_details = db.relationship('TransactionDetails', backref='transaction', lazy=True)

    def __repr__(self):
        return f"<Transaction ID {self.TransactionID}>"


# Transaction Details Table
class TransactionDetails(db.Model):
    __tablename__ = 'TransactionDetails'

    DetailsID = db.Column(db.Integer, primary_key=True)
    TransactionID = db.Column(db.Integer, db.ForeignKey('Transaction.TransactionID'), nullable=False)  # FIXED typo: TransacationID
    ProductID = db.Column(db.Integer, db.ForeignKey('Product.ProductID'), nullable=False)
    Quantity = db.Column(db.Integer, nullable=False)
    Price = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<TransactionDetails TID: {self.TransactionID}, PID: {self.ProductID}>"
