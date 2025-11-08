from app.models import db

class Media(db.Model):
    __tablename__ = 'media'

    media_id = db.Column(db.String(50), primary_key=True)
    question_id = db.Column(db.String(50), db.ForeignKey('questions.question_id', ondelete='CASCADE'))
    file_url = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.Enum('image','video','audio','pdf'), default='image')
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())