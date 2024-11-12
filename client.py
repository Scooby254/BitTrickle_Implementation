import socket
import threading
import time
import os

class BitTrickleClient:
    # initialize system properties and parameters
    def __init__(self, server_host='127.0.0.1', server_port=5000):
        self.server_address = (server_host, server_port)
        self.username = None
        self.active = False
        self.published_files = set()  # To track published files
        self.tcp_port = None  # To be set after authentication

        # Create UDP socket for communication with the server
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Create TCP socket for incoming file requests
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(('', 0))  # Bind to an available port
        self.tcp_port = self.tcp_socket.getsockname()[1]  # Get the assigned TCP port

    #Authentication method
    def authenticate(self):
        while not self.active:
            username = input("Enter your username: ")
            password = input("Enter your password: ")
            self.udp_socket.sendto(f'authenticate {username} {password}'.encode('utf-8'), self.server_address)
            response, _ = self.udp_socket.recvfrom(1024)
            print(response.decode('utf-8'))
            
            if "successful" in response.decode('utf-8'):
                self.username = username
                self.active = True
                threading.Thread(target=self.send_heartbeats).start()
                self.send_tcp_port_to_server()
                print(f"Welcome to BitTrickle!")
                print(f"Available commands are: get, lap, lpf, pub, sch, unp, xit")

    def send_tcp_port_to_server(self):
        # Inform the server of the TCP port used for incoming connections
        message = f'tcp_port {self.username} {self.tcp_port}'
        self.udp_socket.sendto(message.encode('utf-8'), self.server_address)

    def send_heartbeats(self):
        while self.active:
            self.udp_socket.sendto(f'heartbeat {self.username}'.encode('utf-8'), self.server_address)
            time.sleep(2)  # Send heartbeat every 2 seconds

    def listen_for_download_requests(self):
        self.tcp_socket.listen(5)  # Listen for incoming connections
        
        while True:
            conn, addr = self.tcp_socket.accept()  # Accept a new connection
            print(f"Connection established with {addr}.")
            threading.Thread(target=self.handle_file_transfer, args=(conn,)).start()

    def handle_file_transfer(self, conn):
        filename = conn.recv(1024).decode('utf-8')  # Receive the filename requested by the peer
        print(f"Preparing to send file: {filename}")
        
        try:
            with open(filename, 'rb') as f:
                while True:
                    data = f.read(1024)  # Read in chunks of 1024 bytes
                    if not data:
                        break  # End of file reached
                    conn.send(data)  # Send data to the requesting peer
            
            print(f"File {filename} sent successfully.")
        except FileNotFoundError:
            print(f"File {filename} not found.")
            conn.send(b'')  # Send an empty response if file not found
        
        conn.close()  # Close the connection

    #Get File command
    def get_file(self, filename):
        self.udp_socket.sendto(f'get {filename}'.encode('utf-8'), self.server_address)
        response, _ = self.udp_socket.recvfrom(1024)

        if "not found" in response.decode('utf-8'):
            print(response.decode('utf-8'))
            return

        # Assuming the response format is "filename is available at ip:port"
        response_parts = response.decode('utf-8').split()
        if len(response_parts) < 5:
            print("Error: Invalid response from server.")
            return

        peer_address_str = response_parts[-1]  # Get the 'ip:port' part
        try:
            host, port = peer_address_str.split(':')  # Split into host and port
            peer_address = (host, int(port))
        except ValueError:
            print("Error: Could not parse peer address.")
            return

        print(f"Connecting to {peer_address} to download {filename}...")

        # Establish TCP connection with the peer to download the file
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            tcp_sock.connect(peer_address)
        except Exception as e:
            print(f"Error: Could not connect to peer: {e}")
            return

        tcp_sock.send(filename.encode('utf-8'))  # Request the file

        with open(filename, 'wb') as f:
            print("Downloading...")
            while True:
                data = tcp_sock.recv(1024)
                if not data:
                    break
                f.write(data)

        print(f"{filename} downloaded  successfully.")
        tcp_sock.close()


    #Publish File command
    def publish_file(self, filename):
        if filename in self.published_files:
            print(f"{filename} is already published.")
            return
        
        self.udp_socket.sendto(f'pub {filename}'.encode('utf-8'), self.server_address)
        response, _ = self.udp_socket.recvfrom(1024)
        
        if "success" in response.decode('utf-8'):
            self.published_files.add(filename)
            print(f"File Published successfully.")
        else:
            print(f"Failed to publish {filename}: {response.decode('utf-8')}")

    #Search Files Command
    def search_files(self, substring):
        self.udp_socket.sendto(f'sch {substring}'.encode('utf-8'), self.server_address)
        response, _ = self.udp_socket.recvfrom(1024)

        files = response.decode('utf-8').splitlines()
        if files:
            no_of_files_found = len(files)
            print(f"{no_of_files_found} files found:")
            for file in files:
                print(file)
        else:
            print("No files found.")

    #Unpublish File Command
    def unpublish_file(self, filename):
        if filename not in self.published_files:
            print(f"You have not published a file named {filename}.")
            return
        
        self.udp_socket.sendto(f'unp {filename}'.encode('utf-8'), self.server_address)
        response, _ = self.udp_socket.recvfrom(1024)

        if "success" in response.decode('utf-8'):
            self.published_files.remove(filename)
            print(f"Unpublished {filename} successfully.")
        else:
            print(f"Failed to unpublish {filename}: {response.decode('utf-8')}")

    #List Active Peers Command
    def list_active_peers(self):
        self.udp_socket.sendto(b'laps', self.server_address)  # Assuming 'laps' is the command to list peers
        response, _ = self.udp_socket.recvfrom(1024)

        peers = response.decode('utf-8').splitlines()
        # Filter out the current user's username
        filtered_peers = [peer for peer in peers if peer != self.username]
        
        if filtered_peers:
            print("Active peers:")
            for peer in filtered_peers:
                print(peer)
        else:
            print("No active peers.")

    #List Published Files Command
    def list_published_files(self):   
        try:   
            # Request total published files from server   
            self.udp_socket.sendto(b'lpf', self.server_address)   
            response, _ = self.udp_socket.recvfrom(1024)   

            print(response.decode('utf-8'))  # Display the formatted output

        except Exception as e:   
            print(f"An error occurred during listing published files: {e}") 

    #Exit Command
    def exit_client(self): 
      try :      
         message=f'disconnect {self.username}\n'      
         # Send disconnect message      
         self.udp_socket.sendto (message.encode ('utf -8'),self.server_address )      
         
         # Close sockets before exiting      
         self.udp_socket.close ()      
         self.tcp_socket.close ()      
         
         self.active=False
         print("Goodbye!")  
         os._exit(0)    

      except Exception as e :      
         return (f"An error occurred during exit :{e }")

    #Run Commands method
    def run(self):
        
         # Start listening for incoming download requests in a separate thread.
         threading.Thread(target=self.listen_for_download_requests).start()  
        
         while True: 
             command_input = input("Enter command: ") 
             command_parts = command_input.split()

             if command_parts[0] == 'get':
                 if len(command_parts) == 2:
                     self.get_file(command_parts[1])
                 else:
                     print("Invalid command format. Use: get <filename>")
                     
             elif command_parts[0] == 'lap':
                 self.list_active_peers()
                 
             elif command_parts[0] == 'lpf':
                 self.list_published_files()
                 
             elif command_parts[0] == 'pub':
                 if len(command_parts) == 2:
                     self.publish_file(command_parts[1])
                 else:
                     print("Invalid command format. Use: pub <filename>")
                     
             elif command_parts[0] == 'sch':
                 if len(command_parts) == 2:
                     self.search_files(command_parts[1])
                 else:
                     print("Invalid command format. Use: sch <substring>")
                     
             elif command_parts[0] == 'unp':
                 if len(command_parts) == 2:
                     self.unpublish_file(command_parts[1])
                 else:
                     print("Invalid command format. Use: unp <filename>")
                     
             elif command_parts[0] == 'xit':
                 self.exit_client()
                 break
                
             else:
                 print("Unknown command.")

def main():
    import sys
    if len(sys.argv) != 2:
         print("Usage: python3 client.py <server_port>")
         return

    server_port = int(sys.argv[1])
    client = BitTrickleClient(server_host='127.0.0.1', server_port=server_port)
    client.authenticate()
    client.run()

if __name__ == "__main__":
     main()
