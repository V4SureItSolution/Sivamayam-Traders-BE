from app import db

class HRConfig(db.Model):
    __tablename__ = 'hr_config'
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    working_days = db.Column(db.Integer, default=22)

    def to_dict(self):
        return {
            'id': self.id,
            'month': self.month,
            'year': self.year,
            'working_days': self.working_days
        }