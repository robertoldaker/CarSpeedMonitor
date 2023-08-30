from CarSpeedMonitor import CarSpeedMonitor, DetectionResult
from CarSpeedConfig import CarSpeedConfig
from datetime import date
from datetime import datetime
from pathlib import Path
import os
import argparse
import cv2
import time

class CsvWriter:
    def __init__(self):
        # create csv file if not exist
        today = date.today()
        folder="csv"
        self._filename = f"{folder}/CarSpeed_{today.year:04}-{today.month:02}-{today.day:02}.csv"
        folder_path = Path(folder)
        if not folder_path.is_dir():
            os.makedirs(folder)
        csv_path = Path(self._filename)
        if not csv_path.exists():
            header = 'DateTime,Speed,Direction,Counter,SD\n'
            with open(self._filename, 'w') as f:
                f.write(header)

    def add(self,data: DetectionResult):
        cap_time = datetime.fromtimestamp(data.posix_time)
        count = len(data.tracking_data)
        csv_str=(cap_time.strftime("%Y-%m-%d") + ' ' +\
                    cap_time.strftime('%H:%M:%S:%f')+','+("%.0f" % data.mean_speed) + ',' +\
        ("%d" % int(data.direction)) + ',' + ("%d" % count) + ','+ ("%d" % data.sd))
        with open(self._filename, 'a') as f:
            f.write(csv_str+"\n")


class DetectionSaver:
    def __init__(self):
        pass

    def save(self,result: DetectionResult):
        cap_time = datetime.fromtimestamp(result.posix_time)
        # and save the image to disk
        folder = f'detections/{cap_time.year:04}-{cap_time.month:02}-{cap_time.day:02}'
        folderPath = Path(folder)
        if not folderPath.is_dir():
            os.makedirs(folder)        
        fileRoot = folder + "/detection_" + cap_time.strftime("%Y-%m-%d_%H-%M-%S")        

        # main image file
        imageFilename =  fileRoot + ".jpg"
        cv2.imwrite(imageFilename,result.image)

        # json file with metadata
        jsonFilename=fileRoot + ".json"
        # write out json to config file
        with open(jsonFilename, 'w') as f:
            f.write(result.toJson())

        # also images in tracking data
        folderPath = Path(fileRoot)
        if not folderPath.is_dir():
            os.makedirs(fileRoot)        
        index=0
        for td in result.tracking_data:
            imageFilename = f"{fileRoot}/{index}.jpg"
            cv2.imwrite(imageFilename,td.image)
            index+=1


        
        

def car_detected(data: DetectionResult):
    st:float = time.monotonic()
    detectionSaver.save(data)
    csvWriter.add(data)
    ft=time.monotonic()
    print(f"saved in {(ft-st):6.3f}s")


ap = argparse.ArgumentParser(description="Monitors car speed using raspberry pi camera")
ap.add_argument("--file","-f", default=CarSpeedConfig.DEF_CONFIG_FILE, help="Filename to store config")
ap.add_argument("--preview","-p", action='store_true', help="Create preview window")
args = vars(ap.parse_args())

show_preview = args["preview"]

csvWriter = CsvWriter()
detectionSaver = DetectionSaver()

# open config
config = CarSpeedConfig.fromDefJsonFile()

# start the monitor
if config!=None:
    proc = CarSpeedMonitor(config)
    proc.start(detection_hook=car_detected,show_preview=show_preview)



