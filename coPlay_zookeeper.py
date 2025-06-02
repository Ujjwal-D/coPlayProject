# coPlay_zookeeper.py
# Zookeeper-based coPlay with chat and tower click sync

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
        self.last_seen_index = -1  # For chat messages
        self.last_seen_tower_index = -1  # For tower clicks
        self.reset_triggered = False
        self.reset_requester_id = None

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
        tower = request.args['tower']
        requester = request.remote_addr

        logging.info(f"Received tower click: {tower} from {requester}")

        if tower == "reset_request":
            self.reset_requester_id = requester
            zk.create("/coplay/towers/tower-", value=json.dumps({"reset_request": True}).encode('utf-8'), sequence=True)
            return "ok"

        elif tower == "reset_vote":
            if not self.reset_triggered:
                self.reset_triggered = True
                zk.create("/coplay/towers/tower-", value=json.dumps({"reset_vote": True}).encode('utf-8'), sequence=True)
                # Delayed reset to simulate timer
                threading.Timer(1.0, self.delayed_reset).start()
            return "ok"

        else:
            # Normal tower click broadcast
            tower_data = json.dumps({"tower": tower}).encode('utf-8')
            zk.create("/coplay/towers/tower-", value=tower_data, sequence=True)
            return "ok"

    def disk_get(self):
        # Disk sync handled already (no change needed)
        return "ok"

    def updates_get(self):
        # Get all new chat messages
        children_msg = zk.get_children("/coplay/messages")
        children_msg.sort()
        new_messages = []
        for child in children_msg:
            index = int(child.split("-")[1])
            if index > self.last_seen_index:
                data, _ = zk.get(f"/coplay/messages/{child}")
                msg_json = json.loads(data.decode('utf-8'))
                new_messages.append(msg_json)
                self.last_seen_index = index

        # Get all new tower messages
        children_tower = zk.get_children("/coplay/towers")
        children_tower.sort()
        new_tower_events = []
        for child in children_tower:
            index = int(child.split("-")[1])
            if index > self.last_seen_tower_index:
                data, _ = zk.get(f"/coplay/towers/{child}")
                tower_json = json.loads(data.decode('utf-8'))
                new_tower_events.append(tower_json)
                self.last_seen_tower_index = index

        combined_updates = new_messages + new_tower_events
        return json.dumps(combined_updates)

    def delayed_reset(self):
        logging.info("Timer expired, broadcasting reset")
        zk.create("/coplay/towers/tower-", value=json.dumps({"reset": True}).encode('utf-8'), sequence=True)
        self.reset_triggered = False

    def shutdown(self):
        return "<a href='/'>Home</a>"

def peer(browser_port, peer_id):
    Webapp(browser_port, peer_id)

# Launch 3 peers
threading.Thread(target=peer, args=(5000, "peer1")).start()
threading.Thread(target=peer, args=(5002, "peer2"), daemon=True).start()
threading.Thread(target=peer, args=(5004, "peer3"), daemon=True).start()
