from django.core.management.base import BaseCommand
from core.weather_agent import run_daily_cycle

class Command(BaseCommand):
    help = 'Generate and publish the daily Iran provincial weather report and two research/technology/education contents.'
    def handle(self,*args,**options):
        result=run_daily_cycle()
        self.stdout.write(self.style.SUCCESS(f"WEATHER_AGENT=OK DATE={result['date']} PROVINCES={result['provinces']} WEATHER_STORY={result['weather_story_id']} RESEARCH_CONTENTS={result['research_contents']}"))
