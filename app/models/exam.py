from app.models import db

class Exam(db.Model):
    __tablename__ = 'exams'

    exam_id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.String(50), db.ForeignKey('users.user_id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, server_default=db.func.now())