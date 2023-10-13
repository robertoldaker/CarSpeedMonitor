import threading
from CarSpeedMonitor import CarSpeedMonitor, CarSpeedMonitorState, DetectionResult
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
    def __init__(self,rootUrl:str):
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
        print('Upload queue stopped')

class PreviewUploader:
    def __init__(self,rootUrl:str):
        self.uploadQueue = Queue()
        self.process = Process(target=PreviewUploader.uploadWorker,args=[self.uploadQueue,rootUrl,])
        self.process.start()
    
    def uploadPreview(self,result:CarSpeedMonitorState):
        if self.uploadQueue.empty():
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
    def uploadWorker(q: Queue,rootUrl:str):
        signalRHandler = SignalRHandler(rootUrl)
        signalRHandler.start()
        for state in iter(q.get, 'STOP'):
            st:float = time.monotonic()
            state.generateJpg()
            signalRHandler.uploadPreview(state)
            ft=time.monotonic()
        print('Upload queue stopped')
        signalRHandler.stop()
        print('signalRhandler stopped')

class MessageUploader:
    def __init__(self,rootUrl:str):
        self.uploadQueue = Queue()
        self.process = Process(target=MessageUploader.uploadWorker,args=[self.uploadQueue,rootUrl,])
        self.process.start()
        
    def uploadMessage(self,mess:str):
        self.uploadQueue.put(mess)

    def stop(self):
        self.uploadQueue.put('STOP')
            
    @staticmethod
    def uploadWorker(q: Queue,rootUrl:str):
        signalRHandler = SignalRHandler(rootUrl)
        signalRHandler.start()
        for state in iter(q.get, 'STOP'):
            signalRHandler.logMessage(state)
            ft=time.monotonic()
        print('Upload message queue stopped')
        signalRHandler.stop()
        print('signalRhandler stopped')

def main():

    def car_detected(result: DetectionResult):
        detectionUploader.upload(result)

    def preview_available(state:CarSpeedMonitorState):
        previewUploader.uploadPreview(state)
    
    def logMessage(mess: str):
        messageUploader.uploadMessage(mess)

    ap = argparse.ArgumentParser(description="Monitors car speed using raspberry pi camera")
    ap.add_argument("--file","-f", default=CarSpeedConfig.DEF_CONFIG_FILE, help="Filename to store config")
    ap.add_argument("--preview","-p", action='store_true', help="Create preview window")
    args = vars(ap.parse_args())

    show_preview = args["preview"]
    rootUrl = 'http://odin.local:5030'

    detectionUploader = DetectionUploader(rootUrl)
    previewUploader = PreviewUploader(rootUrl)
    messageUploader = MessageUploader(rootUrl)

    # open config
    config = CarSpeedConfig.fromDefJsonFile()

    
    # start the monitor
    if config!=None:
        proc = CarSpeedMonitor(config)
        proc.start(detection_hook=car_detected,preview_hook=preview_available,logger_hook=logMessage,show_preview=show_preview)
        detectionUploader.stop()
        print('detection uploader stopped')
        previewUploader.stop()
        print('preview uploader stopped')

if __name__ == '__main__':
    main()