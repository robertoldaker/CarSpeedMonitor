dest=pi@raspberrypi.local
echo -e "put CarSpeed.py" | sftp $dest
echo -e "put CarSpeedConfig.py" | sftp $dest
echo -e "put CarSpeedProcessor.py" | sftp $dest
echo -e "put CarSpeedConfigureMonitorArea.py" | sftp $dest
echo -e "put CarSpeed_configure.py" | sftp $dest
echo -e "put CarSpeed_configure_area.py" | sftp $dest