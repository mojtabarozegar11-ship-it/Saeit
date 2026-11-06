from django.core.management.base import BaseCommand
from core.weather_agent import run_daily_cycle

class Command(BaseCommand):
    help = 'Publish a complete attributed MET Norway weather report; original research only when specifically authorized.'
    def handle(self,*args,**options):
        result=run_daily_cycle()
        self.stdout.write(self.style.SUCCESS(f"WEATHER_AGENT=OK DATE={result['date']} PROVINCES={result['provinces']} WEATHER_STORY={result['weather_story_id']} WEATHER_NEW={int(result['weather_created'])} RESEARCH_NEW={result['research_contents_created']}"))
