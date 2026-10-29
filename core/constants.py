# core/constants.py
from datetime import time

def generate_time_choices(start=8, end=18, step_minutes=30):
    times = []
    current = time(hour=start)
    while current < time(hour=end):
        times.append((current.strftime('%H:%M'), current.strftime('%H:%M')))
        hour = current.hour
        minute = current.minute + step_minutes
        if minute >= 60:
            hour += 1
            minute = minute % 60
        current = time(hour=hour, minute=minute)
    return times

TIME_CHOICES = generate_time_choices()
