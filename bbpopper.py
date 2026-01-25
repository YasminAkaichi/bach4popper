# From https://www.datacamp.com/tutorial/a-complete-guide-to-socket-programming-in-python

import socket
import threading

from store import STORE
from parser import Parser
from interpreter import Interpreter



def server_banner():
    banner = """

 ____  ____    ____                             
| __ )| __ )  |  _ \ ___  _ __  _ __   ___ _ __ 
|  _ \|  _ \  | |_) / _ \| '_ \| '_ \ / _ \ '__|
| |_) | |_) | |  __/ (_) | |_) | |_) |  __/ |   
|____/|____/  |_|   \___/| .__/| .__/ \___|_|   
                         |_|   |_|              

"""
    print(banner)

    
def handle_client(client_socket, addr):
    try:
        while True:
            # receive and print client messages
            request = client_socket.recv(1024).decode("utf-8")
            print("Launching parser for request")
            print(request)
            ast = myparser.parse(request)
            print(f"ast = {ast}")
            print("launching interpreter")
            bool_res, str_res = myinterpreter.eval(ast,client_socket)
            print("interpreter ended")
            print(f"str res = {str_res}")
            if str_res == "close":
                break
    except Exception as e:
        print(f"Error when hanlding client: {e}")
    finally:
        client_socket.close()
        print(f"Connection to client ({addr[0]}:{addr[1]}) closed")


def run_server():
    server_banner()
    server_ip = "127.0.0.1"  # server hostname or IP address
    port = 8000  # server port number
    # create a socket object
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # bind the socket to the host and port
        server.bind((server_ip, port))
        # listen for incoming connections
        server.listen()
        print(f"Listening on {server_ip}:{port}")

        while True:
            # accept a client connection
            client_socket, addr = server.accept()
            print(f"Accepted connection from {addr[0]}:{addr[1]}")
            # start a new thread to handle the client
            thread = threading.Thread(target=handle_client, args=(client_socket, addr,))
            thread.start()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        server.close()


# To be kept as global objects         
mystore = STORE()
myparser = Parser()
myinterpreter = Interpreter(mystore)


run_server()