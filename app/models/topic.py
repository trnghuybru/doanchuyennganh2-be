from app.models import db

class Topic(db.Model):
    __tablename__ = "topics"

    topic_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
