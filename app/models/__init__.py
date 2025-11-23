from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from app.models.user import User
from app.models.question import Question
from app.models.choice import Choice
from app.models.tag import Tag
from app.models.question_tag import QuestionTag
from app.models.exam import Exam
from app.models.exam_question import ExamQuestion
from app.models.exam_result import ExamResult
from app.models.exam_answer import ExamAnswer
from app.models.media import Media
from app.models.question_set import QuestionSet, QuestionSetQuestion