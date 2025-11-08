from app.models import db

class Choice(db.Model):
    __tablename__ = 'choices'

    choice_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question_id = db.Column(db.String(50), db.ForeignKey('questions.question_id', ondelete='CASCADE'))
    label = db.Column(db.String(1))
    text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)