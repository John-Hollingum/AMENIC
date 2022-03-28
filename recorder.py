import mido
from mido import MidiFile, MidiTrack, Message
import time

def tickDelta():
	global tickDuration
	global lastEventTime

	oldEventTime = lastEventTime
	lastEventTime = time.time()
	return int((time.time() - oldEventTime ) * 1000000 / tickDuration )

print(mido.get_input_names())
tickDuration = 1041 # microseconds based on bpm 120, ticksPerBeat 480,
listenChannel = 3 # say
port = mido.open_input('Steinberg UR22mkII  Port1')
secondaryMidiFile = MidiFile("/Users/johnhollingum/Documents/AMENIC/test.mid")

for m in secondaryMidiFile:
	if str(m.type) == 'set_tempo':
		print(m)
quit()
track = MidiTrack()
secondaryMidiFile.tracks.append(track)
lastMess = Message('program_change', program=12, time=0)
lastEventTime = time.time()


while True:
	msg = port.poll()
	# because of some bug, mido's msg object doesn't support direct comparison with
	# None, even though poll() is documented as either returning a message or a None
	# so stringify it:
	if str(msg) != "None":
		msg.channel = listenChannel # most likely it's coming in on chan 0
		lastMess.time = tickDelta()
		print("appending ",end = ' ')
		print(lastMess)
		track.append(lastMess)
		lastMess = msg
		if msg.note == 22:
			break
	time.sleep(0.01)

secondaryMidiFile.save("/Users/johnhollingum/Documents/AMENIC/capt.mid")
