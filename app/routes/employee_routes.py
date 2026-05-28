# app/routes/employee.py
from flask import Blueprint, request, jsonify, send_from_directory, session, current_app
from app import db
from app.models.employee import Employee
from app.models.usertype import UserType
from app.models.current_company import Company  # Import Company model
from datetime import datetime
import os
import traceback
import json
from sqlalchemy import func
from werkzeug.utils import secure_filename
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import secrets  # Add this import for generating secret key

# Create blueprint
employee_bp = Blueprint('employee', __name__, url_prefix='/api')

# UPLOAD_FOLDER is retrieved from current_app.config during request handling
# but we keep a fallback for the module level if needed
UPLOAD_FOLDER = 'uploads' 

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}

# Function to ensure secret key is set
def ensure_secret_key():
    """Ensure Flask app has a secret key set for session management"""
    try:
        # Try to get the current app context
        app = current_app._get_current_object()
        if not app.secret_key:
            # Generate a random secret key
            app.config['SECRET_KEY'] = secrets.token_hex(32)
            print(f"Secret key generated for session management")
    except:
        # If no app context, we'll handle it later
        pass

# Call this when blueprint is registered
@employee_bp.record
def record_params(setup_state):
    """Called when blueprint is registered with the app"""
    app = setup_state.app
    if not app.secret_key:
        # Generate a secret key for the app
        app.config['SECRET_KEY'] = secrets.token_hex(32)
        print(f"Secret key configured for employee blueprint")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file, prefix=''):
    """Save uploaded file and return filename"""
    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        extension = original_filename.rsplit('.', 1)[1].lower()
        filename = f"{prefix}_{uuid.uuid4().hex}_{original_filename}"
        
        # Use absolute path from config if available, fallback to relative
        upload_dir = current_app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER)
        
        # Create upload directory if it doesn't exist
        os.makedirs(upload_dir, exist_ok=True)
        
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        
        return filename
    return None

def generate_employee_id():
    """Generate auto-incrementing employee ID"""
    last_employee = Employee.query.order_by(Employee.id.desc()).first()
    if last_employee and last_employee.employee_id:
        try:
            # Extract number from employee_id (e.g., EMP001 -> 1)
            num = int(last_employee.employee_id[3:])
            new_num = num + 1
            return f"EMP{new_num:03d}"
        except:
            return "EMP001"
    return "EMP001"


# ========== AUTHENTICATION ROUTES ==========

@employee_bp.route('/auth/login', methods=['POST'])
def employee_login():
    """Employee login endpoint"""
    try:
        # Ensure secret key is set
        ensure_secret_key()
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Find employee by email
        employee = Employee.query.filter_by(email=email).first()
        
        if not employee:
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Check password
        if not employee.password_hash or not check_password_hash(employee.password_hash, password):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Store user info in session
        session['user_id'] = employee.id
        session['user_email'] = employee.email
        session['user_name'] = employee.full_name
        session['user_type'] = employee.user_type
        session['company_id'] = employee.company_id
        session['company_name'] = employee.current_company
        session['logged_in'] = True
        
        # Fetch permissions (Individual override or Role fallback)
        permissions = []
        if employee.permissions:
            try:
                permissions = json.loads(employee.permissions)
            except Exception:
                permissions = []
        
        if not permissions:
            user_type_data = UserType.query.filter(func.lower(UserType.name) == func.lower(employee.user_type)).first()
            if user_type_data and user_type_data.permissions:
                try:
                    permissions = json.loads(user_type_data.permissions)
                except Exception:
                    permissions = []

        # Return user info
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': employee.id,
                'employee_id': employee.employee_id,
                'full_name': employee.full_name,
                'email': employee.email,
                'user_type': employee.user_type,
                'permissions': permissions,
                'department': employee.department,
                'designation': employee.designation,
                'current_company': employee.current_company,
                'phone_number': employee.phone_number,
                'blood_group': employee.blood_group
            }
        }), 200
        
    except Exception as e:
        print(f"Error in employee_login: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': 'Login failed'}), 500

@employee_bp.route('/auth/logout', methods=['POST'])
def employee_logout():
    """Employee logout endpoint"""
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200

@employee_bp.route('/auth/check', methods=['GET'])
def check_login():
    """Check if user is logged in"""
    if 'user_id' in session:
        # Fetch permissions
        employee = Employee.query.get(session.get('user_id'))
        permissions = []
        if employee and employee.permissions:
            try:
                permissions = json.loads(employee.permissions)
            except Exception:
                permissions = []
        
        if not permissions:
            user_type_name = session.get('user_type')
            user_type_data = UserType.query.filter(func.lower(UserType.name) == func.lower(user_type_name)).first() if user_type_name else None
            if user_type_data and user_type_data.permissions:
                try:
                    permissions = json.loads(user_type_data.permissions)
                except Exception:
                    permissions = []

        return jsonify({
            'logged_in': True,
            'user': {
                'id': session.get('user_id'),
                'email': session.get('user_email'),
                'full_name': session.get('user_name'),
                'user_type': user_type_name,
                'permissions': permissions,
                'company_name': session.get('company_name')
            }
        }), 200
    else:
        return jsonify({'logged_in': False}), 200

@employee_bp.route('/auth/me', methods=['GET'])
def get_current_user():
    """Get current logged in user info"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        employee = Employee.query.get(session['user_id'])
        if not employee:
            session.clear()
            return jsonify({'error': 'User not found'}), 404
        
        # Fetch permissions (Individual override or Role fallback)
        permissions = []
        if employee.permissions:
            try:
                permissions = json.loads(employee.permissions)
            except Exception:
                permissions = []
        
        if not permissions:
            user_type_data = UserType.query.filter(func.lower(UserType.name) == func.lower(employee.user_type)).first()
            if user_type_data and user_type_data.permissions:
                try:
                    permissions = json.loads(user_type_data.permissions)
                except Exception:
                    permissions = []

        return jsonify({
            'user': {
                'id': employee.id,
                'employee_id': employee.employee_id,
                'full_name': employee.full_name,
                'email': employee.email,
                'user_type': employee.user_type,
                'permissions': permissions,
                'department': employee.department,
                'designation': employee.designation,
                'current_company': employee.current_company,
                'phone_number': employee.phone_number,
                'blood_group': employee.blood_group
            }
        }), 200
    except Exception as e:
        print(f"Error in get_current_user: {str(e)}")
        return jsonify({'error': 'Failed to get user info'}), 500

# ========== EMPLOYEE CRUD ROUTES ==========

@employee_bp.route('/employees', methods=['GET'])
def get_employees():
    """Get all employees"""
    try:
        # Optional filter by user_type
        user_type = request.args.get('user_type')
        
        if user_type:
            employees = Employee.query.filter_by(user_type=user_type).order_by(Employee.created_at.desc()).all()
        else:
            employees = Employee.query.order_by(Employee.created_at.desc()).all()
            
        return jsonify([employee.to_dict() for employee in employees]), 200
    except Exception as e:
        print(f"Error in get_employees: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': 'Failed to fetch employees'}), 500

@employee_bp.route('/employees/<int:id>', methods=['GET'])
def get_employee(id):
    """Get a single employee by ID"""
    try:
        employee = Employee.query.get(id)
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        return jsonify(employee.to_dict()), 200
    except Exception as e:
        print(f"Error in get_employee: {str(e)}")
        return jsonify({'error': 'Failed to fetch employee'}), 500

@employee_bp.route('/companies/list', methods=['GET'])
def get_companies_list():
    """Get list of all companies for dropdown"""
    try:
        companies = Company.query.filter_by(is_active=True).order_by(Company.name).all()
        companies_list = [{'id': company.id, 'name': company.name} for company in companies]
        return jsonify(companies_list), 200
    except Exception as e:
        print(f"Error in get_companies_list: {str(e)}")
        return jsonify({'error': 'Failed to fetch companies'}), 500

@employee_bp.route('/employees', methods=['POST'])
def create_employee():
    """Create a new employee"""
    try:
        # Auto-generate employee ID
        employee_id = generate_employee_id()
        
        # Check if email exists
        email = request.form.get('email')
        if not email:
            return jsonify({'error': 'Email is required'}), 400
            
        existing_email = Employee.query.filter_by(email=email).first()
        if existing_email:
            return jsonify({'error': 'Email already exists'}), 400
        
        # Get user_type
        user_type = request.form.get('user_type', 'employee')
        
        # Handle date of joining
        date_of_joining = None
        if request.form.get('date_of_joining'):
            try:
                date_of_joining = datetime.strptime(
                    request.form.get('date_of_joining'), '%Y-%m-%d'
                ).date()
            except:
                pass
        
        # Handle company
        current_company = request.form.get('current_company')
        company_id = request.form.get('company_id')
        
        # Validate company if company_id is provided
        if company_id:
            company = Company.query.get(company_id)
            if not company:
                return jsonify({'error': 'Invalid company selected'}), 400
            current_company = company.name
        
        # Handle file uploads
        aadhar_file = request.files.get('aadhar_attachment')
        pan_file = request.files.get('pan_attachment')
        
        aadhar_filename = None
        pan_filename = None
        
        if aadhar_file and aadhar_file.filename:
            aadhar_filename = save_file(aadhar_file, f"aadhar_{employee_id}")
        
        if pan_file and pan_file.filename:
            pan_filename = save_file(pan_file, f"pan_{employee_id}")
        
        # Hash password if provided
        password = request.form.get('password')
        password_hash = generate_password_hash(password) if password else None
        
        # Create employee
        employee = Employee(
            employee_id=employee_id,
            full_name=request.form.get('full_name'),
            email=email,
            password_hash=password_hash,
            phone_number=request.form.get('phone_number'),
            department=request.form.get('department'),
            designation=request.form.get('designation'),
            date_of_joining=date_of_joining,
            current_company=current_company,
            company_id=company_id if company_id else None,
            user_type=user_type,
            aadhar_card_number=request.form.get('aadhar_card_number'),
            pan_card_number=request.form.get('pan_card_number'),
            address=request.form.get('address'),
            emergency_contact=request.form.get('emergency_contact'),
            blood_group=request.form.get('blood_group'),
            marital_status=request.form.get('marital_status'),
            basic_salary=float(request.form.get('basic_salary', 0) or 0),
            aadhar_attachment=aadhar_filename,
            pan_attachment=pan_filename
        )
        
        db.session.add(employee)
        db.session.commit()
        
        # Return employee without password hash
        employee_dict = employee.to_dict()
        return jsonify(employee_dict), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_employee: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': 'Failed to create employee'}), 500

@employee_bp.route('/employees/<int:id>', methods=['PUT'])
def update_employee(id):
    """Update an existing employee"""
    try:
        employee = Employee.query.get(id)
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        
        # Check if email exists for other employee
        email = request.form.get('email')
        if email and email != employee.email:
            existing_email = Employee.query.filter_by(email=email).first()
            if existing_email:
                return jsonify({'error': 'Email already exists'}), 400
        
        # Update user_type if provided
        user_type = request.form.get('user_type')
        if user_type:
            employee.user_type = user_type
        
        # Handle date of joining
        if request.form.get('date_of_joining'):
            try:
                date_of_joining = datetime.strptime(
                    request.form.get('date_of_joining'), '%Y-%m-%d'
                ).date()
                employee.date_of_joining = date_of_joining
            except:
                pass
        
        # Handle company
        current_company = request.form.get('current_company')
        company_id = request.form.get('company_id')
        
        if company_id:
            company = Company.query.get(company_id)
            if not company:
                return jsonify({'error': 'Invalid company selected'}), 400
            employee.current_company = company.name
            employee.company_id = company_id
        elif current_company:
            employee.current_company = current_company
            employee.company_id = None
        else:
            employee.current_company = None
            employee.company_id = None
        
        # Handle file uploads
        aadhar_file = request.files.get('aadhar_attachment')
        pan_file = request.files.get('pan_attachment')
        
        # Delete old files if new ones are uploaded
        if aadhar_file and aadhar_file.filename:
            if employee.aadhar_attachment:
                old_file_path = os.path.join(UPLOAD_FOLDER, employee.aadhar_attachment)
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
            aadhar_filename = save_file(aadhar_file, f"aadhar_{employee.employee_id}")
            employee.aadhar_attachment = aadhar_filename
        
        if pan_file and pan_file.filename:
            if employee.pan_attachment:
                old_file_path = os.path.join(UPLOAD_FOLDER, employee.pan_attachment)
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
            pan_filename = save_file(pan_file, f"pan_{employee.employee_id}")
            employee.pan_attachment = pan_filename
        
        # Update password if provided
        password = request.form.get('password')
        if password and password.strip():
            employee.password_hash = generate_password_hash(password)
        
        # Update fields
        if request.form.get('full_name'):
            employee.full_name = request.form.get('full_name')
        if email:
            employee.email = email
        if request.form.get('phone_number'):
            employee.phone_number = request.form.get('phone_number')
        if request.form.get('department'):
            employee.department = request.form.get('department')
        if request.form.get('designation'):
            employee.designation = request.form.get('designation')
        if request.form.get('aadhar_card_number'):
            employee.aadhar_card_number = request.form.get('aadhar_card_number')
        if request.form.get('pan_card_number'):
            employee.pan_card_number = request.form.get('pan_card_number')
        if request.form.get('address'):
            employee.address = request.form.get('address')
        if request.form.get('emergency_contact'):
            employee.emergency_contact = request.form.get('emergency_contact')
        if request.form.get('blood_group'):
            employee.blood_group = request.form.get('blood_group')
        if request.form.get('marital_status'):
            employee.marital_status = request.form.get('marital_status')
        if request.form.get('basic_salary') is not None:
            try:
                employee.basic_salary = float(request.form.get('basic_salary') or 0)
            except:
                pass
        
        db.session.commit()
        
        # Return employee without password hash
        employee_dict = employee.to_dict()
        return jsonify(employee_dict), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_employee: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': 'Failed to update employee'}), 500

@employee_bp.route('/employees/<int:id>', methods=['DELETE'])
def delete_employee(id):
    """Delete an employee"""
    try:
        employee = Employee.query.get(id)
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        
        # Delete attached files
        upload_dir = current_app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER)
        
        if employee.aadhar_attachment:
            file_path = os.path.join(upload_dir, employee.aadhar_attachment)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        if employee.pan_attachment:
            file_path = os.path.join(upload_dir, employee.pan_attachment)
            if os.path.exists(file_path):
                os.remove(file_path)

        
        db.session.delete(employee)
        db.session.commit()
        
        return jsonify({'message': 'Employee deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in delete_employee: {str(e)}")
        return jsonify({'error': 'Failed to delete employee'}), 500

@employee_bp.route('/employees/by-type/<user_type>', methods=['GET'])
def get_employees_by_type(user_type):
    """Get employees by user type"""
    try:
        employees = Employee.query.filter_by(user_type=user_type).order_by(Employee.created_at.desc()).all()
        return jsonify([employee.to_dict() for employee in employees]), 200
    except Exception as e:
        print(f"Error in get_employees_by_type: {str(e)}")
        return jsonify({'error': 'Failed to fetch employees'}), 500

@employee_bp.route('/employees/user-types', methods=['GET'])
def get_user_types():
    """Get all available user types from database"""
    try:
        user_types = UserType.query.all()
        user_type_names = [user_type.name for user_type in user_types]
        return jsonify({'user_types': user_type_names}), 200
    except Exception as e:
        print(f"Error in get_user_types: {str(e)}")
        return jsonify({'error': 'Failed to fetch user types'}), 500

@employee_bp.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download attached file"""
    try:
        # Security check to prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            return jsonify({'error': 'Invalid filename'}), 400
            
        upload_dir = current_app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER)
            
        return send_from_directory(
            directory=upload_dir,
            path=filename,
            as_attachment=True,
            download_name=filename
        )

    except FileNotFoundError:
        print(f"File not found: {filename}")
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        print(f"Error in download_file: {str(e)}")
        return jsonify({'error': 'Failed to download file'}), 500