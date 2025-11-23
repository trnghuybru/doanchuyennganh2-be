from app.models import db
from sqlalchemy import Enum as SQLEnum

class ExamResult(db.Model):
    __tablename__ = 'exam_results'

    result_id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.String(50), db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True)
    exam_id = db.Column(db.String(50), db.ForeignKey('exams.exam_id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Thông tin điểm số
    total_questions = db.Column(db.Integer, nullable=False)
    correct_answers = db.Column(db.Integer, default=0)
    score = db.Column(db.Float, default=0.0)  # Điểm số (0-100)
    
    # Trạng thái và thời gian
    status = db.Column(SQLEnum('in_progress', 'completed', 'abandoned', name='exam_status'), default='in_progress')
    started_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    
    # Relationships
    user = db.relationship('User', backref='exam_results')
    exam = db.relationship('Exam', backref='exam_results')
    answers = db.relationship('ExamAnswer', backref='exam_result', cascade='all, delete-orphan')

