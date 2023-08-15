dest=pi@raspberrypi.local
files=("CarSpeed.py" "CarSpeedConfig.py" "CarSpeedMonitor.py" "CarSpeedConfigureMonitorArea.py" "CarSpeed_configure.py" "CarSpeed_configure_area.py")
cmd=""
for file in "${files[@]}"
do
    cmd=$cmd"put $file\n"
done
echo -e "$cmd" | sftp $dest
