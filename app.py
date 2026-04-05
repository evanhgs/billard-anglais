import eventlet
eventlet.monkey_patch()

import uuid
from pathlib import Path
from flask import Flask, abort, render_template, send_file, redirect, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'billard-secret-key-2024'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / 'dist'

# rooms[room_id] = { 'players': [sid, ...], 'state': 'waiting'|'playing' }
rooms: dict = {}


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/game')
def game_local():
    return render_template('game.html', room_id=None)

@app.route('/create_room')
def create_room():
    room_id = uuid.uuid4().hex[:8]
    rooms[room_id] = {'players': [], 'state': 'waiting'}
    return redirect(f'/game/{room_id}')

@app.route('/game/<room_id>')
def game_online(room_id):
    if room_id not in rooms:
        return redirect('/')
    return render_template('game.html', room_id=room_id)


# ─── Downloads ────────────────────────────────────────────────────────────────

@app.route('/download/linux')
def dlinux():
    file_path = DIST_DIR / 'billard-linux'
    if not file_path.exists():
        abort(404, description='Binaire Linux introuvable.')
    return send_file(file_path, as_attachment=True, download_name='billard-linux')

@app.route('/download/windows')
def dwindows():
    file_path = DIST_DIR / 'billard-windows.exe'
    if not file_path.exists():
        abort(404, description='Binaire Windows introuvable.')
    return send_file(file_path, as_attachment=True, download_name='billard-windows.exe')

@app.route('/download/macos')
def dmacos():
    file_path = DIST_DIR / 'billard-macos'
    if not file_path.exists():
        abort(404, description='Binaire macOS introuvable.')
    return send_file(file_path, as_attachment=True, download_name='billard-macos')


# ─── Socket events ────────────────────────────────────────────────────────────

@socketio.on('join_game_room')
def handle_join(data):
    room_id = data.get('room_id', '')
    if room_id not in rooms:
        emit('error', {'msg': 'Salle introuvable.'})
        return

    room = rooms[room_id]

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
    room_id = data.get('room_id', '')
    if room_id not in rooms:
        return
    room = rooms[room_id]
    if request.sid not in room['players']:
        return
    player_num = room['players'].index(request.sid) + 1
    # Relay to the other player only
    emit('opponent_shoot', {
        'angle':      data['angle'],
        'power':      data['power'],
        'player_num': player_num,
    }, to=room_id, include_self=False)


@socketio.on('disconnect')
def handle_disconnect():
    for room_id, room in list(rooms.items()):
        if request.sid in room['players']:
            emit('opponent_left', {}, to=room_id, include_self=False)
            del rooms[room_id]
            break


if __name__ == '__main__':
    socketio.run(app, debug=True)
