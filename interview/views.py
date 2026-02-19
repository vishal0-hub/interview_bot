import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import InterviewSession, Question, Answer
from .forms import ResumeUploadForm
from .resume_parser import parse_resume
from . import gemini_service


def home(request):
    """Landing page — redirect to upload."""
    return redirect('upload_resume')


def upload_resume(request):
    """Handle resume upload, parse it, extract skills, generate questions."""
    if request.method == 'POST':
        form = ResumeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            resume_file = form.cleaned_data['resume']
            candidate_name = form.cleaned_data.get('candidate_name', '')

            # Create session
            session = InterviewSession.objects.create(
                resume_file=resume_file,
                candidate_name=candidate_name,
                status='processing',
            )

            try:
                # Parse resume
                resume_text = parse_resume(session.resume_file.path)
                session.resume_text = resume_text

                # Extract skills using Gemini
                skills = gemini_service.extract_skills(resume_text)
                session.skills = skills

                # Generate questions
                questions_data = gemini_service.generate_questions(skills, num_questions=10)

                # Save questions to DB
                for q_data in questions_data:
                    Question.objects.create(
                        session=session,
                        question_text=q_data['question'],
                        skill_category=q_data.get('skill', 'General'),
                        difficulty=q_data.get('difficulty', 'medium'),
                        order=q_data.get('order', 0),
                    )

                session.status = 'ready'
                session.save()

                return redirect('interview_question', session_id=session.pk)

            except Exception as e:
                session.status = 'error'
                session.resume_text = f"Error: {str(e)}"
                session.save()
                form.add_error(None, f"Error processing resume: {str(e)}")
    else:
        form = ResumeUploadForm()

    # Show recent sessions
    recent_sessions = InterviewSession.objects.exclude(status='error')[:5]

    return render(request, 'interview/upload.html', {
        'form': form,
        'recent_sessions': recent_sessions,
    })


def interview_question(request, session_id):
    """Render the interview Q&A page."""
    session = get_object_or_404(InterviewSession, pk=session_id)

    if session.status == 'completed':
        return redirect('interview_report', session_id=session.pk)

    if session.status == 'ready':
        session.status = 'in_progress'
        session.save()

    return render(request, 'interview/interview.html', {
        'session': session,
    })


@require_http_methods(["GET"])
def get_current_question(request, session_id):
    """API endpoint: get the current unanswered question."""
    session = get_object_or_404(InterviewSession, pk=session_id)

    # Find the first unanswered question
    unanswered = session.questions.filter(answers__isnull=True).order_by('order').first()

    if unanswered is None:
        return JsonResponse({
            'status': 'completed',
            'message': 'All questions answered!',
            'redirect': f'/interview/{session.pk}/report/',
        })

    return JsonResponse({
        'status': 'ok',
        'question_id': unanswered.pk,
        'question_text': unanswered.question_text,
        'skill': unanswered.skill_category,
        'difficulty': unanswered.difficulty,
        'question_number': unanswered.order,
        'total_questions': session.total_questions,
        'progress': session.progress_percent,
    })


@csrf_exempt
@require_http_methods(["POST"])
def submit_answer(request, session_id):
    """API endpoint: submit an answer, get it evaluated."""
    session = get_object_or_404(InterviewSession, pk=session_id)

    try:
        data = json.loads(request.body)
        question_id = data.get('question_id')
        answer_text = data.get('answer', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid request data.'}, status=400)

    if not answer_text:
        return JsonResponse({'status': 'error', 'message': 'Answer cannot be empty.'}, status=400)

    question = get_object_or_404(Question, pk=question_id, session=session)

    # Evaluate the answer using Gemini
    try:
        evaluation = gemini_service.evaluate_answer(
            question.question_text,
            answer_text,
            question.skill_category,
        )
    except Exception:
        evaluation = {'score': 5, 'evaluation': 'Could not evaluate. Please continue.'}

    # Save the answer
    Answer.objects.create(
        question=question,
        answer_text=answer_text,
        evaluation=evaluation['evaluation'],
        score=evaluation['score'],
    )

    # Check if all questions are answered
    unanswered_count = session.questions.filter(answers__isnull=True).count()

    return JsonResponse({
        'status': 'ok',
        'score': evaluation['score'],
        'evaluation': evaluation['evaluation'],
        'is_last': unanswered_count == 0,
    })


def interview_report(request, session_id):
    """Generate and display the analysis report."""
    session = get_object_or_404(InterviewSession, pk=session_id)

    # Generate report if not already done
    if not session.report_text or session.status != 'completed':
        try:
            report_data = gemini_service.generate_report(session)
            session.report_text = report_data['report_text']
            session.overall_score = report_data['overall_score']
            session.status = 'completed'
            session.save()
        except Exception as e:
            # Fallback: calculate from individual scores
            answers = Answer.objects.filter(question__session=session)
            if answers.exists():
                avg_score = sum(a.score or 0 for a in answers) / answers.count()
                session.overall_score = avg_score * 10
            session.status = 'completed'
            session.save()

    # Parse report for template
    report = {}
    try:
        report = json.loads(session.report_text)
    except (json.JSONDecodeError, TypeError):
        report = {'summary': 'Report data unavailable.'}

    # Get all Q&A pairs for the report
    questions_with_answers = []
    for question in session.questions.all().order_by('order'):
        answer = question.answers.first()
        questions_with_answers.append({
            'question': question,
            'answer': answer,
        })

    return render(request, 'interview/report.html', {
        'session': session,
        'report': report,
        'questions_with_answers': questions_with_answers,
    })
