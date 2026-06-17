import os
import json
import requests
import ollama
import feedparser
import random
from bs4 import BeautifulSoup
from icalevents.icalevents import events
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import textwrap
from PIL import Image, ImageDraw, ImageFont
import re

JST = ZoneInfo("Asia/Tokyo")
today = datetime.now(JST).strftime('%Y/%m/%d(%a) %H時')

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_persona(prompt_dir="/home/anna/secretary_project/prompts"):
    """
    promptsフォルダ内の.txtファイルをスキャンし、ランダムに1つ読み込む
    """
    files = [f for f in os.listdir(prompt_dir) if f.endswith('.txt')]

    if not files:
        raise FileNotFoundError(f"{prompt_dir} 内に設定ファイルが見つかりません。")

    selected_file = random.choice(files)
    file_path = os.path.join(prompt_dir, selected_file)

    print(f"今日のペルソナ: {selected_file}")

    config = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        parts = content.split('---')

        settings_section = parts[0]
        for line in settings_section.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                if value.isdigit():
                    value = int(value)
                config[key] = value

        config['prompt'] = parts[1].strip() if len(parts) > 1 else ""

    return config

def get_all_locations_weather(api_key, locations, mode="today"):
    """
    mode="today" なら現在の天気、"tomorrow" なら明日の正午ごろの予報を取得
    """
    weather_reports = []
    target_date = datetime.now(JST).date()
    if mode == "tomorrow":
        target_date += timedelta(days=1)

    label = "今日" if mode == "today" else "明日"

    for key, info in locations.items():
        if mode == "today":
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={info['lat']}&lon={info['lon']}&appid={api_key}&units=metric&lang=ja"
        else:
            url = f"https://api.openweathermap.org/data/2.5/forecast?lat={info['lat']}&lon={info['lon']}&appid={api_key}&units=metric&lang=ja"

        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()

                if mode == "today":
                    desc = data['weather'][0]['description']
                    temp = int(data['main']['temp'])
                    weather_reports.append(f"・{info['name']}: {desc}、気温{temp}度")
                else:
                    forecast_list = data.get('list', [])
                    selected_entry = None

                    for entry in forecast_list:
                        dt = datetime.fromtimestamp(entry['dt'], tz=JST)
                        if dt.date() == target_date and 11 <= dt.hour <= 14:
                            selected_entry = entry
                            break

                    if selected_entry:
                        desc = selected_entry['weather'][0]['description']
                        temp = int(selected_entry['main']['temp'])
                        weather_reports.append(f"・{info['name']}: {desc}、予想気温{temp}度")
                    else:
                        weather_reports.append(f"・{info['name']}: 予報データなし")
            else:
                weather_reports.append(f"・{info['name']}: 取得エラー({response.status_code})")
        except Exception:
            weather_reports.append(f"・{info['name']}: 接続失敗")

    header = f"【{label}の天気】\n"
    return header + "\n".join(weather_reports)

def get_calendar(ical_url, mode="today"):
    """iCalカレンダーから予定を取得（終日予定の重複バグ修正版）"""
    now_jst = datetime.now(JST)
    target_date = now_jst.date()
    if mode == "tomorrow":
        target_date += timedelta(days=1)

    label = "今日" if mode == "today" else "明日"

    search_start = datetime.combine(target_date - timedelta(days=1), datetime.min.time()).replace(tzinfo=JST)
    search_end = datetime.combine(target_date + timedelta(days=1), datetime.max.time()).replace(tzinfo=JST)

    try:
        evts = events(ical_url, start=search_start, end=search_end)

        if not evts:
            return f"{label}の予定は特になし。"

        valid_events = []
        for event in evts:
            if event.all_day:
                # 終日予定はタイムゾーン変換せず、iCalの元データの日付をそのまま使用
                start_date = event.start.date()
                end_date = event.end.date() - timedelta(days=1)
                # ソート用にJST 00:00の時刻を作成
                sort_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=JST)
                event_str = f"・（終日）{event.summary}"
            else:
                # 時間指定の予定はJSTに変換
                e_start_jst = event.start.astimezone(JST)
                e_end_jst = event.end.astimezone(JST)
                start_date = e_start_jst.date()
                end_date = (e_end_jst - timedelta(seconds=1)).date()
                
                sort_datetime = e_start_jst
                start_time = e_start_jst.strftime("%H:%M")
                event_str = f"・{start_time}：{event.summary}"

            # 対象日に収まっているか判定
            if start_date <= target_date <= end_date:
                valid_events.append((sort_datetime, event_str))

        if not valid_events:
            return f"{label}の予定は特になし。"

        # 時刻順にソート
        valid_events.sort(key=lambda x: x[0])
        final_list = [item[1] for item in valid_events]
        return f"{label}の予定は以下の通りです：\n" + "\n".join(final_list)

    except Exception as e:
        return f"カレンダーの取得に失敗しました: {e}"

def get_news_headlines(news_rss_url):
    """GoogleニュースRSSから最新の世相を1件取得し、整形する"""
    try:
        feed = feedparser.parse(news_rss_url)
        headlines = []
        for entry in feed.entries[:1]:
            title = entry.title.split(' - ')[0]
            headlines.append(f"・{title}")
        return "\n".join(headlines) if headlines else "特筆すべき世相の変化は見当たりません。"
    except Exception:
        return "新聞の配達が遅れているようです（ニュース取得失敗）。"

def get_jre_all_status():
    """JR東日本の全路線を調査し、遅延を報告する"""
    url = "https://traininfo.jreast.co.jp/train_info/kanto.aspx"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        items = soup.find_all('li', class_='traininfo-routes__table__item')
        trouble_details = []
        for item in items:
            name_el = item.find('span', class_='traininfo-routes__name')
            info_link = item.find('a', class_='traininfo-routes__info')

            if name_el and info_link:
                line_name = name_el.get_text(strip=True)
                status_text = info_link.find('p', class_='traininfo-routes__status').get_text(strip=True)

                if "平常" not in status_text and "お知らせ" not in status_text:
                    trouble_details.append(f"・{line_name}：{status_text}")

        if not trouble_details:
            return "JR東日本管内、全ての鉄路は平常運転です。"

        return "\n".join(trouble_details)
    except Exception:
        return "運行情報を取得できませんでした。"

def ask_ai(model_name, system_setting, user_prompt):
    response = ollama.chat(model=model_name, messages=[
        {'role': 'system', 'content': system_setting},
        {'role': 'user', 'content': user_prompt}
    ])
    return response['message']['content']

def create_eink_image(raw_text, output_path="/var/www/html/eink/display.raw",
                      font_path="/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                      font_size=18,
                      line_spacing=6):
    
    match = re.search(r'<text_body>(.*?)</text_body>', raw_text, re.DOTALL)
    content = match.group(1).strip() if match else raw_text.strip()

    width, height = 400, 300
    image = Image.new('L', (width, height), 255) 
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    wrap_width = (width // font_size) - 2
    wrapped_lines = []
    for line in content.split('\n'):
        wrapped_lines.extend(textwrap.wrap(line, width=wrap_width))

    max_lines = 10
    if len(wrapped_lines) > max_lines:
        display_lines = wrapped_lines[:max_lines]
        display_lines[-1] = display_lines[-1][:-3] + "..."
    else:
        display_lines = wrapped_lines
    
    formatted_text = "\n".join(display_lines)
    draw.multiline_text((20, 20), formatted_text, font=font, fill=0, spacing=line_spacing) 

    image = image.point(lambda p: 0 if p < 128 else 255)
    image = image.convert('1', dither=Image.NONE)

    # 保存先ディレクトリがなければ作成
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    image.save("/var/www/html/eink/display.bmp")

    raw_data = image.tobytes()
    with open(output_path, "wb") as f:
        f.write(raw_data)
    print(f"RAW書き込み完了: {len(raw_data)} バイト (display.raw)")

def judge_time_slot():
    hour = datetime.now(JST).hour
    if 5 <= hour < 11:
        return "morning"
    elif 11 <= hour < 16:
        return "afternoon"
    else:
        return "night"

def report_morning(config, current_loc_name):
    schedule = get_calendar(config['ical_url'], mode="today")
    all_weather = get_all_locations_weather(config['owm_api_key'], config['locations'], mode="today")
    news = get_news_headlines(config['news_rss_url'])
    train = get_jre_all_status()

    user_prompt = f"""
【朝のブリーフィング】
今日の日付: {today}
場所: {current_loc_name}
今日の天気: {all_weather}
今日の家族の予定: {schedule}
鉄道情報: {train}
ニュース: {news}
指示: 今日一日を元気に始められるよう、必要な情報を整理して伝えてください。
"""
    return user_prompt

def report_afternoon(config, current_loc_name):
    train = get_jre_all_status()
    user_prompt = f"""
【午後の見守り】
現在時刻: {today}
現在の鉄道情報: {train}
指示:最初にポケモンの豆知識を1行追加してください。そして学校から帰ってきた子供を温かく迎え、自己肯定感を高める励ましの言葉を伝えてください。
"""
    return user_prompt

def report_night(config, current_loc_name):
    schedule = get_calendar(config['ical_url'], mode="tomorrow")
    all_weather = get_all_locations_weather(config['owm_api_key'], config['locations'], mode="tomorrow")

    user_prompt = f"""
【夜の振り返りと明日への準備】
場所: {current_loc_name}
明日の天気: {all_weather}
明日の家族の予定: {schedule}
指示:最初にかわいい生き物についての豆知識を1行追加してください。そして今日一日を労いつつ、明日のために優しく語りかけてください。
"""
    return user_prompt

def main():
    config = load_config()
    model_name = config['model_name']
    default_key = config['default_location']
    current_loc_name = config['locations'][default_key]['name']

    persona_config = load_persona()
    persona_prompt = persona_config['prompt']

    mode = judge_time_slot()

    if mode == "morning":
        user_prompt = report_morning(config, current_loc_name)
    elif mode == "afternoon":
        user_prompt = report_afternoon(config, current_loc_name)
    else:
        user_prompt = report_night(config, current_loc_name)

    system_setting = f"""
{persona_prompt}
<ルール>
要約: 出力全体を6行以内にまとめること。
形式: <text_body>タグで囲むこと。Markdown不可。
"""

    report = ask_ai(model_name, system_setting, user_prompt)

    print(f"--- {today} ---")
    print(f"--- Running Mode: {mode} ---")
    print(report)

    f_path = persona_config.get('font_path', "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    f_size = persona_config.get('font_size', 18)
    l_space = persona_config.get('line_spacing', 6)

    create_eink_image(report, font_path=f_path, font_size=f_size, line_spacing=l_space)

    print("--- Create E-ink Report Succeeded ---")

if __name__ == "__main__":
    main()
