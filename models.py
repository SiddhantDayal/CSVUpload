from extensions import db

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(200))
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)