from CarSpeedConfig import CarSpeedConfig
import argparse
import pathlib
import subprocess

# Determine is we are running in Raspbian
process = subprocess.run(['cat','/etc/os-release'], capture_output=True, check=True, text=True)
if 'Raspbian' in process.stdout:
    IsRaspbian = True    
else:
    IsRaspbian = False

# load a dummy ConfigureMonitorArea if testing this on non-raspbian OS
if ( IsRaspbian):
    from CarSpeedConfigureMonitorArea import ConfigureMonitorArea
else:
    from _CarSpeedConfigureMonitorArea import ConfigureMonitorArea

def configure_monitor_area():
    print('configure area')
    cma = ConfigureMonitorArea(h_flip=config.h_flip,v_flip=config.v_flip)
    cma.start()
    config.monitor_area = cma.area

ap = argparse.ArgumentParser()
ap.add_argument("--file","-f", default=CarSpeedConfig.DEF_CONFIG_FILE, help="Filename to store config")
args = vars(ap.parse_args())

configFile = args["file"]
configPath = pathlib.Path(configFile)
if ( configPath.exists()):
    print(f"Loading config from  [{configFile}]")
    config = CarSpeedConfig.fromJsonFile(configFile)
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
a = config.monitor_area
value = inputBool(f"Update monitor area?",f"({a.upper_left_x},{a.upper_left_y}),({a.lower_right_x},{a.lower_right_y})")
if value:
    configure_monitor_area()

print(config.toJson())

# write out json to config file
with open(configFile, 'w') as f:
    f.write(config.toJson())
