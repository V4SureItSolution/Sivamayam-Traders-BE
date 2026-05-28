from flask import Blueprint, request, jsonify, make_response
from app.models.billing import Bill, BillItem, Payment
from app.models.product import Product
from app.models.current_company import Company
from app import db
from sqlalchemy import or_, and_, func, text
from datetime import datetime, timedelta
import traceback
import random
import string
from dateutil.relativedelta import relativedelta  # Add this import for warranty calculation

billing_bp = Blueprint("billing_bp", __name__)

def generate_unique_bill_number():
    """Generate a unique random bill number"""
    while True:
        # Format: BT-YYMMDD-XXXXXXXX (BT = Brain Tech)
        now = datetime.now()
        year = str(now.year)[-2:]
        month = str(now.month).zfill(2)
        day = str(now.day).zfill(2)
        
        # Generate 8 random alphanumeric characters
        random_chars = ''.join(random.choices(
            string.ascii_uppercase + string.digits, 
            k=8
        ))
        
        bill_number = f"BT-{year}{month}{day}-{random_chars}"
        
        # Check if this number already exists
        existing = Bill.query.filter_by(bill_number=bill_number).first()
        if not existing:
            return bill_number


# ------------------ SEARCH PRODUCTS FOR BILLING ------------------
@billing_bp.route("/billing/search-products", methods=["GET"])
def search_products_for_billing():
    """Search products by name, model, or type for billing"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 2:
            return jsonify([]), 200
            
        # Search in name, model, and type, only show products with stock > 0
        products = Product.query.filter(
            or_(
                Product.name.ilike(f'%{query}%'),
                Product.model.ilike(f'%{query}%'),
                Product.type.ilike(f'%{query}%')
            )
        ).filter(Product.quantity > 0).limit(10).all()
        
        result = [{
            'id': p.id,
            'name': p.name,
            'model': p.model or '',
            'type': p.type or '',
            'sellPrice': p.sell_price,
            'quantity': p.quantity,
            'inStock': p.quantity > 0
        } for p in products]
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Search error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to search products"}), 400


# ------------------ GET PRODUCT BY BARCODE ------------------
@billing_bp.route("/billing/product/barcode/<string:barcode>", methods=["GET"])
def get_product_by_barcode(barcode):
    """Get product by barcode for quick billing"""
    try:
        if not barcode:
            return jsonify({"error": "Barcode is required"}), 400
            
        product = Product.query.filter_by(barcode=barcode).first()
        
        if not product:
            return jsonify({"error": "Product not found"}), 404
            
        if product.quantity <= 0:
            return jsonify({"error": "Product out of stock"}), 400
            
        return jsonify({
            'id': product.id,
            'name': product.name,
            'model': product.model or '',
            'type': product.type or '',
            'sellPrice': product.sell_price,
            'quantity': product.quantity
        }), 200
        
    except Exception as e:
        print(f"Barcode error: {str(e)}")
        return jsonify({"error": "Failed to fetch product"}), 400


# ------------------ GET CUSTOMER BY PHONE NUMBER ------------------
@billing_bp.route("/billing/customer/<string:phone_number>", methods=["GET"])
def get_customer_by_phone(phone_number):
    """Get customer details by phone number to check for duplicates"""
    try:
        if not phone_number:
            return jsonify({"error": "Phone number is required"}), 400
        
        # Find existing bills with this phone number (get the most recent)
        existing_customer = Bill.query.filter_by(customer_phone=phone_number).order_by(Bill.created_at.desc()).first()
        
        if existing_customer:
            return jsonify({
                'exists': True,
                'customer': {
                    'name': existing_customer.customer_name,
                    'phone': existing_customer.customer_phone,
                    'email': existing_customer.customer_email or '',
                    'gst': existing_customer.customer_gst or '',
                    'address': existing_customer.customer_address or '',
                    'type': existing_customer.customer_type or 'regular'
                }
            }), 200
        else:
            return jsonify({
                'exists': False,
                'customer': None
            }), 200
            
    except Exception as e:
        print(f"Get customer error: {str(e)}")
        return jsonify({"error": "Failed to fetch customer details"}), 400


# ------------------ GET ALL CUSTOMERS (for quick selection) ------------------
@billing_bp.route("/billing/customers", methods=["GET"])
def get_all_customers():
    """Get unique customers from bill history"""
    try:
        # Get unique customers from bills
        customers = db.session.query(
            Bill.customer_name,
            Bill.customer_phone,
            Bill.customer_email,
            Bill.customer_gst,
            Bill.customer_address,
            Bill.customer_type,
            func.count(Bill.id).label('bill_count'),
            func.max(Bill.created_at).label('last_visit')
        ).filter(Bill.customer_phone.isnot(None), Bill.customer_phone != '')\
         .group_by(Bill.customer_name, Bill.customer_phone, Bill.customer_email, 
                   Bill.customer_gst, Bill.customer_address, Bill.customer_type)\
         .order_by(func.max(Bill.created_at).desc()).limit(50).all()
        
        result = [{
            'name': c[0],
            'phone': c[1],
            'email': c[2] or '',
            'gst': c[3] or '',
            'address': c[4] or '',
            'type': c[5] or 'regular',
            'billCount': c[6],
            'lastVisit': c[7].isoformat() if c[7] else None
        } for c in customers]
        
        return jsonify({
            'success': True,
            'customers': result
        }), 200
        
    except Exception as e:
        print(f"Get customers error: {str(e)}")
        return jsonify({"error": "Failed to fetch customers"}), 400


# ------------------ CREATE NEW BILL ------------------
@billing_bp.route("/billing/bills", methods=["POST"])
def create_bill():
    """Create a new bill with items and payment"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('items'):
            return jsonify({"error": "No items in bill"}), 400
            
        if len(data['items']) == 0:
            return jsonify({"error": "Bill must have at least one item"}), 400
        
        # Create new bill instance with unique number
        bill = Bill()
        bill.bill_number = generate_unique_bill_number()
        
        # Customer Information
        bill.customer_name = data.get('customerName', 'Walk-in Customer')
        bill.customer_phone = data.get('customerPhone', '')
        bill.customer_email = data.get('customerEmail', '')
        bill.customer_gst = data.get('customerGST', '')
        bill.customer_address = data.get('customerAddress', '')
        bill.customer_type = data.get('customerType', 'regular')
        
        # Vehicle Information
        bill.vehicle_name = data.get('vehicleName', '')
        bill.vehicle_number = data.get('vehicleNumber', '')
        
        # Company Information - Fetch and store snapshot
        company_id = data.get('companyId')
        if company_id:
            company = Company.query.get(company_id)
            if company:
                bill.company_id = company.id
                bill.company_name = company.name
                bill.company_address = company.address
                bill.company_phone = company.phone
                bill.company_email = company.email
                bill.company_gst = company.gst_number
                bill.company_alternate_phone = company.alternate_phone
                bill.company_bank_name = company.bank_name
                bill.company_bank_account = company.bank_account_number
                bill.company_bank_ifsc = company.bank_ifsc
                bill.company_bank_branch = company.bank_branch
                bill.company_upi_id = company.upi_id
                # Store logo path if exists
                if hasattr(company, 'logo_path') and company.logo_path:
                    bill.company_logo = company.logo_path
        
        # Created By (User information) - Hide discount details from employee
        bill.created_by = data.get('createdBy', None)
        bill.created_by_name = data.get('createdByName', 'System')
        
        # Discount and tax settings (employee should not see discount details)
        # These will be applied but not shown to employee
        bill.discount = float(data.get('discount', 0))
        bill.discount_type = data.get('discountType', 'amount')  # 'amount' or 'percentage'
        bill.tax = float(data.get('tax', 0))
        bill.tax_type = data.get('taxType', 'percentage')
        
        # Payment information
        bill.paid_amount = float(data.get('paidAmount', 0))
        bill.payment_method = data.get('paymentMethod', 'cash')
        
        # Payment details snapshot
        bill.cash_received = float(data.get('cashReceived', 0))
        bill.payment_card_number = data.get('cardNumber', '')
        bill.payment_card_holder = data.get('cardHolderName', '')
        bill.payment_upi_id = data.get('upiId', '')
        bill.payment_transaction_id = data.get('transactionId', '')
        bill.payment_bank_name = data.get('bankName', '')
        bill.payment_cheque_number = data.get('chequeNumber', '')
        
        # Add items and update stock
        items_added = []
        for item_data in data.get('items', []):
            product = Product.query.get(item_data['productId'])
            
            if not product:
                db.session.rollback()
                return jsonify({"error": f"Product with ID {item_data['productId']} not found"}), 404
            
            quantity = int(item_data['quantity'])
            if quantity <= 0:
                db.session.rollback()
                return jsonify({"error": f"Invalid quantity for {product.name}"}), 400
                
            if product.quantity < quantity:
                db.session.rollback()
                return jsonify({"error": f"Insufficient stock for {product.name}. Available: {product.quantity}"}), 400
            
            # Calculate item total with possible discount
            item_total = product.sell_price * quantity
            
            # Create bill item with status (defaults to 'pending' from model)
            bill_item = BillItem(
                product_id=product.id,
                product_name=product.name,
                product_model=product.model or '',
                product_type=product.type or '',
                sell_price=product.sell_price,
                quantity=quantity,
                total=item_total
            )
            
            # Update product quantity
            product.quantity -= quantity
            
            bill.items.append(bill_item)
            items_added.append({
                'name': product.name,
                'quantity': quantity,
                'total': item_total,
                'status': 'pending'
            })
        
        # Calculate all totals (including discount and tax)
        bill.calculate_totals()
        
        # Save to database
        db.session.add(bill)
        db.session.commit()
        
        # Create payment record if amount paid
        if bill.paid_amount > 0:
            payment = Payment(
                bill_id=bill.id,
                payment_id=f"PAY-{bill.bill_number}",
                amount=bill.paid_amount,
                method=bill.payment_method,
                status='completed' if bill.paid_amount >= bill.total else 'partial'
            )
            db.session.add(payment)
            db.session.commit()
        
        # Prepare serialized bill object to return (authoritative server state)
        try:
            bill_serialized = {
                'id': bill.id,
                'billNumber': bill.bill_number,
                'createdAt': bill.created_at.isoformat() if hasattr(bill, 'created_at') and bill.created_at else None,
                'subtotal': round(bill.subtotal, 2) if hasattr(bill, 'subtotal') else None,
                'discount': round(bill.discount, 2),
                'discountType': bill.discount_type,
                'tax': round(bill.tax, 2),
                'taxType': bill.tax_type,
                'total': round(bill.total, 2),
                'paidAmount': round(bill.paid_amount, 2),
                'changeAmount': round(bill.change_amount, 2) if hasattr(bill, 'change_amount') else 0,
                'items': [
                    {
                        'id': it.id,
                        'productId': it.product_id,
                        'productName': it.product_name,
                        'productModel': it.product_model,
                        'sellPrice': float(it.sell_price),
                        'quantity': int(it.quantity),
                        'total': float(it.total)
                    } for it in bill.items
                ]
            }
        except Exception:
            bill_serialized = None

        # Return response - include saved bill snapshot so frontend can use server timestamps and saved item ids
        return jsonify({
            'success': True,
            'message': 'Bill created successfully',
            'billNumber': bill.bill_number,
            'billId': bill.id,
            'total': round(bill.total, 2),
            'changeAmount': round(bill.change_amount, 2) if hasattr(bill, 'change_amount') else 0,
            'items': items_added,
            'bill': bill_serialized
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Create bill error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400


# ------------------ UPDATE CUSTOMER INFORMATION ------------------
@billing_bp.route("/billing/customer/<string:phone_number>", methods=["PUT"])
def update_customer_info(phone_number):
    """Update customer information for all existing records"""
    try:
        data = request.get_json()
        
        if not phone_number:
            return jsonify({"error": "Phone number is required"}), 400
        
        # Find all bills with this phone number and update customer info
        existing_bills = Bill.query.filter_by(customer_phone=phone_number).all()
        
        if not existing_bills:
            return jsonify({"error": "Customer not found"}), 404
        
        # Update all records with new information
        for bill in existing_bills:
            if data.get('name'):
                bill.customer_name = data.get('name')
            if data.get('email'):
                bill.customer_email = data.get('email')
            if data.get('gst'):
                bill.customer_gst = data.get('gst')
            if data.get('address'):
                bill.customer_address = data.get('address')
            if data.get('type'):
                bill.customer_type = data.get('type')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Customer information updated successfully',
            'customer': {
                'name': existing_bills[0].customer_name,
                'phone': existing_bills[0].customer_phone,
                'email': existing_bills[0].customer_email,
                'gst': existing_bills[0].customer_gst,
                'address': existing_bills[0].customer_address,
                'type': existing_bills[0].customer_type
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Update customer error: {str(e)}")
        return jsonify({"error": "Failed to update customer information"}), 400


# ------------------ GET BILLS WITH PENDING ITEMS ------------------
@billing_bp.route("/billing/bills/pending-items", methods=["GET"])
def get_bills_with_pending_items():
    """Get all bills that have pending items"""
    try:
        # Find all bills that have at least one pending item
        bills = Bill.query.join(BillItem).filter(
            BillItem.item_status == 'pending'
        ).distinct(Bill.id).order_by(Bill.created_at.desc()).all()
        
        result = []
        for bill in bills:
            # Count pending items for this bill
            pending_count = BillItem.query.filter_by(
                bill_id=bill.id, 
                item_status='pending'
            ).count()
            
            result.append({
                'id': bill.id,
                'billNumber': bill.bill_number,
                'customerName': bill.customer_name,
                'customerPhone': bill.customer_phone,
                'customerType': bill.customer_type,
                'vehicleName': bill.vehicle_name,
                'vehicleNumber': bill.vehicle_number,
                'companyName': bill.company_name,
                'total': round(bill.total, 2),
                'paidAmount': round(bill.paid_amount, 2),
                'pendingItems': pending_count,
                'createdAt': bill.created_at.isoformat() if bill.created_at else None,
                'createdBy': bill.created_by,
                'createdByName': bill.created_by_name
            })
        
        return jsonify({
            'success': True,
            'bills': result
        }), 200
        
    except Exception as e:
        print(f"Get pending bills error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to fetch pending bills"}), 400


# ------------------ GET PENDING ITEMS FOR A BILL ------------------
@billing_bp.route("/billing/bills/<int:bill_id>/items/pending", methods=["GET"])
def get_pending_bill_items(bill_id):
    """Get all pending items for a specific bill"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        
        pending_items = BillItem.query.filter_by(
            bill_id=bill_id,
            item_status='pending'
        ).all()
        
        items = [{
            'id': item.id,
            'product_id': item.product_id,
            'product_name': item.product_name,
            'product_model': item.product_model,
            'product_type': item.product_type,
            'sell_price': item.sell_price,
            'quantity': item.quantity,
            'total': item.total,
            'item_status': item.item_status
        } for item in pending_items]
        
        return jsonify({
            'success': True,
            'bill_id': bill_id,
            'bill_number': bill.bill_number,
            'customer_type': bill.customer_type,
            'customer_name': bill.customer_name,
            'vehicle_name': bill.vehicle_name,
            'vehicle_number': bill.vehicle_number,
            'company_name': bill.company_name,
            'items': items
        }), 200
        
    except Exception as e:
        print(f"Get pending items error: {str(e)}")
        return jsonify({"error": "Failed to fetch pending items"}), 400


# ------------------ COMPLETE A BILL ITEM ------------------
@billing_bp.route("/billing/bills/<int:bill_id>/items/<int:item_id>/complete", methods=["POST"])
def complete_bill_item(bill_id, item_id):
    """Mark a bill item as completed (inventory already updated during bill creation)"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        item = BillItem.query.get_or_404(item_id)
        
        if item.bill_id != bill.id:
            return jsonify({"error": "Item does not belong to this bill"}), 400
        
        if item.item_status != 'pending':
            return jsonify({"error": "Item is already completed"}), 400
        
        # Update item status to completed
        item.item_status = 'completed'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item marked as completed successfully',
            'item': {
                'id': item.id,
                'status': item.item_status
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Complete item error: {str(e)}")
        return jsonify({"error": str(e)}), 400


# ------------------ COMPLETE ALL ITEMS IN A BILL ------------------
@billing_bp.route("/billing/bills/<int:bill_id>/complete-all", methods=["POST"])
def complete_all_bill_items(bill_id):
    """Mark all pending items in a bill as completed"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        
        # Get all pending items
        pending_items = BillItem.query.filter_by(
            bill_id=bill_id,
            item_status='pending'
        ).all()
        
        if not pending_items:
            return jsonify({"error": "No pending items found in this bill"}), 400
        
        completed_count = 0
        for item in pending_items:
            item.item_status = 'completed'
            completed_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully completed {completed_count} items',
            'completedCount': completed_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Complete all items error: {str(e)}")
        return jsonify({"error": str(e)}), 400


# ------------------ GET ALL BILLS (with pagination) ------------------
@billing_bp.route("/billing/bills", methods=["GET"])
def get_all_bills():
    """Get all bills with pagination and filters"""
    try:
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        customer = request.args.get('customer')
        customer_type = request.args.get('customer_type')
        vehicle_number = request.args.get('vehicle_number')
        payment_method = request.args.get('payment_method')
        payment_status = request.args.get('payment_status')
        company_id = request.args.get('company_id', type=int)
        
        # Build query
        query = Bill.query
        
        if start_date:
            query = query.filter(Bill.created_at >= datetime.fromisoformat(start_date))
        if end_date:
            query = query.filter(Bill.created_at <= datetime.fromisoformat(end_date))
        if customer:
            query = query.filter(Bill.customer_name.ilike(f'%{customer}%'))
        if customer_type:
            query = query.filter(Bill.customer_type == customer_type)
        if vehicle_number:
            query = query.filter(Bill.vehicle_number.ilike(f'%{vehicle_number}%'))
        if payment_method:
            query = query.filter(Bill.payment_method == payment_method)
        if payment_status:
            query = query.filter(Bill.payment_status == payment_status)
        if company_id:
            query = query.filter(Bill.company_id == company_id)
        
        # Order by most recent first
        query = query.order_by(Bill.created_at.desc())
        
        # Paginate
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Format response
        bills = []
        for bill in pagination.items:
            # Count pending items
            pending_count = BillItem.query.filter_by(
                bill_id=bill.id, 
                item_status='pending'
            ).count()
            
            bills.append({
                'id': bill.id,
                'billNumber': bill.bill_number,
                'customerName': bill.customer_name,
                'customerPhone': bill.customer_phone,
                'customerType': bill.customer_type,
                'customerEmail': bill.customer_email,
                'customerGST': bill.customer_gst,
                'vehicleName': bill.vehicle_name,
                'vehicleNumber': bill.vehicle_number,
                'companyName': bill.company_name,
                'companyGST': bill.company_gst,
                'subtotal': round(bill.subtotal, 2),
                'discount': round(bill.discount, 2),
                'tax': round(bill.tax, 2),
                'total': round(bill.total, 2),
                'paidAmount': round(bill.paid_amount, 2),
                'paymentMethod': bill.payment_method,
                'paymentStatus': bill.payment_status,
                'itemCount': len(bill.items),
                'pendingItems': pending_count,
                'createdAt': bill.created_at.isoformat() if bill.created_at else None,
                'createdBy': bill.created_by,
                'createdByName': bill.created_by_name
            })
        
        return jsonify({
            'bills': bills,
            'total': pagination.total,
            'pages': pagination.pages,
            'currentPage': page,
            'perPage': per_page
        }), 200
        
    except Exception as e:
        print(f"Get bills error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to fetch bills"}), 400


# ------------------ GET SINGLE BILL BY ID ------------------
@billing_bp.route("/billing/bills/<int:bill_id>", methods=["GET"])
def get_bill_by_id(bill_id):
    """Get detailed bill information by ID"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        
        # Get payment history
        payments = Payment.query.filter_by(bill_id=bill.id).all()
        
        # Get all items with their status
        items = [{
            'id': item.id,
            'product_id': item.product_id,
            'product_name': item.product_name,
            'product_model': item.product_model,
            'product_type': item.product_type,
            'sell_price': item.sell_price,
            'quantity': item.quantity,
            'total': item.total,
            'item_status': item.item_status
        } for item in bill.items]
        
        bill_dict = bill.to_dict()
        bill_dict['items'] = items
        bill_dict['payments'] = [p.to_dict() for p in payments]
        bill_dict['vehicleName'] = bill.vehicle_name
        bill_dict['vehicleNumber'] = bill.vehicle_number
        bill_dict['createdBy'] = bill.created_by
        bill_dict['createdByName'] = bill.created_by_name
        
        # Add company details to response
        bill_dict['company'] = {
            'id': bill.company_id,
            'name': bill.company_name,
            'address': bill.company_address,
            'city': bill.company_city,
            'phone': bill.company_phone,
            'email': bill.company_email,
            'gst': bill.company_gst,
            'alternatePhone': bill.company_alternate_phone,
            'bankName': bill.company_bank_name,
            'bankAccount': bill.company_bank_account,
            'bankIfsc': bill.company_bank_ifsc,
            'bankBranch': bill.company_bank_branch,
            'upiId': bill.company_upi_id
        }
        
        # Add payment details to response
        bill_dict['paymentDetails'] = {
            'cardNumber': bill.payment_card_number,
            'cardHolder': bill.payment_card_holder,
            'upiId': bill.payment_upi_id,
            'transactionId': bill.payment_transaction_id,
            'bankName': bill.payment_bank_name,
            'chequeNumber': bill.payment_cheque_number,
            'cashReceived': bill.cash_received
        }
        
        return jsonify(bill_dict), 200
        
    except Exception as e:
        print(f"Get bill error: {str(e)}")
        return jsonify({"error": "Bill not found"}), 404


# ------------------ GET BILL BY NUMBER ------------------
@billing_bp.route("/billing/bills/number/<string:bill_number>", methods=["GET"])
def get_bill_by_number(bill_number):
    """Get bill by bill number"""
    try:
        bill = Bill.query.filter_by(bill_number=bill_number).first_or_404()
        
        # Get all items with their status
        items = [{
            'id': item.id,
            'product_id': item.product_id,
            'product_name': item.product_name,
            'product_model': item.product_model,
            'product_type': item.product_type,
            'sell_price': item.sell_price,
            'quantity': item.quantity,
            'total': item.total,
            'item_status': item.item_status
        } for item in bill.items]
        
        bill_dict = bill.to_dict()
        bill_dict['items'] = items
        bill_dict['vehicleName'] = bill.vehicle_name
        bill_dict['vehicleNumber'] = bill.vehicle_number
        bill_dict['createdBy'] = bill.created_by
        bill_dict['createdByName'] = bill.created_by_name
        
        # Add company details to response
        bill_dict['company'] = {
            'id': bill.company_id,
            'name': bill.company_name,
            'address': bill.company_address,
            'city': bill.company_city,
            'phone': bill.company_phone,
            'email': bill.company_email,
            'gst': bill.company_gst,
            'alternatePhone': bill.company_alternate_phone,
            'bankName': bill.company_bank_name,
            'bankAccount': bill.company_bank_account,
            'bankIfsc': bill.company_bank_ifsc,
            'bankBranch': bill.company_bank_branch,
            'upiId': bill.company_upi_id
        }
        
        # Add payment details to response
        bill_dict['paymentDetails'] = {
            'cardNumber': bill.payment_card_number,
            'cardHolder': bill.payment_card_holder,
            'upiId': bill.payment_upi_id,
            'transactionId': bill.payment_transaction_id,
            'bankName': bill.payment_bank_name,
            'chequeNumber': bill.payment_cheque_number,
            'cashReceived': bill.cash_received
        }
        
        return jsonify(bill_dict), 200
        
    except Exception as e:
        print(f"Get bill by number error: {str(e)}")
        return jsonify({"error": "Bill not found"}), 404


# ------------------ UPDATE BILL PAYMENT ------------------
@billing_bp.route("/billing/bills/<int:bill_id>/payment", methods=["PUT"])
def update_bill_payment(bill_id):
    """Update payment information for a bill"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        data = request.get_json()
        
        # Update payment details
        bill.paid_amount = float(data.get('paidAmount', bill.paid_amount))
        bill.payment_method = data.get('paymentMethod', bill.payment_method)
        
        # Update payment details snapshot
        if 'cashReceived' in data:
            bill.cash_received = float(data.get('cashReceived', 0))
        if 'cardNumber' in data:
            bill.payment_card_number = data.get('cardNumber', '')
        if 'cardHolderName' in data:
            bill.payment_card_holder = data.get('cardHolderName', '')
        if 'upiId' in data:
            bill.payment_upi_id = data.get('upiId', '')
        if 'transactionId' in data:
            bill.payment_transaction_id = data.get('transactionId', '')
        if 'bankName' in data:
            bill.payment_bank_name = data.get('bankName', '')
        if 'chequeNumber' in data:
            bill.payment_cheque_number = data.get('chequeNumber', '')
        
        # Recalculate
        bill.calculate_totals()
        
        # Add payment record
        payment = Payment(
            bill_id=bill.id,
            payment_id=f"PAY-{bill.bill_number}-{datetime.now().strftime('%H%M%S')}",
            amount=data.get('additionalAmount', bill.paid_amount),
            method=bill.payment_method,
            status='completed',
            reference=data.get('reference', ''),
            notes=data.get('notes', '')
        )
        
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Payment updated successfully',
            'bill': bill.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Update payment error: {str(e)}")
        return jsonify({"error": str(e)}), 400


# ------------------ CANCEL/REFUND BILL ------------------
@billing_bp.route("/billing/bills/<int:bill_id>/cancel", methods=["POST"])
def cancel_bill(bill_id):
    """Cancel a bill and restore stock"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        # Read optional remarks from request
        try:
            req_data = request.get_json(silent=True) or {}
        except Exception:
            req_data = {}
        cancel_remarks = req_data.get('remarks') or req_data.get('reason') or None
        
        # Restore product quantities for items that are not completed
        for item in bill.items:
            if item.item_status != 'completed':
                product = Product.query.get(item.product_id)
                if product:
                    product.quantity += item.quantity
        
        # Update payment status to refunded and attach remarks if provided
        payments_updated = False
        for payment in bill.payments:
            try:
                payment.status = 'refunded'
                if cancel_remarks and not getattr(payment, 'notes', None):
                    payment.notes = cancel_remarks
                payments_updated = True
            except Exception:
                pass

        # If there were no payments to annotate, create a zero-amount refund record to store remarks
        if cancel_remarks and not payments_updated:
            try:
                refund_payment = Payment(
                    bill_id=bill.id,
                    payment_id=f"REFUND-{bill.bill_number}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    amount=0.0,
                    method='refund',
                    status='refunded',
                    notes=cancel_remarks
                )
                db.session.add(refund_payment)
            except Exception:
                pass

        # Mark bill items as cancelled (but keep record)
        for item in bill.items:
            try:
                item.item_status = 'cancelled'
            except Exception:
                pass

        # Update bill summary/payment status to indicate cancellation
        try:
            bill.payment_status = 'cancelled'
        except Exception:
            bill.payment_status = 'pending'

        # Optionally append suffix to bill number to indicate cancellation (safe-guard uniqueness)
        try:
            if not str(bill.bill_number).endswith('-CANCELLED'):
                bill.bill_number = f"{bill.bill_number}-CANCELLED"
        except Exception:
            pass

        # Commit all changes (do NOT delete the bill row to avoid FK integrity issues)
        db.session.commit()

        # Build a compact bill snapshot for the response
        bill_snapshot = {
            'id': bill.id,
            'billNumber': bill.bill_number,
            'paymentStatus': bill.payment_status,
            'total': round(bill.total, 2) if hasattr(bill, 'total') else None,
            'paidAmount': round(bill.paid_amount, 2) if hasattr(bill, 'paid_amount') else None,
            'createdAt': bill.created_at.isoformat() if hasattr(bill, 'created_at') and bill.created_at else None,
            'items': [
                {
                    'id': it.id,
                    'productId': it.product_id,
                    'productName': it.product_name,
                    'quantity': int(it.quantity),
                    'itemStatus': it.item_status
                } for it in bill.items
            ],
            'payments': [
                {
                    'id': p.id,
                    'paymentId': getattr(p, 'payment_id', None),
                    'amount': float(p.amount) if hasattr(p, 'amount') else None,
                    'status': getattr(p, 'status', None)
                } for p in bill.payments
            ]
        }

        return jsonify({
            'success': True,
            'message': 'Bill marked cancelled and payments refunded',
            'bill': bill_snapshot
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Cancel bill error: {str(e)}")
        return jsonify({"error": str(e)}), 400


# ------------------ GET CANCELLED BILLS ------------------
@billing_bp.route("/billing/bills/canceled", methods=["GET"])
def get_cancelled_bills():
    """Return recently cancelled bills for the UI Cancelled Bills view"""
    try:
        # Find bills marked cancelled by payment_status or by bill number suffix
        cancelled_bills = Bill.query.filter(
            or_(Bill.payment_status == 'cancelled', Bill.bill_number.ilike('%-CANCELLED'))
        ).order_by(Bill.updated_at.desc()).limit(500).all()

        result = []
        for b in cancelled_bills:
            # Try to extract a cancellation remark from any refunded payment notes
            cancel_remarks = ''
            for p in getattr(b, 'payments', []) or []:
                if getattr(p, 'status', '') == 'refunded' and getattr(p, 'notes', None):
                    cancel_remarks = p.notes
                    break

            # Build a compact items preview to match other bill endpoints
            items_preview = []
            for it in getattr(b, 'items', [])[:5]:
                try:
                    items_preview.append({
                        'id': it.id,
                        'productId': it.product_id,
                        'productName': getattr(it, 'product_name', None) or getattr(it, 'productName', None) or None,
                        'quantity': int(getattr(it, 'quantity', 0)),
                        'total': float(getattr(it, 'total', 0))
                    })
                except Exception:
                    continue

            result.append({
                'id': b.id,
                'billNumber': b.bill_number,
                'customerName': b.customer_name,
                'customerPhone': b.customer_phone,
                'total': round(b.total, 2),
                'updatedAt': b.updated_at.isoformat() if b.updated_at else None,
                'cancelRemarks': cancel_remarks,
                'items': items_preview,
                'itemCount': len(getattr(b, 'items', []) or [])
            })

        return jsonify(result), 200

    except Exception as e:
        print(f"Get cancelled bills error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': 'Failed to fetch cancelled bills'}), 500


# ------------------ GET BILLING STATISTICS ------------------
@billing_bp.route("/billing/statistics", methods=["GET"])
def get_billing_statistics():
    """Get billing statistics for dashboard"""
    try:
        # Date range
        today = datetime.now().date()
        start_of_day = datetime(today.year, today.month, today.day, 0, 0, 0)
        end_of_day = datetime(today.year, today.month, today.day, 23, 59, 59)
        
        start_of_week = today - timedelta(days=today.weekday())
        start_of_week = datetime(start_of_week.year, start_of_week.month, start_of_week.day, 0, 0, 0)
        
        start_of_month = datetime(today.year, today.month, 1, 0, 0, 0)
        
        # Today's stats
        today_stats = db.session.query(
            func.count(Bill.id).label('bill_count'),
            func.sum(Bill.total).label('total_sales'),
            func.avg(Bill.total).label('avg_bill_value')
        ).filter(Bill.created_at.between(start_of_day, end_of_day)).first()
        
        # Week's stats
        week_stats = db.session.query(
            func.count(Bill.id).label('bill_count'),
            func.sum(Bill.total).label('total_sales')
        ).filter(Bill.created_at >= start_of_week).first()
        
        # Month's stats
        month_stats = db.session.query(
            func.count(Bill.id).label('bill_count'),
            func.sum(Bill.total).label('total_sales')
        ).filter(Bill.created_at >= start_of_month).first()
        
        # Pending items count
        pending_items_count = BillItem.query.filter_by(item_status='pending').count()
        
        # Payment method distribution
        payment_methods = db.session.query(
            Bill.payment_method,
            func.count(Bill.id).label('count'),
            func.sum(Bill.total).label('total')
        ).group_by(Bill.payment_method).all()
        
        # Customer type distribution
        customer_types = db.session.query(
            Bill.customer_type,
            func.count(Bill.id).label('count'),
            func.sum(Bill.total).label('total')
        ).group_by(Bill.customer_type).all()
        
        # Recent bills
        recent_bills = Bill.query.order_by(Bill.created_at.desc()).limit(5).all()
        
        return jsonify({
            'today': {
                'bills': today_stats.bill_count or 0,
                'sales': round(today_stats.total_sales or 0, 2),
                'average': round(today_stats.avg_bill_value or 0, 2)
            },
            'thisWeek': {
                'bills': week_stats.bill_count or 0,
                'sales': round(week_stats.total_sales or 0, 2)
            },
            'thisMonth': {
                'bills': month_stats.bill_count or 0,
                'sales': round(month_stats.total_sales or 0, 2)
            },
            'pendingItems': pending_items_count,
            'paymentMethods': [{
                'method': pm[0] or 'other',
                'count': pm[1],
                'total': round(pm[2] or 0, 2)
            } for pm in payment_methods],
            'customerTypes': [{
                'type': ct[0] or 'regular',
                'count': ct[1],
                'total': round(ct[2] or 0, 2)
            } for ct in customer_types],
            'recentBills': [{
                'id': b.id,
                'billNumber': b.bill_number,
                'customerName': b.customer_name,
                'customerType': b.customer_type,
                'vehicleName': b.vehicle_name,
                'vehicleNumber': b.vehicle_number,
                'companyName': b.company_name,
                'total': round(b.total, 2),
                'createdAt': b.created_at.isoformat(),
                'createdBy': b.created_by,
                'createdByName': b.created_by_name
            } for b in recent_bills]
        }), 200
        
    except Exception as e:
        print(f"Statistics error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to fetch statistics"}), 400


# ------------------ VOID BILL ITEM ------------------
@billing_bp.route("/billing/bills/<int:bill_id>/items/<int:item_id>/void", methods=["POST"])
def void_bill_item(bill_id, item_id):
    """Void a specific item from bill and adjust stock"""
    try:
        bill = Bill.query.get_or_404(bill_id)
        item = BillItem.query.get_or_404(item_id)
        
        if item.bill_id != bill.id:
            return jsonify({"error": "Item does not belong to this bill"}), 400
        
        # Only restore stock if item is not completed
        if item.item_status != 'completed':
            product = Product.query.get(item.product_id)
            if product:
                product.quantity += item.quantity
        
        # Remove item
        db.session.delete(item)
        
        # Recalculate bill totals
        bill.calculate_totals()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item voided successfully',
            'bill': bill.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Void item error: {str(e)}")
        return jsonify({"error": str(e)}), 400


# ------------------ GET CUSTOMER TYPE SUMMARY ------------------
@billing_bp.route("/billing/customer-types/summary", methods=["GET"])
def get_customer_type_summary():
    """Get summary of bills by customer type"""
    try:
        # Date range parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Build query
        query = db.session.query(
            Bill.customer_type,
            func.count(Bill.id).label('bill_count'),
            func.sum(Bill.total).label('total_sales'),
            func.avg(Bill.total).label('avg_bill_value')
        ).group_by(Bill.customer_type)
        
        if start_date:
            query = query.filter(Bill.created_at >= datetime.fromisoformat(start_date))
        if end_date:
            query = query.filter(Bill.created_at <= datetime.fromisoformat(end_date))
        
        results = query.all()
        
        summary = [{
            'customerType': r[0] or 'regular',
            'billCount': r[1],
            'totalSales': round(r[2] or 0, 2),
            'averageBillValue': round(r[3] or 0, 2)
        } for r in results]
        
        return jsonify({
            'success': True,
            'summary': summary
        }), 200
        
    except Exception as e:
        print(f"Customer type summary error: {str(e)}")
        return jsonify({"error": "Failed to fetch customer type summary"}), 400


# ------------------ GET VEHICLE SUMMARY ------------------
@billing_bp.route("/billing/vehicles/summary", methods=["GET"])
def get_vehicle_summary():
    """Get summary of bills by vehicle number"""
    try:
        # Date range parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Build query for vehicles with bills
        query = db.session.query(
            Bill.vehicle_number,
            Bill.vehicle_name,
            func.count(Bill.id).label('bill_count'),
            func.sum(Bill.total).label('total_spent'),
            func.avg(Bill.total).label('avg_bill_value')
        ).filter(Bill.vehicle_number.isnot(None), Bill.vehicle_number != '')
        
        if start_date:
            query = query.filter(Bill.created_at >= datetime.fromisoformat(start_date))
        if end_date:
            query = query.filter(Bill.created_at <= datetime.fromisoformat(end_date))
        
        results = query.group_by(Bill.vehicle_number, Bill.vehicle_name).order_by(func.sum(Bill.total).desc()).limit(20).all()
        
        vehicles = [{
            'vehicleNumber': r[0],
            'vehicleName': r[1] or '',
            'billCount': r[2],
            'totalSpent': round(r[3] or 0, 2),
            'averageBillValue': round(r[4] or 0, 2)
        } for r in results]
        
        return jsonify({
            'success': True,
            'vehicles': vehicles
        }), 200
        
    except Exception as e:
        print(f"Vehicle summary error: {str(e)}")
        return jsonify({"error": "Failed to fetch vehicle summary"}), 400


# ------------------ GET BILLS BY VEHICLE NUMBER ------------------
@billing_bp.route("/billing/vehicles/<string:vehicle_number>/bills", methods=["GET"])
def get_bills_by_vehicle(vehicle_number):
    """Get all bills for a specific vehicle"""
    try:
        if not vehicle_number:
            return jsonify({"error": "Vehicle number is required"}), 400
        
        bills = Bill.query.filter_by(vehicle_number=vehicle_number).order_by(Bill.created_at.desc()).all()
        
        result = [{
            'id': b.id,
            'billNumber': b.bill_number,
            'customerName': b.customer_name,
            'companyName': b.company_name,
            'total': round(b.total, 2),
            'paidAmount': round(b.paid_amount, 2),
            'paymentStatus': b.payment_status,
            'createdAt': b.created_at.isoformat() if b.created_at else None
        } for b in bills]
        
        return jsonify({
            'success': True,
            'vehicleNumber': vehicle_number,
            'vehicleName': bills[0].vehicle_name if bills else '',
            'bills': result,
            'count': len(result)
        }), 200
        
    except Exception as e:
        print(f"Get bills by vehicle error: {str(e)}")
        return jsonify({"error": "Failed to fetch bills"}), 400
# ==================== WARRANTY ROUTES (Simplified) ====================

# ------------------ WARRANTY SEARCH BY BILL NUMBER ------------------
@billing_bp.route("/billing/warranty/search", methods=["GET"])
def search_warranty_by_bill():
    """Search warranty information by bill number"""
    try:
        bill_number = request.args.get('bill_number')
        
        if not bill_number:
            return jsonify({'error': 'Bill number is required'}), 400
        
        # Use raw SQL to avoid model column issues
        # First, get the bill - using dictionary parameters
        bill_query = """
            SELECT id, bill_number, customer_name, customer_phone, customer_email, 
                   created_at, total 
            FROM bills 
            WHERE bill_number = :bill_number
        """
        bill_result = db.session.execute(text(bill_query), {"bill_number": bill_number})
        bill = bill_result.fetchone()
        
        if not bill:
            return jsonify({'error': 'Bill not found'}), 404
        
        # Get bill items - using dictionary parameters
        items_query = """
            SELECT id, product_id, product_name, product_model, 
                   quantity, sell_price, total 
            FROM bill_items 
            WHERE bill_id = :bill_id
        """
        items_result = db.session.execute(text(items_query), {"bill_id": bill[0]})
        items = items_result.fetchall()
        
        warranty_items = []
        
        for item in items:
            # Get product warranty period from watts field
            product_query = """
                SELECT id, name, model, watts 
                FROM products 
                WHERE id = :product_id
            """
            product_result = db.session.execute(text(product_query), {"product_id": item[1]})
            product = product_result.fetchone()
            
            if not product:
                warranty_period_months = 12  # Default warranty
            else:
                # Get warranty period from watts field (stored in months)
                watts = product[3] if len(product) > 3 else None
                warranty_period_months = int(watts) if watts and watts > 0 else 12
            
            # Warranty start date is bill creation date
            warranty_start_date = bill[5]  # created_at column
            warranty_end_date = warranty_start_date + relativedelta(months=warranty_period_months)
            
            # Calculate warranty status
            current_date = datetime.utcnow()
            
            if current_date <= warranty_end_date:
                days_left = (warranty_end_date - current_date).days
                warranty_status = {
                    'status': 'active',
                    'days_left': days_left,
                    'message': f'Warranty active. {days_left} days remaining'
                }
            else:
                days_expired = (current_date - warranty_end_date).days
                warranty_status = {
                    'status': 'expired',
                    'days_expired': days_expired,
                    'message': f'Warranty expired {days_expired} days ago'
                }
            
            warranty_items.append({
                'productId': item[1],  # product_id
                'productName': item[2],  # product_name
                'productModel': item[3] or 'N/A',  # product_model
                'quantity': item[4],  # quantity
                'sellPrice': float(item[5]),  # sell_price
                'total': float(item[6]),  # total
                'warranty': {
                    'warrantyPeriodMonths': warranty_period_months,
                    'warrantyStartDate': warranty_start_date.isoformat() if warranty_start_date else None,
                    'warrantyEndDate': warranty_end_date.isoformat() if warranty_end_date else None,
                    'warrantyStatus': warranty_status,
                    'isActive': warranty_status['status'] == 'active'
                }
            })
        
        # Bill information
        bill_info = {
            'id': bill[0],
            'billNumber': bill[1],
            'customerName': bill[2] or 'Walk-in Customer',
            'customerPhone': bill[3] or '',
            'customerEmail': bill[4] or '',
            'billedDate': bill[5].isoformat() if bill[5] else None,
            'totalAmount': float(bill[6]) if bill[6] else 0,
            'items': warranty_items
        }
        
        return jsonify(bill_info), 200
        
    except Exception as e:
        print(f"Warranty search error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


# ------------------ CHECK WARRANTY FOR PRODUCT ------------------
@billing_bp.route("/billing/warranty/check/<int:product_id>/<int:bill_id>", methods=["GET"])
def check_product_warranty(product_id, bill_id):
    """Check warranty status for a specific product in a bill"""
    try:
        # Get bill - using dictionary parameters
        bill_query = """
            SELECT id, bill_number, created_at 
            FROM bills 
            WHERE id = :bill_id
        """
        bill_result = db.session.execute(text(bill_query), {"bill_id": bill_id})
        bill = bill_result.fetchone()
        
        if not bill:
            return jsonify({'error': 'Bill not found'}), 404
        
        # Get product warranty period from watts field
        product_query = """
            SELECT id, name, model, watts 
            FROM products 
            WHERE id = :product_id
        """
        product_result = db.session.execute(text(product_query), {"product_id": product_id})
        product = product_result.fetchone()
        
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Get warranty period from product's watts field
        watts = product[3] if len(product) > 3 else None
        warranty_period_months = int(watts) if watts and watts > 0 else 12
        
        # Warranty start date is bill creation date
        warranty_start_date = bill[2]
        warranty_end_date = warranty_start_date + relativedelta(months=warranty_period_months)
        
        # Calculate warranty status
        current_date = datetime.utcnow()
        
        if current_date <= warranty_end_date:
            days_left = (warranty_end_date - current_date).days
            warranty_status = {
                'status': 'active',
                'days_left': days_left,
                'message': f'Warranty active. {days_left} days remaining'
            }
        else:
            days_expired = (current_date - warranty_end_date).days
            warranty_status = {
                'status': 'expired',
                'days_expired': days_expired,
                'message': f'Warranty expired {days_expired} days ago'
            }
        
        return jsonify({
            'productId': product[0],
            'productName': product[1],
            'productModel': product[2] or '',
            'billNumber': bill[1],
            'billedDate': warranty_start_date.isoformat(),
            'warrantyPeriodMonths': warranty_period_months,
            'warrantyStartDate': warranty_start_date.isoformat(),
            'warrantyEndDate': warranty_end_date.isoformat(),
            'warrantyStatus': warranty_status
        }), 200
        
    except Exception as e:
        print(f"Check warranty error: {str(e)}")
        return jsonify({'error': str(e)}), 500
