import mido
from mido import MidiFile
import time

port = mido.open_output('Steinberg UR22mkII  Port1')

#for i, track in enumerate(mid.tracks):
#	print('Track {}: {}'.format(i, track.name))
#	for msg in track:
#		print(msg)

#mf = MidiFile('/users/johnhollingum/Documents/AMENIC/2chan.mid')
#mf = MidiFile('/users/johnhollingum/Documents/AMENIC/secmid.mid')
mf = MidiFile('/users/johnhollingum/Documents/AMENIC/test.mid')
print("ticks per beat : "+str(mf.ticks_per_beat))

for msg in mf:
	if msg.type == 'set_tempo':
		print(msg)
		print("bpm = "+str(60000000/msg.tempo))
		print("beat duration = "+str(msg.tempo)+ " microseconds")
		print("tick duration = "+ str(msg.tempo/mf.ticks_per_beat)+" microseconds")

for msg in mf:
	print(msg)
	time.sleep(msg.time)
	if not msg.is_meta:
		port.send(msg)



print(mido.get_output_names())
