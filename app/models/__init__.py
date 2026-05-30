# app/models/__init__.py

from app.models.attendance import Attendance
from app.models.billing import Bill, BillItem, Payment
from app.models.discount import DiscountRange, DiscountLog
from app.models.employee import Employee
from app.models.invoice import Invoice, InvoiceItem
from app.models.login import login
from app.models.product import Product
from app.models.quotation import Quotation, QuotationItem
from app.models.service import Service, ServiceBillItem
from app.models.supplier import Supplier, Item
from app.models.usertype import UserType
from app.models.enquiry import Enquiry
from app.models.salary import Salary

# Import HRConfig if it exists, otherwise skip
try:
    from app.models.hrconfig import HRConfig
except ImportError:
    pass

# Import Company if it exists
try:
    from app.models.current_company import Company
except ImportError:
    pass

__all__ = [
    'Attendance',
    'Bill',
    'BillItem',
    'Payment',
    'DiscountRange',
    'DiscountLog',
    'Employee',
    'Invoice',
    'InvoiceItem',
    'login',
    'Product',
    'Quotation',
    'QuotationItem',
    'Service',
    'ServiceBillItem',
    'Supplier',
    'Item',
    'UserType',
    'Enquiry',
    'Salary',
    'HRConfig',
    'Company',
]