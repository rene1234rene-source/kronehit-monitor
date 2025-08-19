#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kronehit Duplicate Song Monitor
Überwacht die Playlist von Kronehit und sendet Telegram-Nachrichten bei Wiederholungen
zwischen 09:00 und 17:00 Uhr.
"""

import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, time as dt_time
import logging
from typing import List, Dict, Set
import os

# Konfiguration - Aus Umgebungsvariablen lesen
PLAYLIST_URL = "https://onlineradiobox.com/at/kronehit1058/playlist"
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8416243521:AAFGRcNA1bUL538mavZx_AQ25aDnt_b_a3Q')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '7568927725')
CHECK_INTERVAL = 300  # 5 Minuten in Sekunden

# Zeitfenster für Duplikatsprüfung
MONITOR_START_TIME = dt_time(9, 0)   # 09:00
MONITOR_END_TIME = dt_time(17, 0)    # 17:00

# Logging-Konfiguration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def send_telegram_message(message: str) -> bool:
    """
    Sendet eine Nachricht über Telegram Bot API.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 401:
            logger.error("Telegram Bot Token ist ungültig!")
            return False
        response.raise_for_status()
        logger.info("Telegram-Nachricht erfolgreich gesendet")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Fehler beim Senden der Telegram-Nachricht: {e}")
        return False

def fetch_playlist() -> List[Dict[str, str]]:
    """
    Ruft die Playlist von Kronehit ab und extrahiert die Songs.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(PLAYLIST_URL, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        songs = []
        
        track_rows = soup.select('table.tablelist-schedule tr')
        logger.info(f"Gefunden: {len(track_rows)} Tabellenzeilen")
        
        for i, row in enumerate(track_rows):
            try:
                track_element = row.find('a', class_='ajax')
                time_element = row.find('span', class_='time--schedule')
                
                if track_element and time_element:
                    full_title = track_element.get_text(strip=True)
                    time_str = time_element.get_text(strip=True)
                    
                    if full_title and time_str:
                        if ' - ' in full_title:
                            parts = full_title.split(' - ', 1)
                            artist = parts[0].strip()
                            title = parts[1].strip()
                        elif ': ' in full_title:
                            parts = full_title.split(': ', 1)
                            artist = parts[0].strip()
                            title = parts[1].strip()
                        else:
                            artist = "Unbekannt"
                            title = full_title
                        
                        songs.append({
                            'time': time_str,
                            'artist': artist,
                            'title': title,
                            'full_title': full_title
                        })
                            
            except Exception as e:
                logger.warning(f"Fehler beim Parsen von Zeile {i}: {e}")
                continue
        
        logger.info(f"{len(songs)} Songs aus Playlist extrahiert")
        return songs
        
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Playlist: {e}")
        return []

def parse_song_time(time_str: str) -> datetime:
    """Parst die Zeit eines Songs zu einem datetime-Objekt."""
    try:
        for fmt in ['%H:%M:%S', '%H:%M']:
            try:
                time_obj = datetime.strptime(time_str.strip(), fmt)
                return datetime.combine(datetime.now().date(), time_obj.time())
            except ValueError:
                continue
        
        parts = time_str.strip().split(':')
        if len(parts) >= 2:
            hour = int(parts[0])
            minute = int(parts[1])
            return datetime.combine(datetime.now().date(), dt_time(hour, minute))
            
    except (ValueError, IndexError) as e:
        logger.warning(f"Fehler beim Parsen der Zeit '{time_str}': {e}")
    
    return datetime.now()

def is_within_monitor_hours(song_datetime: datetime) -> bool:
    """Prüft, ob ein Song innerhalb der Überwachungszeiten gespielt wurde."""
    song_time = song_datetime.time()
    return MONITOR_START_TIME <= song_time <= MONITOR_END_TIME

def check_for_duplicates(songs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Prüft auf doppelte Songs innerhalb der Überwachungszeiten."""
    duplicates = []
    seen_songs = {}
    
    for song in songs:
        song_datetime = parse_song_time(song['time'])
        
        if not is_within_monitor_hours(song_datetime):
            continue
        
        song_key = f"{song['artist'].lower().strip()} - {song['title'].lower().strip()}"
        
        if song_key in seen_songs:
            previous_times = seen_songs[song_key]
            duplicates.append({
                'artist': song['artist'],
                'title': song['title'],
                'current_time': song['time'],
                'previous_times': previous_times
            })
            logger.warning(f"Duplikat gefunden: {song['artist']} - {song['title']}")
        else:
            seen_songs[song_key] = [song['time']]
    
    return duplicates

def format_duplicate_message(duplicate: Dict[str, str]) -> str:
    """Formatiert eine Telegram-Nachricht für ein gefundenes Duplikat."""
    previous_times_str = ", ".join(duplicate['previous_times'])
    
    message = f"""🎵 <b>Kronehit Wiederholung erkannt!</b>

<b>Song:</b> {duplicate['artist']} - {duplicate['title']}
<b>Aktuelle Zeit:</b> {duplicate['current_time']}
<b>Vorherige Zeiten:</b> {previous_times_str}

<i>Überwachungszeitraum: 09:00 - 17:00 Uhr</i>"""

    return message

def main():
    """Hauptschleife des Monitoring-Programms."""
    logger.info("Kronehit Duplicate Song Monitor gestartet")
    logger.info(f"Überwachungszeiten: {MONITOR_START_TIME.strftime('%H:%M')} - {MONITOR_END_TIME.strftime('%H:%M')}")
    
    # Teste Telegram-Verbindung
    logger.info("Teste Telegram-Verbindung...")
    test_message = "🚀 Kronehit Monitor gestartet!\nÜberwache auf Wiederholungen zwischen 09:00-17:00 Uhr."
    telegram_works = send_telegram_message(test_message)
    
    if not telegram_works:
        logger.error("WARNUNG: Telegram funktioniert nicht!")
    
    while True:
        try:
            logger.info("Rufe Playlist ab...")
            songs = fetch_playlist()
            
            if not songs:
                logger.warning("Keine Songs gefunden")
                time.sleep(60)
                continue
            
            duplicates = check_for_duplicates(songs)
            
            if duplicates:
                logger.info(f"{len(duplicates)} Duplikat(e) gefunden!")
                
                for duplicate in duplicates:
                    message = format_duplicate_message(duplicate)
                    if telegram_works:
                        send_telegram_message(message)
                    else:
                        logger.warning(f"DUPLIKAT: {duplicate['artist']} - {duplicate['title']}")
                    time.sleep(2)
            else:
                logger.info("Keine Duplikate gefunden")
            
            logger.info(f"Warte {CHECK_INTERVAL} Sekunden...")
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("Monitor gestoppt")
            break
        except Exception as e:
            logger.error(f"Fehler: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
