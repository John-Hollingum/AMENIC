from PIL.ImageQt import ImageQt
from PIL import Image
import numpy as np
import cv2
import jsonpickle # pip install jsonpickle
import json
import time
##import mido
##from mido import MidiFile, MidiTrack, Message, MetaMessage
from decimal import *
from functools import partial
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPixmap, QPainter, QPen, QPalette, QIcon, QColor, QStandardItemModel, QStandardItem, QGuiApplication
import sys
#import vlc #-- Attempted to use VLC for audio playback. It totally garbles the first second or so
from pygame import mixer
#import playsound # playsound blocks. Let's try it with a fork. and it didn't work at all until I installed PyObjC
# let's see if pyobjc helps pygame before trying a forked process
# ok, so it seems that with pyobjc vlc is the best after all!
# kind of. now getting pygame segfaults even though pygame not loaded. de-install pygame, now a) vlc garbling again
# still getting segfaults, but they don't mention pygame any more. Makes me thing that pygame wasn't the source of
# segfaults, it was just its segfault handler was trapping them.
import os, subprocess
import shutil
from mutagen.mp3 import MP3
import re
if sys.argv[1] == 'mp':
	from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip

wavePixmap = None
chanPixmaps = []
chanMuted = []
perfPlayable = False
amenicDir = "/Users/johnhollingum/Documents/AMENIC"
loglevel = 3
orchPath = "./"
orchName = "Untitled"
oExtn = 'orc'
vExtn = 'vcf'
projPath = "./"
projName = "Untitled"
pExtn = 'apr'
cleanProj = True
voices = []
presTable = []
CVMap = []
tWidth = 960
tHeight = 540
mainWindowX = tWidth + 24
mainWindowY = 560
layerWindowX = 1020
fRate = 24
#fRate = 12
ecount=0
emptyImg = None
blackImg = None
blackImgQ = None
board = None
performance = None
audioFile = ''
listenChannel = None
totalTicks = 0
PTList = [ "fixed", "nflat", "vflat","sweep", "nfall", "vfall", "vwobble"]
FUList = [ "xpos", "ypos", "xsize","ysize","opacity"]
yauto = False
bpm = None
iimf = 'c' # internal image manipulation format, q for qpixmap, c for cv

class AmenicMain(QMainWindow):
	def __init__(self):
		super().__init__()
		##icon = QIcon()
		##icon.addPixmap(QPixmap("AmenicIcon.png"), QIcon.Selected, QIcon.On)
		##self.setWindowIcon(icon)
		self.initUI()
		self.vtable = []
		self.loading = False
		self.lastMess = None
		self.lastPerfMess = None

	def initUI(self):
		global emptyImg
		global blackImg
		global blackImgQ
		global cleanPixmap
		global theatre
		global iimf
		global redLEDOn
		global redLEDOff
		global mainWindowX
		global mainWindowY

		self.setWindowTitle('Amenic')

		self.resize(mainWindowX,mainWindowY)

		## ...
		ssLabel = QLabel('Sound Source',self)
		self.ssFileShow= QLineEdit(self)

		## ...

		hbox2 = QHBoxLayout()
		hbox2.addWidget(ssLabel)
		hbox2.addWidget(self.ssFileShow)

		## ...
		container = QWidget()

		## added [

		container.setLayout(hbox2)

		## ]


		## ...

		# Set the central widget of the Window.
		self.setCentralWidget(container)

if __name__ == '__main__':
	app = QApplication(sys.argv)
	main = AmenicMain()
	main.show()
	sys.exit(app.exec_())
