from flask import Blueprint, jsonify, request, current_app
import uuid
import json

from app.models import db, Question, Choice, Tag, QuestionTag, Media, Exam, ExamQuestion, QuestionSet, QuestionSetQuestion, User

main = Blueprint('main', __name__)


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


@main.route('/questions/batch', methods=['POST'])
def create_questions_batch():
	"""Create a list of questions (with choices, tags, media, optional exam linking).

	Expected JSON body: {"questions": [ {question_object}, ... ] }

	question_object fields:
	  - question_text (required)
	  - bloom_level, difficulty, explanation, source (optional)
	  - choices: [{label, text, is_correct}, ...] (optional)
	  - tags: ["tag1", "tag2"] (optional)
	  - media: [{file_url, file_type, description}] (optional)
	  - exam_id: existing exam id to attach this question to (optional)
	  - order_no: order number when attaching to exam (optional)

	Returns JSON with created question_ids and any per-item errors.
	"""
	payload = request.get_json(silent=True)
	if not payload or 'questions' not in payload:
		return jsonify({'message': 'Missing questions list in JSON body'}), 400

	questions_in = payload['questions']
	if not isinstance(questions_in, list):
		return jsonify({'message': 'questions must be a list'}), 400

	results = []

	set_id = None
	user_id = payload.get('user_id')
	if user_id:
		user = User.query.filter_by(user_id=user_id).first()
		if not user:
			return jsonify({'message': 'user_id not found'}), 400

	if 'create_set' in payload:
		cs = payload.get('create_set') or {}
		title = cs.get('title')
		description = cs.get('description')
		if not title:
			return jsonify({'message': 'create_set requires a title'}), 400
		if not user_id:
			return jsonify({'message': 'user_id is required when creating a new set'}), 400
		set_id = _gen_id('s_')
		qs = QuestionSet(set_id=set_id, title=title, description=description, created_by=user_id)
		db.session.add(qs)
		db.session.flush()
	elif 'question_set_id' in payload:
		set_id = payload.get('question_set_id')
		if set_id:
			if not user_id:
				return jsonify({'message': 'user_id is required to add questions to an existing set'}), 400
			exists = QuestionSet.query.filter_by(set_id=set_id).first()
			if not exists:
				return jsonify({'message': 'question_set_id not found'}), 400

	try:
		# Use a single transaction for the whole batch
		for item in questions_in:
			# basic validation
			text = item.get('question_text')
			if not text:
				results.append({'error': 'question_text is required', 'item': item})
				continue

			qid = _gen_id('q_')
			q = Question(
				question_id=qid,
				question_text=text,
				bloom_level=item.get('bloom_level'),
				difficulty=item.get('difficulty'),
				explanation=item.get('explanation'),
				source=item.get('source')
			)
			db.session.add(q)
			db.session.flush()  # Ensure question is inserted before adding related records

			# choices
			choices = item.get('choices') or []
			choice_objs = []
			for c in choices:
				choice_objs.append(Choice(
					question_id=qid,
					label=c.get('label'),
					text=c.get('text'),
					is_correct=bool(c.get('is_correct'))
				))
			if choice_objs:
				db.session.add_all(choice_objs)

			tags = item.get('tags') or []
			qtag_objs = []
			for tname in tags:
				if not tname:
					continue
				tag = Tag.query.filter_by(name=tname).first()
				if not tag:
					tag = Tag(name=tname)
					db.session.add(tag)
					db.session.flush()  # ensure tag.tag_id is available
				qtag_objs.append(QuestionTag(question_id=qid, tag_id=tag.tag_id))
			if qtag_objs:
				db.session.add_all(qtag_objs)

			# media
			medias = item.get('media') or []
			media_objs = []
			for m in medias:
				mid = _gen_id('m_')
				media_objs.append(Media(
					media_id=mid,
					question_id=qid,
					file_url=m.get('file_url'),
					file_type=m.get('file_type'),
					description=m.get('description')
				))
			if media_objs:
				db.session.add_all(media_objs)

			# exam linking (optional)
			exam_id = item.get('exam_id')
			if exam_id:
				exam = Exam.query.filter_by(exam_id=exam_id).first()
				if exam:
					order_no = item.get('order_no')
					if order_no is None:
						# compute next order_no
						last = db.session.query(db.func.max(ExamQuestion.order_no)).filter_by(exam_id=exam_id).scalar()
						order_no = (last or 0) + 1
					eq = ExamQuestion(exam_id=exam_id, question_id=qid, order_no=order_no)
					db.session.add(eq)

			# attach to question set if requested
			if set_id:
				last_order = db.session.query(db.func.max(QuestionSetQuestion.order_no)).filter_by(set_id=set_id).scalar()
				order_no = (last_order or 0) + 1
				db.session.add(QuestionSetQuestion(set_id=set_id, question_id=qid, order_no=order_no))

			results.append({'question_id': qid})
			

		db.session.commit()
		response_data = {'created': results}
		if set_id:
			response_data['set_id'] = set_id

		return jsonify(response_data), 201

	except Exception as e:
		db.session.rollback()
		return jsonify({'message': 'Failed to create questions', 'error': str(e)}), 500

@main.route('/questions/<question_id>', methods=['PUT'])
def edit_question(question_id: str):
	"""Edit an existing question (with choices, tags, exam linking).

	Supports both JSON and multipart form-data:
	  - JSON: question_text, bloom_level, difficulty, explanation, source,
		  choices (array of {label, text, is_correct}),
		  tags (array of tag names)
	  - multipart: same fields (file uploads are ignored by this endpoint)

	Behavior:
	  - Replaces choices/tags if provided (deletes old, creates new)
	  - Updates exam linking if exam_id provided
	"""
	q = Question.query.filter_by(question_id=question_id).first()
	if not q:
		return jsonify({'message': 'Question not found'}), 404
	
	# Parse request (JSON or multipart)
	data = None
	if request.is_json:
		data = request.get_json(silent=True)
	else:
		# multipart form-data
		data = request.form.to_dict()
	
	if not data:
		return jsonify({'message': 'No data provided'}), 400
	
	try:
		# Update basic fields
		if 'question_text' in data:
			q.question_text = data['question_text']
		if 'bloom_level' in data:
			q.bloom_level = data['bloom_level']
		if 'difficulty' in data:
			q.difficulty = data['difficulty']
		if 'explanation' in data:
			q.explanation = data['explanation']
		if 'source' in data:
			q.source = data['source']
		
		# Update choices (replace all)
		if 'choices' in data:
			# Delete old choices
			Choice.query.filter_by(question_id=question_id).delete()
			
			# Parse choices if string (from multipart)
			choices_list = data.get('choices')
			if isinstance(choices_list, str):
				try:
					choices_list = json.loads(choices_list)
					if choices_list is None:
						choices_list = []
				except (ValueError, TypeError) as ex:
					current_app.logger.warning(f"Failed to parse choices JSON: {ex}; raw={choices_list}")
					return jsonify({'message': 'Invalid choices format'}), 400
			elif not isinstance(choices_list, list):
				choices_list = []
			
			# Add new choices
			for c in choices_list:
				db.session.add(Choice(
					question_id=question_id,
					label=c.get('label'),
					text=c.get('text'),
					is_correct=bool(c.get('is_correct'))
				))
		
		# Update tags (replace all)
		if 'tags' in data:
			# Delete old question-tag mappings
			QuestionTag.query.filter_by(question_id=question_id).delete()
			
			# Parse tags if string
			tags_list = data.get('tags')
			if isinstance(tags_list, str):
				try:
					tags_list = json.loads(tags_list)
					if tags_list is None:
						tags_list = []
				except (ValueError, TypeError):
					# fallback: accept comma-separated string "a, b, c"
					tags_list = [t.strip() for t in tags_list.split(',') if t.strip()]
			elif not isinstance(tags_list, list):
				tags_list = []
			
			# Create/attach tags
			for tname in tags_list:
				if not tname:
					continue
				tag = Tag.query.filter_by(name=tname).first()
				if not tag:
					tag = Tag(name=tname)
					db.session.add(tag)
					db.session.flush()
				db.session.add(QuestionTag(question_id=question_id, tag_id=tag.tag_id))
		
		# Note: this endpoint intentionally does not modify media or upload to S3.
		
		# Update exam linking (if provided)
		if 'exam_id' in data:
			exam_id = data['exam_id']
			# Delete old exam-question mapping for this question
			ExamQuestion.query.filter_by(question_id=question_id).delete()
			
			# Add new mapping if exam exists
			if exam_id:
				exam = Exam.query.filter_by(exam_id=exam_id).first()
				if exam:
					order_no = int(data.get('order_no', 0))
					if order_no == 0:
						# compute next order_no
						last = db.session.query(db.func.max(ExamQuestion.order_no)).filter_by(exam_id=exam_id).scalar()
						order_no = (last or 0) + 1
					db.session.add(ExamQuestion(exam_id=exam_id, question_id=question_id, order_no=order_no))
		
		db.session.commit()
		# reload question to ensure we return fresh state
		q = Question.query.filter_by(question_id=question_id).first()
		if not q:
			return jsonify({'message': 'Question updated but failed to load'}), 200
		return jsonify({'message': 'Question updated', 'question': _serialize_question(q)}), 200
	
	except Exception as e:
		db.session.rollback()
		current_app.logger.error(f"Error editing question: {str(e)}")
		return jsonify({'message': 'Failed to update question', 'error': str(e)}), 500


@main.route('/questions/<question_id>', methods=['DELETE'])
def delete_question(question_id: str):
	"""Delete a question and its related records (choices, tags, media, exam links)."""
	q = Question.query.filter_by(question_id=question_id).first()
	if not q:
		return jsonify({'message': 'Question not found'}), 404

	try:
		# Remove related rows first to avoid FK constraint issues
		QuestionTag.query.filter_by(question_id=question_id).delete()
		Choice.query.filter_by(question_id=question_id).delete()
		Media.query.filter_by(question_id=question_id).delete()
		ExamQuestion.query.filter_by(question_id=question_id).delete()

		db.session.delete(q)
		db.session.commit()
		return jsonify({'message': 'Question deleted', 'question_id': question_id}), 200

	except Exception as e:
		db.session.rollback()
		current_app.logger.error(f"Error deleting question: {str(e)}")
		return jsonify({'message': 'Failed to delete question', 'error': str(e)}), 500
