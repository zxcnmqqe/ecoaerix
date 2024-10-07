import os
from dotenv import load_dotenv
import telebot
from telebot import types
import pandas as pd
import geopandas as gpd
import folium
import calendar

load_dotenv()
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(bot_token)

selected_year = None
selected_month = None
selected_day = None

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup(row_width=5)
    for year in range(2019, 2024):
        markup.add(types.InlineKeyboardButton(text=str(year), callback_data=f"year_{year}"))
    bot.send_message(message.chat.id, "Оберіть рік:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("year_"))
def select_year(call):
    global selected_year
    selected_year = int(call.data.split("_")[1])
    months = ['Січень', 'Лютий', 'Березень', 'Квітень', 'Травень', 'Червень',
              'Липень', 'Серпень', 'Вересень', 'Жовтень', 'Листопад', 'Грудень']

    markup = types.InlineKeyboardMarkup(row_width=3)
    for i, month in enumerate(months, start=1):
        markup.add(types.InlineKeyboardButton(text=month, callback_data=f"month_{i}"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=f"Ви обрали {selected_year} рік. Тепер оберіть місяць:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("month_"))
def select_month(call):
    global selected_month
    selected_month = int(call.data.split("_")[1])
    months = ['Січень', 'Лютий', 'Березень', 'Квітень', 'Травень', 'Червень',
              'Липень', 'Серпень', 'Вересень', 'Жовтень', 'Листопад', 'Грудень']
    month_name = months[selected_month - 1].lower()

    days_in_month = calendar.monthrange(selected_year, selected_month)[1]

    markup = types.InlineKeyboardMarkup(row_width=7)
    for day in range(1, days_in_month + 1):
        markup.add(types.InlineKeyboardButton(text=str(day), callback_data=f"day_{day}"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=f"Ви обрали {month_name}. Тепер оберіть день:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("day_"))
def select_day(call):
    global selected_day
    selected_day = int(call.data.split("_")[1])
    formatted_month = f"{selected_month:02d}"
    formatted_day = f"{selected_day:02d}"
    message_text = f"Дані по рівню PM 2.5 на {formatted_day}.{formatted_month}.{selected_year}.\n\nЗа даними https://www.saveecobot.com/"

    create_map(selected_year, selected_month, selected_day)

    with open("kiev_map_with_pm25.html", 'rb') as map_file:
        bot.send_document(call.message.chat.id, map_file)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Обрати іншу дату"))
    bot.send_message(call.message.chat.id, message_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Обрати іншу дату")
def choose_another_date(message):
    start(message)

def create_map(year, mm, dd):
    df = pd.read_csv(rf'data\aqi_pm25_{year}.csv')
    districts = separate_date(chose_kyiv(df))
    day = f"{year}-{mm:02d}-{dd:02d}"
    values = []

    for el in districts:
        e = el[el['date'] == day]
        if not e.empty:
            values.append(round(e['pm25'].mean(), 3))
        else:
            values.append(float('nan'))

    if len(values) != len(districts):
        raise ValueError("Кількість значень PM2.5 не збігається з кількістю районів")

    dfg = gpd.read_file('kyiv.34272c8c.geojson')
    new_gdf = gpd.GeoDataFrame({'NAME': dfg['NAME'], 'pm2.5': values, 'geometry': dfg['geometry']})

    center_lat = 50.4501
    center_lon = 30.5234
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    def style_function(feature):
        pm_value = feature['properties']['pm2.5']
        if pd.isna(pm_value):
            color = 'gray'
        elif pm_value < 20:
            color = 'green'
        elif pm_value < 40:
            color = 'orange'
        else:
            color = 'red'
        return {
            'fillColor': color,
            'color': 'black',
            'weight': 0.5,
            'fillOpacity': 0.6,
        }

    folium.GeoJson(
        new_gdf,
        name='geojson',
        style_function=style_function
    ).add_to(m)

    for _, row in new_gdf.iterrows():
        centroid = row['geometry'].centroid
        name = row['NAME']
        pm_value = row['pm2.5']

        html = f"""
        <div style='font-size: 14px; color: black; text-align: center;'>
            <b style='font-size: 16px; color: darkblue;'>{name}</b><br>
            <span style='font-size: 14px; color: {"green" if pm_value < 35 else "orange" if pm_value < 75 else "red"};'>
                PM2.5: {pm_value if not pd.isna(pm_value) else "Немає даних"} µg/m³
            </span>
        </div>
        """

        folium.Marker(
            location=[centroid.y, centroid.x],
            popup=folium.Popup(html, max_width=250),
            icon=folium.DivIcon(html=html)
        ).add_to(m)

    folium.LayerControl().add_to(m)
    m.save("kiev_map_with_pm25.html")

def chose_kyiv(df):
    golos = df[df['district_id'] == 95]
    darn = df[df['district_id'] == 96]
    desn = df[df['district_id'] == 97]
    dnipr = df[df['district_id'] == 98]
    obolon = df[df['district_id'] == 99]
    pecher = df[df['district_id'] == 100]
    podil = df[df['district_id'] == 101]
    svyatosh = df[df['district_id'] == 102]
    soloma = df[df['district_id'] == 103]
    shev = df[df['district_id'] == 104]

    return [soloma, dnipr, pecher, obolon, podil, darn, desn, golos, svyatosh, shev]

def separate_date(lst):
    res = []
    for el in lst:
        new_date = el['logged_at'].str.split(' ', expand=True)
        new_date.columns = ['date', 'time']
        res.append(pd.concat([el, new_date], axis=1).drop('logged_at', axis=1))
    return res

bot.polling(none_stop=True)