# Wk0_A2_coPlay.py
# Allows to you to chat while playing a game.
# Instantiates 2 webapps.

TESTING=False # automatic tests
reset_triggered = False #Global flag to lock reset
reset_requester_id = None #Track reset requesting peer

from flask import Flask, request
import threading, time, zmq, base64, os, signal, json, requests, logging, random
logging.getLogger('werkzeug').disabled = True

class Webapp:
    # Creates front-end Flask endpoints on localhost:browser_port.
    # Creates listening ZMQ pull socket on zmq_port.
    # Creates sending ZMQ push sockets for each of webapp_ports.
    def __init__(self,browser_port,zmq_port,webapp_ports):
        app = Flask("webapp")
        app.add_url_rule("/","get_home",self.home,methods=['GET'])
        app.add_url_rule("/update","get_update",self.updates_get,methods=['GET'])
        app.add_url_rule("/disk", "get_disk", self.disk_get, methods=['GET'])  # UPDATED CODE. Disk count 
        app.add_url_rule("/tower","get_tower",self.tower_get,methods=['GET'])
        app.add_url_rule("/message","post_message",self.message_post,methods=['POST'])
        app.add_url_rule("/shutdown","get_shutdown",self.shutdown,methods=['GET'])
        context = zmq.Context()
        self.pull_socket = context.socket(zmq.PULL)
        self.pull_socket.bind(f"tcp://127.0.0.1:{zmq_port}")
        other_sockets=[]
        for port in webapp_ports:
            push_socket = context.socket(zmq.PUSH)
            push_socket.connect(f"tcp://127.0.0.1:{port}")
            other_sockets+=[push_socket]
        self.other_sockets=other_sockets
        app.run(port=browser_port)

    #@app.route('/',methods=["GET"])
    # Called when a browser browses to, e.g. http://127.0.0.1:5000/
    # Returns front-end HTML5 coPlay.html.
    def home(self):
        with open('Wk0_A2_coPlay.html', 'r', encoding="utf-8") as file:
            content = file.read()
            return content

    # Sends a JSON message to all webapps, including itself.
    def broadcast(self, jsn): # {"message":solution_messages}
        if random.random()>0.5:
            socket=self.other_sockets.pop()
            self.other_sockets=self.other_sockets+[socket]
        for socket in self.other_sockets:
            time.sleep(0.01)
            socket.send_json(jsn)

    #@app.route('/message',methods=["POST"])
    # Called when a browser sends a chat message.
    # The base64 message is decoded and sent to all webapps.
    def message_post(self):
        text = request.data # body of new message
        decoded_bytes = base64.b64decode(text)
        text = decoded_bytes.decode('utf-8')
        self.broadcast({"message":text})
        return "ok"
    
    # UPDATED CODE.
    # #@app.route('/disk', methods=["GET"])
    # Called when a user changes the number of disks.
    # Broadcasts the new disk count to all peers for synchronization. 
    def disk_get(self):
        disk_count = int(request.args['count'])
        self.broadcast({"disk_number": disk_count})
        return "ok"

    #@app.route('/tower',methods=["GET"])
    # Called when a user clicks on a tower.
    # Broadcasts tower message to all webapps. 
    # UPDATED CODE
    def tower_get(self):
        global reset_triggered, reset_requester_id

        tower = request.args['tower']
        requester = request.remote_addr # or any unique identifier

        if tower == "reset_request":
            reset_requester_id = requester # save the requester
            self.broadcast({"reset_request": True})
            return "ok"

        elif tower == "reset_vote":
            global reset_triggered
            if not reset_triggered:
                reset_triggered = True
                self.broadcast({"reset_vote":True})
                threading.Timer(1.0, self.delayed_reset).start() # 3 seconds wait time for peer sending reset request
            return "ok"

        else:
            self.broadcast({"tower": tower})
            return "ok"


    #@app.route('/update') #,methods=["GET"])
    # Called periodically by the polling browser.
    # Pulls all queued messages and them to browser for processing.
    def updates_get(self):
        global reset_triggered
        messages = []

        while True:
            try:
                ms = self.pull_socket.recv_json(zmq.NOBLOCK)
                if not TESTING:
                    print(ms)
                else:
                    time.sleep(TESTING_DELAY)

                if "shutdown" in ms:
                    threading.Timer(1.0, self.do_shutdown).start()
                    reset_triggered = False
                    messages.append(ms)
                    return messages if TESTING else json.dumps(messages)

                if "reset" in ms:
                    reset_triggered = False

                messages.append(ms)

            except zmq.Again:
                return messages if TESTING else json.dumps(messages)
    
    # UPDATED CODE
    def delayed_reset(self):
        print("Timer expired, broadcasting reset")
        self.broadcast({"reset": True})



    #@app.route('/shutdown')
    # You can ignore this method.
    # Returns a link to homepage - can be used for development purposes.
    def shutdown(self):
        self.broadcast({"shutdown":"shutdown"})
        return "<a href='/'>Home</a>"
    def do_shutdown(self):
        os.kill(os.getpid(), signal.SIGINT)

# Thread target - start a peer by instantiating a Webapp.
def peer(browser_port,webapp_port,webapp_ports): 
    Webapp(browser_port,webapp_port,webapp_ports)

if TESTING: # Keep testing infrastucture stable.
    zmq_ports=[5001,5003,5005]
    threading.Thread(target=peer,args=(5000,5001,zmq_ports),daemon=TESTING).start()
    threading.Thread(target=peer,args=(5002,5003,zmq_ports),daemon=True).start()
    threading.Thread(target=peer,args=(5004,5005,zmq_ports),daemon=True).start()
else:
    zmq_ports=[5001,5003]
    threading.Thread(target=peer,args=(5000,5001,zmq_ports)).start()
    threading.Thread(target=peer,args=(5002,5003,zmq_ports),daemon=True).start()

TESTING_DELAY=0.0
# Remove messages to clean up after a test
def test_clean():
    time.sleep(0.1)
    url1 = 'http://127.0.0.1:5000/update'
    url2 = 'http://127.0.0.1:5002/update'
    url3 = 'http://127.0.0.1:5004/update'
    towers1=requests.get(url1).json()
    towers2=requests.get(url2).json()
    towers3=requests.get(url3).json()

# Test that simulates browser send a Hello world message.
# Checks if the same webapp can receive the sent message.
def test_message_hello_world():
    time.sleep(1)
    # Simulate GUI sending Hello
    url1 = 'http://127.0.0.1:5000/message'
    json_data = base64.b64encode("Hello world".encode('utf-8'))
    response_ignored = requests.post(url1, json_data)
    # Check the message has been broadcasted and is returned when requesting updates.
    url1 = 'http://127.0.0.1:5000/update'
    last_chat=requests.get(url1).json().pop()['message']
    return last_chat=="Hello world"

# Test that simulates lag by introducing delay in receiving update
def test_simulated_lag():
    global TESTING_DELAY
    TESTING_DELAY = 1.5  # 1.5 second processing delay

    print("test_simulated_lag: sending delayed message...")
    url1 = 'http://127.0.0.1:5000/message'
    json_data = base64.b64encode("Delayed message".encode('utf-8'))
    requests.post(url1, json_data)

    # Try to fetch with delay and check result
    url2 = 'http://127.0.0.1:5002/update'
    start_time = time.time()
    response = requests.get(url2).json()
    end_time = time.time()

    TESTING_DELAY = 0  # Reset processing delay
    success = any("Delayed message" in msg.get("message", "") for msg in response)
    print(f"test_simulated_lag: duration={end_time-start_time:.2f}s, success={success}")
    return success


# Test that simulates message reorder by sending multiple messages
def test_message_reorder():
    messages = ["First", "Second", "Third"]
    for msg in messages:
        url = 'http://127.0.0.1:5000/message'
        json_data = base64.b64encode(msg.encode('utf-8'))
        requests.post(url, json_data)
        time.sleep(0.1)

    url = 'http://127.0.0.1:5002/update'
    response = requests.get(url).json()
    received = [msg.get("message") for msg in response if "message" in msg]
    print("test_message_reorder: received =", received)
    return set(messages).issubset(set(received))

#Test that simulates peer crash mid broadcast
def test_peer_crash_mid_broadcast():
    print("test_peer_crash_mid_broadcast: Simulating crash")

    # Normal message post
    url1 = 'http://127.0.0.1:5000/message'
    json_data = base64.b64encode("Crash Test Msg".encode('utf-8'))
    requests.post(url1, json_data)

    #  Kill peer on port 5004 (simulate crash)
    try:
        print("Attempting to kill peer on port 5004...")
        requests.get('http://127.0.0.1:5004/shutdown')
    except Exception as e:
        print("Peer 5004 crashed or unreachable:", e)

    # Broadcast another message
    json_data = base64.b64encode("Post-crash Msg".encode('utf-8'))
    requests.post(url1, json_data)

    # Try to fetch updates from another peer who is live
    url2 = 'http://127.0.0.1:5002/update'
    try:
        result = requests.get(url2).json()
        found = any("Post-crash Msg" in msg.get("message", "") for msg in result)
        print("test_peer_crash_mid_broadcast: remaining peers received message =", found)
        return found
    except Exception as e:
        print("Live peer failed:", e)
        return False

def tests():
    do_test_message_hello_world=True
    if do_test_message_hello_world:
        print(f"test_message_hello_world: {test_message_hello_world()}")
        test_clean()

        print(f"test_message_hello_world: {test_message_hello_world()}")
        test_clean()

        print(f"test_simulated_lag: {test_simulated_lag()}")
        test_clean()

        print(f"test_message_reorder: {test_message_reorder()}")
        test_clean()

        print(f"test_peer_crash_mid_broadcast: {test_peer_crash_mid_broadcast()}")
        test_clean()

if TESTING:
    tests()
