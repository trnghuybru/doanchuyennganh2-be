from app.models import db


class QuestionSet(db.Model):
    __tablename__ = 'question_sets'

    set_id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.String(50), db.ForeignKey('users.user_id', ondelete='SET NULL'), index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())


class QuestionSetQuestion(db.Model):
    __tablename__ = 'question_set_questions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    set_id = db.Column(db.String(50), db.ForeignKey('question_sets.set_id', ondelete='CASCADE'), index=True)
    question_id = db.Column(db.String(50), db.ForeignKey('questions.question_id', ondelete='CASCADE'), index=True)
    order_no = db.Column(db.Integer)
