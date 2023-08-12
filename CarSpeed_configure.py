import json
import argparse
from CarSpeed_configure_monitor_area import ConfigureMonitorArea
from CarSpeed_configure_monitor_area import MonitorArea

class CarSpeedConfig(object):
    def __init__(self):
        self.l2r_distance = 47
        self.r2l_distance = 37
        self.min_speed_image = 0
        self.min_speed_save = 10
        self.max_speed_save = 80
        self.field_of_view = 75 # 75 is standard pi camera module 3, 120 for wide angle
        self.h_flip = False
        self.v_flip = False
        self.monitor_area = MonitorArea(50,50,550,250)

    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)

def configure_monitor_area():
    cma = ConfigureMonitorArea()
    cma.start()
    config.monitor_area = cma.area

ap = argparse.ArgumentParser()
ap.add_argument("--file","-f", default="carspeed.json", help="Filename to store config")
args = vars(ap.parse_args())

configFile = args["file"]

print(f"Configure CarSpeed [{configFile}]")
config = CarSpeedConfig()

value = input(f"Left to right distance (feet) [{config.l2r_distance}]: ")
if value:
    config.l2r_distance = value

value = input(f"Right to left distance (feet) [{config.r2l_distance}]: ")
if value:
    config.r2l_distance = value

value = input(f"Min speed for image save (mph) [{config.min_speed_image}]: ")
if value:
    config.min_speed_image = value

value = input(f"Min speed to report (mph) [{config.min_speed_save}]: ")
if value:
    config.min_speed_save = value

value = input(f"Max speed to report (mph) [{config.max_speed_save}]: ")
if value:
    config.max_speed_save = value

value = input(f"Camera's field of view (deg) [{config.field_of_view}]: ")
if value:
    config.field_of_view = value

prompt = "y" if config.h_flip else "n"
value = input(f"Flip image horizontally ? [{prompt}] (y/n): ")
config.h_flip = True if value.lower()=='y' else False

prompt = "y" if config.v_flip else "n"
value = input(f"Flip image vertically ? [{prompt}] (y/n): ")
config.v_flip = True if value.lower()=='y' else False

a = config.monitor_area
value = input(f"Update monitor area? [({a.upper_left_x},{a.upper_left_y}),({a.lower_right_x},{a.lower_right_y})] (y/n): ")
if value.lower()=='y':
    configure_monitor_area()

print(config.toJson())

