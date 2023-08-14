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


ap = argparse.ArgumentParser()
ap.add_argument("--file","-f", default=CarSpeedConfig.DEF_CONFIG_FILE, help="Filename to store config")
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

cma = ConfigureMonitorArea(config.h_flip,config.v_flip)
if cma.start():
    config.monitor_area = cma.area
    config.h_flip = cma.h_flip
    config.v_flip = cma.v_flip
    print(config.toJson())
    # write out json to config file
    with open(configFile, 'w') as f:
        f.write(config.toJson())

