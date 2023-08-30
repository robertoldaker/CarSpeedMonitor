from CarSpeedMonitor import CarSpeedMonitor, DetectionResult
from CarSpeedConfig import CarSpeedConfig
from datetime import date
from datetime import datetime
from pathlib import Path
import os
import argparse
import cv2
import time
from zipfile import ZipFile
import requests 

class DetectionUploader:
    def __init__(self):
        pass

    def upload(self,result: DetectionResult):
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

        # upload to website
        with open(zipFilename, 'rb') as f:
            files = {"file": f}            
            r = requests.post("http://ser5.local:5174/Detections/Upload", files=files) 
            print(r.status_code)
            print(r.text)


def car_detected(data: DetectionResult):
    st:float = time.monotonic()
    detectionUploader.upload(data)
    ft=time.monotonic()
    print(f"uploaded in {(ft-st):6.3f}s")


ap = argparse.ArgumentParser(description="Monitors car speed using raspberry pi camera")
ap.add_argument("--file","-f", default=CarSpeedConfig.DEF_CONFIG_FILE, help="Filename to store config")
ap.add_argument("--preview","-p", action='store_true', help="Create preview window")
args = vars(ap.parse_args())

show_preview = args["preview"]

detectionUploader = DetectionUploader()

# open config
config = CarSpeedConfig.fromDefJsonFile()

# start the monitor
if config!=None:
    proc = CarSpeedMonitor(config)
    proc.start(detection_hook=car_detected,show_preview=show_preview)