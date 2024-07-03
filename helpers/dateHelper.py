from datetime import date
import calendar

def get_current_date() -> str:
    today = date.today()
    return today.strftime("%-d %b %Y")

def get_current_weekday() -> str:
    today = date.today()
    weekday = calendar.day_name[today.weekday()]
    return weekday