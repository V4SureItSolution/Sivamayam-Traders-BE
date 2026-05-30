from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime
import calendar
from app import db
from app.models import Salary, Employee, Attendance, HRConfig
from sqlalchemy import func
import logging

salary_bp = Blueprint('salary', __name__)
logger = logging.getLogger(__name__)

@salary_bp.route('/calculate', methods=['GET'])
def calculate_salaries():
    """Calculate salaries for all employees for a given month/year"""
    try:
        month = request.args.get('month', datetime.now().month, type=int)
        year = request.args.get('year', datetime.now().year, type=int)
        
        employees = Employee.query.all()
        results = []
        
        # Get working days from config or default to 22
        config = HRConfig.query.filter_by(month=month, year=year).first()
        monthly_working_days = config.working_days if config else 22
        
        # Get total days in month (calendar days)
        _, num_days = calendar.monthrange(year, month)
        
        for emp in employees:
            # Check if salary already exists
            salary_record = Salary.query.filter_by(employee_id=emp.id, month=month, year=year).first()
            
            # Calculate attendance based on status
            attendances = Attendance.query.filter(
                Attendance.employee_id == emp.id,
                func.month(Attendance.date) == month,
                func.year(Attendance.date) == year
            ).all()
            
            present_days = sum(1 for a in attendances if a.status == 'present')
            paid_leaves = sum(1 for a in attendances if a.status == 'paid_leave')
            half_days = sum(1 for a in attendances if a.status == 'half_day')
            
            # Effective paid days = Working days - Unpaid Leaves - Absents - (Half Days * 0.5)
            # This satisfies "Attendance will be marked present automatically untill admin mark absent"
            unpaid_leaves = sum(1 for a in attendances if a.status == 'leave')
            absent_days = sum(1 for a in attendances if a.status == 'absent')
            
            effective_days = monthly_working_days - unpaid_leaves - absent_days - (half_days * 0.5)
            if effective_days < 0:
                effective_days = 0
                
            per_day_rate = emp.basic_salary or 0
            calculated_salary = effective_days * per_day_rate
            
            if not salary_record:
                salary_record = Salary(
                    employee_id=emp.id,
                    month=month,
                    year=year,
                    basic_salary=per_day_rate,
                    calculated_salary=round(calculated_salary, 2),
                    status='pending'
                )
                db.session.add(salary_record)
                db.session.flush()  # Flush to get the ID and populate relationships
            else:
                salary_record.basic_salary = per_day_rate
                salary_record.calculated_salary = round(calculated_salary, 2)
            
            res_dict = salary_record.to_dict()
            res_dict.update({
                'present_days': present_days,
                'paid_leaves': paid_leaves,
                'half_days': half_days,
                'unpaid_leaves': sum(1 for a in attendances if a.status == 'leave'),
                'absent_days': sum(1 for a in attendances if a.status == 'absent'),
                'effective_days': effective_days,
                'num_days_in_month': num_days,
                'working_days_threshold': monthly_working_days
            })
            results.append(res_dict)
            
        db.session.commit()
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f"Salary calculation error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@salary_bp.route('/update-status', methods=['PUT'])
def update_salary_status():
    """Update payment status of a salary record"""
    try:
        data = request.get_json()
        salary_id = data.get('salary_id')
        status = data.get('status')  # 'paid' or 'pending'
        
        salary_record = Salary.query.get(salary_id)
        if not salary_record:
            return jsonify({'error': 'Salary record not found'}), 404
            
        salary_record.status = status
        if status == 'paid':
            salary_record.payment_date = datetime.utcnow()
        else:
            salary_record.payment_date = None
            
        db.session.commit()
        return jsonify(salary_record.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Salary status update error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@salary_bp.route('/pay-all', methods=['POST'])
def pay_all():
    """Mark all pending salaries as paid for a given month/year"""
    try:
        data = request.get_json()
        month = data.get('month')
        year = data.get('year')
        
        salaries = Salary.query.filter_by(month=month, year=year, status='pending').all()
        for s in salaries:
            s.status = 'paid'
            s.payment_date = datetime.utcnow()
            
        db.session.commit()
        return jsonify({'message': f'Marked {len(salaries)} salaries as paid'}), 200
        
    except Exception as e:
        logger.error(f"Pay all error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
