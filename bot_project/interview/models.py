from django.db import models
import json


class InterviewSession(models.Model):
    STATUS_CHOICES = [
        ('processing', 'Processing Resume'),
        ('ready', 'Ready to Start'),
        ('in_progress', 'Interview In Progress'),
        ('completed', 'Interview Completed'),
        ('error', 'Error'),
    ]

    resume_file = models.FileField(upload_to='resumes/')
    resume_text = models.TextField(blank=True, default='')
    skills_json = models.TextField(blank=True, default='[]')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    candidate_name = models.CharField(max_length=200, blank=True, default='')
    report_text = models.TextField(blank=True, default='')
    overall_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Session #{self.pk} - {self.candidate_name or 'Unknown'} ({self.status})"

    @property
    def skills(self):
        try:
            return json.loads(self.skills_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @skills.setter
    def skills(self, value):
        self.skills_json = json.dumps(value)

    @property
    def current_question_index(self):
        """Returns the index of the next unanswered question."""
        answered_count = self.questions.filter(answers__isnull=False).distinct().count()
        return answered_count

    @property
    def total_questions(self):
        return self.questions.count()

    @property
    def progress_percent(self):
        total = self.total_questions
        if total == 0:
            return 0
        return int((self.current_question_index / total) * 100)


class Question(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    skill_category = models.CharField(max_length=100, blank=True, default='')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."

    @property
    def is_answered(self):
        return self.answers.exists()


class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    answer_text = models.TextField()
    evaluation = models.TextField(blank=True, default='')
    score = models.IntegerField(null=True, blank=True)  # 1-10
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Answer to Q{self.question.order}: Score {self.score}/10"
