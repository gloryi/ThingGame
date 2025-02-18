import webbrowser
import json

with open('config.json', encoding = 'utf-8') as f:
    config = json.load(f)

test_players = ["Ann", "Egor", "Gigachad", "Sadist"]

for i in range(config['players_per_game']):
    webbrowser.open(f'http://localhost:8080/?name={test_players[i]}')