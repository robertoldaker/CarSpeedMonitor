PROGRAM_FILE=$1

startme() {
	(python "$PROGRAM_FILE")&
}

stopme() {
    pkill -f "$PROGRAM_FILE"
	PID=$(pgrep -f "$PROGRAM_FILE")	
    while [ ! -z "$PID" ];
    do 
		sleep 1s; 
		PID=$(pgrep -f "$PROGRAM_FILE")	
	done  
}

showme() {
    pgrep -f $PROGRAM_FILE
}

case "$2" in 
    start)   startme ;;
    stop)    stopme ;;
    show)    showme ;;
    restart) stopme; startme ;;
    *) echo "usage: $0 <python script> start|stop|restart|show" >&2
       exit 1
       ;;
esac