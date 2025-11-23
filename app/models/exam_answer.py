from app.models import db

class ExamAnswer(db.Model):
    __tablename__ = 'exam_answers'

    answer_id = db.Column(db.String(50), primary_key=True)
    result_id = db.Column(db.String(50), db.ForeignKey('exam_results.result_id', ondelete='CASCADE'), nullable=False, index=True)
    question_id = db.Column(db.String(50), db.ForeignKey('questions.question_id', ondelete='CASCADE'), nullable=False)
    selected_choice_id = db.Column(db.Integer, db.ForeignKey('choices.choice_id', ondelete='SET NULL'), nullable=True)
    
    # Lưu label của lựa chọn (A, B, C, D) để dễ hiển thị
    selected_choice_label = db.Column(db.String(1), nullable=True)
    
    # Đánh dấu câu trả lời đúng hay sai
    is_correct = db.Column(db.Boolean, default=False)
    
    # Thời gian trả lời
    answered_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    
    # Relationships
    question = db.relationship('Question', backref='exam_answers')
    selected_choice = db.relationship('Choice', backref='exam_answers')

