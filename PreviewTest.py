import os
import threading
import time
from SignalRHandler import SignalRHandler

class CarSpeedMonitorState:
    def __init__(self,jpg,state:str, frameRate:float, detectionEnabled: bool, avgContours: int) -> None:
        self.jpg=jpg
        self.state=state
        self.frameRate=frameRate
        self.detectionEnabled=detectionEnabled
        self.avgContours=avgContours
    

def main():
    def restartMe():
        os.system(f'nohup bash python_starter.sh "{__file__}"')

    def logContinuous():
        x=1
        while not exitThreads:
            signalR.logMessage(f'Hello world! {x}')
            x+=1
            time.sleep(1)
        print("exiting logContinuous")
    
    key = None
    signalR = SignalRHandler("http://localhost:5174","test",debugLogging=False)
    signalR.start()

    with open('PreviewTest.jpg', 'rb') as file_t:
        jpg = file_t.read()

    state=CarSpeedMonitorState(jpg,"WAITING",19,True,99)

    exitThreads=False
    logThread = threading.Thread(target=logContinuous)
    logThread.start()

    while key != "e":        
        key = input(f">>")
        if key == "u":
            signalR.uploadPreview(state)
            state.detectionEnabled=not state.detectionEnabled
            state.frameRate+=1
            state.avgContours+=1
        if key=="r":
            restartMe()

    exitThreads = True
    signalR.stop()

if __name__ == '__main__':
    main()

