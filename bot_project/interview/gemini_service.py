import json
from groq import Groq
from django.conf import settings


def get_client():
    """Initialize and return the Groq client."""
    return Groq(api_key=settings.GROQ_API_KEY)


def _chat(prompt, max_tokens=2000):
    """Helper to send a chat completion request."""
    client = get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Always respond with valid JSON only. No markdown, no explanation."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    text = response.choices[0].message.content.strip()

    # Clean up markdown code blocks if present
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:])
    if text.endswith('```'):
        text = text[:-3]
    return text.strip()


def extract_skills(resume_text):
    """
    Use Groq to extract technical skills from resume text.
    Returns a list of skill strings.
    """
    prompt = f"""You are an expert AI technical interviewer with strong knowledge of software development, data science, system design, and modern technologies.

Your task is to:

1. Carefully analyze the resume provided by the user.
2. Extract ALL technical skills mentioned in the resume.

Focus specifically on:
- Programming languages (Python, Java, JavaScript, C++, etc.)
- Frameworks and libraries (Django, React, Angular, Spring, TensorFlow, etc.)
- Databases (MySQL, PostgreSQL, MongoDB, etc.)
- Tools and platforms (Docker, AWS, Git, Kubernetes, etc.)
- Technical concepts (REST APIs, Microservices, Machine Learning, Data Structures, OOP, etc.)

Return ONLY a valid JSON array of strings.
Do NOT include explanations.
Do NOT include markdown.
Do NOT include extra text.

Example output:
["Python", "Django", "PostgreSQL", "Docker"]

After extracting the skills:
- Start a structured technical interview.
- Begin with a short introduction request.
- Then ask questions step-by-step based on the extracted skills.
- Move from basic to advanced questions.
- Include practical, scenario-based, and problem-solving questions.
- Continue the interview until the session is complete.

Resume:
---
---
{resume_text}
---

JSON array of skills:"""

    text = _chat(prompt)

    try:
        skills = json.loads(text)
        if isinstance(skills, list):
            return [str(s).strip() for s in skills if s]
    except json.JSONDecodeError:
        pass

    # Fallback: try to extract skills from plain text
    return [s.strip().strip('"').strip("'") for s in text.split(',') if s.strip()]


def generate_questions(skills, num_questions=10):
    """
    Use Groq to generate technical interview questions based on skills.
    Returns a list of dicts with 'question', 'skill', and 'difficulty'.
    """
    skills_str = ', '.join(skills[:15])  # Limit to top 15 skills

    prompt = f"""You are a technical interviewer. Generate exactly {num_questions} technical interview questions
based on the following skills: {skills_str}

Requirements:
- Questions should test real understanding, not just definitions
- Include a mix of difficulties: 3 easy, 4 medium, 3 hard
- Cover different skills from the list
- Questions should be clear and specific

Return ONLY a valid JSON array with objects having these keys:
- "question": the question text
- "skill": which skill it tests
- "difficulty": "easy", "medium", or "hard"

No explanation, no markdown. Just the JSON array.

Example:
[{{"question": "What is the difference between a list and a tuple in Python?", "skill": "Python", "difficulty": "easy"}}]

Generate {num_questions} questions:"""

    text = _chat(prompt, max_tokens=3000)

    try:
        questions = json.loads(text)
        if isinstance(questions, list):
            result = []
            for i, q in enumerate(questions):
                if isinstance(q, dict) and 'question' in q:
                    result.append({
                        'question': q['question'],
                        'skill': q.get('skill', 'General'),
                        'difficulty': q.get('difficulty', 'medium'),
                        'order': i + 1,
                    })
            return result[:num_questions]
    except json.JSONDecodeError:
        pass

    # Fallback: return a basic set of questions
    return [
        {
            'question': f"Explain your experience with {skill} and describe a project where you used it.",
            'skill': skill,
            'difficulty': 'medium',
            'order': i + 1,
        }
        for i, skill in enumerate(skills[:num_questions])
    ]


def evaluate_answer(question_text, answer_text, skill):
    """
    Use Groq to evaluate a candidate's answer.
    Returns a dict with 'score' (1-10) and 'evaluation' text.
    """
    prompt = f"""You are a technical interviewer evaluating a candidate's answer.

Question: {question_text}
Skill being tested: {skill}
Candidate's Answer: {answer_text}

Evaluate the answer on a scale of 1-10 where:
- 1-3: Poor (incorrect, vague, or irrelevant)
- 4-5: Below Average (partially correct but missing key points)
- 6-7: Good (mostly correct with minor gaps)
- 8-9: Very Good (correct and well-explained)
- 10: Excellent (perfect answer with deep understanding)

Return ONLY a valid JSON object with these keys:
- "score": integer from 1 to 10
- "evaluation": a brief 2-3 sentence evaluation explaining the score

No markdown, no explanation. Just the JSON object.

Example: {{"score": 7, "evaluation": "The candidate demonstrated good understanding of the concept but missed mentioning the performance implications."}}"""

    text = _chat(prompt)

    try:
        result = json.loads(text)
        if isinstance(result, dict):
            score = result.get('score', 5)
            score = max(1, min(10, int(score)))
            return {
                'score': score,
                'evaluation': result.get('evaluation', 'No detailed evaluation available.'),
            }
    except (json.JSONDecodeError, ValueError):
        pass

    return {
        'score': 5,
        'evaluation': 'Unable to evaluate the answer automatically. Please review manually.',
    }


def generate_report(session):
    """
    Use Groq to generate a comprehensive analysis report from all Q&A pairs.
    Returns a dict with 'overall_score', 'report_text', and 'skill_scores'.
    """
    # Build Q&A summary
    qa_pairs = []
    for question in session.questions.all().order_by('order'):
        answer = question.answers.first()
        if answer:
            qa_pairs.append({
                'question': question.question_text,
                'skill': question.skill_category,
                'difficulty': question.difficulty,
                'answer': answer.answer_text,
                'score': answer.score,
                'evaluation': answer.evaluation,
            })

    if not qa_pairs:
        return {
            'overall_score': 0,
            'report_text': 'No questions were answered.',
            'skill_scores': {},
        }

    qa_text = json.dumps(qa_pairs, indent=2)

    prompt = f"""You are generating a comprehensive interview analysis report.

Candidate Skills: {', '.join(session.skills)}

Interview Q&A Data:
{qa_text}

Generate a detailed analysis report in the following JSON format:
{{
    "overall_score": <float 0-100>,
    "summary": "<2-3 paragraph summary of the candidate's performance>",
    "strengths": ["<strength 1>", "<strength 2>", ...],
    "weaknesses": ["<area for improvement 1>", "<area for improvement 2>", ...],
    "skill_scores": {{"<skill name>": <score 0-100>, ...}},
    "recommendation": "<hiring recommendation: Strong Hire / Hire / Maybe / No Hire>",
    "detailed_feedback": "<detailed paragraph with specific advice for the candidate>"
}}

Return ONLY the JSON object. No markdown, no explanation."""

    text = _chat(prompt, max_tokens=3000)

    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return {
                'overall_score': float(result.get('overall_score', 0)),
                'report_text': json.dumps(result),
                'skill_scores': result.get('skill_scores', {}),
            }
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback
    total_score = sum(qa['score'] for qa in qa_pairs) / len(qa_pairs)
    return {
        'overall_score': total_score * 10,
        'report_text': json.dumps({
            'summary': 'Report could not be generated automatically.',
            'overall_score': total_score * 10,
        }),
        'skill_scores': {},
    }
