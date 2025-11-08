from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from app.models.user import User
from app.models.topic import Topic
from app.models.topic_relation import TopicRelation
from app.models.question import Question
from app.models.choice import Choice
from app.models.tag import Tag
from app.models.question_tag import QuestionTag
from app.models.exam import Exam
from app.models.exam_question import ExamQuestion
from app.models.media import Media