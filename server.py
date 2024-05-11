import socket
import threading
import ssl
import os

from util import *

class Server:
    def __init__(self):
        self.connected_clients = {}
        self.lock = threading.Lock()
        self.host = '172.28.208.1'
        self.port = 3333
        self.initialise_ssl_credentials()
        self.command_id = 0
        self.command_results = {}

    def initialise_ssl_credentials(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        certfile_path = os.path.join(current_dir, 'ssl_certificate/certificate.crt')  
        keyfile_path = os.path.join(current_dir, 'ssl_certificate/private.key')       
        self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.context.load_cert_chain(certfile=certfile_path, keyfile=keyfile_path)

    def handle_client(self, client_socket):
        try:
            while True:
                data = client_socket.recv(1024)
                if not data:
                    break
                request = deserialize(data)
                if request.type == RequestMessageType.CONNECT:
                    response = self.connect_client(request, client_socket)
                    client_socket.sendall(response)
                    self.send_current_clients_list_to_new_connected_client(client_socket)
                elif request.type == RequestMessageType.ADD_CLIENT:
                    response = self.add_contact(request, client_socket)
                    client_socket.sendall(response)
                elif request.type == RequestMessageType.VIEW_CONTACTS:
                    response = self.send_contacts_list(client_socket)
                    client_socket.sendall(response)
                elif request.type == RequestMessageType.SEND_WMI_COMMAND:
                    self.send_wmi_command(request, client_socket)
                elif request.type == RequestMessageType.SEND_WMI_RESULT:
                    self.handle_wmi_result(request, client_socket)
                elif request.type == RequestMessageType.DISCONNECT:
                    self.disconnect_client(client_socket)
                    return
        except Exception as e:
            self.disconnect_client(client_socket)
            return

    def connect_client(self, request, client_socket):
        client_name = request.params[0]
        client_ip = request.params[1]
        client_info = {'socket': client_socket, 'address': client_ip, 'contacts': []}
        print(f"Client {client_name} connected from IP {client_ip}")
        with self.lock:
            self.connected_clients[client_name] = client_info
            self.notify_clients(f"Hey, see that {client_name} has connected from {client_ip}. Type 'add {client_name}' to add them to your list.", current_client=client_name)
        return serialize(Response(ResponseMessageStatus.OK, f"Welcome {client_name} from {client_ip}!"))

    def send_current_clients_list_to_new_connected_client(self, client_socket):
        current_client_name = self.reverse_lookup(client_socket)
        if current_client_name is None:
            print("Error: Client not found.")
            return

        other_clients = [name for name, info in self.connected_clients.items() if name != current_client_name]
    
        if other_clients:
            formatted_clients = "\n".join([f"{index + 1}. {name} --> IP: {info['address']}" for index, (name, info) in enumerate(self.connected_clients.items()) if name != current_client_name])
            message = f"Current clients:\n{formatted_clients}\nType 'add client_name' to add them to your list."
        else: 
            message = "You are the only client connected."
    
        response = serialize(Response(ResponseMessageStatus.OK, message))
        client_socket.sendall(response)
    
    def add_contact(self, request, client_socket):
        current_client_name = self.reverse_lookup(client_socket)
        target_client_name = request.params[0]
        if target_client_name in self.connected_clients:
            current_client_info = self.connected_clients[current_client_name]
            target_client_info = self.connected_clients[target_client_name]
            current_client_info['contacts'].append((target_client_name, target_client_info['address']))
            response = serialize(Response(ResponseMessageStatus.OK, f"{target_client_name} added to your list."))
        else:
            response = serialize(Response(ResponseMessageStatus.ERROR, "Client name not found."))
        return response

    def send_contacts_list(self, client_socket):
        current_client_name = self.reverse_lookup(client_socket)
        contacts = self.connected_clients[current_client_name]['contacts']
        if contacts:
            formatted_contacts = "\n".join([f"{index + 1}. {name} -> IP: {ip}" for index, (name, ip) in enumerate(contacts)])
            message = f"Clients you are connected to:\n{formatted_contacts}"
        else:
            message = "You have no connected clients in your list."
        return serialize(Response(ResponseMessageStatus.OK, message))
        
    def reverse_lookup(self, client_socket):
        for client_name, info in self.connected_clients.items():
            if info['socket'] == client_socket:
                return client_name
        return None
        
                
    def notify_clients(self, message, current_client):
        msg = serialize(Response(ResponseMessageStatus.OK, message))
        for client_name, info in self.connected_clients.items():
            if client_name != current_client:
                try:
                    info['socket'].send(msg)
                except Exception as e:
                    print(f"Error notifying client {client_name}: {e}")
                    
    def send_wmi_command(self, request, client_socket):
        command_id = str(self.command_id)
        self.command_id += 1
        command_info = {'initiator_socket': client_socket, 'receivers': [], 'result': []}
        self.command_results[command_id] = command_info 

        target_clients = request.params[0].split(',')
        wmi_command = ' '.join(request.params[1:])
        results = {}

        with self.lock:
            for client_name in target_clients:
                if client_name in self.connected_clients:
                    self.command_results[command_id]['receivers'].append(client_name)
                    try:
                        client_info = self.connected_clients[client_name]
                        client_info['socket'].send(serialize(Request(RequestMessageType.SEND_WMI_COMMAND, [command_id, wmi_command])))
                    except Exception as e:
                        results[client_name] = f"Failed to send command: {e}"
                else:
                    results[client_name] = "Client not found"
    
        if not self.command_results[command_id]:
            self.send_results_back(client_socket, command_id)
        
    def handle_wmi_result(self, request, client_socket):
        command_id = request.params[0]
        result = ' '.join(request.params[1:])
        if command_id in self.command_results:
            self.command_results[command_id]['result'].append(result)
            if len(self.command_results[command_id]['result']) == len(self.command_results[command_id]['receivers']):
                self.send_results_back(command_id)

    def send_results_back(self, command_id):
        results = self.command_results[command_id]['result']
        formatted_results = "\n".join(results)
        response = serialize(Response(ResponseMessageStatus.OK, formatted_results))
        client_socket = self.command_results[command_id]['initiator_socket']
        client_socket.sendall(response)
                    
    def disconnect_client(self, client_socket):
        with self.lock:
            client_name = self.reverse_lookup(client_socket)
            if client_name:
                del self.connected_clients[client_name]
                client_socket.close()
                self.notify_clients(f"{client_name} has disconnected. If you had him in your list, it is now removed.", current_client=None)
                for name, info in self.connected_clients.items():
                    info['contacts'] = [contact for contact in info['contacts'] if contact[0] != client_name]
        
    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.host, self.port))
        server_socket.listen(10)
        print(f"Server listening on {self.host}:{self.port}")

        while True:
            client_socket, address = server_socket.accept()
            secure_socket = self.context.wrap_socket(client_socket, server_side=True)
            threading.Thread(target=self.handle_client, args=(secure_socket, )).start()
        



if __name__ == "__main__":
    server = Server()
    server.start()