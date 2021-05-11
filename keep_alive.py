from flask import Flask
from waitress import serve
from threading import Thread

app = Flask("AgendaBot")

@app.route('/')
def home():
    return "AgendaBot is now online!"

def run():
	serve(app, host='0.0.0.0', port=8080, url_scheme='https')

def keep_alive():
	t = Thread(target=run)
	t.start()
	print("Web server initialized!")