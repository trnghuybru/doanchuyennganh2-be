from app.models import db

class TopicRelation(db.Model):
    __tablename__ = 'topic_relations'

    relation_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('topics.topic_id', ondelete='CASCADE'), nullable=False)
    parent_name = db.Column(db.String(100), nullable=False)