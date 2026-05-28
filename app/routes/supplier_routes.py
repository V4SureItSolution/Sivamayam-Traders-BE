from flask import Blueprint, request, jsonify, make_response, send_from_directory
from app import db
from app.models.supplier import Supplier, Item, SupplierReturn
from datetime import datetime
import traceback
import os
from werkzeug.utils import secure_filename
import uuid

supplier_bp = Blueprint('supplier', __name__)

# File upload configuration - Use absolute path
# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to the backend root and then into uploads folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(BASE_DIR), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Print debug information
print("=" * 60)
print("📁 FILE UPLOAD CONFIGURATION")
print(f"📁 Base directory: {BASE_DIR}")
print(f"📁 Upload folder path: {UPLOAD_FOLDER}")
print(f"📁 Upload folder absolute: {os.path.abspath(UPLOAD_FOLDER)}")
print(f"📁 Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")
print(f"📁 Current working directory: {os.getcwd()}")
print("=" * 60)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== FILE UPLOAD ROUTES ====================

@supplier_bp.route('/api/upload', methods=['POST', 'OPTIONS'])
def upload_file():
    """Upload a file and return its path"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print("=" * 50)
        print("📤 POST /api/upload called")
        
        # Check if file is present in request
        if 'file' not in request.files:
            print("❌ Error: No file part in request")
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            print("❌ Error: No selected file")
            return jsonify({'error': 'No selected file'}), 400
        
        print(f"📄 File received: {file.filename}")
        print(f"📁 File content type: {file.content_type}")
        
        # Validate file type
        if not allowed_file(file.filename):
            print(f"❌ Error: File type not allowed: {file.filename}")
            return jsonify({'error': 'File type not allowed. Allowed types: pdf, doc, docx, jpg, jpeg, png, txt'}), 400
        
        # Create secure filename and add unique identifier
        original_filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
        
        # Save file to uploads directory
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(file_path)
        
        # Verify file was saved
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print(f"✅ File saved successfully to: {file_path}")
            print(f"📊 File size: {file_size} bytes")
        else:
            print(f"❌ File was not saved properly!")
            return jsonify({'error': 'File save failed'}), 500
        
        # Return the file URL that can be stored in database
        file_url = f"/uploads/{unique_filename}"
        
        print(f"🔗 File URL: {file_url}")
        print("=" * 50)
        
        return jsonify({
            'success': True,
            'filePath': file_url,
            'fileName': original_filename,
            'fileSize': file_size,
            'message': 'File uploaded successfully'
        }), 200
        
    except Exception as e:
        print(f"❌ File upload error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@supplier_bp.route('/uploads/<filename>', methods=['GET', 'OPTIONS'])
def get_uploaded_file(filename):
    """Serve uploaded files"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print(f"📥 GET /uploads/{filename} called")
        
        # Security check to prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            print("❌ Security: Invalid filename")
            return jsonify({'error': 'Invalid filename'}), 400
        
        # Construct full path
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        abs_path = os.path.abspath(file_path)
        
        print(f"🔍 Looking for file at: {abs_path}")
        print(f"📁 Upload folder exists? {os.path.exists(UPLOAD_FOLDER)}")
        
        # Check if file exists
        if not os.path.exists(file_path):
            print(f"❌ File not found: {abs_path}")
            
            # List files in directory for debugging
            if os.path.exists(UPLOAD_FOLDER):
                files = os.listdir(UPLOAD_FOLDER)
                print(f"📋 Files in upload folder ({len(files)}):")
                for f in files[:10]:  # Show first 10 files
                    print(f"   - {f}")
            else:
                print(f"❌ Upload folder does not exist: {UPLOAD_FOLDER}")
            
            return jsonify({'error': 'File not found'}), 404
        
        print(f"✅ File found, serving: {abs_path}")
        
        # Send the file
        return send_from_directory(
            UPLOAD_FOLDER, 
            filename,
            as_attachment=False,
            download_name=filename.split('_', 1)[-1] if '_' in filename else filename
        )
        
    except Exception as e:
        print(f"❌ File serving error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@supplier_bp.route('/api/debug/uploads', methods=['GET', 'OPTIONS'])
def debug_uploads():
    """Debug endpoint to check uploads folder"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        upload_info = {
            'upload_folder_configured': UPLOAD_FOLDER,
            'upload_folder_absolute': os.path.abspath(UPLOAD_FOLDER),
            'upload_folder_exists': os.path.exists(UPLOAD_FOLDER),
            'current_working_directory': os.getcwd(),
            'base_dir': BASE_DIR,
            'allowed_extensions': list(ALLOWED_EXTENSIONS),
        }
        
        if os.path.exists(UPLOAD_FOLDER):
            files = os.listdir(UPLOAD_FOLDER)
            upload_info['file_count'] = len(files)
            
            # Get file details
            file_details = []
            for f in files[:20]:  # First 20 files
                f_path = os.path.join(UPLOAD_FOLDER, f)
                if os.path.isfile(f_path):
                    file_details.append({
                        'name': f,
                        'size': os.path.getsize(f_path),
                        'size_kb': round(os.path.getsize(f_path) / 1024, 2),
                        'modified': datetime.fromtimestamp(os.path.getmtime(f_path)).isoformat(),
                        'url': f'/uploads/{f}'
                    })
            upload_info['files'] = file_details
        
        # Check database attachments
        items_with_attachments = Item.query.filter(Item.attachment.isnot(None)).all()
        db_attachments = []
        for item in items_with_attachments:
            if item.attachment:
                filename = item.attachment.split('/')[-1] if '/' in item.attachment else item.attachment
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                db_attachments.append({
                    'item_id': item.id,
                    'item_name': item.name,
                    'attachment_url': item.attachment,
                    'filename': filename,
                    'file_exists_on_disk': os.path.exists(file_path),
                    'supplier_id': item.supplier_id
                })
        
        upload_info['database_attachments'] = db_attachments
        
        return jsonify({
            'success': True,
            'debug_info': upload_info
        }), 200
        
    except Exception as e:
        print(f"❌ Debug error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@supplier_bp.route('/api/delete-file', methods=['POST', 'OPTIONS'])
def delete_file():
    """Delete an uploaded file"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print("=" * 50)
        print("🗑️ POST /api/delete-file called")
        
        data = request.get_json()
        if not data:
            print("❌ Error: No data provided")
            return jsonify({'error': 'No data provided'}), 400
            
        file_path = data.get('filePath')
        if not file_path:
            print("❌ Error: No file path provided")
            return jsonify({'error': 'No file path provided'}), 400
        
        # Extract filename from URL path
        filename = file_path.split('/')[-1] if '/' in file_path else file_path
        full_path = os.path.join(UPLOAD_FOLDER, filename)
        abs_path = os.path.abspath(full_path)
        
        print(f"Attempting to delete file: {abs_path}")
        
        # Check if file exists and delete it
        if os.path.exists(full_path) and os.path.isfile(full_path):
            os.remove(full_path)
            print(f"✅ File deleted successfully: {abs_path}")
            return jsonify({
                'success': True,
                'message': 'File deleted successfully'
            }), 200
        else:
            print(f"❌ File not found: {abs_path}")
            return jsonify({'error': 'File not found'}), 404
            
    except Exception as e:
        print(f"❌ File delete error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# Test route to verify blueprint is working
@supplier_bp.route('/api/test', methods=['GET', 'POST', 'OPTIONS'])
def test_route():
    """Test route to verify blueprint is working"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
        
        print(f"🧪 Test route called with method: {request.method}")
        
        if request.method == 'POST':
            data = request.get_json()
            print(f"POST data: {data}")
            return jsonify({
                'success': True,
                'message': 'POST test successful',
                'received_data': data,
                'upload_folder': os.path.abspath(UPLOAD_FOLDER)
            }), 200
        else:
            return jsonify({
                'success': True,
                'message': 'GET test successful',
                'method': request.method,
                'upload_folder': os.path.abspath(UPLOAD_FOLDER)
            }), 200
    except Exception as e:
        print(f"Test route error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# Check session route
@supplier_bp.route('/api/check-session', methods=['GET', 'POST', 'OPTIONS'])
def check_session():
    """Check session endpoint"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
        
        print(f"🔐 Check session called with method: {request.method}")
        
        return jsonify({
            'authenticated': True,
            'message': 'Session check successful',
            'method': request.method
        }), 200
    except Exception as e:
        print(f"Check session error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# ==================== SUPPLIER ROUTES ====================

# Get all suppliers
@supplier_bp.route("/api/suppliers", methods=["GET", "OPTIONS"])
def get_suppliers():
    """Get all suppliers"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print("📋 GET /api/suppliers called")
        suppliers = Supplier.query.all()
        return jsonify({
            'success': True,
            'suppliers': [supplier.to_dict() for supplier in suppliers]
        }), 200
    except Exception as e:
        print(f"Get suppliers error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to fetch suppliers"}), 400

# Get single supplier
@supplier_bp.route("/api/suppliers/<int:supplier_id>", methods=["GET", "OPTIONS"])
def get_supplier(supplier_id):
    """Get single supplier by ID"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print(f"👤 GET /api/suppliers/{supplier_id} called")
        supplier = Supplier.query.get(supplier_id)
        if not supplier:
            return jsonify({"error": "Supplier not found"}), 404
        
        return jsonify({
            'success': True,
            'supplier': supplier.to_dict()
        }), 200
    except Exception as e:
        print(f"Get supplier error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to fetch supplier"}), 400

# Create new supplier
@supplier_bp.route("/api/suppliers", methods=["POST", "OPTIONS"])
def create_supplier():
    """Create a new supplier"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print("=" * 50)
        print("➕ POST /api/suppliers called")
        
        # Check content type
        if not request.is_json:
            print("Error: Request is not JSON")
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        # Parse JSON
        try:
            data = request.get_json()
            print(f"Parsed JSON data: {data}")
        except Exception as e:
            print(f"JSON parse error: {str(e)}")
            return jsonify({"error": f"Invalid JSON: {str(e)}"}), 400
        
        # Validate required fields
        if not data:
            print("Error: No data provided")
            return jsonify({"error": "No data provided"}), 400
            
        if not data.get('name'):
            print("Error: Name is required")
            return jsonify({"error": "Name is required"}), 400
            
        if not data.get('company'):
            print("Error: Company is required")
            return jsonify({"error": "Company is required"}), 400
        
        # Create new supplier
        new_supplier = Supplier(
            name=data['name'].strip(),
            company=data['company'].strip(),
            email=data.get('email', '').strip() if data.get('email') else None,
            phone=data.get('phone', '').strip() if data.get('phone') else None,
            address=data.get('address', '').strip() if data.get('address') else None
        )
        
        print(f"Creating supplier: {new_supplier.name}, {new_supplier.company}")
        
        db.session.add(new_supplier)
        db.session.commit()
        
        print(f"✅ Supplier created with ID: {new_supplier.id}")
        
        return jsonify({
            'success': True,
            'message': 'Supplier created successfully',
            'supplier': new_supplier.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Create supplier error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400

# Update supplier
@supplier_bp.route("/api/suppliers/<int:supplier_id>", methods=["PUT", "OPTIONS"])
def update_supplier(supplier_id):
    """Update an existing supplier"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print(f"✏️ PUT /api/suppliers/{supplier_id} called")
        
        supplier = Supplier.query.get(supplier_id)
        if not supplier:
            return jsonify({"error": "Supplier not found"}), 404
        
        data = request.get_json()
        print(f"Update supplier data: {data}")
        
        # Update fields
        if data.get('name'):
            supplier.name = data['name'].strip()
        if data.get('company'):
            supplier.company = data['company'].strip()
        if 'email' in data:
            supplier.email = data['email'].strip() if data['email'] else None
        if 'phone' in data:
            supplier.phone = data['phone'].strip() if data['phone'] else None
        if 'address' in data:
            supplier.address = data['address'].strip() if data['address'] else None
        
        supplier.updated_at = datetime.utcnow()
        db.session.commit()
        
        print(f"✅ Supplier {supplier_id} updated successfully")
        
        return jsonify({
            'success': True,
            'message': 'Supplier updated successfully',
            'supplier': supplier.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Update supplier error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400

# Delete supplier
@supplier_bp.route("/api/suppliers/<int:supplier_id>", methods=["DELETE", "OPTIONS"])
def delete_supplier(supplier_id):
    """Delete a supplier"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print(f"🗑️ DELETE /api/suppliers/{supplier_id} called")
        
        supplier = Supplier.query.get(supplier_id)
        if not supplier:
            return jsonify({"error": "Supplier not found"}), 404
        
        db.session.delete(supplier)
        db.session.commit()
        
        print(f"✅ Supplier {supplier_id} deleted successfully")
        
        return jsonify({
            'success': True,
            'message': 'Supplier deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Delete supplier error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400

# ==================== ITEM ROUTES ====================

# Get all items for a supplier
@supplier_bp.route("/api/suppliers/<int:supplier_id>/items", methods=["GET", "OPTIONS"])
def get_supplier_items(supplier_id):
    """Get all items for a specific supplier"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print(f"📦 GET /api/suppliers/{supplier_id}/items called")
        
        supplier = Supplier.query.get(supplier_id)
        if not supplier:
            return jsonify({"error": "Supplier not found"}), 404
        
        items = Item.query.filter_by(supplier_id=supplier_id).all()
        
        return jsonify({
            'success': True,
            'items': [item.to_dict() for item in items]
        }), 200
    except Exception as e:
        print(f"Get items error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to fetch items"}), 400

# Get single item
@supplier_bp.route("/api/items/<int:item_id>", methods=["GET", "OPTIONS"])
def get_item(item_id):
    """Get single item by ID"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print(f"🔍 GET /api/items/{item_id} called")
        
        item = Item.query.get(item_id)
        if not item:
            return jsonify({"error": "Item not found"}), 404
        
        return jsonify({
            'success': True,
            'item': item.to_dict()
        }), 200
    except Exception as e:
        print(f"Get item error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to fetch item"}), 400

# Create new item
@supplier_bp.route("/api/suppliers/<int:supplier_id>/items", methods=["POST", "OPTIONS"])
def create_item(supplier_id):
    """Create a new item for a supplier"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print("=" * 50)
        print(f"➕ POST /api/suppliers/{supplier_id}/items called")
        
        # Verify supplier exists
        supplier = Supplier.query.get(supplier_id)
        if not supplier:
            print(f"Error: Supplier {supplier_id} not found")
            return jsonify({"error": "Supplier not found"}), 404
        
        if not request.is_json:
            print("Error: Request is not JSON")
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        try:
            data = request.get_json()
            print(f"Parsed item data: {data}")
        except Exception as e:
            print(f"JSON parse error: {str(e)}")
            return jsonify({"error": f"Invalid JSON: {str(e)}"}), 400
        
        # Validate required fields
        if not data:
            print("Error: No data provided")
            return jsonify({"error": "No data provided"}), 400
            
        if not data.get('name'):
            print("Error: Name is required")
            return jsonify({"error": "Name is required"}), 400
            
        if not data.get('model'):
            print("Error: Model is required")
            return jsonify({"error": "Model is required"}), 400
            
        if data.get('buy_price') is None:
            print("Error: Buy price is required")
            return jsonify({"error": "Buy price is required"}), 400
        
        # Create new item with status, attachment, and quantity
        new_item = Item(
            name=data['name'].strip(),
            type=data.get('type', '').strip() if data.get('type') else None,
            model=data['model'].strip(),
            watts=str(data.get('watts', '')).strip() if data.get('watts') is not None else '',
            buy_price=float(data['buy_price']),
            supplier_id=supplier_id,
            status=data.get('status', 'Active'),
            attachment=data.get('attachment', None),
            quantity=int(data.get('quantity', 0))  # ✅ FIXED: Include quantity
        )
        
        print(f"Creating item: {new_item.name}, price: {new_item.buy_price}, status: {new_item.status}, quantity: {new_item.quantity}, attachment: {new_item.attachment}")
        
        db.session.add(new_item)
        db.session.commit()
        
        print(f"✅ Item created with ID: {new_item.id}")
        print("=" * 50)
        
        return jsonify({
            'success': True,
            'message': 'Item created successfully',
            'item': new_item.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Create item error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400

# Update item
@supplier_bp.route("/api/items/<int:item_id>", methods=["PUT", "OPTIONS"])
def update_item(item_id):
    """Update an existing item"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print(f"✏️ PUT /api/items/{item_id} called")
        
        item = Item.query.get(item_id)
        if not item:
            return jsonify({"error": "Item not found"}), 404
        
        data = request.get_json()
        print(f"Update item data: {data}")
        
        # Update fields
        if data.get('name'):
            item.name = data['name'].strip()
        if 'type' in data:
            item.type = data['type'].strip() if data['type'] else None
        if data.get('model'):
            item.model = data['model'].strip()
        if 'watts' in data:
            item.watts = str(data['watts']).strip() if data['watts'] else ''
        if 'buy_price' in data:
            item.buy_price = float(data['buy_price']) if data['buy_price'] else 0
        if 'status' in data:
            item.status = data['status']
        if 'attachment' in data:
            item.attachment = data['attachment']
        if 'quantity' in data:  # ✅ FIXED: Include quantity
            item.quantity = int(data['quantity']) if data['quantity'] else 0
        
        item.updated_at = datetime.utcnow()
        db.session.commit()
        
        print(f"✅ Item {item_id} updated successfully. New quantity: {item.quantity}")
        
        return jsonify({
            'success': True,
            'message': 'Item updated successfully',
            'item': item.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Update item error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400

# Delete item
@supplier_bp.route("/api/items/<int:item_id>", methods=["DELETE", "OPTIONS"])
def delete_item(item_id):
    """Delete an item"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print(f"🗑️ DELETE /api/items/{item_id} called")
        
        item = Item.query.get(item_id)
        if not item:
            return jsonify({"error": "Item not found"}), 404
        
        # Check if item has an attachment and delete it
        if item.attachment:
            try:
                filename = item.attachment.split('/')[-1] if '/' in item.attachment else item.attachment
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"📎 Attachment file deleted: {file_path}")
            except Exception as e:
                print(f"Error deleting attachment file: {str(e)}")
        
        db.session.delete(item)
        db.session.commit()
        
        print(f"✅ Item {item_id} deleted successfully")
        
        return jsonify({
            'success': True,
            'message': 'Item deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Delete item error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400

# ==================== BULK OPERATIONS ====================

# Get all suppliers with their items
@supplier_bp.route("/api/suppliers-with-items", methods=["GET", "OPTIONS"])
def get_suppliers_with_items():
    """Get all suppliers with their items"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print("📋 GET /api/suppliers-with-items called")
        
        suppliers = Supplier.query.all()
        result = []
        
        for supplier in suppliers:
            supplier_dict = supplier.to_dict()
            items = Item.query.filter_by(supplier_id=supplier.id).all()
            supplier_dict['items'] = [item.to_dict() for item in items]
            result.append(supplier_dict)
        
        return jsonify({
            'success': True,
            'suppliers': result
        }), 200
    except Exception as e:
        print(f"Get suppliers with items error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to fetch suppliers with items"}), 400

# Bulk create items
@supplier_bp.route("/api/items/bulk", methods=["POST", "OPTIONS"])
def bulk_create_items():
    """Create multiple items at once"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print("📦 POST /api/items/bulk called")
        
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        data = request.get_json()
        print(f"Bulk create data: {data}")
        
        items_data = data.get('items', [])
        supplier_id = data.get('supplier_id')
        
        if not supplier_id:
            return jsonify({"error": "supplier_id is required"}), 400
        
        # Verify supplier exists
        supplier = Supplier.query.get(supplier_id)
        if not supplier:
            return jsonify({"error": f"Supplier {supplier_id} not found"}), 404
        
        if not items_data:
            return jsonify({"error": "No items data provided"}), 400
        
        created_items = []
        errors = []
        
        for idx, item_data in enumerate(items_data):
            try:
                # Validate required fields
                if not item_data.get('name'):
                    errors.append(f"Item {idx + 1}: Name is required")
                    continue
                if not item_data.get('model'):
                    errors.append(f"Item {idx + 1}: Model is required")
                    continue
                if item_data.get('buy_price') is None:
                    errors.append(f"Item {idx + 1}: Buy price is required")
                    continue
                
                # Create item
                new_item = Item(
                    name=item_data['name'].strip(),
                    type=item_data.get('type', '').strip() if item_data.get('type') else None,
                    model=item_data['model'].strip(),
                    watts=str(item_data.get('watts', '')).strip() if item_data.get('watts') is not None else '',
                    buy_price=float(item_data['buy_price']),
                    supplier_id=supplier_id,
                    status=item_data.get('status', 'Active'),
                    attachment=item_data.get('attachment', None),
                    quantity=int(item_data.get('quantity', 0))  # ✅ FIXED: Include quantity
                )
                
                db.session.add(new_item)
                created_items.append(new_item)
                
            except Exception as e:
                errors.append(f"Item {idx + 1}: {str(e)}")
        
        if created_items:
            db.session.commit()
            print(f"✅ {len(created_items)} items created successfully")
        
        return jsonify({
            'success': len(errors) == 0,
            'message': f'Created {len(created_items)} items' + (f' with {len(errors)} errors' if errors else ''),
            'items_created': len(created_items),
            'items': [item.to_dict() for item in created_items],
            'errors': errors if errors else None
        }), 201 if created_items else 400
        
    except Exception as e:
        db.session.rollback()
        print(f"Bulk create error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400

# Bulk update items
@supplier_bp.route("/api/items/bulk-update", methods=["POST", "OPTIONS"])
def bulk_update_items():
    """Update multiple items at once"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print("📦 POST /api/items/bulk-update called")
        
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        data = request.get_json()
        print(f"Bulk update data: {data}")
        
        items_data = data.get('items', [])
        
        if not items_data:
            return jsonify({"error": "No items data provided"}), 400
        
        updated_items = []
        errors = []
        
        for item_data in items_data:
            try:
                item_id = item_data.get('id')
                if not item_id:
                    errors.append("Item ID is required for update")
                    continue
                
                item = Item.query.get(item_id)
                if not item:
                    errors.append(f"Item {item_id} not found")
                    continue
                
                # Update fields
                if 'name' in item_data:
                    item.name = item_data['name'].strip()
                if 'type' in item_data:
                    item.type = item_data['type'].strip() if item_data['type'] else None
                if 'model' in item_data:
                    item.model = item_data['model'].strip()
                if 'watts' in item_data:
                    item.watts = str(item_data['watts']).strip() if item_data['watts'] else ''
                if 'buy_price' in item_data:
                    item.buy_price = float(item_data['buy_price']) if item_data['buy_price'] else 0
                if 'status' in item_data:
                    item.status = item_data['status']
                if 'attachment' in item_data:
                    item.attachment = item_data['attachment']
                if 'quantity' in item_data:  # ✅ FIXED: Include quantity
                    item.quantity = int(item_data['quantity']) if item_data['quantity'] else 0
                
                item.updated_at = datetime.utcnow()
                updated_items.append(item)
                
            except Exception as e:
                errors.append(f"Item {item_id if 'id' in item_data else 'unknown'}: {str(e)}")
        
        if updated_items:
            db.session.commit()
            print(f"✅ {len(updated_items)} items updated successfully")
        
        return jsonify({
            'success': len(errors) == 0,
            'message': f'Updated {len(updated_items)} items' + (f' with {len(errors)} errors' if errors else ''),
            'items_updated': len(updated_items),
            'items': [item.to_dict() for item in updated_items],
            'errors': errors if errors else None
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Bulk update error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400

# Delete multiple suppliers
@supplier_bp.route("/api/suppliers/bulk-delete", methods=["POST", "OPTIONS"])
def bulk_delete_suppliers():
    """Delete multiple suppliers at once"""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response
            
        print("🗑️ POST /api/suppliers/bulk-delete called")
        
        data = request.get_json()
        print(f"Bulk delete data: {data}")
        
        supplier_ids = data.get('supplier_ids', [])
        
        if not supplier_ids:
            return jsonify({"error": "No supplier IDs provided"}), 400
        
        # Get all items for these suppliers to delete attachments
        items = Item.query.filter(Item.supplier_id.in_(supplier_ids)).all()
        
        # Delete attachment files
        for item in items:
            if item.attachment:
                try:
                    filename = item.attachment.split('/')[-1] if '/' in item.attachment else item.attachment
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    if os.path.exists(file_path) and os.path.isfile(file_path):
                        os.remove(file_path)
                        print(f"📎 Attachment file deleted: {file_path}")
                except Exception as e:
                    print(f"Error deleting attachment file: {str(e)}")
        
        # Delete suppliers
        deleted_count = Supplier.query.filter(
            Supplier.id.in_(supplier_ids)
        ).delete(synchronize_session=False)
        
        db.session.commit()
        
        print(f"✅ {deleted_count} suppliers deleted successfully")
        
        return jsonify({
            'success': True,
            'message': f'{deleted_count} suppliers deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Bulk delete error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400

# ==================== SUPPLIER RETURN ROUTES ====================

@supplier_bp.route("/api/supplier-returns", methods=["POST", "OPTIONS"])
def create_supplier_return():
    """
    Create a return record and delete the original item.
    Body JSON fields:
        item_id, item_name, model, watts, buy_price,
        supplier_id, supplier_name, company_name,
        returned_volume, is_full_return
    """
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response

        print("=" * 50)
        print("↩️  POST /api/supplier-returns called")

        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400

        data = request.get_json()
        print(f"Return data received: {data}")

        # Validate required fields
        if not data:
            return jsonify({"error": "No data provided"}), 400
        if not data.get('item_name'):
            return jsonify({"error": "item_name is required"}), 400
        if not data.get('returned_volume'):
            return jsonify({"error": "returned_volume is required"}), 400

        item_id = data.get('item_id')

        # --- Delete the original item from supplier management ---
        if item_id:
            item = Item.query.get(item_id)
            if item:
                # Delete attachment file if present
                if item.attachment:
                    try:
                        filename = item.attachment.split('/')[-1] if '/' in item.attachment else item.attachment
                        file_path = os.path.join(UPLOAD_FOLDER, filename)
                        if os.path.exists(file_path) and os.path.isfile(file_path):
                            os.remove(file_path)
                            print(f"📎 Attachment deleted: {file_path}")
                    except Exception as e:
                        print(f"Error deleting attachment: {str(e)}")
                db.session.delete(item)
                print(f"🗑️  Item {item_id} marked for deletion")
            else:
                print(f"⚠️  Item {item_id} not found — creating return record only")

        # --- Create the return record ---
        return_record = SupplierReturn(
            item_id=item_id,
            item_name=data['item_name'],
            model=data.get('model', ''),
            watts=data.get('watts', ''),
            buy_price=float(data['buy_price']) if data.get('buy_price') is not None else None,
            supplier_id=data.get('supplier_id'),
            supplier_name=data.get('supplier_name', ''),
            company_name=data.get('company_name', ''),
            returned_volume=data['returned_volume'],
            is_full_return=bool(data.get('is_full_return', False)),
        )

        db.session.add(return_record)
        db.session.commit()

        print(f"✅ Return record created with ID: {return_record.id}")
        print("=" * 50)

        return jsonify({
            'success': True,
            'message': 'Product returned successfully and added to Return Products Report.',
            'return': return_record.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"Create return error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400


@supplier_bp.route("/api/supplier-returns", methods=["GET", "OPTIONS"])
def get_supplier_returns():
    """Fetch all supplier return records, newest first."""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response

        print("📋 GET /api/supplier-returns called")

        returns = SupplierReturn.query.order_by(SupplierReturn.returned_at.desc()).all()

        return jsonify({
            'success': True,
            'returns': [r.to_dict() for r in returns]
        }), 200

    except Exception as e:
        print(f"Get returns error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to fetch return records"}), 400


@supplier_bp.route("/api/supplier-returns/<int:return_id>", methods=["DELETE", "OPTIONS"])
def delete_supplier_return(return_id):
    """Delete a single return record."""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response

        print(f"🗑️ DELETE /api/supplier-returns/{return_id} called")

        record = SupplierReturn.query.get(return_id)
        if not record:
            return jsonify({"error": "Return record not found"}), 404

        db.session.delete(record)
        db.session.commit()

        print(f"✅ Return record {return_id} deleted")

        return jsonify({
            'success': True,
            'message': 'Return record deleted successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Delete return error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400


@supplier_bp.route("/api/supplier-returns/bulk-delete", methods=["POST", "OPTIONS"])
def bulk_delete_supplier_returns():
    """Delete multiple return records at once."""
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            return response

        print("🗑️ POST /api/supplier-returns/bulk-delete called")

        data = request.get_json()
        return_ids = data.get('return_ids', [])

        if not return_ids:
            return jsonify({"error": "No return IDs provided"}), 400

        deleted_count = SupplierReturn.query.filter(
            SupplierReturn.id.in_(return_ids)
        ).delete(synchronize_session=False)

        db.session.commit()

        print(f"✅ {deleted_count} return records deleted")

        return jsonify({
            'success': True,
            'message': f'{deleted_count} return records deleted successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Bulk delete returns error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400