# coPlay_zookeeper.py
# Zookeeper-based coPlay with chat message sync (Issue 2)

from flask import Flask, request
import threading, base64, json, os, signal, logging
from kazoo.client import KazooClient

logging.basicConfig(level=logging.INFO)
logging.getLogger('werkzeug').disabled = True

print("Connecting to Zookeeper at 127.0.0.1:2181...")
zk = KazooClient(hosts='127.0.0.1:2181')
zk.start(timeout=10)
print("Connected to Zookeeper.")

class Webapp:
    def __init__(self, browser_port, peer_id):
        self.peer_id = peer_id
        self.browser_port = browser_port
        self.last_seen_index = -1  # Track last message index seen

        app = Flask("webapp")
        app.add_url_rule("/", "get_home", self.home, methods=["GET"])
        app.add_url_rule("/update", "get_update", self.updates_get, methods=["GET"])
        app.add_url_rule("/disk", "get_disk", self.disk_get, methods=["GET"])
        app.add_url_rule("/tower", "get_tower", self.tower_get, methods=["GET"])
        app.add_url_rule("/message", "post_message", self.message_post, methods=["POST"])
        app.add_url_rule("/shutdown", "get_shutdown", self.shutdown, methods=["GET"])

        self.setup_zookeeper_paths()
        app.run(port=browser_port)

    def setup_zookeeper_paths(self):
        paths = ["/coplay", "/coplay/messages", "/coplay/towers"]
        for path in paths:
            if not zk.exists(path):
                zk.create(path, b"", makepath=True)

    def home(self):
        with open('Wk0_A2_coPlay.html', 'r', encoding="utf-8") as file:
            return file.read()

    def message_post(self):
        # Decode base64 message
        text = base64.b64decode(request.data).decode('utf-8')
        logging.info(f"Received chat message: {text}")

        # Create a sequential znode with message JSON
        message_data = json.dumps({"message": text}).encode('utf-8')
        zk.create("/coplay/messages/msg-", value=message_data, sequence=True)
        return "ok"

    def tower_get(self):
        # <tower click sync> addition required (Issue 3)
        return "ok"

    def disk_get(self):
        # disk sync complete from Issue 1
        return "ok"

    def updates_get(self):
        # Get all new messages after last_seen_index
        children = zk.get_children("/coplay/messages")
        children.sort()  # lex order ensures seq order: msg-00000001, msg-00000002, etc.

        new_messages = []
        for child in children:
            index = int(child.split("-")[1])
            if index > self.last_seen_index:
                data, _ = zk.get(f"/coplay/messages/{child}")
                msg_json = json.loads(data.decode('utf-8'))
                new_messages.append(msg_json)
                self.last_seen_index = index

        return json.dumps(new_messages)

    def shutdown(self):
        return "<a href='/'>Home</a>"

def peer(browser_port, peer_id):
    Webapp(browser_port, peer_id)

# Launch 3 peers
threading.Thread(target=peer, args=(5000, "peer1")).start()
threading.Thread(target=peer, args=(5002, "peer2"), daemon=True).start()
threading.Thread(target=peer, args=(5004, "peer3"), daemon=True).start()
