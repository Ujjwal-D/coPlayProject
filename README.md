# CoPlayProject
**CoPlay** is a lightweight distributed system that combines real-time chat with an interactive game (Tower of Hanoi). It allows multiple users on different peers to communicate and play collaboratively, using ZeroMQ for peer-to-peer communication and Flask for local webapp hosting.

## 🌐 Features

- 🧩 **Interactive Tower of Hanoi**
  - Select number of disks (3–8)
  - Move disks by clicking on towers
  - Solves logic validated via DOM
  - Automatic win detection and reset support

- 💬 **Real-time Chat**
  - Base64-encoded messages sent via POST
  - Broadcasted to all peers using ZMQ
  - Displayed on all connected browser clients

- 🔄 **Peer Synchronization**
  - ZMQ-based broadcast for chat and gameplay updates
  - Periodic polling (`/update`) syncs game state across webapps
  - All events are JSON messages (`{message:...}`, `{tower:...}`)

---

## ⚙️ Tech Stack

| Layer         | Technology            |
|---------------|------------------------|
| Backend       | Python + Flask         |
| Networking    | ZeroMQ (ZMQ)           |
| Frontend      | HTML5 + JavaScript     |
| Styling       | CSS                    |
| Communication | ZMQ Push/Pull Sockets  |
| Transport     | TCP (localhost)        |

---

## 🚀 Getting Started

### 🔧 Requirements
- Python 3.8+
- pip packages: `flask`, `pyzmq`, `requests`

```bash
pip install flask pyzmq requests
