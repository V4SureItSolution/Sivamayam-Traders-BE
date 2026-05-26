from app import db
from datetime import datetime

class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)

    name       = db.Column(db.String(100), nullable=False)
    quantity   = db.Column(db.Integer, nullable=False, default=0)
    volume     = db.Column(db.String(50), nullable=True)
    hsn_code   = db.Column(db.String(50), nullable=True)
    buy_price  = db.Column(db.Float, nullable=False, default=0.0)
    sell_price = db.Column(db.Float, nullable=False, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":        self.id,
            "name":      self.name,
            "quantity":  self.quantity,
            "volume":    self.volume   or "",
            "hsnCode":   self.hsn_code or "",
            "sellPrice": self.sell_price or 0.0,
            "created_at": self.created_at,
        }
