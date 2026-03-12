from pathlib import Path
from flask import Flask, abort, render_template, send_file

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / 'dist'


@app.route('/')
def home():
	return render_template('home.html')

@app.route('/game')
def game():
	return render_template('game.html')

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
		abort(404, description='Binaire Windows introuvable. ')
	return send_file(file_path, as_attachment=True, download_name='billard-windows.exe')

@app.route('/download/macos')
def dmacos():
	file_path = DIST_DIR / 'billard-macos'
	if not file_path.exists():
		abort(404, description='Binaire macOS introuvable.')
	return send_file(file_path, as_attachment=True, download_name='billard-macos')


if __name__ == '__main__':
	app.run()
