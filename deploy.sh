dest=pi@raspberrypi.local
files=("SignalRHandler.py" "SignalRTest.py" "CarSpeed_upload.py" "CameraTest.py" "Legacy\ versions/carspeed_version_3\ (picamera2).py" "CarSpeed.py" "CarSpeedConfig.py" "CarSpeedMonitor.py" "CarSpeedConfigureMonitorArea.py" "CarSpeed_configure.py" "CarSpeed_configure_area.py")
cmd=""
for file in "${files[@]}"
do
    cmd=$cmd"put $file\n"
done
echo -e "$cmd" | sftp $dest
