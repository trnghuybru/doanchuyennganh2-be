from app.models import db

class QuestionTag(db.Model):
    __tablename__ = 'question_tags'

    question_id = db.Column(db.String(50), db.ForeignKey('questions.question_id', ondelete='CASCADE'), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.tag_id', ondelete='CASCADE'), primary_key=True)