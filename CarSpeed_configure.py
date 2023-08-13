import subprocess
import json
import argparse
import pathlib
# Determine is we are running in Raspbian
process = subprocess.run(['cat','/etc/os-release'], capture_output=True, check=True, text=True)
if 'Raspbian' in process.stdout:
    IsRaspbian = True    
else:
    IsRaspbian = False

# load a dummy ConfigureMonitorArea if testing this on non-raspbian OS
if ( IsRaspbian):
    from CarSpeed_configure_monitor_area import ConfigureMonitorArea
else:
    from _CarSpeed_configure_monitor_area import ConfigureMonitorArea

class MonitorArea(object):
    def __init__(self,data=None):
        self.class_name = self.__class__.__name__
        self.upper_left_x = 0
        self.upper_left_y = 0
        self.lower_right_x = 0
        self.lower_right_y = 0
        if data:
            self.__dict__ = data

class CarSpeedConfig(object):
    def __init__(self,data=None):
        self.class_name = self.__class__.__name__
        self.l2r_distance = 47
        self.r2l_distance = 37
        self.min_speed_image = 0
        self.min_speed_save = 10
        self.max_speed_save = 80
        self.field_of_view = 75 # 75 is standard pi camera module 3, 120 for wide angle
        self.h_flip = False
        self.v_flip = False
        self.monitor_area = MonitorArea()
        if  data:
            self.__dict__ = data
            

    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)
    @staticmethod
    def fromJsonFile(file):
        with open(configFile,"r") as f:
            return json.load(f, object_hook=CarSpeedConfig._objectHook)
    @staticmethod
    def fromJsonStr(str):
        return json.loads(str, object_hook=CarSpeedConfig._objectHook)
        
    @staticmethod
    def _objectHook(dict):
        print("ObjectHook")
        print(dict)
        if ( 'class_name' in dict):
            class_name = dict['class_name']
            if (class_name=='CarSpeedConfig'):                
                return CarSpeedConfig(dict)
            elif (class_name=='MonitorArea'):            
                return MonitorArea(dict)


def configure_monitor_area():
    print('configure area')
    cma = ConfigureMonitorArea()
    cma.start()
    config.monitor_area = cma.area

ap = argparse.ArgumentParser()
ap.add_argument("--file","-f", default="CarSpeed.json", help="Filename to store config")
args = vars(ap.parse_args())

configFile = args["file"]
configPath = pathlib.Path(configFile)
if ( configPath.exists()):
    print(f"Loading config from  [{configFile}]")
    config = CarSpeedConfig.fromJsonFile(configFile)
    print(config)
else:
    print(f"Creating config file [{configFile}]")
    config = CarSpeedConfig()

def inputFloat(prompt, value):
    text = input(f'{prompt} [{value}]: ')
    if text:
        return float(text)
    else:
        return value

def inputBool(prompt, value):
    if isinstance(value,bool):
        defValue = "y" if value else "n"
    else:
        defValue = value
    text = input(f'{prompt} [{defValue}] (y/n): ')
    if text:
        return True if text.lower().startswith('y') else False
    else:
        return value
    
config.l2r_distance = inputFloat(f"Left to right distance (feet)", config.l2r_distance)
config.r2l_distance = inputFloat(f"Right to left distance (feet)",config.r2l_distance)
config.min_speed_image = inputFloat(f"Min speed for image save (mph)",config.min_speed_image)
config.min_speed_save = inputFloat(f"Min speed to report (mph)",config.min_speed_save)
config.max_speed_save = inputFloat(f"Max speed to report (mph)",config.max_speed_save)
config.field_of_view = inputFloat(f"Camera's field of view (deg)",config.field_of_view)
config.h_flip = inputBool(f"Flip image horizontally?",config.h_flip)
config.v_flip = inputBool(f"Flip image vertically?",config.v_flip)
a = config.monitor_area
value = inputBool(f"Update monitor area?",f"({a.upper_left_x},{a.upper_left_y}),({a.lower_right_x},{a.lower_right_y})")
if value:
    configure_monitor_area()

print(config.toJson())

# write out json to config file
with open(configFile, 'w') as f:
    f.write(config.toJson())
