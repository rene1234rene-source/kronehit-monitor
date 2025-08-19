#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kronehit Duplicate Song Monitor
Überwacht die Playlist von Kronehit und sendet Telegram-Nachrichten bei Wiederholungen
zwischen 09:00 und 17:00 Uhr (Deutsche Zeit).
"""

import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, time as dt_time
import logging
from typing import List, Dict, Set
from zoneinfo import ZoneInfo

# Konfiguration
PLAYLIST_URL = "https://onlineradiobox.com/at/kronehit1058/playlist"
TELEGRAM_TOKEN = '8416243521:AAFRZt4PnQhkTA_QLUqgP9_H7JiPLZZZ2y8'
TELEGRAM_CHAT_ID = '7568927725'
CHECK_INTERVAL = 180  # 3 Minuten in Sekunden
DUPLICATE_CHECK_INTERVAL = 180  # 3 Minuten nach Duplikat-Fund

# Deutsche Zeitzone
GERMAN_TZ = ZoneInfo("Europe/Berlin")

# Zeitfenster für Duplikatsprüfung (Deutsche Zeit)
MONITOR_START_TIME = dt_time(9, 0)   # 09:00
MONITOR_END_TIME = dt_time(17, 0)    # 17:00
END_NOTIFICATION_TIME = dt_time(17, 0)  # 17:00 für Tagesabschluss-Nachricht

# Logging-Konfiguration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kronehit_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_german_time() -> datetime:
    """
    Gibt die aktuelle Zeit in deutscher Zeitzone zurück.
    
    Returns:
        datetime: Aktuelle Zeit in Europa/Berlin Zeitzone
    """
    return datetime.now(GERMAN_TZ)


def send_telegram_message(message: str) -> bool:
    """
    Sendet eine Nachricht über Telegram Bot API.
    
    Args:
        message (str): Die zu sendende Nachricht
        
    Returns:
        bool: True wenn erfolgreich gesendet, False sonst
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
            logger.error("Telegram Bot Token ist ungültig! Bitte Token überprüfen.")
            logger.error("Tipp: Bot mit @BotFather neu erstellen oder Token prüfen")
            return False
        response.raise_for_status()
        logger.info("Telegram-Nachricht erfolgreich gesendet")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Fehler beim Senden der Telegram-Nachricht: {e}")
        if "401" in str(e):
            logger.error("WICHTIG: Bot Token ist ungültig oder Bot wurde nicht gestartet!")
        return False


def fetch_playlist() -> List[Dict[str, str]]:
    """
    Ruft die Playlist von Kronehit ab und extrahiert die Songs.
    
    Returns:
        List[Dict[str, str]]: Liste mit Dictionaries {'artist': str, 'title': str, 'time': str}
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(PLAYLIST_URL, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        songs = []
        
        # Verwende die korrekten Selektoren aus Ihrem funktionierenden Skript
        track_rows = soup.select('table.tablelist-schedule tr')
        logger.info(f"Gefunden: {len(track_rows)} Tabellenzeilen")
        
        for i, row in enumerate(track_rows):
            try:
                # Songtitel aus <a class="ajax">
                track_element = row.find('a', class_='ajax')
                # Uhrzeit aus <span class="time--schedule">
                time_element = row.find('span', class_='time--schedule')
                
                if track_element and time_element:
                    full_title = track_element.get_text(strip=True)
                    time_str = time_element.get_text(strip=True)
                    
                    if full_title and time_str:
                        # Versuche Artist und Title zu trennen
                        # Übliche Formate: "Artist - Title" oder "Artist: Title"
                        if ' - ' in full_title:
                            parts = full_title.split(' - ', 1)
                            artist = parts[0].strip()
                            title = parts[1].strip()
                        elif ': ' in full_title:
                            parts = full_title.split(': ', 1)
                            artist = parts[0].strip()
                            title = parts[1].strip()
                        else:
                            # Fallback: Alles als Titel, Artist leer
                            artist = "Unbekannt"
                            title = full_title
                        
                        songs.append({
                            'time': time_str,
                            'artist': artist,
                            'title': title,
                            'full_title': full_title  # Für Debugging
                        })
                        
                        if i < 3:  # Debug für erste 3 Songs
                            logger.info(f"Song {i+1}: {time_str} - {artist} - {title}")
                            
            except Exception as e:
                logger.warning(f"Fehler beim Parsen von Zeile {i}: {e}")
                continue
        
        logger.info(f"{len(songs)} Songs aus Playlist extrahiert")
        return songs
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Fehler beim Abrufen der Playlist: {e}")
        return []
    except Exception as e:
        logger.error(f"Unerwarteter Fehler beim Parsen der Playlist: {e}")
        return []


def parse_song_time(time_str: str) -> datetime:
    """
    Parst die Zeit eines Songs zu einem datetime-Objekt in deutscher Zeitzone.
    
    Args:
        time_str (str): Zeit-String (z.B. "14:30" oder "14:30:15")
        
    Returns:
        datetime: Datetime-Objekt mit heutigem Datum in deutscher Zeitzone
    """
    try:
        # Verschiedene Zeitformate berücksichtigen
        for fmt in ['%H:%M:%S', '%H:%M']:
            try:
                time_obj = datetime.strptime(time_str.strip(), fmt)
                # Erstelle datetime in deutscher Zeitzone
                german_time = get_german_time()
                return datetime.combine(german_time.date(), time_obj.time(), GERMAN_TZ)
            except ValueError:
                continue
        
        # Fallback: Nur Stunden und Minuten extrahieren
        parts = time_str.strip().split(':')
        if len(parts) >= 2:
            hour = int(parts[0])
            minute = int(parts[1])
            german_time = get_german_time()
            return datetime.combine(german_time.date(), dt_time(hour, minute), GERMAN_TZ)
            
    except (ValueError, IndexError) as e:
        logger.warning(f"Fehler beim Parsen der Zeit '{time_str}': {e}")
    
    return get_german_time()


def is_within_monitor_hours(song_datetime: datetime) -> bool:
    """
    Prüft, ob ein Song innerhalb der Überwachungszeiten (09:00-17:00) gespielt wurde.
    
    Args:
        song_datetime (datetime): Zeitpunkt des Songs
        
    Returns:
        bool: True wenn innerhalb der Überwachungszeit
    """
    song_time = song_datetime.time()
    return MONITOR_START_TIME <= song_time <= MONITOR_END_TIME


def check_for_duplicates(songs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Prüft auf doppelte Songs innerhalb der Überwachungszeiten.
    
    Args:
        songs (List[Dict[str, str]]): Liste der Songs
        
    Returns:
        List[Dict[str, str]]: Liste der doppelten Songs mit zusätzlicher Info
    """
    duplicates = []
    seen_songs = {}  # Dict: song_key -> [list of times]
    
    for song in songs:
        song_datetime = parse_song_time(song['time'])
        
        # Nur Songs innerhalb der Überwachungszeiten berücksichtigen
        if not is_within_monitor_hours(song_datetime):
            continue
        
        # Eindeutigen Schlüssel für Song erstellen (Artist + Title, normalisiert)
        song_key = f"{song['artist'].lower().strip()} - {song['title'].lower().strip()}"
        
        if song_key in seen_songs:
            # Duplikat gefunden!
            previous_times = seen_songs[song_key]
            duplicates.append({
                'artist': song['artist'],
                'title': song['title'],
                'current_time': song['time'],
                'previous_times': previous_times
            })
            logger.warning(f"Duplikat gefunden: {song['artist']} - {song['title']} um {song['time']}")
        else:
            seen_songs[song_key] = [song['time']]
    
    return duplicates


def format_duplicate_message(duplicate: Dict[str, str]) -> str:
    """
    Formatiert eine Telegram-Nachricht für ein gefundenes Duplikat.
    
    Args:
        duplicate (Dict[str, str]): Duplikat-Information
        
    Returns:
        str: Formatierte Nachricht
    """
    previous_times_str = ", ".join(duplicate['previous_times'])
    german_time = get_german_time()
    
    message = f"""🚨 <b>DUPLIKAT GEFUNDEN!</b> 🚨

<b>Song:</b> {duplicate['artist']} - {duplicate['title']}
<b>Vorherige Zeit(en):</b> {previous_times_str}
<b>Aktuelle Zeit:</b> {duplicate['current_time']}
<b>Deutsche Zeit:</b> {german_time.strftime('%H:%M:%S')}

🔥 <b>RUF SCHNELL KRONEHIT AN!</b> 🔥
📞 Aktualisierungszeit auf alle 3 Minuten ändern!

⏰ <i>Überwachung: 09:00 - 17:00 Uhr (Deutsche Zeit)</i>
🎯 <i>Du bist der Erste, der es weiß!</i>"""

    return message


def main_loop():
    """
    Hauptschleife des Monitoring-Programms.
    """
    logger.info("Kronehit Duplicate Song Monitor gestartet")
    logger.info(f"Überwachungszeiten: {MONITOR_START_TIME.strftime('%H:%M')} - {MONITOR_END_TIME.strftime('%H:%M')} (Deutsche Zeit)")
    logger.info(f"Check-Interval: {CHECK_INTERVAL} Sekunden")
    
    # Status-Variablen für tägliche Benachrichtigungen
    start_notification_sent_today = False
    end_notification_sent_today = False
    duplicates_found_today = False
    current_check_interval = CHECK_INTERVAL
    last_date = get_german_time().date()
    
    # Teste Telegram-Verbindung
    logger.info("Teste Telegram-Verbindung...")
    german_time = get_german_time()
    startup_message = f"""🚀 <b>Kronehit Monitor gestartet!</b>

📊 System läuft und überwacht 24/7
⏰ Benachrichtigungen: 09:00 (Start) & 17:10 (Ende)
🕐 Deutsche Zeit: {german_time.strftime('%H:%M:%S')}
🌍 Zeitzone: Europe/Berlin"""
    telegram_works = send_telegram_message(startup_message)
    
    if not telegram_works:
        logger.error("WARNUNG: Telegram funktioniert nicht! Monitor läuft trotzdem weiter.")
    
    while True:
        try:
            # Verwende deutsche Zeit für alle Zeitberechnungen
            current_time = get_german_time()
            current_date = current_time.date()
            current_time_only = current_time.time()
            
            # Debug-Log alle 30 Minuten
            if current_time.minute % 30 == 0 and current_time.second < 30:
                logger.info(f"Deutsche Zeit: {current_time.strftime('%H:%M:%S')} | Server Zeit: {datetime.now().strftime('%H:%M:%S')}")
            
            # Neuer Tag? Reset der Status-Variablen
            if current_date != last_date:
                start_notification_sent_today = False
                end_notification_sent_today = False
                duplicates_found_today = False
                current_check_interval = CHECK_INTERVAL  # Zurück auf 3 Minuten
                last_date = current_date
                logger.info(f"Neuer Tag (Deutsche Zeit): {current_date}")
            
            # 09:00 Start-Benachrichtigung (Deutsche Zeit)
            if (current_time_only >= MONITOR_START_TIME and 
                current_time_only < dt_time(9, 5) and  # Nur bis 09:05
                not start_notification_sent_today and telegram_works):
                
                start_message = f"""🌅 <b>Guten Morgen!</b>

📅 <b>Datum:</b> {current_date.strftime('%d.%m.%Y')}
⏰ <b>Deutsche Zeit:</b> {current_time.strftime('%H:%M:%S')}
🌍 <b>Zeitzone:</b> Europe/Berlin

🎵 <b>Kronehit Duplikat-Überwachung startet!</b>
🔍 Ab jetzt gilt es, Duplikate zwischen 09:00-17:00 zu finden!

🚀 <i>System bereit - viel Erfolg heute!</i>"""
                
                send_telegram_message(start_message)
                start_notification_sent_today = True
                logger.info("Start-Benachrichtigung für heute gesendet")
            
            # 17:10 Ende-Benachrichtigung (nur wenn keine Duplikate gefunden)
            if (current_time_only >= dt_time(17, 10) and  # 17:10 für Ende-Nachricht
                current_time_only < dt_time(17, 15) and  # Nur bis 17:15
                not end_notification_sent_today and 
                not duplicates_found_today and telegram_works):
                
                end_message = f"""🌅 <b>Tagesabschluss</b>

📅 <b>Datum:</b> {current_date.strftime('%d.%m.%Y')}
⏰ <b>Überwachungszeit:</b> 09:00 - 17:00 Uhr (Deutsche Zeit)
🕐 <b>Aktuelle Zeit:</b> {current_time.strftime('%H:%M:%S')}

✅ <b>Heute war kein Duplikat dabei!</b>
🎵 Kronehit hat heute keine Songs wiederholt.

🌙 <i>Vielleicht morgen... System läuft weiter!</i>"""
                
                send_telegram_message(end_message)
                end_notification_sent_today = True
                logger.info("Tagesabschluss-Benachrichtigung gesendet")
            
            # Playlist nur während der Überwachungszeit prüfen (Deutsche Zeit)
            if MONITOR_START_TIME <= current_time_only <= MONITOR_END_TIME:
                logger.info(f"Rufe Playlist ab... (Deutsche Zeit: {current_time.strftime('%H:%M:%S')})")
                songs = fetch_playlist()
                
                if not songs:
                    logger.warning("Keine Songs gefunden")
                    time.sleep(60)
                    continue
                
                duplicates = check_for_duplicates(songs)
                
                if duplicates:
                    logger.info(f"{len(duplicates)} Duplikat(e) gefunden!")
                    duplicates_found_today = True
                    
                    # Wechsel auf 3-Minuten-Intervall nach Duplikat-Fund
                    current_check_interval = DUPLICATE_CHECK_INTERVAL
                    
                    for duplicate in duplicates:
                        message = format_duplicate_message(duplicate)
                        if telegram_works:
                            send_telegram_message(message)
                        else:
                            logger.warning(f"DUPLIKAT: {duplicate['artist']} - {duplicate['title']}")
                        time.sleep(2)
                    
                    logger.info(f"Check-Interval auf {current_check_interval} Sekunden reduziert")
                else:
                    logger.info("Keine Duplikate in Überwachungszeit gefunden")
            else:
                # Außerhalb der Überwachungszeit - weniger häufige Logs
                if current_time.minute % 30 == 0:  # Alle 30 Minuten eine Info
                    logger.info(f"Außerhalb Überwachungszeit (Deutsche Zeit: {current_time_only.strftime('%H:%M')}). Nächste Überwachung: 09:00")
            
            logger.info(f"Warte {current_check_interval} Sekunden bis zum nächsten Check...")
            time.sleep(current_check_interval)
            
        except KeyboardInterrupt:
            logger.info("Monitor durch Benutzer gestoppt")
            if telegram_works:
                german_time = get_german_time()
                stop_message = f"⏹️ <b>Kronehit Monitor gestoppt</b>\n\n🔧 <i>System wurde manuell beendet</i>\n🕐 <i>Deutsche Zeit: {german_time.strftime('%H:%M:%S')}</i>"
                send_telegram_message(stop_message)
            break
        except Exception as e:
            logger.error(f"Unerwarteter Fehler in Hauptschleife: {e}")
            time.sleep(60)  # Warte 1 Minute bei Fehlern


if __name__ == "__main__":
    main_loop()
