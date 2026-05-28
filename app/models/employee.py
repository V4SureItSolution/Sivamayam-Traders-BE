# app/models/employee.py
from app import db
from datetime import datetime
import json

class Employee(db.Model):
    """Employee Model"""
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))  # New password field
    phone_number = db.Column(db.String(20))
    
    # Employment details
    department = db.Column(db.String(100))
    designation = db.Column(db.String(100))
    date_of_joining = db.Column(db.Date)
    current_company = db.Column(db.String(200))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    
    # User type field (references name in user_types table)
    user_type = db.Column(db.String(50), nullable=False, default='employee')
    
    # Personal details
    aadhar_card_number = db.Column(db.String(20))
    pan_card_number = db.Column(db.String(20))
    address = db.Column(db.Text)
    emergency_contact = db.Column(db.String(100))
    blood_group = db.Column(db.String(5))
    marital_status = db.Column(db.String(20))
    basic_salary = db.Column(db.Float, default=0.0)
    
    # Document attachments
    aadhar_attachment = db.Column(db.String(255))
    pan_attachment = db.Column(db.String(255))
    
    # User-specific permissions (JSON string)
    permissions = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    company = db.relationship('Company', backref='employees', lazy=True)
    
    def __init__(self, **kwargs):
        super(Employee, self).__init__(**kwargs)
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'full_name': self.full_name,
            'email': self.email,
            # Don't include password_hash in dictionary
            'phone_number': self.phone_number,
            'department': self.department,
            'designation': self.designation,
            'date_of_joining': self.date_of_joining.isoformat() if hasattr(self.date_of_joining, 'isoformat') else self.date_of_joining,
            'current_company': self.current_company,
            'company_id': self.company_id,
            'user_type': self.user_type,
            'aadhar_card_number': self.aadhar_card_number,
            'pan_card_number': self.pan_card_number,
            'address': self.address,
            'emergency_contact': self.emergency_contact,
            'blood_group': self.blood_group,
            'marital_status': self.marital_status,
            'basic_salary': self.basic_salary,
            'aadhar_attachment': self.aadhar_attachment,
            'pan_attachment': self.pan_attachment,
            'permissions': json.loads(self.permissions) if self.permissions else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Employee {self.employee_id} - {self.full_name}>'