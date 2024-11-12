import socket
import time

class Peer:
    def __init__(self, username, address):
        self.username = username
        self.address = address
        self.last_active_time = time.time()
        self.published_files = set()
        self.tcp_port = None  # Add TCP port attribute

    def update_last_active(self):
        self.last_active_time = time.time()

class BitTrickleServer:
    def __init__(self, host='127.0.0.1', port=5000):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((host, port))
        self.credentials = self.load_credentials()
        self.active_peers = {}  # Maps username to Peer object

    #Load credentials from a file
    def load_credentials(self):
        credentials = {}
        try:
            with open('credentials.txt', 'r') as f:
                for line in f:
                    username, password = line.strip().split(' ')
                    credentials[username] = password
        except Exception as e:
            print(f"Error loading credentials: {e}")
        return credentials

    #listen to commands from clients
    def listen(self):
        while True:
            data, addr = self.server_socket.recvfrom(1024)
            command_parts = data.decode('utf-8').split()
            command = command_parts[0]

            if command == 'authenticate':
                self.authenticate(command_parts[1], command_parts[2], addr)
            elif command == 'heartbeat':
                self.update_heartbeat(command_parts[1], addr)
            elif command == 'pub':
                self.publish_file(command_parts[1], addr)
                print (f"Received PUB")
            elif command == 'unp':
                self.unpublish_file(command_parts[1], addr)
                print (f"Received UNP")
            elif command == 'get':
                self.handle_get_request(command_parts[1], addr)
                print (f"Received GET")
            elif command == 'sch':
                self.search_files(command_parts[1], addr)
                print (f"Received SCH")
            elif command == 'laps':
                self.list_active_peers(addr)
                print (f"Received LAP")
            elif command == 'lpf':
                self.list_published_files(addr)
                print (f"Received LPF") 
            elif command == 'disconnect':  # Handle disconnection
                username = command_parts[1]
                if username in self.active_peers:
                    del self.active_peers[username]  # Remove peer from active list
                    print(f"{username} has disconnected.")
            elif command == 'tcp_port':
                # Update the TCP port of the authenticated peer
                self.update_peer_tcp_port(command_parts[1], int(command_parts[2]), addr)

    def update_peer_tcp_port(self, username, tcp_port, addr):
        if username in self.active_peers and self.active_peers[username].address == addr:
            self.active_peers[username].tcp_port = tcp_port
            print(f"Updated TCP port for {username} to {tcp_port}")
     

    #Authenticate client users
    def authenticate(self, username, password, addr):
        print(f"Received AUTH from {username}")
        if username not in self.credentials:
            print(f"Sent ERR to {username}")
            response = "Authentication failed: Unknown username."
        elif self.credentials[username] != password:
            response = "Authentication failed. Please try again."
            print(f"Sent ERR to {username}")
        elif username in self.active_peers:
            response = "Authentication failed: User is already active."
            print(f"Sent ERR to {username}")
        else:
            response = "Authentication successful."
            peer = Peer(username, addr)
            self.active_peers[username] = peer
        
        self.server_socket.sendto(response.encode('utf-8'), addr)

    #Display active users if they are still sending heartbeats 
    def update_heartbeat(self, username, addr):
        if username in self.active_peers and self.active_peers[username].address == addr:
            print(f"Received HBT from {username}.")
            self.active_peers[username].update_last_active()

    #Publish files
    def publish_file(self, filename, addr):
        for peer in self.active_peers.values():
            if peer.address == addr:
                peer.published_files.add(filename)
                response = f"File {filename} published successfully."
                break
        else:
            response = "Failed to publish file: Unknown peer."
        
        self.server_socket.sendto(response.encode('utf-8'), addr)

    #Unpublish files
    def unpublish_file(self, filename, addr):
        for peer in self.active_peers.values():
            if peer.address == addr:
                if filename in peer.published_files:
                    peer.published_files.remove(filename)
                    response = f"File {filename} unpublished successfully."
                else:
                    response = f"Failed to unpublish {filename}: File not found."
                break
        else:
            response = "Failed to unpublish file: Unknown peer."

        self.server_socket.sendto(response.encode('utf-8'), addr)

    #Handle get_file functionality
    def handle_get_request(self, filename, addr):
        found_peer = None
        for peer in self.active_peers.values():
            if filename in peer.published_files and peer.address != addr:
                found_peer = peer
                break

        if found_peer and found_peer.tcp_port is not None:
            # Format the address as 'host:port' using the updated TCP port
            ip, _ = found_peer.address
            port = found_peer.tcp_port
            response = f"{filename} is available at {ip}:{port}"
        else:
            response = f"{filename} not found."

        self.server_socket.sendto(response.encode('utf-8'), addr)
 

    #Search file functionality
    def search_files(self, substring, addr):
        matching_files = []
        
        for peer in self.active_peers.values():
            if peer.address != addr:  # Exclude requesting user
                matching_files.extend([f for f in peer.published_files if substring in f])
        
        if matching_files:
            response = "\n".join(matching_files)
        else:
            response = "No files found matching."

        self.server_socket.sendto(response.encode('utf-8'), addr)

    #show active peers
    def list_active_peers(self, addr):
        active_usernames = [peer.username for peer in self.active_peers.values() ]
        
        if active_usernames:
            response = "\n".join(active_usernames)
        else:
            response = "No active peers."

        self.server_socket.sendto(response.encode('utf-8'), addr)

    #count published files
    def count_published_files(self):
        total_files = sum(len(peer.published_files) for peer in self.active_peers.values())
        return total_files
    
    #list published files functionality
    def list_published_files(self, addr):
        total_files = self.count_published_files()
        published_files_list = []

        # Collect all published files from active peers
        for peer in self.active_peers.values():
            published_files_list.extend(peer.published_files)

        # Construct response
        response_lines = [f"{total_files} published files:"]
        if published_files_list:
            response_lines.extend(published_files_list)
        else:
            response_lines.append("No published files.")

        response = "\n".join(response_lines) + "\n"
        
        self.server_socket.sendto(response.encode('utf-8'), addr)

    def disconnect_peer(self, username):
        if username in self.active_peers:
            del self.active_peers[username]  # Remove the user from active peers list
            print(f"{username} has disconnected.")

def main():
    import sys
    if len(sys.argv) != 2:
        print("Usage: python3 server.py <server_port>")
        return

    server_port = int(sys.argv[1])
    server = BitTrickleServer(port=server_port)
    server.listen()

if __name__ == "__main__":
    main()
