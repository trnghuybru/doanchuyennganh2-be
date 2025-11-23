from flask import Blueprint, jsonify, request, current_app
import uuid

from app.models import db, Exam, ExamQuestion, QuestionSet, QuestionSetQuestion, Question, User, Choice, Tag, QuestionTag, Media

exam_routes = Blueprint('exam_routes', __name__)


def _gen_id(prefix: str = 'e_') -> str:
	"""Tạo ID ngắn có prefix."""
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

	return obj


@exam_routes.route('/exams', methods=['POST'])
def create_exam():
	"""
	Tạo đề thi mới và thêm câu hỏi từ các question sets.
	
	Expected JSON body:
	{
		"title": "Tên đề thi" (required),
		"description": "Mô tả đề thi" (optional),
		"created_by": "user_id" (optional),
		"question_sets": [
			{
				"set_id": "s_xxxxx",
				"question_ids": ["q_xxxxx", "q_yyyyy"]  // optional: nếu không có thì lấy tất cả câu hỏi trong set
			},
			...
		]
	}
	
	Returns:
	{
		"exam_id": "e_xxxxx",
		"title": "...",
		"description": "...",
		"created_by": "...",
		"questions_count": 10,
		"questions": [...]
	}
	"""
	payload = request.get_json(silent=True)
	if not payload:
		return jsonify({'message': 'Missing JSON body'}), 400
	
	title = payload.get('title')
	if not title:
		return jsonify({'message': 'title is required'}), 400
	
	description = payload.get('description')
	created_by = payload.get('created_by')
	
	# Validate user if provided
	if created_by:
		user = User.query.filter_by(user_id=created_by).first()
		if not user:
			return jsonify({'message': 'created_by user not found'}), 400
	
	question_sets = payload.get('question_sets', [])
	if not isinstance(question_sets, list):
		return jsonify({'message': 'question_sets must be a list'}), 400
	
	if not question_sets:
		return jsonify({'message': 'At least one question_set is required'}), 400
	
	try:
		# Tạo exam mới
		exam_id = _gen_id('e_')
		exam = Exam(
			exam_id=exam_id,
			title=title,
			description=description,
			created_by=created_by
		)
		db.session.add(exam)
		db.session.flush()
		
		# Thu thập tất cả câu hỏi từ các question sets
		all_question_ids = []
		processed_questions = {}  # Để tránh trùng lặp
		
		for qs_data in question_sets:
			set_id = qs_data.get('set_id')
			if not set_id:
				continue
			
			# Kiểm tra question set có tồn tại không
			question_set = QuestionSet.query.filter_by(set_id=set_id).first()
			if not question_set:
				current_app.logger.warning(f"Question set {set_id} not found, skipping")
				continue
			
			# Lấy danh sách question_ids từ request hoặc lấy tất cả từ set
			requested_question_ids = qs_data.get('question_ids', [])
			
			if requested_question_ids:
				# Chỉ lấy các câu hỏi được chỉ định
				for qid in requested_question_ids:
					if qid not in processed_questions:
						# Kiểm tra câu hỏi có trong set không
						qs_link = QuestionSetQuestion.query.filter_by(
							set_id=set_id,
							question_id=qid
						).first()
						if qs_link:
							all_question_ids.append(qid)
							processed_questions[qid] = True
			else:
				# Lấy tất cả câu hỏi trong set
				qs_links = QuestionSetQuestion.query.filter_by(set_id=set_id).order_by(
					QuestionSetQuestion.order_no
				).all()
				for qs_link in qs_links:
					qid = qs_link.question_id
					if qid not in processed_questions:
						all_question_ids.append(qid)
						processed_questions[qid] = True
		
		if not all_question_ids:
			return jsonify({'message': 'No valid questions found in the provided question sets'}), 400
		
		# Thêm các câu hỏi vào exam
		exam_questions = []
		for order, question_id in enumerate(all_question_ids, start=1):
			# Kiểm tra câu hỏi có tồn tại không
			question = Question.query.filter_by(question_id=question_id).first()
			if not question:
				current_app.logger.warning(f"Question {question_id} not found, skipping")
				continue
			
			exam_question = ExamQuestion(
				exam_id=exam_id,
				question_id=question_id,
				order_no=order
			)
			exam_questions.append(exam_question)
		
		if not exam_questions:
			return jsonify({'message': 'No valid questions to add to exam'}), 400
		
		db.session.add_all(exam_questions)
		db.session.commit()
		
		# Lấy thông tin đầy đủ của exam và câu hỏi để trả về
		exam = Exam.query.filter_by(exam_id=exam_id).first()
		exam_question_links = ExamQuestion.query.filter_by(exam_id=exam_id).order_by(
			ExamQuestion.order_no
		).all()
		
		questions = []
		for eq in exam_question_links:
			q = Question.query.filter_by(question_id=eq.question_id).first()
			if q:
				question_data = _serialize_question(q)
				question_data['order_no'] = eq.order_no
				questions.append(question_data)
		
		# Lấy thông tin creator
		creator = None
		if exam.created_by:
			user = User.query.filter_by(user_id=exam.created_by).first()
			if user:
				creator = {
					'user_id': user.user_id,
					'name': user.name,
					'email': user.email
				}
		
		response_data = {
			'exam_id': exam.exam_id,
			'title': exam.title,
			'description': exam.description,
			'created_by': exam.created_by,
			'creator': creator,
			'created_at': exam.created_at.isoformat() if getattr(exam, 'created_at', None) else None,
			'questions_count': len(questions),
			'questions': questions
		}
		
		return jsonify(response_data), 201
		
	except Exception as e:
		db.session.rollback()
		current_app.logger.error(f"Error creating exam: {str(e)}")
		return jsonify({'message': 'Failed to create exam', 'error': str(e)}), 500


@exam_routes.route('/exams', methods=['GET'])
def list_exams():
	"""
	Lấy danh sách tất cả các đề thi.
	
	Query parameters:
	- created_by: filter by user_id (optional)
	- limit: số lượng kết quả (optional, default: 50)
	- offset: vị trí bắt đầu (optional, default: 0)
	
	Returns:
	{
		"exams": [...],
		"total": 10
	}
	"""
	try:
		created_by = request.args.get('created_by')
		limit = int(request.args.get('limit', 50))
		offset = int(request.args.get('offset', 0))
		
		query = Exam.query
		if created_by:
			query = query.filter_by(created_by=created_by)
		
		total = query.count()
		exams = query.order_by(Exam.created_at.desc()).limit(limit).offset(offset).all()
		
		exams_data = []
		for exam in exams:
			# Đếm số câu hỏi
			questions_count = ExamQuestion.query.filter_by(exam_id=exam.exam_id).count()
			
			# Lấy thông tin creator
			creator = None
			if exam.created_by:
				user = User.query.filter_by(user_id=exam.created_by).first()
				if user:
					creator = {
						'user_id': user.user_id,
						'name': user.name,
						'email': user.email
					}
			
			exams_data.append({
				'exam_id': exam.exam_id,
				'title': exam.title,
				'description': exam.description,
				'created_by': exam.created_by,
				'creator': creator,
				'created_at': exam.created_at.isoformat() if getattr(exam, 'created_at', None) else None,
				'questions_count': questions_count
			})
		
		return jsonify({
			'exams': exams_data,
			'total': total,
			'limit': limit,
			'offset': offset
		}), 200
		
	except Exception as e:
		current_app.logger.error(f"Error listing exams: {str(e)}")
		return jsonify({'message': 'Failed to list exams', 'error': str(e)}), 500


@exam_routes.route('/exams/<exam_id>', methods=['GET'])
def get_exam(exam_id: str):
	"""
	Lấy thông tin chi tiết của một đề thi bao gồm tất cả câu hỏi.
	
	Returns:
	{
		"exam_id": "...",
		"title": "...",
		"description": "...",
		"created_by": "...",
		"creator": {...},
		"questions": [...]
	}
	"""
	try:
		exam = Exam.query.filter_by(exam_id=exam_id).first()
		if not exam:
			return jsonify({'message': 'Exam not found'}), 404
		
		# Lấy tất cả câu hỏi trong exam
		exam_question_links = ExamQuestion.query.filter_by(exam_id=exam_id).order_by(
			ExamQuestion.order_no
		).all()
		
		questions = []
		for eq in exam_question_links:
			q = Question.query.filter_by(question_id=eq.question_id).first()
			if q:
				question_data = _serialize_question(q)
				question_data['order_no'] = eq.order_no
				questions.append(question_data)
		
		# Lấy thông tin creator
		creator = None
		if exam.created_by:
			user = User.query.filter_by(user_id=exam.created_by).first()
			if user:
				creator = {
					'user_id': user.user_id,
					'name': user.name,
					'email': user.email
				}
		
		response_data = {
			'exam_id': exam.exam_id,
			'title': exam.title,
			'description': exam.description,
			'created_by': exam.created_by,
			'creator': creator,
			'created_at': exam.created_at.isoformat() if getattr(exam, 'created_at', None) else None,
			'questions_count': len(questions),
			'questions': questions
		}
		
		return jsonify(response_data), 200
		
	except Exception as e:
		current_app.logger.error(f"Error getting exam: {str(e)}")
		return jsonify({'message': 'Failed to get exam', 'error': str(e)}), 500

