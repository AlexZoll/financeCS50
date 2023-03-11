from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func

# Configure sqlalchemy to use
db = SQLAlchemy()

# Create instances of database tables for future implementation
class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, nullable=False, unique=True)
    hash = db.Column(db.String, nullable=False)
    cash = db.Column(db.Numeric, default=10000, nullable=False)

    def __repr__(self):
        return f"<Users {self.id}>"

class Companies(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String, nullable=False, unique=True)
    name = db.Column(db.String, nullable=False)

    def __repr__(self):
        return f"<Companies {self.symbol}>"

class Stocks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbolid = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    shares = db.Column(db.Integer, nullable=False)
    userid = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    company = db.relationship("Companies", backref="stocks")

    def __init__(self, symbolid, shares, userid):
        self.symbolid = symbolid
        self.shares = shares
        self.userid = userid
        self.price = {}
        self.value = {}

    def __repr__(self):
        return f"<Stocks {self.shares}>"

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbolid = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    shares = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric, nullable=False)
    userid = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    time = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    company = db.relationship("Companies", backref="history")

    def __repr__(self):
        return "<History %r>" % self.shares