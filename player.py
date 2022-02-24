import mido
from mido import MidiFile
import time

port = mido.open_output('Steinberg UR22mkII  Port1')

#for i, track in enumerate(mid.tracks):
#	print('Track {}: {}'.format(i, track.name))
#	for msg in track:
#		print(msg)

for msg in MidiFile('/users/johnhollingum/Documents/AMENIC/2chan.mid'):
	print(msg)
	time.sleep(msg.time)
	if not msg.is_meta:
		port.send(msg)



print(mido.get_output_names())
