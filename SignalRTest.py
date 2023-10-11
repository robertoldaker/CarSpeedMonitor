import logging
from typing import Callable
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol

class SignalRHandler:
    def __init__(self):
        #        .configure_logging(logging.DEBUG)\
        server_url = "http://localhost:5174/NotificationHub"
        self.hub_connection = HubConnectionBuilder()\
        .with_url(server_url)\
        .with_hub_protocol(MessagePackHubProtocol())\
        .with_automatic_reconnect({
            "type": "raw",
            "keep_alive_interval": 10,
            "reconnect_interval": 5,
            "max_attempts": 5
        }).build()

        self.hub_connection.on_open(lambda: print("connection opened and handshake received ready to send messages"))
        self.hub_connection.on_close(lambda: print("connection closed"))

        self.hub_connection.on("NewDetectionLoaded", SignalRHandler.newDetectionLoaded)
    
    def start(self):
        self.hub_connection.start()
    
    def stop(self):
        self.hub_connection.stop()
    
    def uploadPreview(self,image):
        #send_callback_received = threading.Lock()
        #send_callback_received.acquire()
        #image="hello!"
        #image = bytearray()
        #image.append(0xA2)
        #image.append(0x01)
        #image.append(0x02)
        #image.append(0x03)
        #image.append(0x04)
        image = memoryview(b'still allows embedded "double" quotes')
        self.hub_connection.send(
            "PreviewImage", # Method
            [image], # Params
        )
            #lambda m: send_callback_received.release()) # Callback
        #if not send_callback_received.acquire(timeout=1):
        #    raise ValueError("CALLBACK NOT RECEIVED")

    @staticmethod
    def newDetectionLoaded(args):
        print("New detection loaded!!")


def messageReceived(args):
    print("message received!!!")

def main():
    key = None
    sigr = SignalRHandler()
    sigr.start()
    while key != "e":        
        key = input(">> ")
        if key == "u":
            sigr.uploadPreview(1)

if __name__ == '__main__':
    main()
