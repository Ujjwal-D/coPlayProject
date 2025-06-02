# CoPlayProject
**CoPlay** is a lightweight distributed system that combines real-time chat with an interactive game (Tower of Hanoi). It allows multiple users on different peers to communicate and play collaboratively, using ZeroMQ for peer-to-peer communication and Flask for local webapp hosting.

## Features

-  **Interactive Tower of Hanoi**
  - Select number of disks (3–8)
  - Move disks by clicking on towers
  - Solves logic validated via DOM
  - Automatic win detection and reset support

-  **Real-time Chat**
  - Base64-encoded messages sent via POST
  - Broadcasted to all peers using ZMQ
  - Displayed on all connected browser clients

-  **Peer Synchronization**
  - ZMQ-based broadcast for chat and gameplay updates
  - Periodic polling (`/update`) syncs game state across webapps
  - All events are JSON messages (`{message:...}`, `{tower:...}`)

---

##  Tech Stack

| Layer         | Technology            |
|---------------|------------------------|
| Backend       | Python + Flask         |
| Networking    | ZeroMQ (ZMQ)           |
| Frontend      | HTML5 + JavaScript     |
| Styling       | CSS                    |
| Communication | ZMQ Push/Pull Sockets  |
| Transport     | TCP (localhost)        |

---

##  Getting Started

###  Requirements
- Python 3.8+
- pip packages: `flask`, `pyzmq`, `requests`
- Terminal:
pip install -r requirements.txt

### Zookeeper Setup

This project uses Apache Zookeeper to synchronize chat messages and game actions between peers. You must start a Zookeeper server before running coPlay_zookeeper.py.

## Step 1: Download Zookeeper

    Go to https://zookeeper.apache.org/releases.html

    Download the latest stable binary release (e.g., apache-zookeeper-3.8.4-bin.tar.gz or .zip)

    Extract the downloaded archive to a location outside the project folder (e.g., C:/zookeeper/ or ~/zookeeper/)

## Step 2: Start Zookeeper Server

For Windows:

cd C:\zookeeper\apache-zookeeper-3.x.x-bin\bin
zkServer.cmd

For macOS or Linux:

cd ~/zookeeper/apache-zookeeper-3.x.x-bin/bin
./zkServer.sh start

If Zookeeper starts successfully, it will bind to port 2181.

## Step 3: Run the Application

Open a new terminal window and run:

python coPlay_zookeeper.py

Make sure Zookeeper is running and listening on 127.0.0.1:2181. The application will connect automatically.

