# coPlay_zookeeper.py
from flask import Flask, request
import threading, base64, json, os, signal, logging, time
from kazoo.client import KazooClient
from kazoo.recipe.watchers import ChildrenWatch, DataWatch
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('werkzeug').disabled = True

# Enable or disable testing
TESTING = True

# List of ports used by all peers
PORTS = [5000, 5002, 5004]
BASE_URLS = [f"http://localhost:{port}" for port in PORTS]

# Zookeeper node paths
DISK_PATH = "/coplay/disk"
TOWER_PATH = "/coplay/towers"
MESSAGE_PATH = "/coplay/messages"

# Shared state for reset
reset_triggered = False
reset_requester_id = None

# Connect to local Zookeeper
zk = KazooClient(hosts='127.0.0.1:2181')
zk.start(timeout=10)

# Clear old state in Zookeeper
def reset_zookeeper_state():
    for path in [MESSAGE_PATH, TOWER_PATH]:
        if zk.exists(path):
            for child in zk.get_children(path):
                zk.delete(f"{path}/{child}")
    if zk.exists(DISK_PATH):
        zk.set(DISK_PATH, b"3")
    else:
        zk.create(DISK_PATH, b"3", makepath=True)

class WebApp:
    def __init__(self, port, peer_id):
        self.port = port
        self.peer_id = peer_id
        self.last_seen_msg = -1
        self.last_seen_tower = -1
        self.updates = []
        self.update_lock = threading.Lock()

        if peer_id == "peer1":
            reset_zookeeper_state()

        self.setup_paths()
        self.setup_watchers()

        app = Flask(__name__)
        app.add_url_rule("/", "home", self.home, methods=["GET"])
        app.add_url_rule("/update", "update", self.update, methods=["GET"])
        app.add_url_rule("/message", "message", self.message_post, methods=["POST"])
        app.add_url_rule("/tower", "tower", self.tower_get, methods=["GET"])
        app.add_url_rule("/disk", "disk", self.disk_get, methods=["GET"])
        app.add_url_rule("/shutdown", "shutdown", self.shutdown, methods=["GET"])
        app.run(port=port)

    # Ensure all required zNodes exist
    def setup_paths(self):
        for path in ["/coplay", MESSAGE_PATH, TOWER_PATH, DISK_PATH]:
            if not zk.exists(path):
                zk.create(path, b"", makepath=True)

    # Set up watchers for real-time update notifications
    def setup_watchers(self):
        ChildrenWatch(zk, MESSAGE_PATH, self.message_watcher)
        ChildrenWatch(zk, TOWER_PATH, self.tower_watcher)
        DataWatch(zk, DISK_PATH, self.disk_watcher)

    # Watcher callback for messages
    def message_watcher(self, children):
        children.sort()
        for child in children:
            idx = int(child.split("-")[1])
            if idx > self.last_seen_msg:
                data, _ = zk.get(f"{MESSAGE_PATH}/{child}")
                msg = json.loads(data.decode())
                with self.update_lock:
                    self.updates.append(msg)
                self.last_seen_msg = idx

    # Watcher callback for tower events (including reset)
    def tower_watcher(self, children):
        children.sort()
        for child in children:
            idx = int(child.split("-")[1])
            if idx > self.last_seen_tower:
                data, _ = zk.get(f"{TOWER_PATH}/{child}")
                tower_event = json.loads(data.decode())
                if "tower" in tower_event:
                    tower_event["tower"] = int(tower_event["tower"])
                with self.update_lock:
                    self.updates.append(tower_event)
                self.last_seen_tower = idx

    # Watcher callback for disk selector changes
    def disk_watcher(self, data, stat):
        if data:
            try:
                disk_count = int(data.decode())
                with self.update_lock:
                    self.updates.append({"disk_number": disk_count})
            except:
                pass
        return True

    # Serve the static HTML UI
    def home(self):
        with open("Wk0_A2_coPlay.html", "r", encoding="utf-8") as f:
            return f.read()

    # Broadcast new message to all peers via Zookeeper
    def message_post(self):
        text = base64.b64decode(request.data).decode('utf-8')
        zk.create(f"{MESSAGE_PATH}/msg-", value=json.dumps({"message": text}).encode(), sequence=True)
        return "ok"

    # Handle tower click or reset logic
    def tower_get(self):
        global reset_triggered, reset_requester_id
        tower = request.args.get("tower")
        requester = request.remote_addr
        if tower == "reset_request":
            reset_requester_id = requester
            zk.create(f"{TOWER_PATH}/tower-", value=json.dumps({"reset_request": True}).encode(), sequence=True)
        elif tower == "reset_vote":
            if not reset_triggered:
                reset_triggered = True
                zk.create(f"{TOWER_PATH}/tower-", value=json.dumps({"reset_vote": True}).encode(), sequence=True)
                threading.Timer(1.0, self.delayed_reset).start()
        else:
            zk.create(f"{TOWER_PATH}/tower-", value=json.dumps({"tower": int(tower)}).encode(), sequence=True)
        return "ok"

    # Delayed reset broadcast after vote
    def delayed_reset(self):
        global reset_triggered
        zk.create(f"{TOWER_PATH}/tower-", value=json.dumps({"reset": True}).encode(), sequence=True)
        reset_triggered = False

    # Update disk count setting
    def disk_get(self):
        try:
            count = int(request.args.get("count"))
            zk.set(DISK_PATH, str(count).encode())
            return "ok"
        except:
            return "Invalid count", 400

    # Called by browser to fetch new updates
    def update(self):
        with self.update_lock:
            data = list(self.updates)
            self.updates.clear()
            return json.dumps(data)

    # Shutdown this peer (broadcast + delayed exit)
    def shutdown(self):
        zk.create(f"{MESSAGE_PATH}/msg-", value=json.dumps({"shutdown": "shutdown"}).encode(), sequence=True)
        threading.Timer(1.0, self.do_shutdown).start()
        return "<a href='/'>Home</a>"

    # Terminate the Flask process
    def do_shutdown(self):
        os.kill(os.getpid(), signal.SIGINT)

# Start each peer in a separate thread
def run_peer(port, peer_id):
    WebApp(port, peer_id)

for i, port in enumerate(PORTS):
    threading.Thread(target=run_peer, args=(port, f"peer{i+1}"), daemon=(i > 0)).start()

# Optional test function for crash-resilient message passing
def test_fault_tolerance():
    print("Running fault tolerance test")
    def post_msg(peer, text):
        encoded = base64.b64encode(text.encode()).decode()
        requests.post(f"{BASE_URLS[peer]}/message", data=encoded)

    def get_updates(peer):
        res = requests.get(f"{BASE_URLS[peer]}/update").json()
        print(f"Peer{peer+1} updates:", res)
        return res

    def crash_peer(peer):
        try:
            requests.get(f"{BASE_URLS[peer]}/shutdown")
        except:
            print(f"Peer{peer+1} crashed.")

    post_msg(0, "Pre-crash")
    crash_peer(2)
    time.sleep(1)
    post_msg(1, "After crash")
    time.sleep(1)
    updates = get_updates(0)
    print("Final update:", updates)

# Testing in console if its True
if TESTING:
    time.sleep(2)
    test_fault_tolerance()
