from django.core.management.base import BaseCommand
from background_task.models import Task
from engines.current_affairs.tasks import auto_scrape_and_process_ca
import structlog

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Initializes the perpetual automated Current Affairs pipeline"

    def handle(self, *args, **options):
        self.stdout.write("Checking for existing automation...")

        # Check if task already exists in the queue
        existing_task = Task.objects.filter(
            task_hash__contains="auto_scrape_and_process_ca"
        ).exists()

        if existing_task:
            self.stdout.write(
                self.style.WARNING("Automation is already active in the database.")
            )
        else:
            self.stdout.write("Scheduling Current Affairs Automation...")

            # Schedule to run every 24 hours (86400 seconds)
            auto_scrape_and_process_ca(repeat=86400, repeat_until=None)

            self.stdout.write(
                self.style.SUCCESS("✓ Automation successfully established!")
            )
            self.stdout.write("The worker container will now handle this perpetually.")
