import requests
import json
import sqlite3
import config
from TelegramTextApp.TTA_scripts import markdown
from datetime import datetime, timedelta

DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

def now_day(day = None):
    today = datetime.today().weekday()
    if day:
        if day == "tomorrow": 
            today += 1
        if today >= 6:
            today = 0
    return DAYS[today]

def SQL_request(request, params=(), all_data=None):  # Выполнение SQL-запросов
    connect = sqlite3.connect("database.db")
    cursor = connect.cursor()
    if request.strip().lower().startswith('select'):
        cursor.execute(request, params)
        if all_data == None: result = cursor.fetchone()
        else: result = cursor.fetchall()
        connect.close()
        return result
    else:
        cursor.execute(request, params)
        connect.commit()
        connect.close()

def create_users():
    SQL_request("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER,
        complex TEXT,
        user_group TEXT
    )""")

create_users()

def newsletter(tta_data):
    pass

def formating_text(tta_data, text, edit=None):
    try: user_id = tta_data["telegram_data"].message.chat.id
    except: user_id = tta_data["telegram_data"].chat.id
    user = SQL_request("SELECT * FROM users WHERE id = ?", (user_id,))
    if user is None:
        bot_registration(tta_data)
        user = SQL_request("SELECT * FROM users WHERE id = ?", (user_id,))
    text = text.format(
            user_group=user[2],
            day_week=now_day(),
            input_text=tta_data["call_data"].get("input_text"),
        )
    return text


def save_complex(tta_data):
    user_id = tta_data["telegram_data"].message.chat.id
    data = tta_data["call_data"]["data"]
    if data:
        SQL_request("UPDATE users SET complex = ? WHERE id = ?", (data, user_id))

def bot_registration(tta_data):
    try: user_id = tta_data["telegram_data"].message.chat.id
    except: user_id = tta_data["telegram_data"].chat.id
    user = SQL_request("SELECT * FROM users WHERE id = ?", (user_id,))
    if user is None:
        SQL_request("INSERT INTO users (id) VALUES (?)", (user_id,))

def format_schedule_to_text(schedule, week=None):
    result = ""
    for date, lessons in schedule.items():
        if week:
            result += f"\n*{date}*\n"
            result += f"*————————————————*\n"
        else:
            result += f"\n*{date}*\n\n"
        for lesson_num, details in lessons.items():
            time_start = details['time_start']
            time_finish = details['time_finish']
            for lesson_name, teachers in details['lessons'].items():
                result += f"*{lesson_num}*    _{markdown(time_start)} \- {markdown(time_finish)}_\n"
                teacher = list(teachers.keys())[0]
                result += f"*Предмет:* {markdown(lesson_name, True)}\n"
                result += f"_*Преподаватель:*_ {markdown(teacher, True)}\n"
                result += "\n"
    return result

def get_courses(tta_data):
    url = 'https://falpin.ru/api/get_groups'
    data = {"group": "ИСП-8-21"}
    response = requests.get(url)
    groups = json.loads(response.text)
    user_id = tta_data["telegram_data"].message.chat.id
    

    complex_name = tta_data["call_data"]["data"]
    if complex_name == None:
        complex_name = SQL_request("SELECT complex FROM users WHERE id = ?", (user_id,))[0]
    if complex_name == "ros": complex_name = "Российская"
    if complex_name == "blux": complex_name = "Блюхера"

    filtered_data = {key: value for key, value in groups.items() if value['complex'] == complex_name}

    unique_courses = set()
    for key, value in filtered_data.items():
        unique_courses.add(value['course'])

    buttons = {}
    for i in range(len(unique_courses)):
        buttons[f'select_group:{i+1}'] = f"{i+1} курс"

    return buttons

def select_group(tta_data=None):
    url = 'https://falpin.ru/api/get_groups'
    data = {"group": "ИСП-8-21"}
    response = requests.get(url)
    groups = json.loads(response.text)
    user_id = tta_data["telegram_data"].message.chat.id

    select_course = tta_data["call_data"]["data"]
    complex_name = SQL_request("SELECT complex FROM users WHERE id = ?", (user_id,))[0]
    if complex_name == "ros": complex_name = "Российская"
    if complex_name == "blux": complex_name = "Блюхера"

    filtered_data = {key: value for key, value in groups.items() if value['complex'] == complex_name}
    filtered_groups = {key: value for key, value in filtered_data.items() if value['course'] == f"{select_course} курс"}

    buttons = {}
    for group_name in filtered_groups:
        buttons[f'select_schedule:{group_name}'] = group_name

    return buttons

def insert_group(tta_data):
    if tta_data['call_data']["data"]:
        user_id = tta_data["telegram_data"].message.chat.id
        SQL_request("UPDATE users SET user_group = ? WHERE id = ?", (tta_data["call_data"]["data"], user_id))

def schedule(tta_data):
    text = "Расписание не найдено :\("
    url = 'https://falpin.ru/api/get_schedule'
    try:user_id = tta_data["telegram_data"].message.chat.id
    except:user_id = tta_data["telegram_data"].chat.id

    user_group = SQL_request("SELECT user_group FROM users WHERE id = ?", (user_id,))[0]
    if user_group is None:
        return "Сначала выберите группу\!"
    data = {"group": user_group}
    response = requests.post(url, json=data)
    schedule = json.loads(response.text)
    
    if tta_data["call_data"]["data"] == "today":
       tta_data["call_data"]["data"] = now_day("day")
    elif  tta_data["call_data"]["data"] == "tomorrow":
       tta_data["call_data"]["data"] = now_day("tomorrow") 

    if tta_data["call_data"]["data"] == 'full':
        text = format_schedule_to_text(schedule['schedule'], week=True)
    else:
        for date, info in schedule['schedule'].items():
            if tta_data["call_data"]["data"] in date:
                text = format_schedule_to_text( {date: info})
    tta_data["menu_data"]["text"] = text
    return tta_data

if __name__ == "__main__":
    VERSION ="2.2.0"
    print(f"Версия бота: {VERSION}")
    from TelegramTextApp import TTA
    TTA.start(config.API, "menus", debug=True, tta_experience=True, formating_text="formating_text", app=False)