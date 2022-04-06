import mido
from mido import MidiFile
import time

port = mido.open_output('Steinberg UR22mkII  Port1')

#for i, track in enumerate(mid.tracks):
#	print('Track {}: {}'.format(i, track.name))
#	for msg in track:
#		print(msg)

#mf = MidiFile('/users/johnhollingum/Documents/AMENIC/ticktest.mid')
mf = MidiFile('/users/johnhollingum/Documents/AMENIC/mid16.mid')
print("ticks per beat : "+str(mf.ticks_per_beat))

for msg in mf:
	if msg.type == 'set_tempo':
		print(msg)
		print("bpm = "+str(60000000/msg.tempo))
		bd = msg.tempo / 1000000 # convert to seconds
		print("beat duration = "+str(msg.tempo)+ " microseconds")
		print("tick duration = "+ str(msg.tempo/mf.ticks_per_beat)+" microseconds")

for i, track in enumerate(mf.tracks):
	print('Track {}: {}'.format(i, track.name))
	chans = []
	msgTypes = []
	for msg in track:
		#print(str(type(msg)))
		print(str(msg))
		if msgTypes.count(msg.type) == 0:
			msgTypes.append(msg.type)
		if str(type(msg)) != "<class 'mido.midifiles.meta.MetaMessage'>":
			if chans.count(msg.channel) == 0:
				chans.append(msg.channel)
	print("Track "+str(i)+" contains events for channels ",end='')
	print(chans)
	print("Track "+str(i)+ " contains messages of type ",end='')
	print(msgTypes)
quit()
at = 0
for msg in mf:

	print("t = "+ str(at)+" beats = "+str(at/bd))
	print(msg)
	at += msg.time




print(mido.get_output_names())
