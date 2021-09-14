from flask import Flask, render_template
from waitress import serve
from threading import Thread

app = Flask("AgendaBot")

@app.route('/')
def home():
    return render_template('online.html')

def run():
	serve(app, host='0.0.0.0', port=8080, url_scheme='https')

def keep_alive():
	t = Thread(target=run)
	t.start()
	print("Web server initialized!")