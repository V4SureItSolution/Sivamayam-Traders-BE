from app import db
from datetime import datetime

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    company = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('login.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    items = db.relationship('Item', backref='supplier', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Supplier {self.name} - {self.company}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'company': self.company,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'created_by': self.created_by,
            'items': [item.to_dict() for item in self.items] if self.items else [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50))
    model = db.Column(db.String(100), nullable=False)
    watts = db.Column(db.String(50), default='')
    buy_price = db.Column(db.Float, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)

    # ✅ NEW FIELDS ADDED
    status = db.Column(db.String(50), default="Active")
    attachment = db.Column(db.String(255))  # stores file path (pdf/excel/word)
    quantity = db.Column(db.Integer, default=0)  # ADDED quantity field

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Item {self.name} - {self.model}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'model': self.model,
            'watts': self.watts or '',
            'buy_price': self.buy_price,
            'supplier_id': self.supplier_id,
            'status': self.status,           
            'attachment': self.attachment,
            'quantity': self.quantity,  # ADDED quantity to dict
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# ── NEW: SupplierReturn model ──
class SupplierReturn(db.Model):
    __tablename__ = 'supplier_returns'

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, nullable=True)          # original item id (may be deleted)
    item_name = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100))                        # HSN code
    watts = db.Column(db.String(50))                         # original volume
    buy_price = db.Column(db.Float)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id', ondelete='SET NULL'), nullable=True)
    supplier_name = db.Column(db.String(100))
    company_name = db.Column(db.String(100))
    returned_volume = db.Column(db.String(100), nullable=False)
    is_full_return = db.Column(db.Boolean, default=False)
    returned_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SupplierReturn {self.item_name} - {self.returned_at}>"

    def to_dict(self):
        return {
            'id': self.id,
            'item_id': self.item_id,
            'item_name': self.item_name,
            'model': self.model,
            'watts': self.watts or '',
            'buy_price': self.buy_price,
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier_name or '',
            'company_name': self.company_name or '',
            'returned_volume': self.returned_volume,
            'is_full_return': self.is_full_return,
            'returned_at': self.returned_at.isoformat() if self.returned_at else None,
        }