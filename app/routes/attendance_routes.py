# app/routes/attendance_routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from datetime import datetime, date
from sqlalchemy import and_, func
from app import db
from app.models import Attendance, Employee, HRConfig
import logging

from flask_cors import CORS

attendance_bp = Blueprint('attendance', __name__)
logger = logging.getLogger(__name__)


# ✅ Check In - Simple check-in without location/device
@attendance_bp.route('/check-in', methods=['POST'])
def check_in():
    """Employee check-in - Simple version"""
    try:
        data = request.get_json() or {}
        current_user_id = None
        
        logger.info(f"Check-in request data: {data}")
        
        # Try to get JWT if provided (optional)
        try:
            verify_jwt_in_request(optional=True)
            current_user_id = get_jwt_identity()
            logger.info(f"JWT Identity: {current_user_id}")
        except:
            pass
        
        # Get employee by user_id, employee_id, or email
        employee = None
        if 'employee_id' in data:
            logger.info(f"Looking for employee by ID: {data['employee_id']}")
            employee = Employee.query.get(data['employee_id'])
        elif 'email' in data:
            logger.info(f"Looking for employee by email: {data['email']}")
            employee = Employee.query.filter_by(email=data['email']).first()
        elif current_user_id:
            logger.info(f"Looking for employee by user ID: {current_user_id}")
            employee = Employee.query.filter_by(id=current_user_id).first()
        
        if not employee:
            logger.error(f"Employee not found. Data: {data}, Current User ID: {current_user_id}")
            # Debug: return all employees for troubleshooting
            all_employees = Employee.query.all()
            return jsonify({
                'error': 'Employee not found. Please provide employee_id or email in request body.',
                'debug_employees_count': len(all_employees),
                'received_data': data
            }), 404
        
        today = date.today()
        
        # Check if already checked in today
        existing_attendance = Attendance.query.filter(
            and_(
                Attendance.employee_id == employee.id,
                Attendance.date == today
            )
        ).first()
        
        if existing_attendance and existing_attendance.check_in_time:
            return jsonify({'error': 'Already checked in today'}), 400
        
        # Create or update attendance record
        if existing_attendance:
            attendance = existing_attendance
            attendance.check_in_time = datetime.now()
            attendance.status = 'present'
        else:
            attendance = Attendance(
                employee_id=employee.id,
                date=today,
                check_in_time=datetime.now(),
                status='present'
            )
            db.session.add(attendance)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Check-in successful',
            'data': attendance.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Check-in error: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': f"Internal server error: {str(e)}"}), 500


# ✅ Check Out - Simple check-out without location/device
@attendance_bp.route('/check-out', methods=['PUT'])
def check_out():
    """Employee check-out - Simple version"""
    try:
        data = request.get_json() or {}
        current_user_id = None
        
        # Try to get JWT if provided (optional)
        try:
            verify_jwt_in_request(optional=True)
            current_user_id = get_jwt_identity()
        except:
            pass
        
        # Get employee
        employee = None
        if 'employee_id' in data:
            employee = Employee.query.get(data['employee_id'])
        elif 'email' in data:
            employee = Employee.query.filter_by(email=data['email']).first()
        elif current_user_id:
            employee = Employee.query.filter_by(id=current_user_id).first()
        
        if not employee:
            return jsonify({'error': 'Employee not found. Please provide employee_id or email in request body.'}), 404
        
        today = date.today()
        
        attendance = Attendance.query.filter(
            and_(
                Attendance.employee_id == employee.id,
                Attendance.date == today
            )
        ).first()
        
        if not attendance or not attendance.check_in_time:
            return jsonify({'error': 'No check-in record found for today'}), 404
        
        if attendance.check_out_time:
            return jsonify({'error': 'Already checked out today'}), 400
        
        # Set check-out time
        attendance.check_out_time = datetime.now()
        
        # Calculate total hours
        if attendance.check_in_time and attendance.check_out_time:
            time_diff = attendance.check_out_time - attendance.check_in_time
            attendance.total_hours = round(time_diff.total_seconds() / 3600, 2)
            
            # Calculate overtime (assuming 8 hours standard workday)
            standard_hours = 8
            if attendance.total_hours > standard_hours:
                attendance.overtime = round(attendance.total_hours - standard_hours, 2)
        
        attendance.status = 'present'
        db.session.commit()
        
        return jsonify({
            'message': 'Check-out successful',
            'data': attendance.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Check-out error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ✅ Get today's attendance for current user
@attendance_bp.route('/today', methods=['GET'])
def get_today_attendance():
    """Get today's attendance for current user"""
    try:
        current_user_id = None
        
        # Try to get JWT if provided (optional)
        try:
            verify_jwt_in_request(optional=True)
            current_user_id = get_jwt_identity()
        except:
            pass
        
        employee_id = request.args.get('employee_id')
        
        # Get employee
        if employee_id:
            employee = Employee.query.get(employee_id)
        elif current_user_id:
            employee = Employee.query.filter_by(id=current_user_id).first()
        else:
            return jsonify({'error': 'Please provide employee_id as query parameter or JWT token'}), 400
        
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        
        today = date.today()
        
        attendance = Attendance.query.filter(
            and_(
                Attendance.employee_id == employee.id,
                Attendance.date == today
            )
        ).first()
        
        if attendance:
            return jsonify(attendance.to_dict()), 200
        else:
            return jsonify({
                'employee_id': employee.id,
                'employee_name': employee.name,
                'date': today.isoformat(),
                'check_in_time': None,
                'check_out_time': None,
                'status': 'not_started',
                'total_hours': 0
            }), 200
            
    except Exception as e:
        logger.error(f"Get today's attendance error: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ✅ Get attendance history for current user
@attendance_bp.route('/history', methods=['GET'])
def get_attendance_history():
    """Get attendance history for current user"""
    try:
        current_user_id = None
        
        # Try to get JWT if provided (optional)
        try:
            verify_jwt_in_request(optional=True)
            current_user_id = get_jwt_identity()
        except:
            pass
        
        employee_id = request.args.get('employee_id')
        
        # Get employee
        if employee_id:
            employee = Employee.query.get(employee_id)
        elif current_user_id:
            employee = Employee.query.filter_by(id=current_user_id).first()
        else:
            return jsonify({'error': 'Please provide employee_id as query parameter or JWT token'}), 400
        
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        
        # Get query parameters for filtering
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 30, type=int)
        
        query = Attendance.query.filter(Attendance.employee_id == employee.id)
        
        # Apply filters
        if start_date:
            query = query.filter(Attendance.date >= start_date)
        if end_date:
            query = query.filter(Attendance.date <= end_date)
        
        # Order by date descending and limit
        attendances = query.order_by(Attendance.date.desc()).limit(limit).all()
        
        # Calculate summary
        total_present = sum(1 for a in attendances if a.status == 'present')
        total_absent = sum(1 for a in attendances if a.status == 'absent')
        total_late = sum(1 for a in attendances if a.status == 'late')
        total_hours = sum(a.total_hours or 0 for a in attendances)
        total_overtime = sum(a.overtime or 0 for a in attendances)
        
        return jsonify({
            'attendances': [a.to_dict() for a in attendances],
            'summary': {
                'total_days': len(attendances),
                'present': total_present,
                'absent': total_absent,
                'late': total_late,
                'total_hours': round(total_hours, 2),
                'total_overtime': round(total_overtime, 2)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Get attendance history error: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ✅ Get monthly summary for dashboard
@attendance_bp.route('/monthly-summary', methods=['GET'])
def get_monthly_summary():
    """Get monthly attendance summary"""
    try:
        current_user_id = None
        
        # Try to get JWT if provided (optional)
        try:
            verify_jwt_in_request(optional=True)
            current_user_id = get_jwt_identity()
        except:
            pass
        
        employee_id = request.args.get('employee_id')
        
        # Get employee
        if employee_id:
            employee = Employee.query.get(employee_id)
        elif current_user_id:
            employee = Employee.query.filter_by(id=current_user_id).first()
        else:
            return jsonify({'error': 'Please provide employee_id as query parameter or JWT token'}), 400
        
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        
        year = request.args.get('year', datetime.now().year, type=int)
        month = request.args.get('month', datetime.now().month, type=int)
        
        # Get attendance for the month
        attendances = Attendance.query.filter(
            and_(
                Attendance.employee_id == employee.id,
                func.year(Attendance.date) == year,
                func.month(Attendance.date) == month
            )
        ).all()
        
        # Calculate statistics
        total_days = len(attendances)
        present_days = sum(1 for a in attendances if a.status == 'present')
        absent_days = sum(1 for a in attendances if a.status == 'absent')
        late_days = sum(1 for a in attendances if a.status == 'late')
        total_hours = sum(a.total_hours or 0 for a in attendances)
        
        return jsonify({
            'year': year,
            'month': month,
            'statistics': {
                'total_days': total_days,
                'present': present_days,
                'absent': absent_days,
                'late': late_days,
                'attendance_rate': round((present_days / total_days * 100) if total_days > 0 else 0, 2),
                'total_hours': round(total_hours, 2)
            },
            'attendances': [a.to_dict() for a in attendances]
        }), 200
        
    except Exception as e:
        logger.error(f"Get monthly summary error: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ✅ Get all employees for attendance tracking (Admin)
@attendance_bp.route('/employees', methods=['GET'])
def get_employees():
    """Get list of employees for attendance tracking"""
    try:
        employees = Employee.query.all()
        
        logger.info(f"Total employees in database: {len(employees)}")
        
        return jsonify({
            'total_employees': len(employees),
            'employees': [{
                'id': e.id,
                'employee_id': e.employee_id,
                'full_name': e.full_name,
                'email': e.email,
                'department': e.department,
                'designation': e.designation
            } for e in employees]
        }), 200
        
    except Exception as e:
        logger.error(f"Get employees error: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ✅ Update attendance record (Admin only)
@attendance_bp.route('/update/<int:attendance_id>', methods=['PUT'])
def update_attendance(attendance_id):
    """Update attendance record (admin only)"""
    try:
        data = request.get_json()
        
        attendance = Attendance.query.get(attendance_id)
        if not attendance:
            return jsonify({'error': 'Attendance record not found'}), 404
        
        # Update fields
        if 'check_in_time' in data:
            attendance.check_in_time = datetime.fromisoformat(data['check_in_time'])
        if 'check_out_time' in data:
            attendance.check_out_time = datetime.fromisoformat(data['check_out_time'])
        if 'status' in data:
            attendance.status = data['status']
        if 'notes' in data:
            attendance.notes = data['notes']
        
        # Recalculate hours if times updated
        if attendance.check_in_time and attendance.check_out_time:
            time_diff = attendance.check_out_time - attendance.check_in_time
            attendance.total_hours = round(time_diff.total_seconds() / 3600, 2)
            
            standard_hours = 8
            if attendance.total_hours > standard_hours:
                attendance.overtime = round(attendance.total_hours - standard_hours, 2)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Attendance updated successfully',
            'data': attendance.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Update attendance error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@attendance_bp.route('/monthly-list', methods=['GET'])
def list_monthly_attendance():
    """Get monthly summary for all employees for a given month/year"""
    try:
        month = request.args.get('month', datetime.now().month, type=int)
        year = request.args.get('year', datetime.now().year, type=int)
        
        employees = Employee.query.all()
        results = []
        
        for emp in employees:
            attendances = Attendance.query.filter(
                Attendance.employee_id == emp.id,
                func.month(Attendance.date) == month,
                func.year(Attendance.date) == year
            ).all()
            
            present = sum(1 for a in attendances if a.status == 'present')
            leave = sum(1 for a in attendances if a.status == 'leave')
            paid_leave = sum(1 for a in attendances if a.status == 'paid_leave')
            half_day = sum(1 for a in attendances if a.status == 'half_day')
            absent = sum(1 for a in attendances if a.status == 'absent')
            
            # Fetch working days to accurately calculate present days by default
            config = HRConfig.query.filter_by(month=month, year=year).first()
            monthly_working_days = config.working_days if config else 22
            
            # Auto-mark present assumption
            effective_days = monthly_working_days - leave - absent - (half_day * 0.5)
            if effective_days < 0:
                effective_days = 0
            
            # Estimate actual present for display if it wasn't auto-generated for every day
            display_present = max(present, int(effective_days - paid_leave))
            
            results.append({
                'employee_id': emp.id,
                'employee_name': emp.full_name,
                'present': display_present,
                'leave': leave,
                'paid_leave': paid_leave,
                'half_day': half_day,
                'absent': absent,
                'effective_days': effective_days
            })
            
        return jsonify(results), 200
    except Exception as e:
        logger.error(f"Monthly list error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@attendance_bp.route('/list', methods=['GET'])
def list_attendance():
    "Get attendance for all employees for a given date. Auto-creates records as 'present' if missing."
    try:
        date_str = request.args.get('date')
        if not date_str:
            target_date = date.today()
        else:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
        employees = Employee.query.all()
        results = []
        
        for emp in employees:
            try:
                attendance = Attendance.query.filter_by(employee_id=emp.id, date=target_date).first()
                
                if not attendance:
                    attendance = Attendance(
                        employee_id=emp.id,
                        date=target_date,
                        status='present'
                    )
                    attendance.employee = emp  # Explicitly set to ensure to_dict() works
                    db.session.add(attendance)
                    db.session.flush()
                    
                results.append(attendance.to_dict())
            except Exception as e:
                logger.error(f"Error processing employee {emp.id} attendance: {str(e)}")
                # Don't rollback the whole session yet, we'll try to get as many as possible
                # But since it's a flush error, we might need to rollback and skip
                db.session.rollback()
            
        db.session.commit()
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f'List attendance error: {str(e)}')
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
@attendance_bp.route('/get-config', methods=['GET'])
def get_attendance_config():
    """Get monthly working days config"""
    try:
        month = request.args.get('month', datetime.now().month, type=int)
        year = request.args.get('year', datetime.now().year, type=int)
        
        config = HRConfig.query.filter_by(month=month, year=year).first()
        if not config:
            # Default to 22
            return jsonify({'month': month, 'year': year, 'working_days': 22}), 200
            
        return jsonify(config.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@attendance_bp.route('/set-config', methods=['POST'])
def set_attendance_config():
    """Set monthly working days config"""
    try:
        data = request.get_json()
        month = data.get('month')
        year = data.get('year')
        working_days = data.get('working_days', 22)
        
        if not month or not year:
            return jsonify({'error': 'Month and year required'}), 400
            
        config = HRConfig.query.filter_by(month=month, year=year).first()
        if config:
            config.working_days = working_days
        else:
            config = HRConfig(month=month, year=year, working_days=working_days)
            db.session.add(config)
            
        db.session.commit()
        return jsonify(config.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
