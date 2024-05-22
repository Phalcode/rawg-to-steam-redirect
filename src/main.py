import os
import re
import logging
import bleach
import requests
import html
import sqlite3
import json
import datetime
from time import time, strftime
from flask import Flask, jsonify, request, redirect
from dateutil import parser
from steam_web_api import Steam
from waitress import serve

default_language = os.environ.get("R2S_LANG", "english")
log_level = int(os.environ.get("R2S_LOG_LEVEL", logging.INFO))

app = Flask(__name__)
logger = logging.getLogger()
logger.setLevel(log_level)

sanitizer = bleach.sanitizer.Cleaner(tags=[], attributes=[], strip=True, strip_comments=True, filters=[], protocols=[])

conn = sqlite3.connect('./database.sqlite', check_same_thread=False)
cursor = conn.cursor()
    
#region Utility
def clean_string(string):
    string = html.unescape(string)
    string = sanitizer.clean(string)
    string = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', string)
    string = re.sub(r'\s+', ' ', string)
    string = string.encode('ascii', 'ignore').decode('unicode_escape')
    return string

def retry_request(url, retries=3):
    for _ in range(retries):
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to retrieve data. Status code: {response.status_code}")
            time.sleep(1)
    logger.error("Failed to retrieve data after multiple attempts.")
    return None
#endregion

#region Business Logic
def get_steam_app_details(app_id, lang_parameter=default_language):
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l={lang_parameter}"
    cached_data = get_cached_data(url)
    if cached_data:
        increment_stat('games_from_cache')
        return cached_data

    data = retry_request(url)
    app.logger.debug(data)
    if data and data.get(str(app_id), {}).get("success", False) == True:
        cache_data(url, json.dumps(data))
        return data
    else:
        logger.error("Failed to retrieve data.")
        return None

def get_game_tags(app_id):
    url = f"https://steamspy.com/api.php?request=appdetails&appid={app_id}"
    cached_data = get_cached_data(url)
    if cached_data:
        return cached_data

    data = retry_request(url)
    if data and "tags" in data:
        tags = data.get("tags", [])
        game_tags = [{"id": tag_id, "name": tag_name, "language": "eng"} for tag_name, tag_id in tags.items()]
        app.logger.debug(data)
        cache_data(url, json.dumps(game_tags))
        return game_tags
    else:
        logger.error("Failed to retrieve tags.")
        return None

def test_url(url):
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

def fix_bg_url(game_data):
    bg_option1 = game_data["background_raw"]
    bg_option2 = game_data["background"]
    bg_option3 = game_data["screenshots"][0]["path_full"]

    if test_url(bg_option1):
        return bg_option1
    elif test_url(bg_option2):
        return bg_option2
    elif test_url(bg_option3):
        return bg_option3
    else:
        return None



def map_game(game_data, app_id): 
    new_background_image = fix_bg_url(game_data)       
    return {
        "id": game_data["steam_appid"],
        "name": clean_string(game_data["name"]),
        "slug": clean_string(game_data["name"]).lower().replace(" ", "-"),
        "background_image": new_background_image,
        "box_image": f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/library_600x900_2x.jpg",
        "description_raw": clean_string(game_data.get("detailed_description", "")),
        "metacritic": game_data.get("metacritic", {}).get("score", None),
        "website": game_data.get("website", None),
        "genres": [{"id": int(genre.get("id", None)), "name": genre.get("description", None)} for genre in game_data.get("genres", [])],
        "tags": [{"id": int(tag.get("id", None)), "name": tag.get("description", None), "language": "eng"} for tag in game_data.get("categories", [])],
        "released": parser.parse(game_data.get("release_date", {}).get("date", None)).strftime('%Y-%m-%dT%H:%M:%SZ') if game_data.get("release_date", {}).get("date", None) else None,
        "developers": [{"id": abs(hash(dev)) % (10 ** 9), "name": dev} for dev in game_data.get("developers", [])],
        "publishers": [{"id": abs(hash(pub)) % (10 ** 9), "name": pub} for pub in game_data.get("publishers", [])],
    }
#endregion

#region Cache
def cache_data(url, data):
    cursor.execute("REPLACE INTO cache (url, data, timestamp) VALUES (?, ?, ?)", (url, data, time()))
    conn.commit()
    logger.debug(f"Cached data for {url}")

def get_cached_data(url):
    cursor.execute("SELECT data, timestamp FROM cache WHERE url = ?", (url,))
    result = cursor.fetchone()

    if result:
        data, timestamp = result
        if time() - timestamp <= 30 * 24 * 3600:
            logger.debug(f"Retrieved cached data for {url}")
            return json.loads(data)
    return None

def increment_stat(stat, amount=1):
    cursor.execute("INSERT OR IGNORE INTO stats (stat, count) VALUES (?, 0)", (stat,))
    cursor.execute("UPDATE stats SET count = count + ? WHERE stat = ?", (amount, stat))
    conn.commit()
#endregion


@app.route("/api/games", methods=["GET"])
def search_steam_games():
    search = request.args.get("search", "")
    steam = Steam("")
    steam_games = steam.apps.search_games(search)
    app.logger.debug(steam_games)
    formatted_games = {
        "count": len(steam_games["apps"]),
        "results": [
            {
                "id": game["id"][0],
                "slug": clean_string(game["name"]).lower().replace(" ", "-"),
                "name": clean_string(game["name"]),
                "background_image": f"https://cdn.akamai.steamstatic.com/steam/apps/{game['id'][0]}/header.jpg",
                "platforms": [{"platform": {"id": 1, "name": "Steam"}}],
                "box_art": f"https://steamcdn-a.akamaihd.net/steam/apps/{game['id'][0]}/library_600x900_2x.jpg"
            }
            for game in steam_games["apps"]
        ]
    }
    increment_stat('searches')
    increment_stat('search_results', len(steam_games["apps"]))
    return jsonify(formatted_games)

@app.route("/api/games/<int:app_id>", methods=["GET"])
def get_steam_game(app_id):
    steam_game = get_steam_app_details(app_id, request.args.get("lang", default_language))
    if not steam_game:
        return jsonify({"error": "Game not found"}), 404
    game_data = steam_game.get(str(app_id), {}).get("data", {})
    mapped_game = map_game(game_data, app_id)
    tags = get_game_tags(app_id)
    if tags:
        mapped_game.setdefault("tags", []).extend(tags)
    increment_stat('games')
    return jsonify(mapped_game)

@app.route("/api/stats")
def stats():
    cursor.execute("SELECT * FROM stats")
    stats_data = cursor.fetchall()
    style_string ="<head><link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css'/></head>"
    stats_string = "<br>".join([f"✅ {stat[0]}: {stat[1]}" for stat in stats_data])
    return f"{style_string}<h1>🙏 This rawg-to-steam-redirect instance has proudly served: ✨</h1>{stats_string}"

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def help(path):
    return redirect("https://github.com/Phalcode/rawg-to-steam-redirect", code=302)

@app.after_request
def log_request(response):
    timestamp = strftime("[%Y-%b-%d %H:%M]")
    original_ip = request.environ.get("HTTP_X_FORWARDED_FOR", request.environ.get("HTTP_X_REAL_IP", request.remote_addr))
    app.logger.error("%s %s %s %s %s %s", timestamp, original_ip, request.method, request.scheme, request.path, response.status)
    return response

if __name__ == "__main__":
    #Init
    cursor.execute('''CREATE TABLE IF NOT EXISTS cache (url TEXT PRIMARY KEY, data TEXT, timestamp REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS stats (stat TEXT PRIMARY KEY, count INTEGER)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_url ON cache (url)''')
    #Migrations
    cursor.execute('''DROP TABLE IF EXISTS games''')
    cursor.execute('''DROP TABLE IF EXISTS games_v2''')
    cursor.execute('''DELETE FROM cache WHERE timestamp < 1715249693''')
    conn.commit()
    serve(app, host="0.0.0.0", port=9999)
