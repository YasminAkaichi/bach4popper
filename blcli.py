import socket

def cli_prompt():
    banner = """
 ____   _      ____              ____  _  _ 
| __ ) | |    |  _ \  _   _     / ___|| |(_)
|  _ \ | |    | |_) || | | |   | |    | || |
| |_) || |___ |  __/ | |_| |   | |___ | || |
|____/ |_____||_|     \__, |    \____||_||_|
                      |___/               

"""
    print(banner)


    
def run_client():
    # create a socket object
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # establish connection with server
    server_ip = "127.0.0.1"  # replace with the server's IP address
    server_port = 8000  # replace with the server's port number
    client.connect((server_ip, server_port))

    try:
        cli_prompt()
        while True:
            # get input message from user and send it to the server
            msg = input("Bach:   ")
            client.send(msg.encode("utf-8")[:1024])

            # receive message from the server
            response = client.recv(1024)
            response = response.decode("utf-8")

            # if server sent us "closed" in the payload, we break out of
            # the loop and close our socket
            if response.lower() == "closed":
                break

            print(f"   >>>  {response}\n")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # close client socket (connection to the server)
        client.close()
        print("Connection to server closed")


run_client()

