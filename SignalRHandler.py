from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol
import logging
import time

class SignalRHandler:
    def __init__(self,server_root,onConnection=None,debugLogging=False):
        self.onConnection = onConnection
        self.connected = False
        self.server_url=f'{server_root}/NotificationHub'
        builder= HubConnectionBuilder()\
        .with_url(self.server_url)\
        .with_hub_protocol(MessagePackHubProtocol())\
        .with_automatic_reconnect({
            "type": "raw",
            "keep_alive_interval": 10,
            "reconnect_interval": 5,
            "max_attempts": 100000
        })
        if debugLogging:
            builder = builder.configure_logging(logging.DEBUG)
        self.hub_connection = builder.build()

        def onOpen():
            self.connected=True
            if self.onConnection:
                self.onConnection(self.connected)
            print(f"Connection opened [{self.server_url}]")

        def onClose():
            self.connected=False
            if self.onConnection:
                self.onConnection(self.connected)
            print("Connection closed")

        self.hub_connection.on_open(onOpen)
        self.hub_connection.on_close(onClose)
    
    def start(self):
        cont = True
        firstException=True
        while cont:
            try:
                self.hub_connection.start()
                cont = False
            except:
                if firstException:
                    print(f"Waiting to connect to server [{self.server_url}]")
                    firstException=False
                time.sleep(1)
    
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

    def uploadConfig(self,config):
        print(f'UploadConfig')
        print(config)
        if self.connected:
            print(f'Sending monito config')
            monitorConfig = config.shortDict()
            self.hub_connection.send("MonitorConfig",[monitorConfig])