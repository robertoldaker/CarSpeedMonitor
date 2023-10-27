import logging
import sys
import threading
from typing import Callable
import requests
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol
import platform
from CarSpeedConfig import CarSpeedConfig

from SignalRHandler import SignalRHandler

class CarSpeedMonitorState:
    def __init__(self,state:str,jpg: bytes) -> None:
        self.state=state
        self.frameRate=99.99
        self.detectionEnabled=False
        self.avgContours=0
        self.lightLevel=9
        self.jpg=jpg  

def main():
    def startMonitor(args):
        print('start monitor')
        state = CarSpeedMonitorState("WAITING",jpg)
        signalRHandler.uploadPreview(state)

    def stopMonitor(args):
        print('stop monitor')
        state = CarSpeedMonitorState("IDLE",jpg)
        signalRHandler.uploadPreview(state)

    def toggleDetection(args):
        print('toggle detection')

    def resetTracking(args):
        print('reset tracking')
    
    def shutdown(args):
        print('shutdown')
        exitEvent.set()

    def reboot(args):
        print('reboot')
        exitEvent.set()

    def configEdited(args):
        print('config edited')

    def onConnection(connected: bool):
        if connected:
            print('on connection')
            hubConnectionEvent.set()

    def getConfig()->CarSpeedConfig|None:        
        try:
            # load config from db
            config = loadConfig()
            return config
        except Exception as e:
            print(f'Error loading config [{e.args[0]}]')
            signalRHandler.logMessage(e.args[0])

    def loadConfig()->CarSpeedConfig:
        r = requests.get(f"{rootUrl}/Monitor/Config",params={'monitorName': monitorName})
        if r.status_code==200:
            newConfig = CarSpeedConfig.fromJsonStr(r.text)
            if not newConfig:
                raise Exception("Could not parse config")
        else:
            raise Exception(f"Invalid status code downloading new config [{r.status_code}]")
        return newConfig

    rootUrl = 'http://localhost:5174'
    hubConnectionEvent = threading.Event()
    exitEvent = threading.Event()
    monitorName = platform.node()
    print(f'name={monitorName}')    
    with open('PreviewTest.jpg', 'rb') as file_t:
        jpg = file_t.read()

    signalRHandler = SignalRHandler(rootUrl,monitorName)
    signalRHandler.onConnection = onConnection
    signalRHandler.hub_connection.on("StartMonitor", startMonitor)
    signalRHandler.hub_connection.on("StopMonitor", stopMonitor)
    signalRHandler.hub_connection.on("ToggleDetection", toggleDetection)
    signalRHandler.hub_connection.on("ResetTracking", resetTracking)
    signalRHandler.hub_connection.on("Shutdown", shutdown)
    signalRHandler.hub_connection.on("Reboot", reboot)
    signalRHandler.hub_connection.on("MonitorConfigEdited", configEdited)

    signalRHandler.start()

    print('Waiting for hub connection ...')
    config = getConfig()
    if config:
        print(f'configId={config.id}')
        state = CarSpeedMonitorState("WAITING",jpg)
        signalRHandler.uploadPreview(state)


    print('Waiting for exit ...')
    exitEvent.wait()
    
    signalRHandler.stop()

if __name__ == '__main__':
    main()
