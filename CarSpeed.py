from CarSpeedMonitor import CarSpeedMonitor
from CarSpeedConfig import CarSpeedConfig
from datetime import date
from datetime import datetime
from pathlib import Path
import os

def car_detected(data):
    cap_time = datetime.fromtimestamp(data.posix_time)
    csv_str=(cap_time.strftime("%Y-%m-%d") + ' ' +\
                cap_time.strftime('%H:%M:%S:%f')+','+("%.0f" % data.mean_speed) + ',' +\
    ("%d" % int(data.direction)) + ',' + ("%d" % data.counter) + ','+ ("%d" % data.sd))
    with open(csv_filename, 'a') as f:
        f.write(csv_str+"\n")

print('CarSpeed monitor')
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
proc = CarSpeedMonitor(config)
proc.start(detection_hook=car_detected)

