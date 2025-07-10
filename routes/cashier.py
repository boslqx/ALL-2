from flask import Blueprint, render_template, session, current_app, request, jsonify, send_from_directory, url_for, Response
from flask.views import MethodView
import sqlite3
from datetime import datetime, timedelta
import os
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
import base64
from extensions import apply_role_protection, cashier_required


cashier_bp = Blueprint('cashier', __name__, template_folder='../templates')
apply_role_protection(cashier_bp, 'cashier')


# Database
class CashierBaseView:
    @staticmethod
    def get_db_connection():
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def get_cashier_name(user_id):
        cashier_name = 'Cashier'
        if user_id:
            try:
                conn = CashierBaseView.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT Name FROM User WHERE UserID = ?", (user_id,))
                result = cursor.fetchone()
                if result:
                    cashier_name = f"Cashier {result[0]}"
            except sqlite3.Error as e:
                print(f"Database error: {e}")
            finally:
                if 'conn' in locals():
                    conn.close()
        return cashier_name


# Dashboard Display
class DashboardView(MethodView, CashierBaseView):
    def get(self):
        user_id = session.get('user_id')
        cashier_name = self.get_cashier_name(user_id)
        return render_template(
            'cashier.html',
            cashier_name=cashier_name,
            active_tab='dashboard'
        )


# Retrieving Cashier's Data
class CashierProfileAPIView(MethodView, CashierBaseView):
    decorators = [cashier_required]
    def get(self):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT UserID as id, Name as name, Email as email, Role as role
                FROM User 
                WHERE UserID = ?
            """, (user_id,))
            
            user = cursor.fetchone()
            if not user:
                return jsonify({'error': 'Cashier not found'}), 404
                
            return jsonify(dict(user))
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if 'conn' in locals():
                conn.close()


# Show Today's Transactions & Revenue + Display Low Stock Items & Recent Transactions
class CashierDashboardStatsAPIView(MethodView, CashierBaseView):
    decorators = [cashier_required]

    def get(self):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            today = datetime.now().strftime('%Y-%m-%d')

            # Count today's transactions
            cursor.execute("""
                SELECT COUNT(*) 
                FROM "Transaction"  
                WHERE CashierID = ? AND DATE(Datetime) = ?
            """, (user_id, today))
            today_transactions = cursor.fetchone()[0]

            # Sum today's revenue
            cursor.execute("""
                SELECT COALESCE(SUM(TotalAmount), 0)
                FROM "Transaction"  
                WHERE CashierID = ? AND DATE(Datetime) = ?
            """, (user_id, today))
            today_revenue = cursor.fetchone()[0]

            # Count low stock items
            cursor.execute("SELECT COUNT(*) FROM Product WHERE StockQuantity <= 5")
            low_stock_items = cursor.fetchone()[0]

            # Recent transactions 
            cursor.execute("""
                SELECT TransactionID, Datetime, TotalAmount
                FROM "Transaction" 
                WHERE CashierID = ? AND DATE(Datetime) = ?
                ORDER BY Datetime DESC
                LIMIT 5
            """, (user_id, today))
            recent_transactions = [dict(row) for row in cursor.fetchall()]

            # Return dashboard data
            return jsonify({
                'today_transactions': today_transactions,
                'today_revenue': today_revenue,
                'low_stock_items': low_stock_items,
                'recent_transactions': recent_transactions
            })

        except Exception as e:
            current_app.logger.error(f"CashierDashboardStats Error: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500
        finally:
            if 'conn' in locals():
                conn.close()


# new_transaction.html-----------------------------------------------------------------------------
# New Transaction Page
class NewTransactionView(MethodView, CashierBaseView):
    def get(self):
        user_id = session.get('user_id')
        cashier_name = self.get_cashier_name(user_id)

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT Category FROM Product")
            categories = [row['Category'] for row in cursor.fetchall()]
        finally:
            if 'conn' in locals():
                conn.close()

        return render_template(
            'new_transaction.html',
            cashier_name=cashier_name,
            categories=categories,
            active_tab='new_transaction'
        )


# Display Product Image
class ServeProductImageView(MethodView):
    def get(self, filename):
        return send_from_directory(os.path.join(current_app.static_folder, 'product_image'), filename)
    

# Fetch Product Based on Filtering
class SearchProductsView(MethodView, CashierBaseView):
    def get(self):
        query = request.args.get('query', '').lower()
        category = request.args.get('category', '')
        stock_filter = request.args.get('stock_filter', 'all')

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            sql = "SELECT * FROM Product WHERE 1=1"
            params = []

            if query:
                sql += " AND LOWER(ProductName) LIKE ?"
                params.append(f'%{query}%')

            if category:
                sql += " AND Category = ?"
                params.append(category)

            if stock_filter == 'low':
                sql += " AND StockQuantity < 10"
            elif stock_filter == 'out':
                sql += " AND StockQuantity = 0"

            sql += " ORDER BY ProductName LIMIT 50"
            cursor.execute(sql, params)
            products = cursor.fetchall()

            products_data = []
            for product in products:
                image_url = url_for('static', filename=f'product_image/{product["Image"]}') if product["Image"] else None
                products_data.append({
                    'ProductID': product['ProductID'],
                    'ProductName': product['ProductName'],
                    'ProductBrand': product['ProductBrand'] if product['ProductBrand'] else '',
                    'Price': product['Price'],
                    'StockQuantity': product['StockQuantity'],
                    'Category': product['Category'],
                    'Image': image_url
                })

            return jsonify(products_data)
        finally:
            if 'conn' in locals():
                conn.close()


# Display Product Info
class GetProductView(MethodView, CashierBaseView):
    def get(self, product_id):
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Product WHERE ProductID = ?", (product_id,))
            product = cursor.fetchone()

            if product:
                return jsonify({
                    'id': product['ProductID'],
                    'name': product['ProductName'],
                    'price': product['Price'],
                    'stock': product['StockQuantity']
                })
            return jsonify({'error': 'Product not found'}), 404
        finally:
            if 'conn' in locals():
                conn.close()



# checkout.html--------------------------------------------------------------------
# Recording Transaction After Checkout
class CheckoutView(MethodView, CashierBaseView):
    def post(self):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not logged in'}), 401

        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'error': 'Invalid request data'}), 400

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            total_amount = sum(item['price'] * item['quantity'] for item in data['items'])
            payment_method = data.get('paymentMethod', 'Cash')

            cursor.execute("""
                INSERT INTO "Transaction"  (CashierID, Datetime, TotalAmount, PaymentMethod)
                VALUES (?, ?, ?, ?)
            """, (user_id, datetime.utcnow(), total_amount, payment_method))
            transaction_id = cursor.lastrowid

            for item in data['items']:
                cursor.execute("SELECT StockQuantity FROM Product WHERE ProductID = ?", (item['productId'],))
                product = cursor.fetchone()

                if not product:
                    conn.rollback()
                    return jsonify({'error': f'Product {item["productId"]} not found'}), 404

                if product['StockQuantity'] < item['quantity']:
                    conn.rollback()
                    return jsonify({'error': f'Not enough stock for product ID {item["productId"]}'}), 400

                cursor.execute("""
                    INSERT INTO TransactionDetails (TransactionID, ProductID, Quantity, Price)
                    VALUES (?, ?, ?, ?)
                """, (transaction_id, item['productId'], item['quantity'], item['price']))

                cursor.execute("""
                    UPDATE Product SET StockQuantity = StockQuantity - ? WHERE ProductID = ?
                """, (item['quantity'], item['productId']))

            conn.commit()

            return jsonify({
                'success': True,
                'transaction_id': transaction_id,
                'total_amount': total_amount
            })
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f'Checkout error: {str(e)}')
            return jsonify({'error': 'Failed to process transaction'}), 500
        finally:
            if 'conn' in locals():
                conn.close()


# Checkout Page
class CheckoutPageView(MethodView, CashierBaseView):
    def get(self):
        user_id = session.get('user_id')
        cashier_name = self.get_cashier_name(user_id)
        return render_template(
            'checkout.html',
            cashier_name=cashier_name,
            active_tab='new_transaction',
            cart_items=[],
            total=0
        )


# Complete Transaction
class CompleteTransactionView(MethodView, CashierBaseView):
    def post(self):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not logged in'}), 401

        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'error': 'Invalid request data'}), 400

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT Name FROM User WHERE UserID = ?", (user_id,))
            cashier = cursor.fetchone()
            cashier_name = cashier['Name'] if cashier else "Unknown"
            payment_method = data.get('paymentMethod', 'Cash')

            cursor.execute("""
                INSERT INTO "Transaction"  (CashierID, Datetime, TotalAmount, PaymentMethod)
                VALUES (?, ?, ?, ?)
            """, (user_id, datetime.utcnow(), data['totalAmount'], payment_method))
            transaction_id = cursor.lastrowid

            details = []
            for item in data['items']:
                cursor.execute("SELECT StockQuantity, ProductName FROM Product WHERE ProductID = ?", (item['productId'],))
                product = cursor.fetchone()

                if not product:
                    conn.rollback()
                    return jsonify({'error': f'Product {item["productId"]} not found'}), 404

                if product['StockQuantity'] < item['quantity']:
                    conn.rollback()
                    return jsonify({'error': f'Not enough stock for product ID {item["productId"]}'}), 400

                cursor.execute("""
                    INSERT INTO TransactionDetails (TransactionID, ProductID, Quantity, Price)
                    VALUES (?, ?, ?, ?)
                """, (transaction_id, item['productId'], item['quantity'], item['price']))

                cursor.execute("""
                    UPDATE Product SET StockQuantity = StockQuantity - ? WHERE ProductID = ?
                """, (item['quantity'], item['productId']))

                details.append({
                    'ProductID': item['productId'],
                    'ProductName': product['ProductName'],
                    'Quantity': item['quantity'],
                    'Price': item['price']
                })

            pdf_base64 = self.generate_receipt(transaction_id, details, cashier_name, data['totalAmount'], payment_method)
            pdf_binary = base64.b64decode(pdf_base64)

            cursor.execute("""
                UPDATE "Transaction" 
                SET Receipt = ?
                WHERE TransactionID = ?
            """, (pdf_binary, transaction_id))

            conn.commit()

            return jsonify({
                'success': True,
                'transactionId': transaction_id,
                'totalAmount': data['totalAmount'],
                'receiptPdf': pdf_base64
            })
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f'Transaction error: {str(e)}')
            return jsonify({'error': 'Failed to process transaction'}), 500
        finally:
            if 'conn' in locals():
                conn.close()

    # Receipt Generation
    def generate_receipt(self, transaction_id, transaction_details, cashier_name, total_amount, payment_method):
        try:
            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            # Header
            p.setFont("Helvetica-Bold", 16)
            p.drawString(1 * inch, height - 1 * inch, "Wanton Convenience Store")
            p.setFont("Helvetica", 12)
            p.drawString(1 * inch, height - 1.25 * inch, "Bukit Jambul, Penang")
            p.drawString(1 * inch, height - 1.5 * inch, "Phone: 016 750-9149")
            p.line(1 * inch, height - 1.6 * inch, width - 1 * inch, height - 1.6 * inch)

            # Transaction Info
            p.setFont("Helvetica-Bold", 14)
            p.drawString(1 * inch, height - 2 * inch, f"Transaction ID: {transaction_id}")
            p.setFont("Helvetica", 12)
            p.drawString(1 * inch, height - 2.25 * inch, f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
            p.drawString(1 * inch, height - 2.5 * inch, f"Cashier: {cashier_name}")
            p.drawString(1 * inch, height - 2.75 * inch, f"Payment Method: {payment_method}")

            # Items header
            p.line(1 * inch, height - 3 * inch, width - 1 * inch, height - 3 * inch)
            p.setFont("Helvetica-Bold", 12)
            p.drawString(1 * inch, height - 3.2 * inch, "Item")
            p.drawString(4 * inch, height - 3.2 * inch, "Qty")
            p.drawString(5 * inch, height - 3.2 * inch, "Price")
            p.drawString(6.5 * inch, height - 3.2 * inch, "Total")
            p.line(1 * inch, height - 3.3 * inch, width - 1 * inch, height - 3.3 * inch)

            # Items list
            y_position = height - 3.5 * inch
            p.setFont("Helvetica", 10)
            subtotal = 0

            for detail in transaction_details:
                item_total = detail['Quantity'] * detail['Price']
                subtotal += item_total

                p.drawString(1 * inch, y_position, detail['ProductName'])
                p.drawString(4 * inch, y_position, str(detail['Quantity']))
                p.drawString(5 * inch, y_position, f"RM{detail['Price']:.2f}")
                p.drawString(6.5 * inch, y_position, f"RM{item_total:.2f}")
                y_position -= 0.25 * inch

                if y_position < 1 * inch:
                    p.showPage()
                    y_position = height - 1 * inch

            # Total
            p.line(1 * inch, y_position - 0.1 * inch, width - 1 * inch, y_position - 0.1 * inch)
            p.setFont("Helvetica-Bold", 12)
            p.drawString(5 * inch, y_position - 0.3 * inch, "Subtotal:")
            p.drawString(6.5 * inch, y_position - 0.3 * inch, f"RM{subtotal:.2f}")

            # Footer
            p.setFont("Helvetica", 10)
            p.drawString(1 * inch, y_position - 1.5 * inch, "Thank you for shopping with us!")

            p.showPage()
            p.save()
            buffer.seek(0)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            current_app.logger.error(f'Receipt generation error: {str(e)}')
            raise


# transaction_history.html----------------------------------------------------------------------------------------------
# Fetch Data for Transaction History
class TransactionHistoryView(MethodView, CashierBaseView):
    def get(self):
        user_id = session.get('user_id')
        cashier_name = self.get_cashier_name(user_id)

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT t.TransactionID, t.Datetime, t.TotalAmount, t.PaymentMethod, u.Name as CashierName
                FROM "Transaction"  t
                JOIN User u ON t.CashierID = u.UserID
                ORDER BY t.Datetime DESC
            """)
            transactions = [dict(transaction) for transaction in cursor.fetchall()]
            
            for transaction in transactions:
                transaction['Datetime'] = datetime.strptime(transaction['Datetime'], '%Y-%m-%d %H:%M:%S.%f')

            return render_template(
                'transaction_history.html',
                cashier_name=cashier_name,
                transactions=transactions,
                active_tab='transaction_history'
            )
        finally:
            if 'conn' in locals():
                conn.close()



# Display for Transaction Details
class TransactionDetailsView(MethodView, CashierBaseView):
    def get(self, transaction_id):
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    t.TransactionID,
                    t.CashierID,
                    t.TotalAmount,
                    t.PaymentMethod,
                    t.Datetime,
                    u.Name as CashierName
                FROM "Transaction"  t
                JOIN User u ON t.CashierID = u.UserID
                WHERE t.TransactionID = ?
            """, (transaction_id,))
            transaction = cursor.fetchone()

            if not transaction:
                return jsonify({'error': 'Transaction not found'}), 404

            transaction_dict = dict(transaction)
           
            if isinstance(transaction_dict['Datetime'], str):
                try:
                    dt = datetime.strptime(transaction_dict['Datetime'], '%Y-%m-%d %H:%M:%S.%f')
                    transaction_dict['Datetime'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    pass
            elif hasattr(transaction_dict['Datetime'], 'strftime'):
                transaction_dict['Datetime'] = transaction_dict['Datetime'].strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("""
                SELECT td.*, p.ProductName, p.ProductBrand
                FROM TransactionDetails td
                JOIN Product p ON td.ProductID = p.ProductID
                WHERE td.TransactionID = ?
            """, (transaction_id,))
            details = [dict(detail) for detail in cursor.fetchall()]

            return jsonify({
                'success': True,
                'transaction': transaction_dict,
                'details': details
            })
        except Exception as e:
            current_app.logger.error(f'Error fetching transaction details: {str(e)}')
            return jsonify({'error': 'Failed to fetch transaction details'}), 500
        finally:
            if 'conn' in locals():
                conn.close()

# Fetch Receipt
class GetReceiptView(MethodView, CashierBaseView):
    def get(self, transaction_id):
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
           
            cursor.execute('SELECT Receipt FROM "Transaction"  WHERE TransactionID = ?', (transaction_id,))
            receipt_data = cursor.fetchone()
           
            if not receipt_data or not receipt_data['Receipt']:
                return "Receipt not found", 404
               
            return Response(receipt_data['Receipt'], mimetype='application/pdf')
        except Exception as e:
            current_app.logger.error(f'Error retrieving receipt: {str(e)}')
            return "Error retrieving receipt", 500
        finally:
            if 'conn' in locals():
                conn.close()


# Register all views
cashier_bp.add_url_rule('/dashboard', view_func=DashboardView.as_view('dashboard'))
cashier_bp.add_url_rule('/cashier/api/profile', view_func=CashierProfileAPIView.as_view('cashier_profile_api'))
cashier_bp.add_url_rule('/cashier/api/dashboard-stats', view_func=CashierDashboardStatsAPIView.as_view('cashier_dashboard_stats_api'))
cashier_bp.add_url_rule('/cashier/new-transaction', view_func=NewTransactionView.as_view('new_transaction'))
cashier_bp.add_url_rule('/cashier/search-products', view_func=SearchProductsView.as_view('search_products'))
cashier_bp.add_url_rule('/cashier/get-product/<int:product_id>', view_func=GetProductView.as_view('get_product'))
cashier_bp.add_url_rule('/cashier/checkout', view_func=CheckoutView.as_view('checkout'), methods=['POST'])
cashier_bp.add_url_rule('/cashier/checkout-page', view_func=CheckoutPageView.as_view('checkout_page'))
cashier_bp.add_url_rule('/cashier/complete-transaction', view_func=CompleteTransactionView.as_view('complete_transaction'), methods=['POST'])
cashier_bp.add_url_rule('/static/product_image/<filename>', view_func=ServeProductImageView.as_view('serve_product_image'))
cashier_bp.add_url_rule('/cashier/get-receipt/<int:transaction_id>', view_func=GetReceiptView.as_view('get_receipt'))
cashier_bp.add_url_rule('/cashier/transaction-history', view_func=TransactionHistoryView.as_view('transaction_history'))
cashier_bp.add_url_rule('/cashier/transaction-details/<int:transaction_id>', view_func=TransactionDetailsView.as_view('transaction_details'))