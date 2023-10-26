import platform
import signal
import threading
from CarSpeedMonitor import CarSpeedMonitor, CarSpeedMonitorState, Commands, DetectionResult
from CarSpeedConfig import CarSpeedConfig
from SignalRHandler import SignalRHandler
from datetime import date
from datetime import datetime
from pathlib import Path
import os
import argparse
import cv2
import time
from zipfile import ZipFile
import requests
from multiprocessing import Process, Queue
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol
import logging

class DetectionUploader:
    def __init__(self,rootUrl:str,configId:int):
        self.uploadQueue = Queue()
        self.rootUrl = rootUrl
        self.process = Process(target=DetectionUploader.uploadWorker,args=[self.uploadQueue,rootUrl,])        
        self.process.start()
    
    def upload(self,result: DetectionResult):
        self.uploadQueue.put(result)
    
    def stop(self):
        self.uploadQueue.put('STOP')
    
    @staticmethod
    def saveZipfile(result: DetectionResult)->str:
        cap_time = datetime.fromtimestamp(result.posix_time)
        # and save the image to disk
        folder = f'detections/{cap_time.year:04}-{cap_time.month:02}-{cap_time.day:02}'
        folderPath = Path(folder)
        if not folderPath.is_dir():
            os.makedirs(folder)        
        fileRoot = folder + "/detection_" + cap_time.strftime("%Y-%m-%d_%H-%M-%S")   

        # save to zip file
        zipFilename = fileRoot + '.zip'
        with ZipFile(zipFilename, 'w') as myzip:
            jsonFilename=f"{fileRoot}/detection_data.json"
            myzip.writestr(jsonFilename,result.toJson())
            if not result.image is None:
                imageFilename =  f"{fileRoot}/detection_image.jpg";
                jpgData = cv2.imencode('.jpg', result.image)[1]
                myzip.writestr(imageFilename,jpgData)
            index=0
            for td in result.tracking_data:
                imageFilename = f"{fileRoot}/{index}.jpg"
                jpgData = cv2.imencode('.jpg', td.image)[1]
                myzip.writestr(imageFilename,jpgData)
                index+=1

        return zipFilename

    @staticmethod
    def uploadZipfile(fn,rootUrl: str):
        # upload to website
        uploaded = False
        with open(fn, 'rb') as f:
            files = {"file": f}
            try:
                r = requests.post(f"{rootUrl}/Detections/Upload", files=files)
                if r.status_code==200:
                    uploaded = True
                else:
                    print(f"Invalid status code uploaded detection [{r.status_code}]");
            except:
                print(f"Problem uploading detection")                
        if uploaded:
            os.remove(fn)
        
    @staticmethod
    def uploadWorker(q: Queue, rootUrl: str):
        for dr in iter(q.get, 'STOP'):
            fn = DetectionUploader.saveZipfile(dr)
            DetectionUploader.uploadZipfile(fn,rootUrl)

class PreviewUploader:
    def __init__(self,rootUrl:str,monitorName:str):
        self.uploadQueue = Queue()
        self.process = Process(target=PreviewUploader.uploadWorker,args=[self.uploadQueue,rootUrl,monitorName,])
        self.process.start()
    
    def uploadPreview(self,result:CarSpeedMonitorState):
        # always send if state idle since only one of these is sent and it needs to get through for the state to change in the gui
        if self.uploadQueue.empty() or result.state=='IDLE':
            self.uploadQueue.put(result)
        else:
            pass
    
    def stop(self):
        self.uploadQueue.put('STOP')
            
    @staticmethod
    def _uploadWorker(q: Queue):
        for fn in iter(q.get, 'STOP'):
            print(fn)

    @staticmethod
    def uploadWorker(q: Queue,rootUrl:str,monitorName:str):
        signalRHandler = SignalRHandler(rootUrl,monitorName)
        signalRHandler.start()
        for state in iter(q.get, 'STOP'):
            st:float = time.monotonic()
            state.generateJpg()
            signalRHandler.uploadPreview(state)
            ft=time.monotonic()
        signalRHandler.stop()

class MessageUploader:
    def __init__(self,rootUrl:str,monitorName:str):
        self.uploadQueue = Queue()
        self.process = Process(target=MessageUploader.uploadWorker,args=[self.uploadQueue,rootUrl,monitorName,])
        self.process.start()
        
    def uploadMessage(self,mess:str):
        self.uploadQueue.put(mess)

    def stop(self):
        self.uploadQueue.put('STOP')
            
    @staticmethod
    def uploadWorker(q: Queue,rootUrl:str,monitorName:str):
        signalRHandler = SignalRHandler(rootUrl,monitorName)
        signalRHandler.start()
        for state in iter(q.get, 'STOP'):
            signalRHandler.logMessage(state)
            ft=time.monotonic()
        signalRHandler.stop()

def main():

    def processCommand():
        nonlocal command
        if command!=Commands.CONTINUE:            
            newCommand = command
            command = Commands.CONTINUE
            return newCommand
        else:
            return Commands.CONTINUE

    def car_detected(result: DetectionResult):
        if detectionUploader and config:
            result.configId=config.id
            detectionUploader.upload(result)

    def preview_available(state:CarSpeedMonitorState):
        if previewUploader:
            previewUploader.uploadPreview(state)
    
    def logMessage(mess: str):
        if messageUploader:
            messageUploader.uploadMessage(mess)
    
    def start():
        nonlocal running
        while(not exitProgram and config):
            running = True
            proc.setConfig(config)
            proc.start(detection_hook=car_detected,command_hook=processCommand,preview_hook=preview_available,logger_hook=logMessage,show_preview=False)
            running=False
            if not exitProgram:
                notRunningEvent.wait()
                notRunningEvent.clear()

    def signal_handler(sig, frame):
        startExit()
    
    def startExit():
        # this should allow us to exit gracefully        
        nonlocal exitProgram, command
        # exception check needed since this get called for each of the 4 processes
        # and running does not exists in those contexts
        try:
            hubConnectionEvent.set()
            exitProgram=True
            if running:
                command=Commands.EXIT
            else:
                notRunningEvent.set()
            print('Exiting ....')
        except NameError:
            pass

    def startMonitor(args):
        notRunningEvent.set()        

    def stopMonitor(args):
        nonlocal command
        if running:
            command = Commands.EXIT

    def toggleDetection(args):
        nonlocal command
        if running:
            command = Commands.TOGGLE_DETECTION

    def resetTracking(args):
        nonlocal command
        if running:
            command = Commands.RESET_TRACKING 
    
    def shutdown(args):
        nonlocal shutdownOnExit
        shutdownOnExit=True
        startExit()

    def reboot(args):
        nonlocal rebootOnExit
        rebootOnExit=True
        startExit()

    def configEdited(args):
        nonlocal config
        try:
            # load config from db
            config = loadConfig()
            stopMonitor(None)
            startMonitor(None)
        except Exception as e:
            print("Error loading config from db")
            print(e.args)
            signalRHandler.logMessage(e.args)
    
    def getConfig():        
        try:
            # load config from db
            config = loadConfig()
            return config
        except Exception as e:
            print(f'error loading config [{e.args[0]}]')
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
    
    def onConnection(connected)->None:
        if connected:
            hubConnectionEvent.set()

    # set up SIGINT handler (for ctrl-c) so we can exit gracefully
    signal.signal(signal.SIGINT, signal_handler)
    
    ap = argparse.ArgumentParser(description="Car speed monitor client")
    ap.add_argument("--server","-s", default="production", help="Server to use")
    args = vars(ap.parse_args())

    server = args["server"]
    if ( server == 'production'):
        rootUrl = 'http://odin.local:5030'
    else:
        rootUrl = 'http://ser5.local:5174' 

    print(f"Car speed monitor client, configured with url [{rootUrl}]")

    detectionUploader=None
    previewUploader=None
    messageUploader=None
    command = Commands.CONTINUE
    exitProgram = False
    shutdownOnExit=False
    rebootOnExit=False
    running = False
    notRunningEvent = threading.Event()
    hubConnectionEvent = threading.Event()

    monitorName = platform.node()
    signalRHandler = SignalRHandler(rootUrl,monitorName=monitorName,debugLogging=False)
    signalRHandler.onConnection = onConnection
    signalRHandler.hub_connection.on("StartMonitor", startMonitor)
    signalRHandler.hub_connection.on("StopMonitor", stopMonitor)
    signalRHandler.hub_connection.on("ToggleDetection", toggleDetection)
    signalRHandler.hub_connection.on("ResetTracking", resetTracking)
    signalRHandler.hub_connection.on("Shutdown", shutdown)
    signalRHandler.hub_connection.on("Reboot", reboot)
    signalRHandler.hub_connection.on("MonitorConfigEdited", configEdited)
    signalRHandler.start()
    #
    print('Waiting for hub connection ...')
    hubConnectionEvent.wait()
    if not exitProgram:
        # set new config
        config = getConfig()
        # start
        if config:
            previewUploader = PreviewUploader(rootUrl,monitorName)
            messageUploader = MessageUploader(rootUrl,monitorName)
            detectionUploader = DetectionUploader(rootUrl,config.id)
            proc = CarSpeedMonitor(config)
            start()

    if detectionUploader:
        detectionUploader.stop()
    if previewUploader:
        previewUploader.stop()
    if messageUploader:
        messageUploader.stop()
    signalRHandler.stop()
    if shutdownOnExit:
        print('shutting down os ...')
        os.system('nohup sudo shutdown now')
    if rebootOnExit:
        print('rebooting os ...')
        os.system('nohup sudo reboot')

if __name__ == '__main__':
    main()