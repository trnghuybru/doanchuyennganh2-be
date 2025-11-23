"""
seed.py - Tạo dữ liệu giả cho project Flask + SQLAlchemy
Cách chạy:
    python seed.py          # chỉ thêm dữ liệu mới
    python seed.py --reset  # xóa DB cũ rồi tạo lại dữ liệu mới
"""

import sys
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker
from werkzeug.security import generate_password_hash
from app import create_app
from app.models import (
    db, User, Question,
    Choice, Tag, QuestionTag, Exam, ExamQuestion, Media,
    ExamResult, ExamAnswer
)
from app.models import QuestionSet, QuestionSetQuestion

fake = Faker("vi_VN")
app = create_app()

# =====================
# Helper function
# =====================

def uid(prefix=""):
    """Tạo ID ngắn có prefix (vd: u_ab12cd34)."""
    return prefix + str(uuid.uuid4())[:8]

# =====================
# SEED FUNCTIONS
# =====================

def create_users(n=10):
    """Tạo user với email duy nhất, password mặc định."""
    users = []
    used_emails = set()
    for i in range(n):
        # tạo email không trùng
        while True:
            email = f"user{random.randint(1, 99999)}@example.com"
            if email not in used_emails:
                used_emails.add(email)
                break

        user = User(
            user_id = uid("u_"),
            name = fake.name(),
            email = email,
            password = generate_password_hash("password123")
        )
        users.append(user)

    db.session.add_all(users)
    db.session.commit()
    print(f"✅ Đã tạo {len(users)} users (email duy nhất).")
    return users


# Topics removed: project uses tags only now


def create_tags(n=12):
    """Tạo tags không trùng tên."""
    names = set()
    tags = []
    while len(names) < n:
        new_name = fake.word()
        if new_name not in names:
            names.add(new_name)
            tags.append(Tag(name=new_name))
    db.session.add_all(tags)
    db.session.commit()
    print(f"✅ Đã tạo {len(tags)} tags (không trùng).")
    return Tag.query.all()


def create_questions(tags, n=30):
    """Tạo câu hỏi, lựa chọn và gán tag (không có topic)."""
    questions = []
    for _ in range(n):
        qid = uid("q_")
        q = Question(
            question_id=qid,
            question_text=fake.sentence(nb_words=12),
            bloom_level=random.choice(["remember", "understand", "apply", "analyze", "evaluate", "create"]),
            difficulty=random.choice(["easy", "medium", "hard"]),
            explanation=fake.sentence(nb_words=10),
            source=fake.domain_name()
        )
        questions.append(q)

    # 🟢 Bước 1: Commit câu hỏi trước
    db.session.add_all(questions)
    db.session.commit()

    # 🟢 Bước 2: Tạo lựa chọn & tag (sau khi câu hỏi đã tồn tại)
    choices_all, qtags = [], []
    for q in questions:
        labels = ["A", "B", "C", "D"]
        correct = random.choice(labels)
        for lab in labels:
            choices_all.append(
                Choice(
                    question_id=q.question_id,
                    label=lab,
                    text=fake.sentence(nb_words=6),
                    is_correct=(lab == correct)
                )
            )

        # Gán tag ngẫu nhiên (1–3 tags)
        chosen_tags = random.sample(tags, k=min(len(tags), random.randint(1, 3)))
        for t in chosen_tags:
            qtags.append(QuestionTag(question_id=q.question_id, tag_id=t.tag_id))

    db.session.add_all(choices_all + qtags)
    db.session.commit()
    print(f"✅ Đã tạo {len(questions)} questions, {len(choices_all)} choices, {len(qtags)} question_tags.")
    return questions


def create_exams(users, questions, n=5):
    """Tạo đề thi và gán câu hỏi vào."""
    exams, exam_questions = [], []
    for _ in range(n):
        exam_id = uid("e_")
        creator = random.choice(users) if users else None
        ex = Exam(
            exam_id=exam_id,
            title=fake.sentence(nb_words=4),
            description=fake.paragraph(nb_sentences=2),
            created_by=creator.user_id if creator else None
        )
        exams.append(ex)

        # mỗi đề có 5–10 câu hỏi
        qs = random.sample(questions, k=min(len(questions), random.randint(5, 10)))
        for order, q in enumerate(qs, start=1):
            exam_questions.append(
                ExamQuestion(exam_id=exam_id, question_id=q.question_id, order_no=order)
            )

    db.session.add_all(exams + exam_questions)
    db.session.commit()
    print(f"✅ Đã tạo {len(exams)} exams, {len(exam_questions)} exam_questions.")
    return exams


def create_media(questions, n=10):
    """Tạo file minh họa (media) cho câu hỏi."""
    medias = []
    for _ in range(n):
        q = random.choice(questions)
        medias.append(
            Media(
                media_id=uid("m_"),
                question_id=q.question_id,
                file_url=f"https://example.com/media/{uid()}.jpg",
                file_type="image",
                description=fake.sentence(nb_words=6)
            )
        )
    db.session.add_all(medias)
    db.session.commit()
    print(f"✅ Đã tạo {len(medias)} media items.")
    return medias


def create_question_sets(users, questions, n=3):
    """Tạo một vài bộ câu hỏi và gán ngẫu nhiên các câu vào mỗi bộ.

    Each set will be assigned a random user from `users` as its owner (created_by).
    """
    sets = []
    s_links = []
    for _ in range(n):
        sid = uid('s_')
        title = fake.sentence(nb_words=3)
        desc = fake.sentence(nb_words=8)
        owner = random.choice(users) if users else None
        created_by = owner.user_id if owner else None
        sets.append(QuestionSet(set_id=sid, title=title, description=desc, created_by=created_by))

    db.session.add_all(sets)
    db.session.flush()

    # Attach random questions to each set (5-10 questions)
    for s in sets:
        count = min(len(questions), random.randint(5, 10))
        chosen = random.sample(questions, k=count)
        for order, q in enumerate(chosen, start=1):
            s_links.append(QuestionSetQuestion(set_id=s.set_id, question_id=q.question_id, order_no=order))

    if s_links:
        db.session.add_all(s_links)
    db.session.commit()
    print(f"✅ Đã tạo {len(sets)} question sets và gán {len(s_links)} liên kết.")
    return sets


def create_exam_results(users, exams, n=15):
    """Tạo kết quả bài thi cho người dùng.
    
    Tạo một số kết quả với các trạng thái khác nhau:
    - completed: đã hoàn thành với điểm số
    - in_progress: đang làm dở
    - abandoned: đã bỏ dở
    """
    results = []
    
    for _ in range(n):
        user = random.choice(users) if users else None
        exam = random.choice(exams) if exams else None
        
        if not user or not exam:
            continue
            
        # Lấy số câu hỏi trong đề thi
        exam_questions = ExamQuestion.query.filter_by(exam_id=exam.exam_id).all()
        total_questions = len(exam_questions)
        
        if total_questions == 0:
            continue
        
        # Chọn trạng thái ngẫu nhiên
        status = random.choice(['completed', 'in_progress', 'abandoned'])
        
        # Tạo thời gian bắt đầu (trong vòng 30 ngày gần đây)
        started_at = fake.date_time_between(start_date='-30d', end_date='now')
        
        # Tính số câu đã trả lời và số câu đúng
        if status == 'completed':
            # Đã hoàn thành: trả lời tất cả câu hỏi
            answered_count = total_questions
            # Số câu đúng: 60-100% (để có điểm số thực tế)
            correct_answers = random.randint(
                int(total_questions * 0.6), 
                total_questions
            )
            completed_at = started_at + timedelta(minutes=random.randint(30, 120))
        elif status == 'in_progress':
            # Đang làm: trả lời 30-70% câu hỏi
            answered_count = random.randint(
                int(total_questions * 0.3), 
                int(total_questions * 0.7)
            )
            # Số câu đúng trong số đã trả lời
            correct_answers = random.randint(
                int(answered_count * 0.5), 
                answered_count
            )
            completed_at = None
        else:  # abandoned
            # Bỏ dở: trả lời ít hơn 30% câu hỏi
            answered_count = random.randint(1, int(total_questions * 0.3))
            correct_answers = random.randint(0, answered_count)
            completed_at = None
        
        # Tính điểm (0-100)
        score = round((correct_answers / total_questions) * 100, 2) if total_questions > 0 else 0.0
        
        result = ExamResult(
            result_id=uid("r_"),
            user_id=user.user_id,
            exam_id=exam.exam_id,
            total_questions=total_questions,
            correct_answers=correct_answers,
            score=score,
            status=status,
            started_at=started_at,
            completed_at=completed_at
        )
        results.append((result, exam_questions, answered_count))
    
    # Commit results trước
    db.session.add_all([r[0] for r in results])
    db.session.commit()
    print(f"✅ Đã tạo {len(results)} exam results.")
    return results


def create_exam_answers(exam_results_data):
    """Tạo câu trả lời cho các kết quả bài thi.
    
    exam_results_data: list of tuples (result, exam_questions, answered_count)
    """
    all_answers = []
    
    for result, exam_questions, answered_count in exam_results_data:
        # Chỉ tạo câu trả lời cho các câu đã được trả lời
        questions_to_answer = exam_questions[:answered_count]
        
        for eq in questions_to_answer:
            question = Question.query.get(eq.question_id)
            if not question:
                continue
            
            # Lấy tất cả choices của câu hỏi
            choices = Choice.query.filter_by(question_id=question.question_id).all()
            if not choices:
                continue
            
            # Chọn một choice ngẫu nhiên (có thể đúng hoặc sai)
            # Tỷ lệ chọn đúng: 60-80% để có điểm số hợp lý
            if random.random() < random.uniform(0.6, 0.8):
                # Chọn đáp án đúng
                selected_choice = next((c for c in choices if c.is_correct), choices[0])
                is_correct = True
            else:
                # Chọn đáp án sai
                wrong_choices = [c for c in choices if not c.is_correct]
                selected_choice = random.choice(wrong_choices) if wrong_choices else choices[0]
                is_correct = False
            
            # Tạo thời gian trả lời (sau khi bắt đầu làm bài)
            answered_at = result.started_at + timedelta(
                minutes=random.randint(1, 60)
            )
            
            answer = ExamAnswer(
                answer_id=uid("a_"),
                result_id=result.result_id,
                question_id=question.question_id,
                selected_choice_id=selected_choice.choice_id,
                selected_choice_label=selected_choice.label,
                is_correct=is_correct,
                answered_at=answered_at
            )
            all_answers.append(answer)
    
    db.session.add_all(all_answers)
    db.session.commit()
    print(f"✅ Đã tạo {len(all_answers)} exam answers.")
    return all_answers

# =====================
# MAIN ENTRY
# =====================

def run_all(reset=False):
    with app.app_context():
        if reset:
            print("⚠️ Đang xóa toàn bộ dữ liệu cũ ...")
            db.drop_all()
            db.create_all()
            print("✅ Database đã được reset.")

        print("🚀 Đang tạo dữ liệu giả ...")
        users = create_users(8)
        tags = create_tags(12)
        questions = create_questions(tags, n=40)
        exams = create_exams(users, questions, n=6)
        create_media(questions, n=12)
        # create question sets and attach questions (sets belong to users)
        create_question_sets(users, questions, n=3)
        
        # Tạo kết quả bài thi và câu trả lời
        exam_results_data = create_exam_results(users, exams, n=15)
        exam_answers = create_exam_answers(exam_results_data)
        
        print(f"\n🎉 Hoàn tất seed data:")
        print(f"   - Users: {len(users)}")
        print(f"   - Questions: {len(questions)}")
        print(f"   - Exams: {len(exams)}")
        print(f"   - Exam Results: {len(exam_results_data)}")
        print(f"   - Exam Answers: {len(exam_answers)}")


if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    run_all(reset=reset_flag)
