dest=$1
if [ "$dest" = "-p" ]; then
	destServ="rob@speedy-prod.local"
    echo "1 [$destServ]"
elif [ "$dest" = "-d" ]; then
    destServ="pi@speed-dev.local"
    echo "2 [$destServ]"
else
    echo "Usage: bash deploy.sh [-p|-s]"
    exit 1
fi
files=("SignalRHandler.py" "SignalRTest.py" "CarSpeed_client.py" "CameraTest.py" "Legacy\ versions/carspeed_version_3\ (picamera2).py" "CarSpeed.py" "CarSpeedConfig.py" "CarSpeedMonitor.py" "CarSpeedConfigureMonitorArea.py" "CarSpeed_configure.py" "CarSpeed_configure_area.py")
cmd=""
for file in "${files[@]}"
do
    cmd=$cmd"put $file\n"
done
echo -e "$cmd" | sftp $destServ
