#import vlc

#st = vlc.MediaPlayer("File:///Users/johnhollingum/Documents/AMENIC/sixteenbars.mp3")
#st.play()

import time
from pygame import mixer


mixer.init()
mixer.music.load("/Users/johnhollingum/Documents/AMENIC/sixteenbars.mp3")
mixer.music.play()
while mixer.music.get_busy():  # wait for music to finish playing
    time.sleep(1)
