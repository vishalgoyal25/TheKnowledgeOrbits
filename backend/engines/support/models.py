from django.db import models

class Feedback(models.Model):
    USER_TYPE_CHOICES = [
        ('aspirant', 'UPSC Aspirant'),
        ('student_school', 'School Student'),
        ('student_college', 'College Student'),
        ('educator', 'Educator/Teacher'),
        ('researcher', 'Researcher'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=255)  # Mandatory
    email = models.EmailField()              # Mandatory
    phone = models.CharField(max_length=20, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    institution = models.CharField(max_length=255, blank=True, null=True, help_text="School, College or Coaching Center")
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='aspirant')
    message = models.TextField()             # Mandatory
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Feedbacks"

    def __str__(self):
        return f"Feedback from {self.name or 'Anonymous'} - {self.created_at.strftime('%Y-%m-%d')}"
