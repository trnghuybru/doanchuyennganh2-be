from flask import Blueprint, jsonify, request, current_app
import uuid
import json

from app.models import db, Question, Choice, Tag, QuestionTag, Media, Exam, ExamQuestion, QuestionSet, QuestionSetQuestion, User

set_routes = Blueprint('set_routes', __name__)


def _gen_id(prefix: str = 'q_') -> str:
	return prefix + str(uuid.uuid4())[:8]


def _serialize_question(q: Question) -> dict:
	"""Return a JSON-serializable dict for a Question and its relations."""
	# basic fields
	obj = {
		'question_id': q.question_id,
		'question_text': q.question_text,
		'bloom_level': q.bloom_level,
		'difficulty': q.difficulty,
		'explanation': q.explanation,
		'source': q.source,
		'created_at': q.created_at.isoformat() if getattr(q, 'created_at', None) else None,
		'updated_at': q.updated_at.isoformat() if getattr(q, 'updated_at', None) else None,
	}

	# choices
	choice_rows = Choice.query.filter_by(question_id=q.question_id).order_by(Choice.choice_id).all()
	obj['choices'] = [
		{
			'choice_id': c.choice_id,
			'label': c.label,
			'text': c.text,
			'is_correct': bool(c.is_correct)
		}
		for c in choice_rows
	]

	# tags
	tag_rows = (Tag.query
				.join(QuestionTag, Tag.tag_id == QuestionTag.tag_id)
				.filter(QuestionTag.question_id == q.question_id)
				.all())
	obj['tags'] = [t.name for t in tag_rows]

	# media
	media_rows = Media.query.filter_by(question_id=q.question_id).order_by(Media.media_id).all()
	obj['media'] = [
		{
			'media_id': m.media_id,
			'file_url': m.file_url,
			'file_type': m.file_type,
			'description': m.description
		}
		for m in media_rows
	]

	# exams linking
	eq_rows = ExamQuestion.query.filter_by(question_id=q.question_id).all()
	exams = []
	for eq in eq_rows:
		exam = Exam.query.filter_by(exam_id=eq.exam_id).first()
		exams.append({
			'exam_id': eq.exam_id,
			'order_no': eq.order_no,
			'exam_title': getattr(exam, 'title', None) if exam else None
		})
	obj['exams'] = exams

	return obj


@set_routes.route('/question-sets', methods=['POST'])
def create_question_set():
	"""Create an empty QuestionSet (no questions)."""
	payload = request.get_json(silent=True) or {}
	title = payload.get('title')
	description = payload.get('description')
	created_by = payload.get('created_by')
	if not title:
		return jsonify({'message': 'title is required'}), 400

	# validate created_by if provided
	if created_by:
		user = User.query.filter_by(user_id=created_by).first()
		if not user:
			return jsonify({'message': 'created_by user not found'}), 400

	set_id = _gen_id('s_')
	qs = QuestionSet(set_id=set_id, title=title, description=description, created_by=created_by)
	try:
		db.session.add(qs)
		db.session.commit()
		return jsonify({'set_id': set_id, 'title': title, 'description': description}), 201
	except Exception as e:
		db.session.rollback()
		current_app.logger.error(f"Error creating question set: {str(e)}")
		return jsonify({'message': 'Failed to create question set', 'error': str(e)}), 500


@set_routes.route('/users/<user_id>/question-sets/<set_id>', methods=['GET'])
def get_question_set(user_id: str, set_id: str):
	"""Return a question set and its questions (ordered by order_no)."""
	qs = QuestionSet.query.filter_by(set_id=set_id, created_by=user_id).first()
	if not qs:
		return jsonify({'message': 'Question set not found or you do not have permission to view it'}), 404
	creator = None
	if qs.created_by:
		user = User.query.filter_by(user_id=qs.created_by).first()
		if user:
			creator = {'user_id': user.user_id, 'username': user.name}

	links = QuestionSetQuestion.query.filter_by(set_id=set_id).order_by(QuestionSetQuestion.order_no).all()
	questions = []
	for l in links:
		q = Question.query.filter_by(question_id=l.question_id).first()
		if not q:
			continue
		questions.append(_serialize_question(q))

	return jsonify({
		'set_id': qs.set_id,
		'title': qs.title,
		'description': qs.description,
		'creator': creator,
		'created_at': qs.created_at.isoformat() if getattr(qs, 'created_at', None) else None,
		'updated_at': qs.updated_at.isoformat() if getattr(qs, 'updated_at', None) else None,
		'questions': questions
	}), 200

@set_routes.route('/users/<user_id>/question-sets', methods=['GET'])
def list_user_question_sets(user_id: str):
	"""Return all question sets owned by a given user."""
	user = User.query.filter_by(user_id=user_id).first()
	if not user:
		return jsonify({'message': 'User not found'}), 404

	sets = QuestionSet.query.filter_by(created_by=user_id).order_by(QuestionSet.created_at.desc()).all()
	out = []
	for s in sets:
		count = QuestionSetQuestion.query.filter_by(set_id=s.set_id).count()
		out.append({
			'set_id': s.set_id,
			'title': s.title,
			'description': s.description,
			'created_at': s.created_at.isoformat() if getattr(s, 'created_at', None) else None,
			'question_count': count,
			'creator': {
				'user_id': user.user_id,
				'username': user.name
			}
		})

	return jsonify({'user_id': user_id, 'sets': out}), 200
