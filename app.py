import eventlet
eventlet.monkey_patch()

import math
import os
import time
import uuid
from pathlib import Path
from flask import Flask, render_template, send_file, redirect, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'billard-secret-key-2024')
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / 'dist'

# Durée de vie d'une salle restée en attente d'adversaire (secondes)
ROOM_TTL = 60 * 60

# rooms[room_id] = { 'players': [sid, ...], 'state': 'waiting'|'playing', 'created': float }
rooms: dict = {}


def purge_stale_rooms():
    """Supprime les salles en attente trop anciennes (jamais rejointes ou abandonnées)."""
    now = time.time()
    for room_id, room in list(rooms.items()):
        if room['state'] == 'waiting' and now - room['created'] > ROOM_TTL:
            del rooms[room_id]


def get_player_room(data):
    """Retourne (room_id, room, player_num) si l'émetteur est joueur de la salle, sinon None."""
    if not isinstance(data, dict):
        return None
    room_id = data.get('room_id', '')
    room = rooms.get(room_id)
    if room is None or request.sid not in room['players']:
        return None
    return room_id, room, room['players'].index(request.sid) + 1


def as_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/game')
def game_local():
    return render_template('game.html', room_id=None)

@app.route('/create_room')
def create_room():
    purge_stale_rooms()
    room_id = uuid.uuid4().hex[:8]
    rooms[room_id] = {'players': [], 'state': 'waiting', 'created': time.time()}
    return redirect(f'/game/{room_id}')

@app.route('/game/<room_id>')
def game_online(room_id):
    if room_id not in rooms:
        return redirect('/')
    return render_template('game.html', room_id=room_id)


# ─── Downloads ────────────────────────────────────────────────────────────────

# Les binaires sont publiés dans les GitHub Releases (tag vX.Y.Z → workflow build-binaries).
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'evanhgs/billard-anglais')
RELEASE_URL = f'https://github.com/{GITHUB_REPO}/releases/latest/download'


def download_binary(filename):
    """Sert le binaire depuis dist/ s'il existe localement, sinon redirige vers la dernière release."""
    file_path = DIST_DIR / filename
    if file_path.exists():
        return send_file(file_path, as_attachment=True, download_name=filename)
    return redirect(f'{RELEASE_URL}/{filename}')

@app.route('/download/linux')
def dlinux():
    return download_binary('billard-linux')

@app.route('/download/windows')
def dwindows():
    return download_binary('billard-windows.exe')

@app.route('/download/macos')
def dmacos():
    return download_binary('billard-macos')


# ─── Socket events ────────────────────────────────────────────────────────────

@socketio.on('join_game_room')
def handle_join(data):
    room_id = data.get('room_id', '') if isinstance(data, dict) else ''
    if room_id not in rooms:
        emit('error', {'msg': 'Salle introuvable.'})
        return

    room = rooms[room_id]

    if request.sid in room['players']:
        return

    if len(room['players']) >= 2:
        emit('error', {'msg': 'Salle pleine.'})
        return

    room['players'].append(request.sid)
    join_room(room_id)
    player_num = len(room['players'])  # 1 or 2

    emit('player_assigned', {'player_num': player_num})

    if player_num == 2:
        # Both players present → start the game
        room['state'] = 'playing'
        host_sid = room['players'][0]
        emit('game_start', {'player_num': 1}, to=host_sid)
        emit('game_start', {'player_num': 2})  # to current client


@socketio.on('shoot')
def handle_shoot(data):
    found = get_player_room(data)
    if found is None:
        return
    room_id, room, player_num = found
    if room['state'] != 'playing':
        return
    angle = as_number(data.get('angle'))
    power = as_number(data.get('power'))
    if angle is None or power is None or not 2 <= power <= 20:
        return
    # Relay to the other player only
    emit('opponent_shoot', {
        'angle':      angle,
        'power':      power,
        'player_num': player_num,
    }, to=room_id, include_self=False)


@socketio.on('turn_result')
def handle_turn_result(data):
    """Le tireur envoie l'état final de son tour : l'adversaire s'aligne dessus."""
    found = get_player_room(data)
    if found is None:
        return
    room_id, room, _ = found
    if room['state'] != 'playing':
        return
    balls  = data.get('balls')
    scores = data.get('scores')
    joueur = data.get('joueur')
    if (not isinstance(balls, list) or len(balls) != 3
            or not isinstance(scores, list) or len(scores) != 2
            or joueur not in (1, 2)):
        return
    clean_balls = []
    for ball in balls:
        if not isinstance(ball, dict):
            return
        x, z = as_number(ball.get('x')), as_number(ball.get('z'))
        if x is None or z is None:
            return
        clean_balls.append({'x': x, 'z': z})
    if not all(isinstance(s, int) and not isinstance(s, bool) and s >= 0 for s in scores):
        return
    emit('turn_result', {
        'balls':  clean_balls,
        'scores': scores,
        'joueur': joueur,
    }, to=room_id, include_self=False)


@socketio.on('disconnect')
def handle_disconnect():
    for room_id, room in list(rooms.items()):
        if request.sid in room['players']:
            if room['state'] == 'waiting':
                # Partie pas encore commencée : on libère la place (ex. rechargement
                # de la page par l'hôte) sans détruire la salle.
                room['players'].remove(request.sid)
                leave_room(room_id)
            else:
                emit('opponent_left', {}, to=room_id, include_self=False)
                del rooms[room_id]
            break


if __name__ == '__main__':
    socketio.run(app, debug=True)
