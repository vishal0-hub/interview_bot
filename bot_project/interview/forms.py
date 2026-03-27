from django import forms
from .models import InterviewSession


class ResumeUploadForm(forms.Form):
    resume = forms.FileField(
        label='Upload Your Resume',
        help_text='Accepted formats: PDF, DOCX (Max 5MB)',
    )
    candidate_name = forms.CharField(
        max_length=200,
        required=False,
        label='Your Name (optional)',
        widget=forms.TextInput(attrs={'placeholder': 'Enter your name'}),
    )

    def clean_resume(self):
        resume = self.cleaned_data.get('resume')
        if resume:
            # Check file size (5MB limit)
            if resume.size > 5 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 5MB.')

            # Check file extension
            ext = resume.name.lower().split('.')[-1]
            if ext not in ('pdf', 'docx'):
                raise forms.ValidationError('Only PDF and DOCX files are accepted.')

        return resume
