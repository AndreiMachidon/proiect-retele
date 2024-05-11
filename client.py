import socket
import threading
import ssl
import os
import wmi
import pythoncom
from util import *;

class Client:
    def __init__(self):
        self.host = '172.28.208.1'
        self.port = 3333
        self.initialise_ssl_credentials()

    def listen_for_messages(self):
        try:
            while True:
                message = self.secure_socket.recv(1024)
                if not message:
                    break

                deserialized_message = deserialize(message)

                if isinstance(deserialized_message, Request) and deserialized_message.type == RequestMessageType.SEND_WMI_COMMAND:
                    command_id = deserialized_message.params[0]
                    wmi_command = ' '.join(deserialized_message.params[1:])
                    result = self.execute_wmi_command(wmi_command)
                    self.send_wmi_result(command_id, result)
                    continue
        
            
                if isinstance(deserialized_message, Response):
                    if deserialized_message.status == ResponseMessageStatus.OK:   
                        print("Message from the server: \n", deserialized_message.payload)
                    else:
                        print("Received an error message from the server: \n", deserialized_message.payload)
                else:
                    print("Received a non-response message, handling not implemented: \n", deserialized_message.params)
            
                print("> ", end='', flush=True)    
                 
        except Exception as e:
            print("An error occurred while receiving the message:", e)
        
    def execute_wmi_command(self, command):
        pythoncom.CoInitialize()
        try:
            wmi_client = wmi.WMI()
            output = wmi_client.query(command)
            result = '\n'.join([str(item) for item in output])
        except Exception as e:
            result = f"Error executing WMI command: {str(e)}"
        finally:
            pythoncom.CoUninitialize()
        return result
            
    def send_wmi_result(self, command_id, result):
        self.send_command(RequestMessageType.SEND_WMI_RESULT, [command_id, result])
            
    def initialise_ssl_credentials(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        certfile_path = os.path.join(current_dir, 'ssl_certificate/certificate.crt')
        self.context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        self.context.load_verify_locations(certfile_path)
        self.context.check_hostname = False
        self.context.verify_mode = ssl.CERT_REQUIRED
        
    def send_command(self, command, params=None):
        if not params:
            params = []
        request = Request(type=command, params=params)
        serialized_request = serialize(request)
        self.secure_socket.sendall(serialized_request)

        
    def connect_to_server(self):
        plain_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.secure_socket = self.context.wrap_socket(plain_socket, server_hostname=self.host)
        self.secure_socket.connect((self.host, self.port))
        print("Securely connected to server.")
        self.listen_thread = threading.Thread(target=self.listen_for_messages)
        self.listen_thread.start()
        
    def start(self):
        self.connect_to_server()
        machine_name = socket.gethostname()
        machine_ip = socket.gethostbyname(machine_name)
        print("Commands:\n",
          "- 'add [client_name]' to add a client to your contacts\n",
          "- 'list' to see the list of connected clients\n",
          "- 'wmi [clients_names] [command]' to send a WMI command to the specified client(s)\n",
          "- 'exit' to disconnect\n")
        self.send_command(RequestMessageType.CONNECT, [machine_name, machine_ip])

        while True:
            user_input = input("> ")
            try:
                self.handle_input(user_input)
            except Exception as e:
                print(f"An error occurred: {e}")

    def handle_input(self, user_input):
        if user_input == 'exit':
            self.send_command(RequestMessageType.DISCONNECT)
            self.secure_socket.close()
        elif user_input.startswith('add '):
            self.handle_add_command(user_input)
        elif user_input == 'list':
            self.send_command(RequestMessageType.VIEW_CONTACTS, socket.gethostname())
        elif user_input.startswith('wmi '):
            self.handle_wmi_command(user_input)
        else:
            print("Unknown command. Please try again.")

    def handle_add_command(self, user_input):
        add_command_info = user_input.split(' ')
        if len(add_command_info) != 2:
            print("Invalid command. Please try again.")
        else:
            client_name = add_command_info[1]
            self.send_command(RequestMessageType.ADD_CLIENT, [client_name])

    def handle_wmi_command(self, user_input):
        command_parts = user_input.split(' ', 2)
        if len(command_parts) != 3:
            print("Invalid command. Usage: wmi [client1,client2,...] [command]")
        else:
            target_clients = command_parts[1].split(',')
            wmi_command = command_parts[2]
            self.send_command(RequestMessageType.SEND_WMI_COMMAND, [','.join(target_clients), wmi_command])
        

        
if __name__ == "__main__":
    client = Client()
    client.start()
