from CarSpeedMonitor import CarSpeedMonitor, DetectionResult
from CarSpeedConfig import CarSpeedConfig
from datetime import date
from datetime import datetime
from pathlib import Path
import os
import argparse

def car_detected(data: DetectionResult):
    cap_time = datetime.fromtimestamp(data.posix_time)
    count = len(data.tracking_data)
    csv_str=(cap_time.strftime("%Y-%m-%d") + ' ' +\
                cap_time.strftime('%H:%M:%S:%f')+','+("%.0f" % data.mean_speed) + ',' +\
    ("%d" % int(data.direction)) + ',' + ("%d" % count) + ','+ ("%d" % data.sd))
    with open(csv_filename, 'a') as f:
        f.write(csv_str+"\n")


ap = argparse.ArgumentParser(description="Monitors car speed using raspberry pi camera")
ap.add_argument("--file","-f", default=CarSpeedConfig.DEF_CONFIG_FILE, help="Filename to store config")
ap.add_argument("--preview","-p", action='store_true', help="Create preview window")
args = vars(ap.parse_args())

show_preview = args["preview"]

# create csv file if not exist
today = date.today()
folder="csv"
csv_filename = f"{folder}/CarSpeed_{today.year:04}-{today.month:02}-{today.day:02}.csv"
folder_path = Path(folder)
if not folder_path.is_dir():
    os.makedirs(folder)

csv_path = Path(csv_filename)
if not csv_path.exists():
    header = 'DateTime,Speed,Direction, Counter,SD\n'
    with open(csv_filename, 'w') as f:
        f.write(header)

# open config
config = CarSpeedConfig.fromDefJsonFile()
# start the monitor
if config!=None:
    proc = CarSpeedMonitor(config)
    proc.start(detection_hook=car_detected,show_preview=show_preview)

