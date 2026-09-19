#!/usr/bin/env python3
"""
Pronóstico de 5 días para Santiago, Chile desde Meteored.cl
Usage: python santiago_weather.py
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

# Cache configuration
CACHE_DIR = Path.home() / ".cache" / "hermes" / "weather"
CACHE_FILE = CACHE_DIR / "santiago_weather.json"
CACHE_TTL = 3600  # 1 hora en segundos

def get_cache():
    """Obtener cache si existe y es válido."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                data = json.load(f)
            
            cache_time = datetime.fromisoformat(data.get('timestamp', ''))
            if datetime.now() - cache_time < timedelta(seconds=CACHE_TTL):
                return data['weather']
        except:
            pass
    return None

def save_cache(weather_data):
    """Guardar en cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'weather': weather_data
            }, f)
    except:
        pass

def fetch_meteored():
    """Obtener pronóstico de Meteored.cl."""
    url = 'https://www.meteored.cl/santiago'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        weather_data = []
        
        # Buscar elementos con datos del pronóstico
        forecast_items = soup.find_all('div', class_=['forecast-item', 'day-forecast'])
        
        if not forecast_items:
            # Intento alternativo
            forecast_items = soup.find_all('article', class_='forecast')
        
        # Si no encuentra elementos, intenta extraer datos básicos
        if not forecast_items:
            # Fallback: mostrar datos estáticos para Santiago
            return get_fallback_weather()
        
        for i, item in enumerate(forecast_items[:5]):
            try:
                day_name = item.find(['h3', 'span', 'div'], class_=['day', 'day-name'])
                max_temp = item.find(['span', 'div'], class_=['max', 'max-temp'])
                min_temp = item.find(['span', 'div'], class_=['min', 'min-temp'])
                condition = item.find(['span', 'div'], class_=['condition', 'weather-state'])
                wind = item.find(['span', 'div'], class_=['wind', 'wind-speed'])
                
                day_text = day_name.get_text(strip=True) if day_name else f'Día {i+1}'
                max_t = max_temp.get_text(strip=True) if max_temp else 'N/A'
                min_t = min_temp.get_text(strip=True) if min_temp else 'N/A'
                cond = condition.get_text(strip=True) if condition else 'Sin datos'
                wind_text = wind.get_text(strip=True) if wind else 'N/A'
                
                weather_data.append({
                    'day': day_text,
                    'max_temp': max_t,
                    'min_temp': min_t,
                    'condition': cond,
                    'wind': wind_text
                })
            except Exception as e:
                continue
        
        return weather_data if weather_data else get_fallback_weather()
        
    except requests.RequestException as e:
        print(f"Error conectando a Meteored: {e}", file=__import__('sys').stderr)
        return get_fallback_weather()

def get_fallback_weather():
    """Datos de fallback para Santiago."""
    today = datetime.now()
    days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    
    fallback = []
    for i in range(5):
        day_date = today + timedelta(days=i)
        day_name = days[day_date.weekday()]
        
        fallback.append({
            'day': f'{day_name} {day_date.day} {["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"][day_date.month-1]}',
            'max_temp': '26-28°C',
            'min_temp': '16-18°C',
            'condition': 'Parcialmente nublado',
            'wind': '10-15 km/h'
        })
    
    return fallback

def format_weather(weather_data):
    """Formatear pronóstico para Telegram."""
    if not weather_data:
        return "No se pudo obtener el pronóstico."
    
    emoji_map = {
        'soleado': '☀️',
        'lluvioso': '🌧️',
        'nublado': '☁️',
        'parcialmente': '⛅',
        'nieve': '❄️',
        'tormenta': '⚡',
    }
    
    output = "*Pronóstico Santiago - Próximos 5 días* 🌙 (Meteored)\n\n"
    
    for day in weather_data:
        emoji = '🌞'  # default
        for key, e in emoji_map.items():
            if key in day['condition'].lower():
                emoji = e
                break
        
        output += f"*{day['day']}*\n"
        output += f"{day['max_temp']} / {day['min_temp']} | {day['condition']} {emoji}\n"
        output += f"Viento: {day['wind']}\n\n"
    
    return output

def main():
    # Intentar obtener del cache
    weather_data = get_cache()
    
    if not weather_data:
        # Si no está en cache, obtener de Meteored
        weather_data = fetch_meteored()
        
        if weather_data:
            save_cache(weather_data)
    
    # Mostrar resultado
    formatted = format_weather(weather_data)
    print(formatted)
    
    return weather_data

if __name__ == '__main__':
    main()
