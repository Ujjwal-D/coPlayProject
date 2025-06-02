# coPlay_zookeeper.py
# Rebuild of coPlay using Zookeeper (Kazoo) instead of ZMQ

from flask import Flask, request
import threading, time, base64, os, signal, json, logging
from kazoo.client import KazooClient
from kazoo.exceptions import NoNodeError

logging.getLogger('werkzeug').disabled = True

zk = KazooClient(hosts='127.0.0.1:2181')
zk.start()

class Webapp:
    def __init__(self, browser_port, peer_id):
        self.peer_id = peer_id
        self.browser_port = browser_port
        self.queue = []

        # Flask app setup
        app = Flask("webapp")
        app.add_url_rule("/", "get_home", self.home, methods=['GET'])
        app.add_url_rule("/update", "get_update", self.updates_get, methods=['GET'])
        app.add_url_rule("/disk", "get_disk", self.disk_get, methods=['GET'])  # Disks already synced
        app.add_url_rule("/tower", "get_tower", self.tower_get, methods=['GET'])
        app.add_url_rule("/message", "post_message", self.message_post, methods=['POST'])
        app.add_url_rule("/shutdown", "get_shutdown", self.shutdown, methods=['GET'])

        self.setup_zookeeper_paths()
        app.run(port=browser_port)

    def setup_zookeeper_paths(self):
        paths = ["/coplay/messages", "/coplay/towers"]
        for path in paths:
            try:
                zk.create(path, b"", makepath=True)
            except:
                pass

    def home(self):
        with open('Wk0_A2_coPlay.html', 'r', encoding="utf-8") as file:
            return file.read()

    def message_post(self):
        # <chat message sync> addition required
        return "ok"

    def tower_get(self):
        # <tower click sync> addition required
        return "ok"

    def disk_get(self):
        # <disk sync already complete> - no changes required
        return "ok"

    def updates_get(self):
        # <message/tower delivery> addition required
        return json.dumps([])

    def shutdown(self):
        return "<a href='/'>Home</a>"

def peer(browser_port, peer_id):
    Webapp(browser_port, peer_id)

# Launch 3 peers
threading.Thread(target=peer, args=(5000, "peer1")).start()
threading.Thread(target=peer, args=(5002, "peer2"), daemon=True).start()
threading.Thread(target=peer, args=(5004, "peer3"), daemon=True).start()
