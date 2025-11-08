from app.models import db

class Question(db.Model):
    __tablename__ = "questions"

    question_id = db.Column(db.String(50), primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.topic_id", ondelete="SET NULL"))
    bloom_level = db.Column(db.Enum("remember", "understand", "apply", "analyze", "evaluate", "create"))
    difficulty = db.Column(db.Enum("easy", "medium", "hard"))
    explanation = db.Column(db.Text)
    source = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
