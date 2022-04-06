#import vlc

#st = vlc.MediaPlayer("File:///Users/johnhollingum/Documents/AMENIC/sixteenbars.mp3")
#st.play()
import keyboard
import time
from pygame import mixer


mixer.init()
mixer.music.load("/Users/johnhollingum/Documents/AMENIC/sixteenbars.mp3")
mixer.music.play()
t = time.time()
while mixer.music.get_busy():  # wait for music to finish playing
	if keyboard.read_key() == "s":
		print(str(t - time.time()))
		quit()
	time.sleep(0.01)
