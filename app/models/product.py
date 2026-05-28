from app import db
from datetime import datetime

class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)

    name          = db.Column(db.String(100), nullable=False)
    model         = db.Column(db.String(100), nullable=True)
    type          = db.Column(db.String(100), nullable=True)
    watts         = db.Column(db.Float(), nullable=True)
    buy_price     = db.Column(db.Float(), nullable=False)
    sell_price    = db.Column(db.Float(), nullable=False)
    quantity      = db.Column(db.Integer, nullable=False)
    profit_percent = db.Column(db.Float(), nullable=True)
    amount        = db.Column(db.Float(), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":             self.id,
            "name":           self.name,
            "model":          self.model or "",
            "type":           self.type or "",
            "watts":          self.watts or 0.0,
            "quantity":       self.quantity,
            "buyPrice":       self.buy_price or 0.0,
            "sellPrice":      self.sell_price or 0.0,
            "profitPercent":  self.profit_percent or 0.0,
            "amount":         self.amount or 0.0,
            "created_at":     self.created_at,
        }
