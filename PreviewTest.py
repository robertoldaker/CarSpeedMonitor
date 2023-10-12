from SignalRHandler import SignalRHandler

class CarSpeedMonitorState:
    def __init__(self,jpg,state:str, frameRate:float, detectionEnabled: bool, avgContours: int) -> None:
        self.jpg=jpg
        self.state=state
        self.frameRate=frameRate
        self.detectionEnabled=detectionEnabled
        self.avgContours=avgContours
    

def main():
    key = None
    signalR = SignalRHandler("http://localhost:5174",debugLogging=False)
    signalR.start()

    with open('PreviewTest.jpg', 'rb') as file_t:
        jpg = file_t.read()

    state=CarSpeedMonitorState(jpg,"WAITING",19,True,99)

    x=1;
    while key != "e":        
        key = input(">> ")
        if key == "u":
            signalR.uploadPreview(state)
            state.detectionEnabled=not state.detectionEnabled
            state.frameRate+=1
            state.avgContours+=1
        if key == "l":
            signalR.logMessage(f'Hello world! {x}')
            x+=1
    
    signalR.stop()

if __name__ == '__main__':
    main()

