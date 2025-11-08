from app.models import db

class ExamQuestion(db.Model):
    __tablename__ = 'exam_questions'

    exam_id = db.Column(db.String(50), db.ForeignKey('exams.exam_id', ondelete='CASCADE'), primary_key=True)
    question_id = db.Column(db.String(50), db.ForeignKey('questions.question_id', ondelete='CASCADE'), primary_key=True)
    order_no = db.Column(db.Integer)