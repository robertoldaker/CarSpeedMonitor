from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol
import logging

class SignalRHandler:
    def __init__(self,server_root=None,debugLogging=False):
        #\
        if ( not server_root):
            server_root = "http://odin.local:5030"
        self.connected = False
        self.server_url=f'{server_root}/NotificationHub'
        builder= HubConnectionBuilder()\
        .with_url(self.server_url)\
        .with_hub_protocol(MessagePackHubProtocol())\
        .with_automatic_reconnect({
            "type": "raw",
            "keep_alive_interval": 10,
            "reconnect_interval": 5,
            "max_attempts": 5
        })
        if debugLogging:
            builder = builder.configure_logging(logging.DEBUG)
        self.hub_connection = builder.build()

        def onOpen():
            self.connected=True
            print(f"connection opened [{self.server_url}]")

        def onClose():
            self.connected=False
            print("connection closed")

        def monitorStateUpdated(data):
            if debugLogging:
                print("MonitoStateUpdated")
                print(data)

        self.hub_connection.on_open(onOpen)
        self.hub_connection.on_close(onClose)

        self.hub_connection.on("MonitorStateUpdated", monitorStateUpdated)
    
    def start(self):
        self.hub_connection.start()
    
    def stop(self):
        self.hub_connection.stop()
    
    def uploadPreview(self,st):
        if self.connected:
            state=st.__dict__
            self.hub_connection.send(
                "PreviewState", # Method
                [state], # Params
            )

    def logMessage(self,mess):
        if self.connected:
            self.hub_connection.send(
                "LogMessage", # Method
                [mess], # Params
            )            