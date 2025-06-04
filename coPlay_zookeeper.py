# coPlay_zookeeper.py

# Import necessary modules
from flask import Flask, request
import threading, base64, json, os, signal, logging, time
from kazoo.client import KazooClient
from kazoo.recipe.watchers import ChildrenWatch, DataWatch
import requests

# Enable simple logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('werkzeug').disabled = True

# Toggle this to True for testing via console instead of browser
TESTING = True

# List of ports for peer nodes
PORTS = [5000, 5002, 5004]
BASE_URLS = [f"http://localhost:{port}" for port in PORTS]

# Zookeeper paths for storing game data
DISK_PATH = "/coplay/disk"
TOWER_PATH = "/coplay/towers"
MESSAGE_PATH = "/coplay/messages"

# Global flags for reset functionality
reset_triggered = False
reset_requester_id = None

# Connect to local Zookeeper server
zk = KazooClient(hosts='127.0.0.1:2181')
zk.start(timeout=10)

# Clear previous game state and initialize with default disk count
def reset_zookeeper_state():
    for path in [MESSAGE_PATH, TOWER_PATH]:
        if zk.exists(path):
            for child in zk.get_children(path):
                zk.delete(f"{path}/{child}")
    if zk.exists(DISK_PATH):
        zk.set(DISK_PATH, b"3")
    else:
        zk.create(DISK_PATH, b"3", makepath=True)

# WebApp represents one peer (a single browser tab in real scenario)
class WebApp:
    def __init__(self, port, peer_id):
        self.port = port
        self.peer_id = peer_id
        self.last_seen_msg = -1
        self.last_seen_tower = -1
        self.updates = []
        self.update_lock = threading.Lock()

        # Reset state only once for the first peer
        if peer_id == "peer1":
            reset_zookeeper_state()

        self.setup_paths()
        self.setup_watchers()

        # Setup Flask routes
        app = Flask(__name__)
        app.add_url_rule("/", "home", self.home, methods=["GET"])
        app.add_url_rule("/update", "update", self.update, methods=["GET"])
        app.add_url_rule("/message", "message", self.message_post, methods=["POST"])
        app.add_url_rule("/tower", "tower", self.tower_get, methods=["GET"])
        app.add_url_rule("/disk", "disk", self.disk_get, methods=["GET"])
        app.add_url_rule("/shutdown", "shutdown", self.shutdown, methods=["GET"])
        app.run(port=port)

    # Create required paths in Zookeeper if they don’t exist
    def setup_paths(self):
        for path in ["/coplay", MESSAGE_PATH, TOWER_PATH, DISK_PATH]:
            if not zk.exists(path):
                zk.create(path, b"", makepath=True)

    # Attach watchers for message, tower, and disk updates
    def setup_watchers(self):
        ChildrenWatch(zk, MESSAGE_PATH, self.message_watcher)
        ChildrenWatch(zk, TOWER_PATH, self.tower_watcher)
        DataWatch(zk, DISK_PATH, self.disk_watcher)

    # Callback to track new chat messages
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

    # Callback to track tower actions
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

    # Callback to track disk number updates
    def disk_watcher(self, data, stat):
        if data:
            try:
                disk_count = int(data.decode())
                with self.update_lock:
                    self.updates.append({"disk_number": disk_count})
            except:
                pass
        return True

    # Load the main game page
    def home(self):
        with open("Wk0_A2_coPlay.html", "r", encoding="utf-8") as f:
            return f.read()

    # Post a new chat message to Zookeeper
    def message_post(self):
        text = base64.b64decode(request.data).decode('utf-8')
        zk.create(f"{MESSAGE_PATH}/msg-", value=json.dumps({"message": text}).encode(), sequence=True)
        return "ok"

    # Handle tower click or reset commands
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

    # Broadcast reset command after a small delay
    def delayed_reset(self):
        global reset_triggered
        zk.create(f"{TOWER_PATH}/tower-", value=json.dumps({"reset": True}).encode(), sequence=True)
        reset_triggered = False

    # Update the number of disks used in game
    def disk_get(self):
        try:
            count = int(request.args.get("count"))
            zk.set(DISK_PATH, str(count).encode())
            return "ok"
        except:
            return "Invalid count", 400

    # Return new updates to the browser or test
    def update(self):
        with self.update_lock:
            data = list(self.updates)
            self.updates.clear()
            return json.dumps(data)

    # Trigger shutdown and return to Home link
    def shutdown(self):
        zk.create(f"{MESSAGE_PATH}/msg-", value=json.dumps({"shutdown": "shutdown"}).encode(), sequence=True)
        threading.Timer(1.0, self.do_shutdown).start()
        return "<a href='/'>Home</a>"

    # Kill the process
    def do_shutdown(self):
        os.kill(os.getpid(), signal.SIGINT)

# Launch each peer node
threads = []
for i, port in enumerate(PORTS):
    t = threading.Thread(target=lambda: WebApp(port, f"peer{i+1}"), daemon=(i > 0))
    t.start()
    threads.append(t)

# Helper to send base64 encoded messages
def post_msg(peer, text):
    encoded = base64.b64encode(text.encode()).decode()
    r = requests.post(f"{BASE_URLS[peer]}/message", data=encoded)
    print(f"Sent to Peer{peer+1}: '{text}' | Status: {r.status_code}")

# Helper to retrieve updates
def get_updates(peer):
    try:
        res = requests.get(f"{BASE_URLS[peer]}/update")
        data = res.json()
        print(f"Updates from Peer{peer+1}: {data}")
        return data
    except Exception as e:
        print(f"Failed to get updates from Peer{peer+1}: {e}")
        return []

# Helper to simulate a peer crash
def crash_peer(peer):
    try:
        requests.get(f"{BASE_URLS[peer]}/shutdown")
        print(f"Shutdown signal sent to Peer{peer+1}")
    except:
        print(f"Peer{peer+1} is unreachable or already shut down")

# Test crash during broadcast
def test_crash():
    print("\nRunning test_crash...")
    post_msg(0, "before crash")
    time.sleep(1)
    crash_peer(2)
    post_msg(1, "after crash")
    time.sleep(2)
    updates = get_updates(0)
    if any("after crash" in u.get("message", "") for u in updates):
        print("PASS: Message after crash received")
    else:
        print("FAIL: Message after crash not found")

# Test sending messages in order
def test_message_order():
    print("\nRunning test_message_order...")
    msgs = ["One", "Two", "Three"]
    for msg in msgs:
        post_msg(1, msg)
        time.sleep(0.5)
    updates = get_updates(0)
    received = [u["message"] for u in updates if "message" in u]
    if all(m in received for m in msgs):
        print("PASS: All ordered messages received")
    else:
        print("FAIL: Message(s) missing")

# Test delayed message arrival
def test_lag():
    print("\nRunning test_lag...")
    post_msg(0, "lag test")
    time.sleep(3)
    updates = get_updates(1)
    if any("lag test" in u.get("message", "") for u in updates):
        print("PASS: Lagged message received")
    else:
        print("FAIL: Lagged message missing")

# Run all tests if testing mode is enabled
if TESTING:
    time.sleep(2)
    test_message_order()
    test_lag()
    test_crash()
    print("\nAll tests finished.")
