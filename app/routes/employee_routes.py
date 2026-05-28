# app/routes/employee.py
from flask import Blueprint, request, jsonify, send_from_directory, session, current_app
from app import db
from app.models.employee import Employee
from app.models.usertype import UserType
from app.models.current_company import Company
from datetime import datetime
import os
import traceback
import json
from sqlalchemy import func
from werkzeug.utils import secure_filename
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

# Create blueprint
employee_bp = Blueprint('employee', __name__, url_prefix='/api')

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}

def ensure_secret_key():
    try:
        app = current_app._get_current_object()
        if not app.secret_key:
            app.config['SECRET_KEY'] = secrets.token_hex(32)
    except:
        pass

@employee_bp.record
def record_params(setup_state):
    app = setup_state.app
    if not app.secret_key:
        app.config['SECRET_KEY'] = secrets.token_hex(32)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file, prefix=''):
    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        filename = f"{prefix}_{uuid.uuid4().hex}_{original_filename}"
        upload_dir = current_app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER)
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        return filename
    return None

def generate_employee_id():
    last_employee = Employee.query.order_by(Employee.id.desc()).first()
    if last_employee and last_employee.employee_id:
        try:
            num = int(last_employee.employee_id[3:])
            new_num = num + 1
            return f"EMP{new_num:03d}"
        except:
            return "EMP001"
    return "EMP001"


# ========== AUTHENTICATION ROUTES ==========

@employee_bp.route('/auth/login', methods=['POST'])
def employee_login():
    try:
        ensure_secret_key()
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        email = data.get('email')
        password = data.get('password')
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        employee = Employee.query.filter_by(email=email).first()
        if not employee:
            return jsonify({'error': 'Invalid email or password'}), 401
        if not employee.password_hash or not check_password_hash(employee.password_hash, password):
            return jsonify({'error': 'Invalid email or password'}), 401
        session['user_id'] = employee.id
        session['user_email'] = employee.email
        session['user_name'] = employee.full_name
        session['user_type'] = employee.user_type
        session['company_id'] = employee.company_id
        session['company_name'] = employee.current_company
        session['logged_in'] = True
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
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200

@employee_bp.route('/auth/check', methods=['GET'])
def check_login():
    if 'user_id' in session:
        employee = Employee.query.get(session.get('user_id'))
        permissions = []
        if employee and employee.permissions:
            try:
                permissions = json.loads(employee.permissions)
            except Exception:
                permissions = []
        user_type_name = session.get('user_type')
        if not permissions:
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
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    try:
        employee = Employee.query.get(session['user_id'])
        if not employee:
            session.clear()
            return jsonify({'error': 'User not found'}), 404
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
    try:
        user_type = request.args.get('user_type')
        if user_type:
            employees = Employee.query.filter_by(user_type=user_type).order_by(Employee.created_at.desc()).all()
        else:
            employees = Employee.query.order_by(Employee.created_at.desc()).all()
        return jsonify([employee.to_dict() for employee in employees]), 200
    except Exception as e:
        print(f"Error in get_employees: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Failed to fetch employees: {str(e)}'}), 500

@employee_bp.route('/employees/<int:id>', methods=['GET'])
def get_employee(id):
    try:
        employee = Employee.query.get(id)
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        return jsonify(employee.to_dict()), 200
    except Exception as e:
        print(f"Error in get_employee: {str(e)}")
        return jsonify({'error': f'Failed to fetch employee: {str(e)}'}), 500

@employee_bp.route('/companies/list', methods=['GET'])
def get_companies_list():
    try:
        companies = Company.query.filter_by(is_active=True).order_by(Company.name).all()
        companies_list = [{'id': company.id, 'name': company.name} for company in companies]
        return jsonify(companies_list), 200
    except Exception as e:
        print(f"Error in get_companies_list: {str(e)}")
        return jsonify({'error': f'Failed to fetch companies: {str(e)}'}), 500

@employee_bp.route('/employees', methods=['POST'])
def create_employee():
    try:
        employee_id = generate_employee_id()
        email = request.form.get('email', '').strip()
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        existing_email = Employee.query.filter_by(email=email).first()
        if existing_email:
            return jsonify({'error': 'Email already exists'}), 400
        user_type = request.form.get('user_type', 'employee').strip() or 'employee'
        date_of_joining = None
        doj_str = request.form.get('date_of_joining', '').strip()
        if doj_str:
            try:
                date_of_joining = datetime.strptime(doj_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        current_company = request.form.get('current_company', '').strip() or None
        company_id_raw = request.form.get('company_id', '').strip()
        company_id = None
        if company_id_raw:
            try:
                company_id_int = int(company_id_raw)
                company = Company.query.get(company_id_int)
                if not company:
                    return jsonify({'error': 'Invalid company selected'}), 400
                current_company = company.name
                company_id = company_id_int
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid company ID format'}), 400
        aadhar_file = request.files.get('aadhar_attachment')
        pan_file = request.files.get('pan_attachment')
        aadhar_filename = None
        pan_filename = None
        if aadhar_file and aadhar_file.filename:
            aadhar_filename = save_file(aadhar_file, f"aadhar_{employee_id}")
        if pan_file and pan_file.filename:
            pan_filename = save_file(pan_file, f"pan_{employee_id}")
        password = request.form.get('password', '').strip()
        password_hash = generate_password_hash(password) if password else None
        salary_raw = request.form.get('basic_salary', '').strip()
        try:
            basic_salary = float(salary_raw) if salary_raw else 0.0
        except ValueError:
            basic_salary = 0.0
        employee = Employee(
            employee_id=employee_id,
            full_name=request.form.get('full_name', '').strip(),
            email=email,
            password_hash=password_hash,
            phone_number=request.form.get('phone_number', '').strip() or None,
            department=request.form.get('department', '').strip() or None,
            designation=request.form.get('designation', '').strip() or None,
            date_of_joining=date_of_joining,
            current_company=current_company,
            company_id=company_id,
            user_type=user_type,
            aadhar_card_number=request.form.get('aadhar_card_number', '').strip() or None,
            pan_card_number=request.form.get('pan_card_number', '').strip() or None,
            address=request.form.get('address', '').strip() or None,
            emergency_contact=request.form.get('emergency_contact', '').strip() or None,
            blood_group=request.form.get('blood_group', '').strip() or None,
            marital_status=request.form.get('marital_status', '').strip() or None,
            basic_salary=basic_salary,
            aadhar_attachment=aadhar_filename,
            pan_attachment=pan_filename
        )
        db.session.add(employee)
        db.session.commit()
        return jsonify(employee.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_employee: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Failed to create employee: {str(e)}'}), 500

@employee_bp.route('/employees/<int:id>', methods=['PUT'])
def update_employee(id):
    try:
        employee = Employee.query.get(id)
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        email = request.form.get('email', '').strip()
        if email and email != employee.email:
            existing_email = Employee.query.filter_by(email=email).first()
            if existing_email:
                return jsonify({'error': 'Email already exists'}), 400
        user_type = request.form.get('user_type', '').strip()
        if user_type:
            employee.user_type = user_type
        doj_str = request.form.get('date_of_joining', '').strip()
        if doj_str:
            try:
                employee.date_of_joining = datetime.strptime(doj_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        current_company = request.form.get('current_company', '').strip() or None
        company_id_raw = request.form.get('company_id', '').strip()
        if company_id_raw:
            try:
                company_id_int = int(company_id_raw)
                company = Company.query.get(company_id_int)
                if not company:
                    return jsonify({'error': 'Invalid company selected'}), 400
                employee.current_company = company.name
                employee.company_id = company_id_int
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid company ID format'}), 400
        elif current_company:
            employee.current_company = current_company
            employee.company_id = None
        else:
            employee.current_company = None
            employee.company_id = None
        upload_dir = current_app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER)
        aadhar_file = request.files.get('aadhar_attachment')
        pan_file = request.files.get('pan_attachment')
        if aadhar_file and aadhar_file.filename:
            if employee.aadhar_attachment:
                old_path = os.path.join(upload_dir, employee.aadhar_attachment)
                if os.path.exists(old_path):
                    os.remove(old_path)
            employee.aadhar_attachment = save_file(aadhar_file, f"aadhar_{employee.employee_id}")
        if pan_file and pan_file.filename:
            if employee.pan_attachment:
                old_path = os.path.join(upload_dir, employee.pan_attachment)
                if os.path.exists(old_path):
                    os.remove(old_path)
            employee.pan_attachment = save_file(pan_file, f"pan_{employee.employee_id}")
        password = request.form.get('password', '').strip()
        if password:
            employee.password_hash = generate_password_hash(password)
        if request.form.get('full_name', '').strip():
            employee.full_name = request.form.get('full_name').strip()
        if email:
            employee.email = email
        if request.form.get('phone_number', '').strip():
            employee.phone_number = request.form.get('phone_number').strip()
        if request.form.get('department', '').strip():
            employee.department = request.form.get('department').strip()
        if request.form.get('designation', '').strip():
            employee.designation = request.form.get('designation').strip()
        if request.form.get('aadhar_card_number', '').strip():
            employee.aadhar_card_number = request.form.get('aadhar_card_number').strip()
        if request.form.get('pan_card_number', '').strip():
            employee.pan_card_number = request.form.get('pan_card_number').strip()
        if request.form.get('address', '').strip():
            employee.address = request.form.get('address').strip()
        if request.form.get('emergency_contact', '').strip():
            employee.emergency_contact = request.form.get('emergency_contact').strip()
        if request.form.get('blood_group', '').strip():
            employee.blood_group = request.form.get('blood_group').strip()
        if request.form.get('marital_status', '').strip():
            employee.marital_status = request.form.get('marital_status').strip()
        salary_raw = request.form.get('basic_salary', '').strip()
        if salary_raw:
            try:
                employee.basic_salary = float(salary_raw)
            except ValueError:
                pass
        db.session.commit()
        return jsonify(employee.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_employee: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Failed to update employee: {str(e)}'}), 500

@employee_bp.route('/employees/<int:id>', methods=['DELETE'])
def delete_employee(id):
    try:
        employee = Employee.query.get(id)
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
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
        return jsonify({'error': f'Failed to delete employee: {str(e)}'}), 500

@employee_bp.route('/employees/by-type/<user_type>', methods=['GET'])
def get_employees_by_type(user_type):
    try:
        employees = Employee.query.filter_by(user_type=user_type).order_by(Employee.created_at.desc()).all()
        return jsonify([employee.to_dict() for employee in employees]), 200
    except Exception as e:
        print(f"Error in get_employees_by_type: {str(e)}")
        return jsonify({'error': f'Failed to fetch employees: {str(e)}'}), 500

@employee_bp.route('/employees/user-types', methods=['GET'])
def get_user_types():
    try:
        user_types = UserType.query.all()
        user_type_names = [user_type.name for user_type in user_types]
        return jsonify({'user_types': user_type_names}), 200
    except Exception as e:
        print(f"Error in get_user_types: {str(e)}")
        return jsonify({'error': f'Failed to fetch user types: {str(e)}'}), 500

@employee_bp.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
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
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        print(f"Error in download_file: {str(e)}")
        return jsonify({'error': f'Failed to download file: {str(e)}'}), 500