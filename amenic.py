from PIL.ImageQt import ImageQt
from PIL import Image
import numpy as np
import cv2
import jsonpickle # pip install jsonpickle
import json
import time
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
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
import math

if len(sys.argv) == 2:
	if sys.argv[1] != 'e':
		mode = 'export'
	else:
		mode = 'edit'
else:
	mode = 'export'
if mode == 'export':
	from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip

wavePixmap = None
chanPixmaps = []
chanMuted = []
perfPlayable = False
vExtn = 'vcf'
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
fRate = 24 # a 'super default'. This will get set to the setup frate and possibly a project frate
ecount=0
emptyImg = None
blackImg = None
blackImgQ = None
board = None
performance = None
audioFile = ''
listenChannel = None
inPortName = None
totalTicks = 0
PTList = [ "fixed", "nflat", "vflat","sweep", "nfall", "vfall", "vwobble","avwobble", "vaccel"]
FUList = [ "xpos", "ypos", "xsize","ysize","opacity"]
yauto = False
bpm = None
iimf = 'c' # internal image manipulation format, q for qpixmap, c for cv
setup = dict()

def toJsonFile(data,fn):
	saveData = json.dumps(data, indent = 1)
	fh = open(fn,"w")
	fh.write(saveData)
	fh.close()


def fromJsonFile(fname):
	#print("opening "+fname)
	fh = open(fname,'r')
	loadData = fh.read()
	fh.close()
	if loadData == None:
		print("for some reason, there's no loaddata")
		quit()
	#else:
	#	print("===")
	#	print(loadData)
	#	print("===")

	return json.loads(loadData)

def getAmenicDir():
	global amenicDir
	global amSetup

	if not "AMENICDIR" in os.environ:
		# say where it is in my dev system
		amenicDir = "/Users/johnhollingum/Documents/AMENIC"
	else:
		amenicDir = os.environ['AMENICDIR']
	amSetup = amenicDir +'/'+ 'amenicSetup.json'

def setupDefaults():
	global setup

	setup['loglevel'] = 3
	setup['frate'] = 24
	setup['projpath'] = "~/Movies/Amenic"
	setup['preferredmidiinput'] = '<none>'
	setup['voicespath'] = setup['projpath']+"/Voices"
	setup['lastaudiosource'] = setup['projpath']
	setup['lastimagesource'] = setup['projpath']
	setup['lastmidisource'] = setup['projpath']

def loadSetup():
	global setup
	global fRate, inPortName,loglevel, projPath, voicesPath

	getAmenicDir()
	if not os.path.exists(amSetup):
		setupDefaults()
		saveSetup()
	else:
		setup = fromJsonFile(amSetup)

	# use setup to set some 'session defaults'. These may well be overridden by per-project values
	# so in most cases, it's not appropriate to access setup values directly
	fRate = setup['frate']
	# indicating home dir with a ~ is a shell thing, so expand any ref to it in home projpath
	hd = os.environ['HOME']
	pp = setup['projpath']
	expPath = re.sub('~',hd,pp)
	print('Project path is '+expPath)
	if not os.path.isdir(expPath):
		os.mkdir(expPath)
	vp = setup['voicespath']
	expVp = re.sub('~',hd,vp)
	if not os.path.isdir(expVp):
		os.mkdir(expVp)
	projPath = expPath
	voicesPath = expVp
	if setup['preferredmidiinput'] == "<none>":
		inPortName = None
	else:
		inPortName = setup['preferredmidiinput']
		# really should check this is still valid !!!
	loglevel = setup['loglevel']

def saveSetup():
	global setup
	toJsonFile(setup,amSetup)

def checkSetupChange(name,value):
	#print('setting '+name+' to '+str(value))
	setup[name] = value
	# if there is currently no project, save this change to the setup file,
	# otherwise leave it to possibly get saved with the project
	if projName == 'Untitled':
		#print('updating setup file')
		saveSetup()

# bunch of general utility functions
def MakeWaveform(in_file, out_file):
	# print(in_file + " "+out_file )
	command = 'ffmpeg'
	args = '\
 -hide_banner -loglevel panic \
-i "{in_file}" \
-filter_complex \
"[0:a]aformat=channel_layouts=mono, \
compand=gain=5, \
showwavespic=s=600x120:colors=#9cf42f[fg]; \
color=s=600x120:color=#44582c, \
drawgrid=width=iw/10:height=ih/5:color=#9cf42f@0.1[bg]; \
[bg][fg]overlay=format=rgb, \
drawbox=x=(iw-w)/2:y=(ih-h)/2:w=iw:h=1:color=#9cf42f" \
-vframes 1 \
-y "{out_file}" > /dev/null 2>/dev/null'.format(
			in_file = in_file,
			out_file = out_file
		)
	#print(command)
	#print(args)
	subprocess.run(command + args, shell = True )

# Convert an opencv image to QPixmap
def convertCvImage2QtImage(cv_img):
	rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
	PIL_image = Image.fromarray(rgb_image).convert('RGB')
	return QPixmap.fromImage(ImageQt(PIL_image))

def qt2cv(qpm):
	# convert qpixmap to qimage
	img = qpm.toImage()
	buffer = QBuffer()
	buffer.open(QBuffer.ReadWrite)
	# encode qimage as a png
	img.save(buffer, "PNG")
	# read from the buffer as PIL image
	pil_image = Image.open(io.BytesIO(buffer.data()))
	# make it look more like an opencv image:
	open_cv_image = np.array(pil_image)
	# Convert RGB to BGR
	open_cv_image = open_cv_image[:, :, ::-1].copy()
	return open_cv_image

def timeLineGeometry():
	global timeLineWidth
	global timeLineHeight
	global layerWindowX
	global tableWidth
	global chanNumberX
	global voiceNameX
	global listenCheckX
	global muteCheckX
	global clearBtnX
	global timeLineWidth
	global timeLineHeight

	tableWidth = layerWindowX - 42
	chanNumberX = 55
	voiceNameX = 180
	listenCheckX = 50
	muteCheckX = 50
	clearBtnX =70
	timeLineWidth = tableWidth - ( chanNumberX + voiceNameX + clearBtnX + listenCheckX + muteCheckX)
	timeLineHeight = 28

def overlay_transparent(background, overlay, x, y):
	# Taken from https://stackoverflow.com/questions/40895785/using-opencv-to-overlay-transparent-image-onto-another-image
	# note that it overwrites background

	background_width = background.shape[1]
	background_height = background.shape[0]

	# if the overlay image is placed beyond the background image, just
	# return the background image
	if x >= background_width or y >= background_height:
		return background
	# how big is the overlay?
	h, w = overlay.shape[0], overlay.shape[1]
	if h == 0 or w == 0:
		return background

	# will the overlay go beyond the bounds of the background?
	if x + w > background_width:
		w = background_width - x
		overlay = overlay[:, :w]

	# does it go beyond bounds in the other direction?
	if x + w < 0:
		return background # oos
	if x < 0:
		nw = x + w
		ns = w - nw
		x = 0
		w = nw
		# trim down overlay to width nw from the right
		overlay = overlay[:,ns:]

	if y + h > background_height:
		h = background_height - y
		overlay = overlay[:h]

	if y + h < 0:
		return background # oos
	if y < 0:
		nh = y + h
		ns = h - nh
		y = 0
		h = nh
		# trim overlay height to nh from the bottom
		overlay = overlay [ns:]

	# if the overlay image doesn't have a transparency channel
	# construct one for it, but bear in mind that for jpegs, this will
	# effectively make a white rectangular background for the extent of
	# the file's dimensions
	if overlay.shape[2] < 4:
		overlay = np.concatenate(
			[
				overlay,
				np.ones((overlay.shape[0], overlay.shape[1], 1), dtype = overlay.dtype) * 255
			],
			axis = 2,
		)

	# this puts the RGB info into overlay_image and puts the transparency info into mask
	overlay_image = overlay[..., :3] # keep all dimensions except the transparency channel
	mask = overlay[..., 3:] / 255.0  # keep only the transparency channel

	# my added debug
	if False:
		print('background ')
		print(background.shape)
		print('mask ')
		print(mask.shape)
		print('overlay_image')
		print(overlay_image.shape)
	# ends

	# here a miracle occurs:
	background[y:y+h, x:x+w] = (1.0 - mask) * background[y:y+h, x:x+w] + mask * overlay_image

	return background

def overlaySzOpAt(background,overlay,xsize,ysize,opacity,xpos,ypos):
	#print("xsize"+str(xsize)+" ysize "+str(ysize)+" opacity "+str(opacity)+" xpos "+str(xpos)+ " ypos "+str(ypos))
	if str(type(overlay)) == "<class 'NoneType'>":
		#print("nonetype overlay")
		return background
	if ysize == -1: # retain AR
		ar =  overlay.shape[0] / overlay.shape[1]
		ysize = int(xsize * ar)
		#print("Adjusted xsize"+str(xsize)+" ysize "+str(ysize)+" AR "+str(ar)+" opacity "+str(opacity)+" xpos "+str(xpos)+ " ypos "+str(ypos))
	opacity = opacity / 100

	if opacity == 1:
		bg = background
	else:
		bg = background.copy()

	if xsize != 0: # use scaled size
		# print("scaled")
		if xsize == 0 or ysize == 0:
			return background.copy()
		else:
			comb1 = overlay_transparent(bg,cv2.resize(overlay,(xsize,ysize)),xpos,ypos)
	else: # use native size
		#print("native size")
		comb1 = overlay_transparent(bg,overlay,xpos,ypos)

	if opacity < 1:
		alpha = 1 - opacity
		beta = opacity
		combined = cv2.addWeighted(background,alpha,comb1,beta,0.0)
	else:
		combined = comb1
	return combined

def to_name(nn):
	nnt = [ "C  ","C#","D  ","D#","E  ","F  ","F#","G  ","G#","A  ", "A#","B  "]
	on = int(nn / 12) -1 # opinion seems to differ about whether it's necessary to subtract 1
	nis = nn % 12
	nname = nnt[nis]
	return nname + " " + str(on)

def logit(ll,mymess):
	global loglevel
	if loglevel >= ll:
		print(mymess)

def mess(mymess):
	msg = QMessageBox()
	msg.setIcon(QMessageBox.Information)
	msg.setText(mymess)
	msg.setStandardButtons(QMessageBox.Ok)
	retval = msg.exec_()

def warn(mymess):
	msg = QMessageBox()
	msg.setIcon(QMessageBox.Warning)
	msg.setText(mymess)
	msg.setStandardButtons(QMessageBox.Ok)
	retval = msg.exec_()

def err(mymess):
	msg = QMessageBox()
	msg.setIcon(QMessageBox.Critical)
	msg.setText(mymess)
	msg.setStandardButtons(QMessageBox.Ok)
	retval = msg.exec_()

def getVoiceByName(vName):
	# mess(" there are "+str(len(voices))+" voices stored")
	# print("in getvoicebyname, seeking "+vName)
	for v in voices:
		if v.vdata['name'] == vName:
			return v
	return None

def populateVoices(vcb,withAdd):
	vcb.clear()
	vcb.addItem("<none>")
	if withAdd and ( mode == 'edit'):
		vcb.addItem("+Add New")
	vc =0
	for v in voices:
		vc += 1
		vcb.addItem(v.vdata["name"])

def newTiming(t):
	global ticksPerBeat
	global bpm
	global beatDuration
	global tickDuration

	bpm = 60000000/t
	beatDuration = t
	tickDuration = t/ticksPerBeat

def midiTiming(mf):
	global beatDuration
	global tickDuration
	global ticksPerBeat
	global bpm

	# info from header
	ticksPerBeat = mf.ticks_per_beat
	# find the first set_tempo message
	for msg in mf:
		if msg.type == 'set_tempo':
			newTiming(msg.tempo)
			return

def timelineXMap(t):
	global tlXScale
	return int(t * tlXScale)

def timelineYMap(n):
	global tlYscale
	return timeLineHeight - int((n - 21) * tlYscale)

def drawline(snap,msg,aTime):
	global timeLineWidth
	global timeLineHeight
	global chanPixmaps
	global blackImgQ
	# find the note_on in snap corresponding to the note_off/note_on V0 in msg
	# create a line on the appropriate channel timeline from the note_on time
	# to atime. Poss with y value related to note and colour related to velocity
	# there's no particular need to integrate the images into cvmap, rather put
	# them in a specialist table which is incorporated into data model in cvedit
	# in a similar way to the wavePixmap
	#logit(3,"In Drawline")
	if len(chanPixmaps) == 0:
		#logit(3,"initializing pixmaps")
		for i in range(0,16):
			# add a black image and a 'clean' flag
			chanPixmaps.append([ blackImgQ.scaled(timeLineWidth,timeLineHeight,0,1).copy(),True])

	#logit(3,"Pixmaps initialized")
	chan = msg.channel
	for ch in snap.keys():
		if ch == chan:
			for n in snap[ch].keys():
				if n == msg.note:
					#print("In Drawline, note on at "+str(snap[ch][n][0]) + " note off at "+ str(aTime))
					x1 = timelineXMap(snap[ch][n][0])
					y1 = timelineYMap(n)
					x2 = timelineXMap(aTime)
					y2 = y1
					p = QPainter(chanPixmaps[chan][0])
					chanPixmaps[chan][1] = False
					p.setPen(QPen( QColor('#ffffff'), 2, Qt.SolidLine, Qt.FlatCap))
					p.drawLine(x1, y1, x2, y2)
					p.end()

def checkVidGen(mw):
	cg = False
	if mode == "export":
		if len(chanPixmaps) > 0:
			for i in range(0,16):
				if not chanPixmaps[i][1]:
					cg = True
	mw.setCanGenVid(cg)

def makeChannelTimelines(mf):
	global timeLineWidth
	global timeLineHeight
	global audioDuration
	global tlXScale
	global tlYscale
	# this is going to have to poke the generated images into an appropriate
	# timeline image
	#logit(3,"in makeChannelTimelines")
	tlXScale = timeLineWidth / audioDuration
	tlYscale = timeLineHeight / 88 # but subtract 21 before applying

	startBoard = soundBoard('asap')
	#logit(3,"made soundboard for makeChannelTimelines")
	aTime = 0
	frameTime = 0
	#logit(3,"reading through memory 'midifile' for msg")
	for msg in mf:
		aTime += msg.time
		#logit(3,str(aTime))
		gotBoard = False
		snap = startBoard.currentNotes()
		noteEnd = False
		if msg.type == 'note_on':
			if msg.velocity == 0:
				drawline(snap,msg,aTime)
			startBoard.noteOn(msg,aTime)
		elif msg.type == 'note_off':
			drawline(snap,msg,aTime)
			startBoard.noteOff(msg)

class voiceExport(QDialog):
	def __init__(self):
		super().__init__()
		self.setModal(True)
		self.initUI()
		self.selVoice = None

	def checkOK(self):
		if self.voiceCombo.currentText() != '<none>':
			self.expOK.setEnabled(True)
		else:
			self.expOK.setEnabled(False)

	def okExp(self):
		self.selVoice = self.voiceCombo.currentText()
		self.accept()

	def cancelExp(self):
		self.selVoice = "<none>"
		self.reject()

	def initUI(self):

		self.setWindowTitle('voice export')
		self.resize(300,80)
		self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.Tool)

		self.voiceCombo = QComboBox()
		populateVoices(self.voiceCombo,False)
		self.voiceCombo.currentTextChanged.connect(self.checkOK)

		expCancel = QPushButton()
		expCancel.setText('Cancel')
		expCancel.clicked.connect(self.cancelExp)

		self.expOK = QPushButton()
		self.expOK.setText('OK')
		self.expOK.clicked.connect(self.okExp)
		self.expOK.setEnabled(False)

		vb = QVBoxLayout()
		vb.addWidget(self.voiceCombo)
		hb = QHBoxLayout()
		hb.addWidget(expCancel)
		hb.addWidget(self.expOK)
		vb.addLayout(hb)
		self.setLayout(vb)

def addPath(forUse,pathAttr):
	p = ipath(forUse,pathAttr['ptype'])
	p.setFromLoad(pathAttr)
	return p

def internaliseVoice(projVoice,vname):
	v = voice()
	v.vdata['name'] = vname
	v.vdata['imgTable'] = projVoice['imgTable']
	# cache the images and aspect ratio in the imgTable. So imgtable rows are:
	# note number, image filename, qpixmap, aspect ratio
	for nm in v.vdata["imgTable"]:
		if iimf == 'q':
			image = QPixmap(nm[1])
		else:
			image = cv2.imread(nm[1], cv2.IMREAD_UNCHANGED)
		nm.append(image) # nm is a ref not a copy right?
		if iimf == 'q':
			ar = image.height() / image.width() # multiply target width by ar to get target height
		else:
			ar = image.shape[0] / image.shape[1]
		nm.append(ar)
	v.vdata['xpos'] =    addPath("xpos",projVoice['xpos'])
	v.vdata['ypos'] =    addPath("ypos",projVoice['ypos'])
	v.vdata['xsize'] =   addPath("xsize",projVoice['xsize'])
	v.vdata['ysize'] =   addPath("ysize",projVoice['ysize'])
	v.vdata['opacity'] = addPath("opacity",projVoice['opacity'])
	return v

def jsonAbleVoice(v,vname):
	jav= dict()
	jav['imgTable'] = []
	for iti in v.vdata['imgTable']:
		jiti = iti.copy()
		jav['imgTable'].append(jiti)
	for nm in jav["imgTable"]:
		idx = 0
		for x in nm:
			idx += 1
			#print(str(idx)+": "+str(type(x)))
		# strip the cached image file and calculated aspect ratio, but they may not have been added
		# yet if just editing voices and saving
		while len(nm) > 2:
			del nm[2]
	jav['xpos'] = v.vdata['xpos'].data
	jav['ypos'] = v.vdata['ypos'].data
	jav['xsize'] = v.vdata['xsize'].data
	jav['ysize'] = v.vdata['ysize'].data
	jav['opacity'] = v.vdata['opacity'].data

	return jav

class vidExport(QDialog):
	def __init__(self,ofile):
		super().__init__()
		self.setModal(True)
		self.initUI(ofile)
		self.cframe = 0

	def cancelExp(self):
		self.reject()

	def initUI(self,ofile):
		global audioDuration
		global fRate

		self.setWindowTitle('mp4 export')
		self.ofile = ofile
		self.resize(300,80)
		self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.Tool)
		self.expProgress = QProgressBar()
		nframes = int(audioDuration * fRate )
		self.totalSteps = 20 + nframes + 40 # wild guess that start, stop processing takes about as long as processiing 20 frames
		self.expProgress.setRange(0,self.totalSteps)
		cvalue = 20
		self.expProgress.setValue(cvalue)
		expCancel = QPushButton()
		expCancel.setText('Cancel')
		expCancel.clicked.connect(self.cancelExp)
		self.addsound = False # that doesn't mean we don't want to add sound, only that it isn't yet time to do it
		vb = QVBoxLayout()
		vb.addWidget(self.expProgress)
		vb.addWidget(expCancel)
		self.setLayout(vb)
		self.stage = "init"
		QTimer.singleShot(100,self.expSlot)

	def expSlot(self):
		global fRate
		global performance
		global audioDuration
		global chanMuted

		# render and output to file in asap time
		if self.stage == "init":
			#print("here1")
			self.startBoard = soundBoard('asap')
			self.cam = camera(self.ofile,None)
			self.frameDuration = 1 / fRate
			self.aTime = 0
			self.frameTime = 0
			self.frameCount = 20 # not really, but, well, progress
			self.expProgress.setValue(self.frameCount)
			self.stage = 'frames'
			QTimer.singleShot(50,self.expSlot)
			return

		if self.stage == 'frames':
			print("here2")
			for msg in performance:
				# !!! need to add some breaks in here to allow update of pbar
				# need to be careful not to drop data.
				self.aTime += msg.time
				gotBoard = False
				#if msg.type == 'note_on' or msg.type == 'note_off':
				#	print("msg time "+str(msg.time)+" aTime "+str(self.aTime)+" frame time "+str(self.frameTime)+" note "+str(msg.note)+" velocity "+str(msg.velocity))
				while self.aTime >= self.frameTime:
					#print("gen frame "+str(frameCount -20 ))
					if not gotBoard:
						snap = self.startBoard.currentNotes()
					# render snap at different frame times
					self.cam.snapExposure(snap,self.frameTime)
					self.frameTime += self.frameDuration
					self.frameCount += 1
					if self.frameCount % 10 == 0:
						self.expProgress.setValue(self.frameCount)
				#if msg.type == 'note_on' or msg.type == 'note_off':
				#	print(" aTime "+str(self.aTime)+" frame time "+str(self.frameTime)+" velocity "+str(msg.velocity))

				if msg.type == 'note_on':
					if not chanMuted[msg.channel]:
						self.startBoard.noteOn(msg,self.aTime)
				elif msg.type == 'note_off':
					if not chanMuted[msg.channel]:
						self.startBoard.noteOff(msg)
			self.stage = 'deadend'
			QTimer.singleShot(50,self.expSlot)
			return

		# dead space after all performance Info
		if self.stage == 'deadend':
			print("here3")
			while audioDuration > self.frameTime:
				#print("gen frame "+str(frameCount -20 ))
				self.cam.snapExposure(None,self.frameTime)
				# render black frame
				self.frameTime += self.frameDuration
				self.frameCount += 1
				if self.frameCount % 20 == 0:
					self.expProgress.setValue(self.frameCount)
				#print(" aTime "+str(audioDuration)+" frame time "+str(frameTime))
				if self.frameCount % 100 == 0:
					break # let the UI update
			if audioDuration <= self.frameTime:
				self.stage = 'exportsilent'
			QTimer.singleShot(50,self.expSlot)
			return

		if self.stage == 'exportsilent':
			# write to file then
			#print("here 4")
			self.cam.wrap()
			self.expProgress.setValue(self.frameCount+20)
			self.stage = 'addsound'
			QTimer.singleShot(50,self.expSlot)
			return

		if self.stage == 'addsound':
			# load the video
			video_clip = VideoFileClip(self.ofile, audio = False)
			# load the audio
			audio_clip = AudioFileClip(audioFile)
			# use the volume factor to increase/decrease volume
			audio_clip = audio_clip.volumex(1) # basically does nothing, but 0.9 makes quieter, 1.1 makes louder
			final_clip = video_clip.set_audio(audio_clip)
			final_clip.write_videofile("xxx_tmp.mp4", audio_codec='aac')
			shutil.move("xxx_tmp.mp4",self.ofile)
			self.expProgress.setValue(self.totalSteps)
			time.sleep(0.5)
			self.close()

def timeToBeats(s):
	global bpm

	if bpm == None:
		error("Someone's messed up. You shouldn't be calling timeToBeats if the project has no BPM set")
		quit()
	b = bpm / 60 * s
	return b

def beatsToTime(b):
	global bpm

	if bpm == None:
		error("Someone's messed up. You shouldn't be calling beatsToTime if the project has no BPM set")
		quit()
	s = b * 60 / bpm
	return s

# home of the ipath functions
class ipath():
	def __init__(self,forUse,pt):
		self.data = {
			"ptype": None,
			"timestep": None,
			"imin": None,
			"imax": None,
			"omin": None,
			"omax": None,
			"ts2": None,
			"invert": None,
			'usedfor': None,
			'maintar': None, # only significant on xsize
			'scaling': None, # relationship between irange and orange
			'native': None  # only significant on xsize
		}
		if not pt in PTList:
			error("ipath supplied with bad ptype "+pt)
			quit()
		if not forUse in FUList:
			error("ipath supplied with bad forUse type "+forUse)
			quit()
		self.data["ptype"]= pt
		self.data["usedfor"] = forUse
		self.setDefaults()

	def copy(self):
		cip = ipath(self.data['usedfor'],self.data['ptype'])
		for k in self.data:
			cip.data[k] = self.data[k]
		return cip

	def setDefaults(self):

		forUse = self.data['usedfor']
		pt = self.data['ptype']

		self.data['omin'] = 0
		if forUse in [ 'xpos', 'xsize']:
			self.data['omax'] = tWidth
		if forUse in [ 'ypos', 'ysize']:
			self.data['omax'] = tHeight
		if forUse == 'opacity':
			if pt == 'fixed':
				self.data['omin'] = 100
			self.data['omax'] = 100
		self.data['timestep'] = 0.5
		self.data['ts2'] = 2
		self.data['maintar'] = True

		if forUse == 'xsize':
			self.data['maintar'] = True
			self.data['native']  = True

		if pt in ['nflat', 'nfall' ]:
			self.data['imin'] = 21
			self.data['imax'] = 108

		if pt in ['vflat', 'vfall', 'vwobble','avwobble','vaccel']:
			self.data['imin'] = 0
			self.data['imax'] = 127

		if pt == 'vaccel':
			self.data['ival'] = int((self.data['omax'] + self.data['omin'])/2)
			self.data['scaling'] = 5
			self.data['scaling2'] = -2

		self.data['invert'] = False
		self.calcScaling()
		self.calcTop()

	def setFromLoad(self,loadData):
		self.data = loadData.copy()
		self.calcScaling()
		self.calcTop()

	def calcScaling(self):
		orange = int(self.data['omax']) - self.data['omin'] + 1
		if self.data['ptype'] in ['vflat', 'vfall', 'nflat','nfall']:
			irange = self.data['imax'] - self.data['imin'] + 1
			self.data['scaling'] = orange / irange
		if self.data['ptype'] in ['sweep', 'avwobble']:
			self.data['scaling'] = orange / self.data['timestep']
		if self.data['ptype'] in ['vwobble', 'avwobble']:
			self.data['centre'] = ( self.data['omin'] + self.data['omax']) / 2
			self.data['maxamp'] = orange
		if self.data['ptype'] in ['avwobble']:
			self.data['scaling2'] = orange / self.data['ts2']

	def calcTop(self):
		if self.data['invert']:
			if self.data['usedfor'] == 'xpos':
				self.data['top'] = tWidth
			elif self.data['usedfor'] == 'ypos':
				self.data['top'] = tHeight
			elif self.data['usedfor'] == 'opacity':
				self.data['top'] = 100

	def present(self,usedfor,val):
		if self.data['invert']:
			if self.data['usedfor'] in ['xsize','ysize']:
				val = self.data['omax'] - val
				if val < 1 :
					# weird stuff happens if it goes negative
					val = 1
			else:
				val = self.data['top'] - val
		if usedfor == 'opacity':
			return val
		if usedfor == 'xsize':
			# return 0 if 'native', return normally if preserve AR, otherwise return -ive
			if self.data['native']:
				return 0
			elif self.data['maintar']:
				return int(val)
			else:
				# sizing will use independent x and y
				return int(val * -1)
		else:
			return int(val)

	def getVal(self,note,onTime,velocity, aTime = None):

		if self.data['ptype'] == "fixed":
			return self.present(self.data["usedfor"],self.data["omin"])

		if self.data['ptype'] == "nflat":
			# value basically proportional to input note value, scaled
			# to the range omin to omax, but with the option of
			# truncating the input sensitivity, so, for example the whole
			# output range could be output my a range of just four notes
			if note < self.data['imin']:
				return self.data['omin']
			if note > self.data['imax']:
				return self.data['omax']
			val = (note - self.data['imin']) * self.data['scaling'] + self.data['omin']
			return self.present(self.data["usedfor"],val)

		if self.data['ptype'] == "vflat":
			if velocity < self.data['imin']:
				return self.data['omin']
			if velocity > self.data['imax']:
				return self.data['omax']
			val = (velocity - self.data['imin']) * self.data['scaling'] + self.data['omin']
			return self.present(self.data["usedfor"],val)

		if aTime == None:
			#print('atime 1 ontime = '+str(onTime),end=' ')
			e = time.time() - onTime
		else:
			#print('atime 1',end=' ')
			e = aTime - onTime

		if self.data['ptype'] == "sweep":
			val = e * self.data['scaling'] + self.data['omin']
			if val > self.data['omax']:
				val = self.data['omax']
			#print("e ="+str(e)+' Scaling '+str(self.data['scaling'])+" omin "+str(self.data['omin'])+' val '+str(val))
			return self.present(self.data["usedfor"],val)

		# like sweep, but initial value comes from velocity and falls
		if self.data['ptype'] == "vfall":
			val = (velocity - self.data['imin']) + self.data['scaling'] * e
			return self.present(self.data['usedfor'],val)

		# like vfall, but based on note rather than velocity
		if self.data['ptype'] == "nfall":
			val = (note - self.data['imin']) + self.data['scaling'] * e
			return self.present(self.data['usedfor'],val)


		if self.data['ptype'] in ["vwobble","avwobble"]:
			angle = (e % self.data['timestep']) / self.data['timestep'] * math.pi * 2
			if self.data['ptype'] == 'vwobble':
				radius = self.data['maxamp'] * velocity / 256
			else:
				#print(str(self.data['scaling']))
				#print(str(e))
				#print(str(self.data['scaling']*e))
				attn = self.data['scaling2'] * e # at 0 time, this is 0, at time ts2 it would be maxamp
				if attn >= self.data['maxamp']:
					radius = 0
				else:
					radius = ( self.data['maxamp'] - attn) * velocity / 256
			# we want amplitude to be proportional to velocity. If velocity is imax,
			# oscillation should be between omin and omax, if it is imin, it should be
			# static at (omin + omax ) /2
			# how should the frequency relate to the time period?
			# it should go from 0 to 2pi  every timestep. So we don't care how many timesteps, we want to
			# know how far down the current timestep
			# the attenuation is linear. The amplitude goes to 0 in ts2
			#print("Radius: "+ str(radius))
			val = self.data['centre'] + math.sin(angle) * radius
			return self.present(self.data['usedfor'],val)

		if self.data['ptype'] == 'vaccel':
			# s = ut + (at^2)/2
			# u = note velocity * scaling
			# a = scaling2
			# t = e
			s = self.data['ival'] + int(velocity * self.data['scaling'] * e + ( self.data['scaling2'] * e ** 2)/2)
			return self.present(self.data['usedfor'],s)

def cvLayers(layers):
	baseImg = blackImg.copy()
	for l in layers:
		if l == None:
			continue
		if l['xsize'] < 0: # independent x and y
			ys = l['ysize']
			xs = int(l['xsize'] * -1)
		elif l['xsize']== 0:
			ys = 0 # use native size
			xs = 0
		else:
			# retain AR based on x size
			ys = -1
			xs = l['xsize']
		#print("overlaying at opacity "+str(l['opacity']) )
		baseImg = overlaySzOpAt(baseImg,l['img'],xs,ys,l['opacity'],l['xpos'],l['ypos'])
	return baseImg

# class that does the painting of the theatre display on the main window
class theatreLabel(QLabel):
	def __init__(self, parent):
		global tWidth, tHeight

		super().__init__(parent=parent)
		self.setStyleSheet('QFrame {background-color:grey;}')
		self.resize(tWidth, tHeight)
		self.layers =[]

	def setLayers(self,l):
		self.layers = l

	def paintEvent(self, e):
		global iimf
		global emptyImg

		qp = QPainter(self)
		if iimf == 'c':
			baseImg = cvLayers(self.layers)
		else:
			baseImg = emptyImg.copy(QRect())
			qp.drawPixmap(0,0,baseImg)
			for l in self.layers:
				if str(type(l['img'])) == "<class 'NoneType'>":
					continue
				# manipulate qpixmap
				# print("in paintEvent xpos: "+str(l['xpos'])+" ypos: "+str(l['ypos'])+" opacity: "+str(l['opacity']))
				# we need layer to contain values for position, scale and
				# opacity. That'll do for starters
				if l['opacity'] != 100:
					o = l['opacity'] / 100
					qp.setOpacity(o)
					#print("drawing image at ",str(l['xpos'])+","+str(l['ypos'])+" at opacity "+ str(o))
				else:
					#print("drawing image at ",str(l['xpos'])+","+str(l['ypos'])+" at opacity, presumably 1")
					pass

				if l['opacity'] != 0:
					#print(str(type(l['xpos']))+ " "+str(type(l['ypos']))+" "+str(type(l['img'])))
					if l['xsize'] == 0 :
						# use raw/native size
						qp.drawPixmap(l['xpos'],l['ypos'],l['img'])
					else:
						xs = l['xsize']
						if xs > 0:
							# preserve aspect ratio
							# specify excessive y size and ask for preserve aspect ratio based on X
							qp.drawPixmap(l['xpos'],l['ypos'],l['img'].scaled(xs,tHeight,1,0))
						else:
							# independent x and y, so distorting
							xs = xs * -1
							ys = l['ysize']
							qp.drawPixmap(l['xpos'],l['ypos'],l['img'].scaled(xs,ys,0,0))

		if iimf == 'c':
			qi = convertCvImage2QtImage(baseImg)
			#self.setPixmap(qi)
			qp.drawPixmap(0,0,qi)
			#QGuiApplication.processEvents()

# the intermediate object that holds currently active performance info
class soundBoard():
	# registers all currently-playing notes whether from midi file or
	# live performance
	def __init__(self, mode):
		self.board = dict()
		self.evLockQueue = []
		self.locked = False
		self.mode = mode
		if not self.mode in ['realtime','asap']:
			err("soundboard object created with bad mode ["+self.mode+"]")
			quit()

	def addNoteOn(self,msg, absTime = None):
		if absTime == None:
			# we're running in realtime mode
			t = time.time()
		else:
			# we're running in asap mode
			t = absTime
		if msg.channel not in self.board.keys():
			self.board[msg.channel] = {}
		#print("[Board] chan "+str(msg.channel)+" note "+str(msg.note)+ " time " + str(t) + " velocity "+ str(msg.velocity))
		#print("chan "+str(msg.channel)+" note "+str(msg.note)+ " time " + str(msg.time) + " velocity "+ str(msg.velocity))
		if msg.velocity ==0: # It's effectively an old skule note off
			#print("removing note "+str(msg.note)+" in response to note on v0")
			self.board[msg.channel].pop(msg.note)
		else:  # it's a genuine note on
			self.board[msg.channel][msg.note] = [ t,msg.velocity]
		#print("[board chan 0 contents] "+str(self.board[msg.channel]))

	def addNoteOff(self,msg):
		try:
			#print("removing note "+str(msg.note)+" in response to note off")
			self.board[msg.channel].pop(msg.note)
		except KeyError:
			print("KeyError trying to remove board["+str(msg.channel)+"]["+str(msg.note)+"]")
		except:
			print("some other weird shit here")
			quit()


	def noteOn(self,msg, absTime = None):
		if self.locked:
			# it's never going to be locked in asap mode
			self.evLockQueue.append(msg)
		else:
			if absTime == None:
				if self.mode == 'asap':
					err("asap mode soundboard::noteOn called with no absTime")
					quit()
				self.addNoteOn(msg)
			else:
				if self.mode == 'realtime':
					err("realtime mode soundboard::noteOn called specifying absTime")
					quit()
				self.addNoteOn(msg,absTime)

	def noteOff(self,msg):
		addnow = True
		if self.mode == 'realtime':
			if self.locked:
				self.evLockQueue.append(msg)
				addnow = False
		if addnow:
			self.addNoteOff(msg)

	def stopAll(self):
		self.board = []

	def lockBoard(self):
		if self.mode == 'asap':
			err("Can't call soundboard::lockBoard on asap mode soundBoard")
			quit()
		self.locked = True

	def unLockBoard(self):
		# locking is not used in asap mode
		while len(self.evLockQueue) >0:
			msg = self.evLockQueue.pop(0)
			if msg.type == 'note_on':
				self.addNoteOn(msg)
			else:
				self.addNoteOff(msg)

	def currentNotes(self):
		if self.mode == 'realtime':
			if not self.locked:
				err("Call to currentNotes without 'realtime' mode soundBoard locked")
				quit()
		return self.board.copy()

# The function 'play' inside amenicMain starts the various concurrent listeners and players
# here we've got various classes to support that playing, starting  with the thing that
# takes midi events from the midifile and sends them to the board.

class player():
	#pushes midi events out from a 'file' onto the soundboard
	def __init__(self,p,mainWind):
		self.stopIt = False
		self.pauseIt = False
		self.msgList = []
		for m in p:
			self.msgList.append(m)
		self.mw = mainWind

	def playNext(self,sendNow):
		global board
		global bpm
		global chanMuted

		#print("in playnext ",end= ' ')
		#print(str(sendNow))
		self.stopIt = False
		if str(sendNow) != "None":
			# print("[player] "+str(sendNow))
			if sendNow.type == 'note_on':
				# print("[PlayNext a] sending note_on "+str(sendNow.note))
				if not chanMuted[sendNow.channel]:
					board.noteOn(sendNow)
			elif sendNow.type == 'note_off':
				# print("[PlayNext a] sending note_off "+str(sendNow.note))
				if not chanMuted[sendNow.channel]:
					board.noteOff(sendNow)
			nextSendTime = sendNow.time
		else:
			nextSendTime = 0

		if len(self.msgList) > 0:
			msg = self.msgList.pop(0)
			while msg.time == 0:
				if msg.type == 'note_on':
					if not chanMuted[msg.channel]:
						board.noteOn(msg)
				elif msg.type == 'note_off':
					if not chanMuted[msg.channel]:
						board.noteOff(msg)
				elif msg.type == 'set_tempo':
					newTiming(msg.tempo)
					self.mw.bpmShow.setText(str(bpm))
				nextSendTime = msg.time
				if len(self.msgList) ==0:
					msg = None
					break
				else:
					msg = self.msgList.pop(0)
		else:
			msg = None
		# the msg we have now is not 'send now'
		return msg

	def stop(self):
		self.stopIt = True

	def pause(self):
		self.pauseIt = True

	def unPause(self):
		self.pauseIt = False

# the thing that, at frame time constructs the output to theatre from the content of soundboard
class camera():

	def __init__(self, fname, qTheatre ):
		if qTheatre != None:
			self.myTheatre = qTheatre
			self.theatreMode = True
		elif fname == None:
			err("Can't create a camera with no output theatre and no output file")
			quit()
		else:
			self.theatreMode = False
			fourcc = cv2.VideoWriter_fourcc(*'mp4v')
			self.writer = cv2.VideoWriter(fname, fourcc, fRate, (tWidth,tHeight))
		self.cacheShow =''
		self.imgCache = dict()
		self.pathCache = dict()

	def layerFor(self,ch,n,nvn, aTime = None ):

		if len(self.imgCache) == 0:
			for cv in CVMap:
				if cv[1] != "<none>": # if the mapping isn't blank
					# mapIndex =15 - cv[0] # because it's backwards
					mapIndex = cv[0] -1 # because it's not backwards any more but it is shifted down one
					vname = cv[1]
					voice = getVoiceByName(vname)
					if voice == None:
						mess("lookup for voice '"+vname+"' produced no result")
						quit()

					#print("mapindex "+str(mapIndex))
					self.pathCache[mapIndex] = dict()
					self.pathCache[mapIndex]['opacity'] = voice.vdata['opacity']
					self.pathCache[mapIndex]['xpos']    = voice.vdata['xpos']
					self.pathCache[mapIndex]['ypos']    = voice.vdata['ypos']
					self.pathCache[mapIndex]['xsize']   = voice.vdata['xsize']
					self.pathCache[mapIndex]['ysize']   = voice.vdata['ysize']

					self.imgCache[mapIndex] = dict()
					# $$$ This gives an index error if the voices have been edited in this session
					for i in voice.vdata["imgTable"]:
						#print("mapIndex = "+str(mapIndex)+" note = "+ str(i[0]))
						self.imgCache[mapIndex][i[0]] = i[2] # cache[ch][note]= image

		image = None
		#print("imgcache keys",end=' ')
		#print(self.imgCache.keys())
		if not ch in self.imgCache:
			print("Playing channel is "+str(ch))
			print("imgcache keys",end=' ')
			print(self.imgCache.keys())
			print("mutes",end=' ')
			print(str(chanMuted))

		if n in self.imgCache[ch]: # if there's a direct map use it (Includes Rest)
			# print("setting specific note image")
			image = self.imgCache[ch][n]
		elif n > -1: # it's not a rest and there's no direct map
			if -1 in self.imgCache[ch]: # if the default exists
				# print("setting default image")
				image = self.imgCache[ch][-1]
		elif n == -2:
			if not n in self.imgCache[ch]:
				return None

		l = dict()
		l['img'] = image
		#print(str(type(l['xpos']))+ " "+str(type(l['ypos']))+" "+str(type(l['img'])))
		#print("type of image is "+str(type(l['img'])))
		# the rest note (-2) isn't associated with a note, if the path is dependent on
		# time, note velocity pitch, we're not able to calculate the current path value
		# so, for now at least:
		#print("ch is "+str(ch))
		#print("keys in pathCache ",end = " ")
		#print(self.pathCache.keys())
		if n == -2:
			# does the voice *have* a rest image?

			# this jiggery pokery is fairly arbitrary. It's just to give a safe value
			# for the note start time in the event that one of the paths for a 'rest'
			# value is time-based
			if aTime != None:
				ago = 0.3
				if aTime <= ago:
					now = 0
				else:
					now = aTime - ago
			else:
				now = time.time()

			l['xpos'] = self.pathCache[ch]['xpos'].getVal(21,now,64,aTime)
			l['ypos'] = self.pathCache[ch]['ypos'].getVal(21,now,64,aTime)
			l['xsize'] = self.pathCache[ch]['xsize'].getVal(21,now,64,aTime)
			l['ysize'] = self.pathCache[ch]['ysize'].getVal(21,now,64,aTime)
			l['opacity'] = self.pathCache[ch]['opacity'].getVal(21,now,64,aTime)
		else:
			#print("channel : "+str(ch) + " note = "+str(n))
			# print("nv 0 and 1 are "+str(nvn[0])+ " and "+ str(nvn[1]))
			l['xpos'] = self.pathCache[ch]['xpos'].getVal(n,nvn[0],nvn[1],aTime) # note, time velocity
			l['ypos'] = self.pathCache[ch]['ypos'].getVal(n,nvn[0],nvn[1],aTime)
			l['xsize'] = self.pathCache[ch]['xsize'].getVal(n,nvn[0],nvn[1],aTime)
			l['ysize'] = self.pathCache[ch]['ysize'].getVal(n,nvn[0],nvn[1],aTime)
			l['opacity'] = self.pathCache[ch]['opacity'].getVal(n,nvn[0],nvn[1],aTime)

		return l

	def render(self,ch,nv,aTime = None):
		global CVMap
		global emptyImg

		if len(nv) == 0:
			#print("rest", end = " ")
			l  = self.layerFor(ch,-2,nv,aTime)

		for n in nv.keys():
			t = nv[n][0]
			v = nv[n][1]
			# so we have channel in ch, note in n and velocity in v
			# and start time in t.
			l = self.layerFor(ch,n,nv[n],aTime)

			# print("in render note: "+str(n)+" xpos: "+str(l['xpos'])+" ypos: "+str(l['ypos'])+" opacity: "+str(l['opacity']))

		return l

	def merge(self,layers):
		# bang the list of qpixmaps and path values in layers into one merged image
		if self.theatreMode:
			self.myTheatre.setLayers(layers)
			self.myTheatre.show()
		else:
			img = cvLayers(layers)
			self.writer.write(img)

	def wrap(self):
		self.writer.release()

	def snapExposure(self,snap,aTime):
		# for non-realtime use when exporting to mp4
		if snap == None:
			self.writer.write(blackImg)
			return
		layers = []
		for ch in range(0,15): # enforce correct order of layers
			if ch in snap.keys():
				#print("Trying to render for channel "+str(ch))
				#print(snap[ch])
				layers.append(self.render(ch,snap[ch],aTime))
		self.merge(layers)

	def exposure(self):
		global board
		global ecount
		# construct image from myBoard, then show in myTheatre
		board.lockBoard()
		snap = board.currentNotes()
		board.unLockBoard()
		layers = []
		ecount += 1
		#print("E "+str(ecount))
		for ch in range(0,15):
			if ch in snap.keys():
				#print("Trying to render for channel "+str(ch)) # !!!
				#print(snap[ch])
				layers.append(self.render(ch,snap[ch]))
		self.merge(layers)

# the data model for the layers table which associates voices with midi channels or live performance data
class cvmModel(QAbstractTableModel):
	header_labels = ['Layer', 'Voice', "Listen", "Mute", "Clear", "Timeline" ]

	def __init__(self, data):
		super().__init__()
		self._data = data

	def flags(self, index):
		if index.column() == 1:
			# col 0 is editable
			return Qt.ItemIsSelectable|Qt.ItemIsEnabled|Qt.ItemIsEditable
		else:
			# the other columns are not editable
			return Qt.ItemIsSelectable|Qt.ItemIsEnabled

	def setData(self, index, value, role):
		if role == Qt.EditRole:
			self._data[index.row()][index.column()] = value
			return True
		return False

	def headerData(self, section, orientation, role=Qt.DisplayRole):
		if role == Qt.DisplayRole and orientation == Qt.Horizontal:
			return self.header_labels[section]
		return QAbstractTableModel.headerData(self, section, orientation, role)

	def data(self, index, role):
		if index.isValid():

			if role == Qt.DisplayRole or role == Qt.EditRole:
				val = self._data[index.row()][index.column()]
				return str(val)

	def rowCount(self, index):
		# The length of the outer list.
		return len(self._data)

	def columnCount(self, index):
		# The following takes the first sub-list, and returns
		# the length (only works if all rows are an equal length)
		return len(self._data[0])

# the data model for the voice note images table
class TableModel(QAbstractTableModel):

	header_labels = ['N No.', 'N Name', ' ', 'Image File']

	def __init__(self, data):
		super().__init__()
		self._data = data

	def flags(self, index):
		if index.column() == 0 or index.column == 2:
			# col 0 is editable
			return Qt.ItemIsSelectable|Qt.ItemIsEnabled|Qt.ItemIsEditable
		else:
			# the other columns are not editable
			return Qt.ItemIsSelectable|Qt.ItemIsEnabled

	def setData(self, index, value, role):
		if role == Qt.EditRole:
			self._data[index.row()][index.column()] = value
			return True
		return False

	def headerData(self, section, orientation, role=Qt.DisplayRole):
		if role == Qt.DisplayRole and orientation == Qt.Horizontal:
			return self.header_labels[section]
		return QAbstractTableModel.headerData(self, section, orientation, role)

	def data(self, index, role):
		if index.isValid():
			if role == Qt.BackgroundRole:
				if index.column() == 1 or index.column() == 3:
					return QColor('#eeeeee')
				if index.column() == 0 and index.row() == 60 - 21:
					return QColor('#f01010')

			if role == Qt.DecorationRole:
				if index.column() == 1:
					value = self._data[index.row()][index.column()]
					if value[1] == '#':
						c = '#000000'
					else:
						c = '#ffffff'
					return QColor(c)

			if role == Qt.DisplayRole or role == Qt.EditRole:
				val = self._data[index.row()][index.column()]
				if index.column() == 0:
					self._data[index.row()][1] = to_name(int(Decimal(val)))
				return str(val)

	def rowCount(self, index):
		# The length of the outer list.
		return len(self._data)

	def columnCount(self, index):
		# The following takes the first sub-list, and returns
		# the length (only works if all rows are an equal length)
		return len(self._data[0])

# a voice object with note image table and path definitions for specific attributes
class voice():

	def sd(self):
		#mess('voice object set dirty')
		self.isClean = False

	def __init__(self):
		self.vdata = {
			"imgTable": [ ],
			"name": 'Untitled',
			"xpos": None ,
			"ypos": None,
			"xsize": None,
			"ysize": None,
			"opacity": None
		}
		self.vdata["xpos"] = ipath("xpos","fixed")
		self.vdata["ypos"] = ipath("ypos","fixed")
		self.vdata["xsize"] = ipath("xsize","fixed")
		self.vdata["ysize"] = ipath("ysize","fixed")
		self.vdata["opacity"] = ipath("opacity","fixed")
		self.isClean = True

	def edit(self):
		ve = vEditD(self)
		ve.changedVoice.connect(self.sd)
		ve.exec_()
		return

	def copy(self):
		cv = voice()
		for k1 in self.vdata:
			#print(str(k1))
			if k1 == "name":
				cv.vdata[k1] = self.vdata[k1]
			else:
				cv.vdata[k1] = self.vdata[k1].copy()
		return cv

# special combo class that is used for selecting path type for a particular voice Attribute
class PCombo(QComboBox):
	def __init__(self,path):
		global PTList
		super().__init__()
		for t in PTList:
			self.addItem(t)
		i = self.findText(path.data['ptype'])
		self.setCurrentIndex(i)
		self.myPath = path
		self.currentTextChanged.connect(self.edPath)

	def edPath(self):
		global yauto

		# if this has changed, what's dirty? The path or the voice?
		# if this can't be cancelled, then it's the voice that is dirty.
		# cancel doesn't set it back to it's original ptype, so this is making
		# the voice edit dirty, so get the voice edit to tie the currentTextChanged
		# to its own dirty slot
		if not yauto:
			self.myPath.data['timestep'] = 0
			self.myPath.data['omin'] = 0
		self.myPath.data['ptype'] = self.currentText()
		self.myPath.setDefaults()
		if not yauto:
			if self.myPath.data['ptype'] == 'vaccel':
				pe = accelPathEdit(self.myPath)
			else:
				pe = pathEdit(self.myPath)
			pe.exec_()

# special combo specifically for selecting the pathtype of xsize. It's special because it may also
# manipulate the path info for ysize
class xsizeCombo(QComboBox):
	def __init__(self,xpath,ypath,ycombo):
		global PTList
		super().__init__()
		self.xpath = xpath
		self.ypath = ypath
		self.ycombo = ycombo
		for t in PTList:
			self.addItem(t)
		i = self.findText(self.xpath.data['ptype'])
		self.setCurrentIndex(i)
		self.currentTextChanged.connect(self.edPath)

	def edPath(self):
		global maintainAR
		global yauto

		self.xpath.data['timestep'] = 0
		self.xpath.data['omin'] = 0
		self.xpath.data['ptype'] = self.currentText()
		pe = pathEdit(self.xpath)
		pe.exec_()
		# mess("in xsizecombo edpath, link = "+str(maintainAR))
		if maintainAR:
			# if we want the xsize to be the driver in maintainAR mode, we need Y to be banged up to a marginally excessive scaled size and
			# set AspectRatioMode to KeepAspectRatio. If we are allowing independent x and y control, we just need to
			# set AspectRatioMode to IgnoreAspectRatio
			# I think that if we are not to create excessive 'padding' at the bottom of the image, we need to
			# a) have an accurate idea of the original aspect ratio of the image being presented
			# b) ensure that a reasonable Y value is maintained for every x change.
			# this isn't so that the eventual AR is maintained, it's to ensure that the scaled image doesn't have extra dead space
			# at the bottom
			# at the point of setting the scaling, we don't know the original size of the image we are scaling, so we can't know its AR
			# maybe when we load images we should calculate and store their aspect ratio. Then at scale time, a Y value could be calculated
			# to correspond to the required X value
			# $$$ actually all this depends on the iimf
			self.xpath.data['maintar'] = True
			# none of this duplication is important except the change in ptype for appearance sake
			self.ypath.data = self.xpath.data.copy()
			self.ypath.data['usedfor'] = 'ysize'
			yauto = True
			i = self.ycombo.findText(self.ypath.data['ptype'])
			self.ycombo.setCurrentIndex(i)
			yauto = False
		else:
			self.xpath.data['maintar'] = False

# special button for editing the details of a path without changing the path type
class PEButton(QPushButton):
	changedPath = pyqtSignal()

	def __init__(self,path):
		super().__init__()
		self.setText("Edit")
		self.clicked.connect(self.eptype)
		self.myPath = path

	def eptype(self,idx):
		if self.myPath.data['ptype'] == 'vaccel':
			self.pe = accelPathEdit(self.myPath)
		else:
			self.pe = pathEdit(self.myPath)
		self.pe.exec_()
		if not self.pe.isClean:
			#mess("emitting signal")
			self.changedPath.emit()
		#else:
		#	mess("no need to emit signal")

# slider control for path controls
class vSlide(QSlider):
	def __init__(self,min,max,linkedLabel,current,isInt,parent):
		super().__init__(Qt.Horizontal,parent)
		self.parent = parent
		self.isInt = isInt
		if self.isInt:
			self.setMinimum(min)
			self.setMaximum(max)
			self.setValue(int(current))
		else:
			self.setMinimum(min * 100)
			self.setMaximum(max * 100)
			self.setValue(int(current * 100))
		self.setGeometry(30, 40, 200, 30)
		self.myLinkedLabel = linkedLabel
		self.valueChanged[int].connect(self.updLabel)

	def updLabel(self):
		if self.isInt:
			self.myLinkedLabel.setText(str(self.value()))
		else:
			self.myLinkedLabel.setText(str(self.value()/100))
		self.parent.sd()

	def getVal(self):
		if self.isInt:
			return self.value()
		else:
			return self.value() / 100

class accelPathEdit(QDialog):
	# it's just too different to be handled by the generic path editor
	def __init__(self,path):
		super().__init__()
		self.setModal(True)
		self.myPath = path
		self.isClean = True
		self.initUI()

	def setClean(self,clean):
		self.isClean = clean
		self.btnSave.setEnabled(not self.isClean)

	def sd(self):
		self.setClean(False)

	def cancelOut(self):
		self.setClean(True)
		self.reject()

	def saveOut(self):
		self.myPath.data['ival'] = self.initValSlide.getVal()
		self.myPath.data['scaling'] = self.initVelSlide.getVal()
		self.myPath.data['scaling2'] = self.accelSlide.getVal()
		self.accept()

	def initUI(self):
		global bpm

		self.setWindowTitle('Edit Attribute Path')
		self.resize(400,400)
		self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.Tool)

		# how we caption these and whether we show them at all will depend on ptype
		forUse = self.myPath.data['usedfor']

		ptype = self.myPath.data['ptype']
		self.forLabel = QLabel()
		self.forLabel.setTextFormat(1)
		self.forLabel.setText("<big>Parameters for <b>"+forUse+"</b> Path type <b>"+ptype+"</b></big>")

		self.initValLabel = QLabel(str(self.myPath.data['ival']))
		self.initValSlide = vSlide(self.myPath.data['omin'],self.myPath.data['omax'],self.initValLabel,self.myPath.data['ival'],True,self)

		orange = self.myPath.data['omax'] - self.myPath.data['omin']
		ascale = 40 / orange
		print("ORange: "+str(orange)+" arbitrary scaling :"+ str(ascale))
		vminmax = int(ascale * orange)
		self.initVelLabel = QLabel(str(self.myPath.data['scaling']))
		self.initVelSlide = vSlide(-1 * vminmax,vminmax,self.initVelLabel,self.myPath.data['scaling'],False,self)

		as2 = 500 / orange
		print("ORange: "+str(orange)+" arbitrary scaling 2:"+ str(as2))
		aminmax = int(as2 * orange)
		self.accelLabel = QLabel(str(self.myPath.data['scaling2']))
		self.accelSlide = vSlide(-1 * aminmax,aminmax,self.accelLabel,self.myPath.data['scaling2'],False, self)

		self.btnSave = QPushButton()
		self.btnSave.setText("Save")
		self.btnSave.clicked.connect(self.saveOut)
		self.btnSave.setEnabled(False)

		self.btnCancel = QPushButton()
		self.btnCancel.setText("Cancel")
		self.btnCancel.clicked.connect(self.cancelOut)

		outerVBox = QVBoxLayout()

		outerVBox.addWidget(self.forLabel)

		ivGBox = QGroupBox("Initial Value")
		ivVBox = QVBoxLayout()
		ivVBox.addWidget(self.initValLabel)
		ivVBox.addWidget(self.initValSlide)
		ivGBox.setLayout(ivVBox)
		outerVBox.addWidget(ivGBox)

		iVelGBox = QGroupBox("Initial Velocity Scaling")
		iVelVBox = QVBoxLayout()
		iVelVBox.addWidget(self.initVelLabel)
		iVelVBox.addWidget(self.initVelSlide)
		iVelGBox.setLayout(iVelVBox)
		outerVBox.addWidget(iVelGBox)

		accelGBox = QGroupBox("Acceleration")
		accelVBox = QVBoxLayout()
		accelVBox.addWidget(self.accelLabel)
		accelVBox.addWidget(self.accelSlide)
		accelGBox.setLayout(accelVBox)
		outerVBox.addWidget(accelGBox)

		bhbox = QHBoxLayout()
		bhbox.addWidget(self.btnCancel)
		bhbox.addWidget(self.btnSave)

		outerVBox.addLayout(bhbox)

		self.setLayout(outerVBox)

# path editor, invoked by changes to pcombo, xsizeCombo or clicks on PEButton
class pathEdit(QDialog):
	def __init__(self,path):
		super().__init__()
		self.setModal(True)
		self.myPath = path
		self.isclean = True
		self.initUI()

	def setClean(self,clean):
		self.isClean = clean
		self.btnSave.setEnabled(not self.isClean)

	def sd(self):
		self.setClean(False)

	def saveOut(self):

		ptype = self.myPath.data['ptype']
		if self.scaledFromTime:
			self.myPath.data['timestep'] = self.getTime(self.tUnits1,self.tUnitsCombo)

		else:
			self.myPath.data['timestep'] = 0

		if self.useSecondaryTime:
			self.myPath.data['ts2'] = self.getTime(self.tUnits2,self.tUnits2Combo)
		else:
			self.myPath.data['ts2'] = 0

		if ptype == 'fixed':
			self.myPath.data['omin'] = int(self.fixVEdit.text())
		else:
			self.myPath.data['omin'] = int(self.oLower.text())
			self.myPath.data['omax'] = int(self.oUpper.text())

		if self.scaledFromInput:
			self.myPath.data['imin'] = int(self.iLower.text())
			self.myPath.data['imax'] = int(self.iUpper.text())

		if self.scaledFromInput or self.scaledFromTime:
			self.myPath.data['invert'] = self.inverseCheck.isChecked()

		self.myPath.calcScaling()
		self.myPath.calcTop()

		print(self.myPath.data)
		self.accept()

	def invertCheck(self):
		self.setClean(False)
		inverse = self.inverseCheck.isChecked()
		self.nqualify.setText(self.ocaptionneg[inverse])

	def cancelOut(self):
		self.setClean(True)
		self.reject()

	# time always stored in seconds at save time, but can be displayed at edit time
	# in seconds or beats
	def getTime(self,unitsText,unitsCombo):
		if unitsCombo.currentText == 'seconds':
			return float(unitsText.text())
		else:
			return beatsToTime(float(unitsText.text()))

	def ctu(self,unitsText,unitsCombo):
		if unitsCombo.currentText() == 'seconds':
			# this is 'on change' so it must previously have been beats
			s = beatsToTime(float(unitsText.text()))
			unitsText.setText(str(s))
		else:
			b = timeToBeats(float(unitsText.text()))
			unitsText.setText(str(b))

	def changeTimeUnits(self):
		self.setClean(False)
		self.ctu(self.tUnits1,self.tUnitsCombo)

	def changeTime2Units(self):
		self.setClean(False)
		self.ctu(self.tUnits2,self.tUnits2Combo)

	def initUI(self):
		global bpm

		self.setWindowTitle('Edit Attribute Path')
		self.resize(400,400)
		self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.Tool)

		maintar = self.myPath.data['maintar']

		# how we caption these and whether we show them at all will depend on ptype
		forUse = self.myPath.data['usedfor']

		ptype = self.myPath.data['ptype']
		self.forLabel = QLabel()
		self.forLabel.setTextFormat(1)
		self.forLabel.setText("<big>Parameters for <b>"+forUse+"</b> Path type <b>"+ptype+"</b></big>")

		self.scaledFromInput = ptype in [ "nflat","vflat","nfall","vfall","vwobble",'avwobble']

		self.scaledFromTime = ptype in [ "sweep", "nfall", "vfall", "vwobble", 'avwobble']
		self.useSecondaryTime = ptype in [ "avwobble" ]

		timeLower = 1 / fRate # not much point (I *think*) in allowing a time period less than the frame rate
		timeUpper = 20        # I can't see (for the moment) wanting any effect to take longer than 20 seconds. Mostly
						      # I'm expecting time steps to be < 1s
		# these following are the default values of the ranges that the user will define. Don't confuse them with ranges of
		# valid input for individual numbers
		ilower = self.myPath.data['imin']
		iupper = self.myPath.data['imax']

		olower = self.myPath.data['omin']
		oupper = self.myPath.data['omax']

		ts = self.myPath.data['timestep']
		ts2 = self.myPath.data['ts2']

		inverse = self.myPath.data['invert']

		if self.scaledFromInput:
			if ptype in [ "nflat", "nfall"]:
				iscalecaption = "As Note varies from "
			if ptype in ["vflat","vfall","vwobble","avwobble"]:
				iscalecaption = "As velocity varies from "

		if self.scaledFromInput or self.scaledFromTime:
			if forUse == "xpos":
				oscalecaption = "Vary output X value from "
				ocaption2 = " to "
				# indexed by Inverse
				self.ocaptionneg = { False: "pixels from left", True: "pixels from right"}
			if forUse == "ypos":
				oscalecaption = "Vary output Y value from "
				ocaption2 = " to "
				self.ocaptionneg = { False: "pixels from bottom", True: "pixels from top"}

			if forUse == "xsize":
				oscalecaption = "Vary X size from "
				ocaption2 = " to "
				if maintar:
					self.ocaptionneg = { False: " small to big, Y maintains aspect ratio", True: " big to small, Y mainains aspect ration"}
				else:
					self.ocaptionneg = { False: " small to big, independent of Y", True: " big to small, independent of Y"}

			if forUse == "ysize":
				# if you get here, you're not maintaining AR
				oscalecaption = "Vary Y size from "
				ocaption2 = " to "
				self.ocaptionneg = { False: " small to big, independent of X", True: " big to small, independent of X" }

			if forUse == "opacity":
				oscalecaption = "Vary output opacity value from "
				ocaption2 = "% to "
				self.ocaptionneg = { False: "% in direct proportion", True: "% in inverse proportion"}

		if self.scaledFromInput:
			inputGBox = QGroupBox("Input Range Control")
			self.iLowerLabel = QLabel(iscalecaption)
			self.iLower = QLineEdit()
			self.iLower.setText(str(ilower))
			self.iLower.textChanged.connect(self.sd)
			self.iUpperLabel = QLabel(" to ")
			self.iUpper = QLineEdit()
			self.iUpper.setText(str(iupper))
			self.iUpper.textChanged.connect(self.sd)
			inputHBox = QHBoxLayout()
			inputHBox.addWidget(self.iLowerLabel)
			inputHBox.addWidget(self.iLower)
			inputHBox.addWidget(self.iUpperLabel)
			inputHBox.addWidget(self.iUpper)
			inputGBox.setLayout(inputHBox)

		if self.scaledFromInput or self.scaledFromTime:
			self.outputGBox = QGroupBox("Output Range Control")
			outputVBox = QVBoxLayout()
			invHBox = QHBoxLayout()
			self.inverseLabel = QLabel('Inverse ')
			self.inverseCheck = QCheckBox()
			self.inverseCheck.setChecked(inverse)
			self.inverseCheck.stateChanged.connect(self.invertCheck)
			self.oLowerLabel = QLabel(oscalecaption)
			self.oLower = QLineEdit()
			self.oLower.setText(str(olower))
			self.oLower.textChanged.connect(self.sd)
			self.oUpperLabel = QLabel(ocaption2)
			self.oUpper = QLineEdit()
			self.oUpper.setText(str(oupper))
			self.oUpper.textChanged.connect(self.sd)
			self.nqualify = QLabel(self.ocaptionneg[inverse])
			outputHBox = QHBoxLayout()
			invHBox.addWidget(self.inverseLabel)
			invHBox.addWidget(self.inverseCheck)
			outputVBox.addLayout(invHBox)
			outputHBox.addWidget(self.oLowerLabel)
			outputHBox.addWidget(self.oLower)
			outputHBox.addWidget(self.oUpperLabel)
			outputHBox.addWidget(self.oUpper)
			outputVBox.addLayout(outputHBox)
			outputVBox.addWidget(self.nqualify)
			self.outputGBox.setLayout(outputVBox)

		if self.scaledFromTime:
			self.timeGBox = QGroupBox("Time Control")
			self.tUnitsLabel1 = QLabel("taking ")
			self.tUnits1 = QLineEdit()
			self.tUnits1.setText(str(ts))
			self.tUnits1.textChanged.connect(self.sd)
			self.tUnitsCombo = QComboBox()
			self.tUnitsCombo.addItem("seconds")
			if bpm != None:
				self.tUnitsCombo.addItem("beats")
			self.tUnitsCombo.currentTextChanged.connect(self.changeTimeUnits)
			if ptype in ["nfall","vfall"]:
				self.tUnitsLabel2 = QLabel("to go from initial output to 0")
			else:
				self.tUnitsLabel2 = QLabel("to go from min output to max output")
			timeVBox = QVBoxLayout()
			timeHBox = QHBoxLayout()
			timeHBox.addWidget(self.tUnitsLabel1)
			timeHBox.addWidget(self.tUnits1)
			timeHBox.addWidget(self.tUnitsCombo)
			timeVBox.addLayout(timeHBox)
			timeVBox.addWidget(self.tUnitsLabel2)
			if self.useSecondaryTime:
				if ptype == 'avwobble':
					self.t2Label = QLabel("Attenuate to 0 amplitude after")
				else:
					self.t2Label = QLabel("some generic time 2 thing")
				self.tUnits2 = QLineEdit()
				self.tUnits2.setText(str(ts2))
				self.tUnits2.textChanged.connect(self.sd)
				self.tUnits2Combo = QComboBox()
				self.tUnits2Combo.addItem("seconds")
				if bpm != None:
					self.tUnits2Combo.addItem("beats")
				self.tUnits2Combo.currentTextChanged.connect(self.changeTime2Units)
				time2HBox = QHBoxLayout()
				time2HBox.addWidget(self.t2Label)
				time2HBox.addWidget(self.tUnits2)
				time2HBox.addWidget(self.tUnits2Combo)
				timeVBox.addLayout(time2HBox)

			self.timeGBox.setLayout(timeVBox)

		if ptype == "fixed":
			self.omin = self.myPath.data["omin"]
			self.fixLabel = QLabel("Fixed value for "+forUse)
			self.fixVEdit = QLineEdit()
			self.fixVEdit.setText(str(self.omin))
			self.fixVEdit.textChanged.connect(self.sd)
			#self.fixSlide = vSlide(self.myPath.data['omin'],self.myPath.data['omax'],self.fixVLabel,self.omin,self)

		self.btnSave = QPushButton()
		self.btnSave.setText("Save")
		self.btnSave.clicked.connect(self.saveOut)
		self.btnSave.setEnabled(False)

		self.btnCancel = QPushButton()
		self.btnCancel.setText("Cancel")
		self.btnCancel.clicked.connect(self.cancelOut)

		vbox = QVBoxLayout()

		vbox.addWidget(self.forLabel)
		if self.scaledFromInput:
			vbox.addWidget(inputGBox)

		if self.scaledFromInput or self.scaledFromTime:
			vbox.addWidget(self.outputGBox)

		if self.scaledFromTime:
			vbox.addWidget(self.timeGBox)

		if ptype == "fixed":
			fixHBox = QHBoxLayout()
			fixHBox.addWidget(self.fixLabel)
			fixHBox.addWidget(self.fixVEdit)
			vbox.addLayout(fixHBox)

		bhbox = QHBoxLayout()
		bhbox.addWidget(self.btnCancel)
		bhbox.addWidget(self.btnSave)

		vbox.addLayout(bhbox)

		self.setLayout(vbox)

# edits the layers list controlling association of voices with incoming live performance data or
# midi file playback channels
class CVMapEdit(QDialog):
	# this may change the project by editing voices or clearing _data
	# both of those are instant and non-cancellable
	# changing channel voice assignments and listen/mute status are cancellable and get
	# signalled at saveOut time
	changedProj = pyqtSignal()

	def setClean(self,clean):
		self.isClean = clean
		if not self.isClean:
			self.btnSave.setEnabled(True)
			self.changedProj.emit()

	def sd(self):
		self.setClean(False)

	def saveEnable(self):
		# use this for cancellable changes. It enables save, and saveout may signal dirty
		self.btnSave.setEnabled(True)

	def __init__(self,mainWind):
		super().__init__()
		self.setModal(True)
		self.initUI()
		self.newCVMap = []
		self.mw = mainWind
		self.isClean = True

	def cbValues(self,idx,vname):
		global chanMuted
		#mess("in cbvalues vname = "+vname)
		gotVoice = ( vname != '<none>')
		clean = chanPixmaps[idx -1][1]
		listenWidget = self.cvm.indexWidget(self.model.index(idx,2))
		listenWidget.setEnabled(clean and gotVoice and inPortName != "<none>")
		if not (clean and gotVoice):
			listenWidget.setChecked(False)
		muteWidget = self.cvm.indexWidget(self.model.index(idx,3))
		muteWidget.setChecked(not gotVoice)
		chanMuted[idx - 1 ] = not gotVoice
		muteWidget.setEnabled(gotVoice and (not clean))

	def checkNew(self,idx):
		global voices
		global CVMap

		self.saveEnable()
		w = self.cvm.indexWidget(self.model.index(idx,1))
		if w.currentText() == "+Add New":
			v = voice()
			v.edit()
			if not v.isClean:
				self.sd()
			if v != None:
				if v.vdata["name"] == "Untitled":
					v= None
			if v != None:
				voices.append(v)
				w.addItem(v.vdata["name"]) # no doubt causes a kinda recursive call here
				i = w.findText(v.vdata["name"])
				w.setCurrentIndex(i)
				# check if the listen checkbox should now be active
				self.cbValues(idx,v.vdata["name"])
			else:
				i = w.findText("<none>")
				w.setCurrentIndex(i)
		# check if the listen checkbox should now be active
		self.cbValues(idx,w.currentText())

	def toggleChecked(self,idx):
		global listenChannel
		global redLEDOff
		global redLEDOn

		self.saveEnable()
		w = self.cvm.indexWidget(self.model.index(idx, 2))
		if w.checkState():
			# ensure it has a mapping
			cbw = self.cvm.indexWidget(self.model.index(idx,1))
			vname = cbw.currentText()
			if vname == "<none>":
				#mess("Can't listen on channel with no voice assigned")
				w.setChecked(False)
				self.mw.recLED.setPixmap(redLEDOff)
			else:
				# ensure no others are checked
				self.mw.recLED.setPixmap(redLEDOn)
				#mess("Unchecking all others")
				for i in range(1,16):
					if i != idx:
						w = self.cvm.indexWidget(self.model.index(i, 2))
						w.setChecked(False)
					else:
						listenChannel = self.model._data[i][0]
						#mess("Listening on channel "+str(listenChannel))
		else:
			#mess("state changed, now unchecked")
			self.mw.recLED.setPixmap(redLEDOff)
			listenChannel = None

	def toggleMute(self,idx):
		global chanMuted

		self.saveEnable()
		w = self.cvm.indexWidget(self.model.index(idx, 3))
		chanMuted[idx - 1] = w.checkState()

	def clearChan(self,idx):
		global performance

		trackName = "forChan"+str(idx -1)
		for i in range(len(performance.tracks)-1, 0, -1):
			if performance.tracks[i].name == trackName:
				print("deleting track with index "+str(i))
				del performance.tracks[i]
				# we seem to have a problem with multiple forchan0 tracks being created.
				# I don't think this is the right place to fix it, but let's not break
				# here, but let it splat several
				# break
		self.sd()
		tl = self.cvm.indexWidget(self.model.index(idx,5))
		tl.setPixmap(cleanPixmap.scaled(timeLineWidth,timeLineHeight,0,1))
		chanPixmaps[idx-1][0] = blackImgQ.scaled(timeLineWidth,timeLineHeight,0,1).copy()
		chanPixmaps[idx -1][1] = True
		cb = self.cvm.indexWidget(self.model.index(idx,3))
		cb.setEnabled(False)
		lc = self.cvm.indexWidget(self.model.index(idx,2))
		lc.setEnabled(True)
		checkVidGen(self.mw)

	def comboAdd(self,idx):
		global wavePixmap
		global cleanPixmap
		global timeLineWidth
		global timeLineHeight
		global audioFile
		global inPortName

		if idx == 0:
			if audioFile != '':
				self.model._data[idx][1] = audioFile
		else:
			selVoiceCombo = QComboBox()
			populateVoices(selVoiceCombo,True)

			# because of the presence of the sound row, the rows in the internal cvmap are
			# 1 out of sync with the index of the model.
			if CVMap[idx -1][1] == "<none>" or CVMap[idx -1][1] == None:
				gotVoice = False
				i = selVoiceCombo.findText("<none>")
			else:
				gotVoice = True
				i = selVoiceCombo.findText(CVMap[idx -1][1])

			selVoiceCombo.setCurrentIndex(i)
			selVoiceCombo.currentTextChanged.connect(partial(self.checkNew,idx))
			self.cvm.setIndexWidget(self.model.index(idx, 1), selVoiceCombo)

		if idx > 0:
			if len(chanPixmaps) >0:
				clean = chanPixmaps[idx -1][1]
			else:
				# not sure this can happen
				clean = True
			canListen =  clean and gotVoice and inPortName != None and inPortName != "<none>"
			listening = QCheckBox()
			listening.setTristate(False)
			listening.setChecked(False)
			listening.setEnabled(canListen)
			self.cvm.setIndexWidget(self.model.index(idx,2),listening)
			listening.stateChanged.connect(partial(self.toggleChecked,idx))

			clearBtn = QPushButton()
			clearBtn.setText("Clear")
			clearBtn.clicked.connect(partial(self.clearChan,idx))
			clearBtn.setEnabled(not clean)
			self.cvm.setIndexWidget(self.model.index(idx,4),clearBtn)

			# only enabled if not clean and has voice
			mute = QCheckBox()
			mute.setTristate(False)
			mute.setChecked(chanMuted[idx -1])
			self.cvm.setIndexWidget(self.model.index(idx,3),mute)
			mute.stateChanged.connect(partial(self.toggleMute,idx))
			mute.setEnabled((not clean) and gotVoice )

		timeLine = QLabel()
		if idx ==0:
			if wavePixmap != None:
				timeLine.setPixmap(wavePixmap.scaled(timeLineWidth,timeLineHeight,0,1))
				self.cvm.setIndexWidget(self.model.index(idx,5),timeLine)
			return
		if len(chanPixmaps) == 0:
			for i in range(0,16):
				chanPixmaps.append([ blackImgQ.scaled(timeLineWidth,timeLineHeight,0,1).copy(),True])

		if chanPixmaps[idx -1][1]:
			# it's a clean channel
			timeLine.setPixmap(cleanPixmap.scaled(timeLineWidth,timeLineHeight,0,1))
			self.cvm.setIndexWidget(self.model.index(idx,5),timeLine)
		else:
			# there is an activity pixmap
			timeLine.setPixmap(chanPixmaps[idx -1][0].scaled(timeLineWidth,timeLineHeight,0,1))
			self.cvm.setIndexWidget(self.model.index(idx,5),timeLine)

	def initUI(self):
		global timeLineWidth
		global timeLineHeight
		global layerWindowX
		global tableWidth
		global chanNumberX
		global voiceNameX
		global listenCheckX
		global muteCheckX
		global clearBtnX
		global timeLineWidth
		global timeLineHeight

		self.setWindowTitle('Edit Channel/Voice mapping')
		self.resize(layerWindowX,625)
		self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.Tool)

		self.cvm = QTableView()
		CVPresTable = []

		for row in range(0,17):
			if row == 0:
				CVPresTable.append(['Sound',"","","","",""])
			else:
				CVPresTable.append([ row -1, None, "","","",""])
		self.model = cvmModel(CVPresTable)

		self.cvm.setModel(self.model)

		self.cvm.verticalHeader().hide()


		self.cvm.setColumnWidth(0,chanNumberX)
		self.cvm.setColumnWidth(1,voiceNameX)
		self.cvm.setColumnWidth(2,listenCheckX)
		self.cvm.setColumnWidth(3,muteCheckX)
		self.cvm.setColumnWidth(4,clearBtnX)
		self.cvm.setColumnWidth(5,timeLineWidth)

		for idx in range(0, 17):
			self.comboAdd(idx)

		self.btnCancel = QPushButton('Cancel')
		self.btnCancel.setToolTip("Cancel channel voice mappings/mutes/listens; Voice creates and performance clears can't be backed out")
		self.btnCancel.clicked.connect(self.cancelOut)

		self.btnSave = QPushButton('Save')
		self.btnSave.clicked.connect(self.saveOut)
		self.btnSave.setEnabled(False)

		# Layout
		vbox = QVBoxLayout()

		vbox.addWidget(self.cvm)

		hbox5 = QHBoxLayout()
		hbox5.addWidget(self.btnCancel)
		hbox5.addWidget(self.btnSave)
		vbox.addLayout(hbox5)
		self.setLayout(vbox)

	def cancelOut(self):
		self.reject()

	def saveOut(self):
		global CVMap

		self.setClean(False)
		CVMap.clear()
		for idx in range(1, 17):
			w = self.cvm.indexWidget(self.model.index(idx, 1))
			CVMap.append([idx,w.currentText() ] )
		self.accept()

# the voice editor

class vEditD(QDialog):
	changedVoice = pyqtSignal()

	def __init__(self, v:voice):
		super().__init__()
		self.setModal(True)
		self.initUI(v)
		# a reference to the passed-in voice. We need this so we can write to it
		# at save time and totally ignore it at cancel time
		self.myv = v
		# the problem at cancel time is that we can ignore the parts of the voice
		# that have been changed by the widgets in this window, but some parts may
		# have already been changed and saved at the voice level. We need a copy
		self.revertCopy = v.copy()

	def setClean(self,clean):
		self.isClean = clean
		self.btnSave.setEnabled(not self.isClean)
		if not self.isClean:
			self.changedVoice.emit()

	def sd(self):
		#mess('Sd for veditd called')
		self.setClean(False)
		#mess('isClean = '+str(self.isClean))

	def resumeTimer(self):
		# flush out any midi events that may have come in while we were dealing with the event
		for msg in self.inport.iter_pending():
			pass
		self.midiTimer.start(50)

	def checkMidi(self):
		self.midiTimer.stop()
		msg = self.inport.poll()
		# because of some bug, mido's msg object doesn't support direct comparison with
		# None, even though poll() is documented as either returning a message or a None
		# so stringify it:
		if str(msg) != "None":
			if msg.type == 'note_on':
				idx = msg.note - 21
				self.getImg(idx)
		self.resumeTimer()

	def getImg(self,idx):
		self.midiTimer.stop()
		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open file', setup['lastimagesource'],"Image files (*.png *.jpg *.jpeg)")
		if fname != '':
			self.model._data[idx][3] = fname
			setup['lastimagesource'] = os.path.dirname(fname)
			checkSetupChange('lastimagesource',setup['lastimagesource'])
			iw = self.noteMap.indexWidget(self.model.index(idx,2))
			iw.setText("Remove Image")
			iw.clicked.disconnect()
			iw.clicked.connect(partial(self.removeImg, idx))
			self.sd()
		self.resumeTimer()

	def removeImg(self,idx):
		# tricky as we have to flip the function of the button too
		self.midiTimer.stop()
		self.model._data[idx][3] = '' # this isn't getting redrawn!!!
		self.pv.setPixmap(QPixmap(self.emptyPath).scaled(self.PVWidth,self.PVHeight,2,1))
		self.pvPath.setText('')
		iw = self.noteMap.indexWidget(self.model.index(idx,2))
		iw.setText("Select Image")
		iw.clicked.disconnect()
		iw.clicked.connect(partial(self.getImg, idx))
		self.sd()
		self.resumeTimer()

	def getDefImg(self,idx):
		self.midiTimer.stop()
		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open Default Image',setup['lastimagesource'],"Image files (*.png *.jpg *.jpeg)")
		if fname != '':
			self.sd()
			setup['lastimagesource'] = os.path.dirname(fname)
			checkSetupChange('lastimagesource',setup['lastimagesource'])
			self.diEdit.setText(fname)
		self.resumeTimer()

	def imgt(self,v,n):
		# imgTable rows have 0= note 1 = filename 2= cached image
		for it in v.vdata["imgTable"]:
			if it[0] == n:
				return it[1]

	def getRestImg(self,idx):
		self.midiTimer.stop()
		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open Rest Image', setup['lastimagesource'],"Image files (*.png *.jpg *.jpeg)")
		if fname != '':
			self.sd()
			setup['lastimagesource'] = os.path.dirname(fname)
			checkSetupChange('lastimagesource',setup['lastimagesource'])
			self.restEdit.setText(fname)
		self.resumeTimer()

	def noteRowAdd(self,idx):
		# This only adds the button to a pre-existing row created by
		# the SetModel call. It doesn't actually add a row
		if self.model._data[idx][3] == '':
			btnGetImg = QPushButton("Select Image")
			btnGetImg.clicked.connect(partial(self.getImg, idx))
		else:
			btnGetImg = QPushButton('Remove Image')
			btnGetImg.clicked.connect(partial(self.removeImg, idx))
		self.noteMap.setIndexWidget(self.model.index(idx, 2), btnGetImg)

	def toggleSizeControl(self):
		self.nativeSize = not self.sizeGBox.isChecked()
		self.myv.vdata['xsize'].data['native'] = self.nativeSize

	def toggleSync(self):
		global maintainAR
		global yauto

		maintainAR = not maintainAR
		self.ysPCombo.setEnabled(not maintainAR)
		self.ysE.setEnabled(not maintainAR)
		self.sd()
		if maintainAR:
			# do the sync right now. Most of this is just for appearance
			self.myv.vdata['xsize'].data['maintar'] = True
			self.myv.vdata['ysize'].data = self.myv.vdata['xsize'].data.copy()
			self.myv.vdata['ysize'].data['usedfor'] = 'ysize'
			yauto = True
			i = self.ysPCombo.findText(self.myv.vdata['xsize'].data['ptype'])
			self.ysPCombo.setCurrentIndex(i)
			yauto = False
		else:
			self.myv.vdata['xsize'].data['maintar'] = False

	def setInport(self):
		global inPortName

		if inPortName == None:
			self.inport = None
		else:
			self.inport = mido.open_input(inPortName)
			self.midiTimer = QTimer(self)
			self.midiTimer.timeout.connect(self.checkMidi)
			self.midiTimer.start(50)

	def onRowChange(self,item):
		row = item.row()
		if self.model._data[row][3] != None:
			# I'm sure it's cached somewhere, but for now:
			self.pvPath.setText(self.model._data[row][3])
			self.pv.setPixmap(QPixmap(self.model._data[row][3]).scaled(self.PVWidth,self.PVHeight,2,1))

	def initUI(self, v:voice):
		global maintainAR
		global inPortName

		self.setWindowTitle('Edit Voice')
		self.resize(1000,600)
		self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.Tool)

		self.isClean = True # don't use setclean at this stage as the objects it references aren't yet instantiated
		if v.vdata["name"] == "Untitled":
			self.nameAcquired = False
			self.new = True
		else:
			self.nameAcquired = True
			self.new = False

		self.setInport()

		# set up widgets
		self.nameLabel = QLabel('Name')
		self.nameEdit = QLineEdit()
		if not self.new:
			self.nameEdit.setEnabled(False)
			self.btnCname = QPushButton("Change")
			self.btnCname.clicked.connect(self.chName)
		else:
			self.nameEdit.setEnabled(True)
			self.nameEdit.setEchoMode(QLineEdit.Normal)

		self.nameEdit.setText(v.vdata["name"])
		self.nameEdit.textChanged.connect(self.maybeActiveSave)

		self.diLabel = QLabel("Default Image")
		self.diEdit = QLineEdit(self)
		self.diEdit.setText(self.imgt(v,-1))
		self.diEdit.setToolTip("Image shown when any key pressed unless overridded in note map table")
		self.diEdit.textChanged.connect(self.sd)
		self.diLookup = QPushButton('>')
		self.diLookup.clicked.connect(self.getDefImg)

		self.restLabel = QLabel("Rest Image")
		self.restEdit = QLineEdit(self)
		self.restEdit.setText(self.imgt(v,-2))
		self.restEdit.setToolTip("Image, in monophonic mode shown when no note playing")
		self.restEdit.textChanged.connect(self.sd)
		self.restLookup = QPushButton('>')
		self.restLookup.clicked.connect(self.getRestImg)

		self.noteMap = QTableView()
		# while the actual data in the model comes from vdata["imgTable"],
		# there's a lot of 'presentation' stuff in the model that we don't want
		# to store. Conversely, we probably want to retain the bitmap, or a ref
		# to it in vdata["imgTable"] which wouldn't be presented.
		presTable = []
		# v.vdata["imgTable"] is sparse mapped, presTable covers all (practical) possibilities
		definedNotes ={}
		if len(v.vdata["imgTable"]) > 0:
			for iti in range(0,len(v.vdata["imgTable"])):
				#mess("loading into note map "+v.vdata["imgTable"][iti][1])
				definedNotes[ v.vdata["imgTable"][iti][0] ] = iti

		ci = -1
		for pti in range (21,108):
			if pti in definedNotes:
				idx = definedNotes[pti]
				presTable.append([ v.vdata["imgTable"][idx][0], to_name(v.vdata["imgTable"][idx][0]), None, v.vdata["imgTable"][idx][1] ])
				ci = pti
			else:
				presTable.append([pti,to_name(pti),None,""])

		self.model = TableModel(presTable)
		if ci == -1:
			cidx = self.model.index(60 - 21,0)
		else:
			cidx = self.model.index(ci,0)
		# this is working on a nice-if where we move the ?viewport? to make populated rows visible (if any) or
		# middle C if not. But I can't figure out how/whether that could be done
		self.noteMap.setModel(self.model)
		for idx in range(0, len(presTable)-1):
			self.noteRowAdd(idx)

		self.noteMap.verticalHeader().hide()

		self.noteMap.setColumnWidth(0,55)
		self.noteMap.setColumnWidth(1,80)
		self.noteMap.setColumnWidth(3,240)

		self.noteMap.clicked.connect(self.onRowChange)

		self.btnCancel = QPushButton('Cancel')
		self.btnCancel.clicked.connect(self.cancelOut)

		self.btnSave = QPushButton('Save')
		self.btnSave.clicked.connect(self.saveOut)
		self.btnSave.setEnabled(self.nameAcquired and not self.isClean)

		self.xpP = v.vdata["xpos"]
		self.xposLabel = QLabel("xpos")
		self.xpPCombo = PCombo(self.xpP)
		self.xpPCombo.currentTextChanged.connect(self.sd) # we're always dirty if the ptype has changed
		self.xpE = PEButton(self.xpP)
		self.xpE.changedPath.connect(self.sd) # we're only dirty if the click on the PEButton resulted in the path being modified

		self.ypP = v.vdata["ypos"]
		self.yposLabel = QLabel("ypos")
		self.ypPCombo = PCombo(self.ypP)
		self.ypPCombo.currentTextChanged.connect(self.sd)
		self.ypE = PEButton(self.ypP)
		self.ypE.changedPath.connect(self.sd)

		self.xsP = v.vdata["xsize"]
		self.xsizeLabel = QLabel("xsize")
		self.xsE = PEButton(self.xsP)
		self.xsE.changedPath.connect(self.sd)

		maintainAR = v.vdata['xsize'].data['maintar']
		self.nativeSize = v.vdata['xsize'].data['native']

		self.maintainARLabel = QLabel("Sync to X Scaling")
		self.maintainARCb = QCheckBox()
		self.maintainARCb.setTristate(False)
		self.maintainARCb.setChecked(maintainAR)
		self.maintainARCb.stateChanged.connect(self.toggleSync)

		self.ysP = v.vdata["ysize"]
		self.ysizeLabel = QLabel("ysize")
		self.ysPCombo = PCombo(self.ysP)
		self.ysPCombo.setEnabled(not maintainAR)
		self.ysPCombo.currentTextChanged.connect(self.sd)
		self.ysE = PEButton(self.ysP)
		self.ysE.changedPath.connect(self.sd)
		self.ysE.setEnabled(not maintainAR)

		self.xsPCombo = xsizeCombo(self.xsP,self.ysP,self.ysPCombo)
		self.xsPCombo.currentTextChanged.connect(self.sd)

		self.opP = v.vdata["opacity"]
		self.opacityLabel = QLabel("opacity")
		self.opPCombo = PCombo(self.opP)
		self.opPCombo.currentTextChanged.connect(self.sd)
		self.opE =PEButton(self.opP)
		self.opE.changedPath.connect(self.sd)

		previewLabel = QLabel("Image")
		self.pv = QLabel()
		self.pvPath = QLabel()
		self.emptyPath = amenicDir+"/Empty.png"
		self.PVWidth = 180
		self.PVHeight = 180
		self.pv.setPixmap(QPixmap(self.emptyPath).scaled(self.PVWidth,self.PVHeight,2,1))

		# Layout
		hboxouter = QHBoxLayout()
		vbox = QVBoxLayout()
		hbox1=QHBoxLayout()
		hbox1.addWidget(self.nameLabel)
		hbox1.addWidget(self.nameEdit)
		if not self.new:
			hbox1.addWidget(self.btnCname)
		vbox.addLayout(hbox1)

		hbox2 = QHBoxLayout()
		hbox2.addWidget(self.diLabel)
		hbox2.addWidget(self.diEdit)
		hbox2.addWidget(self.diLookup)
		vbox.addLayout(hbox2)

		hbox3 = QHBoxLayout()
		hbox3.addWidget(self.restLabel)
		hbox3.addWidget(self.restEdit)
		hbox3.addWidget(self.restLookup)
		vbox.addLayout(hbox3)

		vbox.addWidget(self.noteMap)

		hbox5 = QHBoxLayout()
		hbox5.addWidget(self.btnCancel)
		hbox5.addWidget(self.btnSave)
		vbox.addLayout(hbox5)

		vbox2 = QVBoxLayout()

		hboxXPos = QHBoxLayout()
		hboxXPos.addWidget(self.xposLabel)
		hboxXPos.addWidget(self.xpPCombo)
		hboxXPos.addWidget(self.xpE)
		vbox2.addLayout(hboxXPos)

		hboxYPos = QHBoxLayout()
		hboxYPos.addWidget(self.yposLabel)
		hboxYPos.addWidget(self.ypPCombo)
		hboxYPos.addWidget(self.ypE)
		vbox2.addLayout(hboxYPos)

		hboxOpacity = QHBoxLayout()
		hboxOpacity.addWidget(self.opacityLabel)
		hboxOpacity.addWidget(self.opPCombo)
		hboxOpacity.addWidget(self.opE)
		vbox2.addLayout(hboxOpacity)

		self.sizeGBox = QGroupBox("Use Image Size Control")
		self.sizeGBox.setCheckable(True)
		self.sizeGBox.setChecked(not self.nativeSize)
		self.sizeGBox.clicked.connect(self.toggleSizeControl)
		vboxSize = QVBoxLayout()

		hboxxsize = QHBoxLayout()
		hboxxsize.addWidget(self.xsizeLabel)
		hboxxsize.addWidget(self.xsPCombo)
		hboxxsize.addWidget(self.xsE)
		vboxSize.addLayout(hboxxsize)

		hboxXSync = QHBoxLayout()
		hboxXSync.addWidget(self.maintainARLabel)
		hboxXSync.addWidget(self.maintainARCb)
		vboxSize.addLayout(hboxXSync)

		hboxysize = QHBoxLayout()
		hboxysize.addWidget(self.ysizeLabel)
		hboxysize.addWidget(self.ysPCombo)
		hboxysize.addWidget(self.ysE)
		vboxSize.addLayout(hboxysize)

		self.sizeGBox.setLayout(vboxSize)

		vbox2.addWidget(self.sizeGBox)
		hboxouter.addLayout(vbox)
		hboxouter.addLayout(vbox2)

		vbox3 = QVBoxLayout()
		vbox3.addWidget(previewLabel)
		vbox3.addWidget(self.pvPath)
		vbox3.addWidget(self.pv)

		hboxouter.addLayout(vbox3)

		self.setLayout(hboxouter)

	def chName(self):
		mess("Here we offer to change the name of the voice")

	def cancelOut(self):
		# this doesn't revert changes to voice-owned paths, which it should
		# how does path edit cancel revert changes?? - it does nothing, it simply doesn't copy the data from
		# the widgets into the voice. We'd have to keep a copy
		self.midiTimer.stop()
		self.reject()
		self.myv.vdata = self.revertCopy.vdata
		return None

	def imgNamed(self,fn):
		if iimf == 'c':
			image = cv2.imread(fn,cv2.IMREAD_UNCHANGED)
		else:
			image = QPixmap(fn)
		return image

	def saveOut(self):
		self.changedVoice.emit()
		self.midiTimer.stop()
		self.myv.vdata["name"] = self.nameEdit.text()
		# mess("model data size  "+str(len(self.model._data)))
		defImgIdx = None
		restImgIdx = None
		for idx in range(0, len(self.model._data)):
			if self.model._data[idx][0] == -1:
				defImgIdx = idx
			if self.model._data[idx][0] == -2:
				restImgIdx = idx

		if defImgIdx == None and self.diEdit.text() != None and self.diEdit.text() != '':
			# create new entry in imgTable for default image
			image = self.imgNamed(self.diEdit.text())
			self.model._data.append([-1,None,None,self.diEdit.text(),image])
		elif defImgIdx != None:
			image = self.imgNamed(self.diEdit.text())
			self.model._data[defImgIdx] = [-1,None,None,self.diEdit.text(),image]

		if restImgIdx == None and self.restEdit.text() != None and self.restEdit.text() != '':
			# create new entry in imgTable for rest image
			image = self.imgNamed(self.restEdit.text())
			self.model._data.append([-2,None,None,self.restEdit.text(),image])
		elif restImgIdx != None:
			image = self.imgNamed(self.restEdit.text())
			self.model._data[restImgIdx] = [-2,None,None,self.restEdit.text(),image]

		self.myv.vdata["imgTable"] = []
		for idx in range(0, len(self.model._data)):
			if self.model._data[idx][3] != None and self.model._data[idx][3] != '':
				# mess("found "+ self.model._data[idx][3]+" in note map")
				image = self.imgNamed(self.model._data[idx][3])
				# put cached image into table
				self.myv.vdata["imgTable"].append([ self.model._data[idx][0], self.model._data[idx][3],image])
		self.accept()

	def maybeActiveSave(self):
		s = self.nameEdit.text
		if s != "Untitled" and s != "" and s != None :
			self.btnSave.setEnabled(True)
		else:
			self.btnSave.setEnabled(False)
		# whether it's saveable or not, it's definitely dirty:
		self.sd()

# the main window
class AmenicMain(QMainWindow):
	def __init__(self):
		super().__init__()
		icon = QIcon()
		icon.addPixmap(QPixmap("AmenicIcon.png"), QIcon.Selected, QIcon.On)
		self.setWindowIcon(icon)
		self.vtable = []
		self.loading = False
		self.lastMess = None
		self.lastPerfMess = None
		self.setupTime = True
		self.initUI()
		self.setupTime = False

	def setGotAudio(self,gotAudio):
		self.setPlayable(gotAudio)
		self.newPAct.setEnabled(gotAudio)
		# non-invertable states:
		if not gotAudio:
			self.savePAct.setEnabled(False)
			self.expVAct.setEnabled(False)
			self.expVidAct.setEnabled(False)
		self.savePAsAct.setEnabled(gotAudio)
		self.impVAct.setEnabled(gotAudio)
		self.impMAct.setEnabled(gotAudio)
		self.nVoiceBtn.setEnabled(gotAudio and ( mode == 'edit'))
		self.edCombo.setEnabled(gotAudio and ( mode == 'edit'))
		self.cMapBtn.setEnabled(gotAudio)

	def setGotVoices(self,gotVoices):
		self.expVAct.setEnabled(gotVoices)

	def setGotMappedVoices(self,gotMappedVoices):
		pass

	def setGotProjName(self,gotProjName):
		global cleanProj

		#self.savePAct.setEnabled(gotProjName and not cleanProj)
		self.savePAct.setEnabled(not cleanProj)

	def setCanGenVid(self,canGen):
		self.expVidAct.setEnabled(canGen)

	def setPlayable(self,playable):
		# just means the play button should be active, not that there is
		# enough data to generate video
		self.btnPlay.setEnabled(playable)

	def setPerfPlayable(self,p):
		global perfPlayable

		perfPlayable = p
		if not p:
			self.btnPlay.setText("Play (audio Only)")
		else:
			self.btnPlay.setText("Play")
		#mess("perfPlayable: "+str(perfPlayable))

	def setClean(self,clean):
		global cleanProj
		global projName

		gotProjName = ( projName != 'Untitled')
		#self.savePAct.setEnabled((not clean) and gotProjName)
		self.savePAct.setEnabled((not clean))
		self.dirtyCheck.setChecked(not clean)
		cleanProj = clean

	def sd(self):
		self.setClean(False)

	def checkSave(self):
		qm = QMessageBox()
		resp = qm.question(self,'', "Save "+projName+" first? ", qm.Yes | qm.No | qm.Cancel )
		if resp == qm.Cancel:
			return False
		if resp == qm.Yes:
			if projName == "Untitled":
				self.sPAs()
			else:
				self.saveProj()
		return True

	def closeEvent(self,event):
		if not cleanProj:
			if self.checkSave():
				event.accept()
			else:
				return # they hit cancel

	def emptyProj(self):
		global audioFile
		global performanceFile
		global performance
		global iimf
		global wavePixmap
		global cleanProj
		global projName

		self.setClean(True)
		self.loading = False
		projName = "Untitled"
		audioFile = ''
		performanceFile = ''
		chanMuted.clear()
		for i in range(0,16):
			chanMuted.append(False)
		self.setGotAudio(False)
		self.setAudio()
		self.setWaveform(audioFile)
		self.setMidi(performanceFile)

		performance = MidiFile()
		# need to stuff in a tempo Message
		# make a pure tempo track. This is fairly normally the first track in a type 1 midi file
		tt = MidiTrack()
		tt.name = 'Tempo Track'
		performance.tracks.append(tt)
		bpm = 120
		ctempo = int(60000000 /bpm)
		msg = MetaMessage('set_tempo',tempo = ctempo, time = 0 )
		tt.append(msg)

		midiTiming(performance)
		voices.clear() # DON'T do voices = [] as that declares a local voices!
		CVMap.clear()
		for row in range(0,16):
			CVMap.append([ row, None,'','',''])
		self.edComboInit()
		chanPixmaps.clear()

	def newProj(self):
		global cleanProj

		if not cleanProj:
			if not self.checkSave():
				return
		loadSetup() # revert to general setup, not any proj-specific setup
		self.emptyProj()
		self.startImg()

	def projFromFn(self,fn):
		pn = os.path.basename(fn)
		pn = re.sub('.apr$','',pn)
		return pn

	def openProj(self):
		global audioFile
		global performanceFile
		global iimf
		global wavePixmap
		global projName
		global cleanProj
		global setup
		global inPortName

		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open Project File', projPath,"Amenic Project files (*.apr)")
		if fname == '':
			return
		if projName != None:
			if not cleanProj:
				npn = self.projFromFn(fname)
				if npn == projName:
					# ok to revert npn to saved
					qm = QMessageBox()
					resp = qm.question(self,'', "OK to revert project "+projName+ " to saved version?", qm.Yes | qm.No )
					if resp == qm.Yes:
						pass
					else:
						return
				else:
					# save projname first?
					qm = QMessageBox()
					resp = qm.question(self,'', "Save project "+projName+ " first?", qm.Yes | qm.No )
					if resp == qm.Yes:
						self.saveProj()
					else:
						pass
		self.emptyProj()
		self.startImg()
		self.loading = True
		proj = fromJsonFile(fname)

		voices.clear() # DON'T do voices = [] as that declares a local voices!
		CVMap.clear()
		self.setClean(True)
		projName = self.projFromFn(fname)

		self.setWindowTitle('Amenic - '+fname)

		for vname in proj["voices"]:
			# print("Loading voice "+vname)
			internalVoice = internaliseVoice(proj['voices'][vname],vname)
			voices.append(internalVoice)

		if len(voices) > 0:
			self.setGotVoices(True)

		for map in proj["cvmap"]:
			CVMap.append(map)

		audioFile = proj["audiofile"]
		self.setWaveform(audioFile)

		self.setAudio()
		# has to be audio then midi as MakeWaveform calculates the timeLineWidth
		performanceFile = proj["midifile"]
		self.setMidi(proj["midifile"])

		if 'projsetup' in proj.keys():
			setup = proj['projsetup']
		inPortName = setup['preferredmidiinput']
		self.inPortInit()

		self.edComboInit()
		self.loading = False
		self.setGotAudio(True)
		self.setGotProjName(True)
		checkVidGen(self)
		self.checkPerfPlayable(True)

	def genVid(self):
		n = projPath + '/'+ projName + ".mp4"
		( mp4out, filter ) = QFileDialog.getSaveFileName(self,"Export to MP4",n,"MPEG-4 files (*.mp4)")
		if mp4out == '':
			return
		exportToMp4 = vidExport(mp4out)
		exportToMp4.exec_()

	def sPAs(self):
		self.saveProj(True)

	def saveProj(self,saveAs = False):
		global performanceFile
		global projName
		global setup

		firstSave = (projName == "Untitled")
		proj = dict()
		proj["voices"]= dict()
		for v in voices:
			vname = v.vdata["name"]
			proj['voices'][vname] = jsonAbleVoice(v,vname)

		proj["cvmap"] = []
		for map in CVMap:
			proj["cvmap"].append(map)

		proj["audiofile"] = audioFile
		proj["projsetup"] = setup

		n = projPath +'/'+ projName + "."+pExtn
		if saveAs or firstSave:
			( projFileName, filter ) = QFileDialog.getSaveFileName(self,"Save Project File",n,"Amenic Project (*.apr)")
			if projFileName == '':
				return
			# !!! need to save midi, and I'm guessing audio under a different filename. Ultimately we'd want a project
			# directory or zipfile covering images too, but just saving the midi under the new project name should do
		else:
			projFileName = n
		if performanceFile == '' or saveAs or firstSave:
			performanceFile = re.sub('.'+pExtn+'$','.apf',projFileName)

		if firstSave:
			projName = self.projFromFn(projFileName)
			self.setWindowTitle('Amenic - '+projFileName)
		proj["midifile"] = performanceFile
		performance.save(performanceFile)

		toJsonFile(proj,projFileName)
		self.setClean(True)
		self.setGotProjName(True)

	def exportVoice(self):
		ve = voiceExport()
		ve.exec_()
		voiceName = ve.selVoice
		if voiceName == "<none>":
			return
		v = getVoiceByName(voiceName)
		saveData = json.dumps(jsonAbleVoice(v,voiceName), indent = 1)
		n = projPath + voiceName + ".avc"
		( avcOut, filter ) = QFileDialog.getSaveFileName(self,"Export to Amenic voice file",n,"Avc files (*.avc)")
		if avcOut == '':
			return
		fh = open(avcOut,"w")
		fh.write(saveData)
		fh.close()

	def importVoice(self):
		( avcIn, filter ) = QFileDialog.getOpenFileName(self,"Import from Amenic voice file",voicesPath,"Avc files (*.avc)")
		if avcIn == '':
			return
		vfname = os.path.basename(avcIn)
		vfname = re.sub('.avc$','',vfname)
		cv = getVoiceByName(vfname)
		if cv != None:
			mess("Name collision "+ vfname)
			return
		fh = open(avcIn,'r')
		loadData = fh.read()
		fh.close()
		lv = json.loads(loadData)
		iv = internaliseVoice(lv,vfname)
		voices.append(iv)
		self.edComboInit()
		self.setClean(False)
		self.setGotVoices(True)

	def setAudio(self):
		global audioFile
		global audioDuration

		if audioFile != '':
			self.ssFileShow.setText(audioFile)
			self.setPlayable(True)

			# may as well initialise the audio player here
			audio = MP3(audioFile)
			audioDuration = audio.info.length
			durationInFrames = int(audioDuration * fRate)
			self.adShow.setText(f'{audioDuration:.2f}')
			self.difShow.setText(str(durationInFrames))
			mixer.init()
			mixer.music.load(audioFile)
			#self.st = "got audio"
			#self.st = vlc.MediaPlayer("File://"+audioFile)

		else:
			self.ssFileShow.setText('')
			self.adShow.setText('')
			self.difShow.setText('')
			self.st = None
			if performance == None:
				self.setPlayable(False)
		self.checkPerfPlayable(False)

	def setWaveform(self,audioFile):
		global wavePixmap

		if audioFile == '':
			wavePixmap = QPixmap(amenicDir + "nowave.jpg")
		else:
			MakeWaveform(audioFile,amenicDir +"/tempWave.jpg")
			wavePixmap = QPixmap(amenicDir + "/tempWave.jpg")

	def importAudio(self):
		global audioFile

		( audioFile, filter)  = QFileDialog.getOpenFileName(self, 'Open file', setup['lastaudiosource'],"Sound files (*.mp3)")
		if audioFile != '':
			setup['lastaudiosource'] = os.path.dirname(audioFile)
			checkSetupChange('lastaudiosource',setup['lastaudiosource'])
			self.setAudio()
			self.setWaveform(audioFile)
			self.setClean(False)
			self.setGotAudio(True)
			self.setPlayable(True) # in a limited sort of way

	def convertPerformance(self):
		global performance

		# analyse and adjust raw midi file to .apf requirements
		if performance.type == 0:
			performance.type = 1
			# think that's about all there is to that
		elif performance.type == 2:
			err("Can't import files with midi type 2")
			return False
		gotTrackFor =[]
		for i, track in enumerate(performance.tracks):
			#print('Track {}: {}'.format(i, track.name))
			chans = []
			msgTypes = []
			for msg in track:
				#print(str(type(msg)))
				if msgTypes.count(msg.type) == 0:
					msgTypes.append(msg.type)
				if str(type(msg)) != "<class 'mido.midifiles.meta.MetaMessage'>":
					if chans.count(msg.channel) == 0:
						chans.append(msg.channel)
			#print("Track "+str(i)+" contains events for channels ",end='')
			#print(chans)
			if len(chans) > 1:
				err('Too complicated: multiple channels per track')
				return False
			if len(chans) == 0:
				continue # no channeled events on this track (?maybe tempo or just empty?)
			if gotTrackFor.count(chans[0]) != 0:
				err('Too complicated: multiple tracks with events for channel '+str(chans[0]))
				return False
			track.name = "forChan"+str(chans[0])
		return True

	def checkPerfPlayable(self,loadTime):
		global CVMap, chanMuted

		self.setPerfPlayable(False)
		if len(CVMap) ==0:
			return
		if performanceFile == None:
			return
		for i in range(0,16):
			if CVMap[i][1] == None or CVMap[i][1] == "<none>":
				chanMuted[i] = True
			else:
				# at load time we set it to unmuted as we know that will be ok
				# at all other times we respect the current muted state
				if loadTime:
					chanMuted[i] = False
				if not chanMuted[i]:
					self.setPerfPlayable(True)
					continue

	def setMidi(self, performanceFile, imported = False):
		global performance
		global bpm
		global CVMap
		global chanMuted

		gotFile = False
		if performanceFile != '':
			gotFile = True
			performance = MidiFile(performanceFile)
			if imported:
				gotFile = self.convertPerformance()

		if gotFile:
			self.setPlayable(True)
			self.mpFileShow.setText(performanceFile)
			midiTiming(performance) # this actually extracts info from the file
			self.bpmShow.setText(str(bpm))
			makeChannelTimelines(performance)
			self.checkPerfPlayable(False)
		else:
			self.mpFileShow.setText('')
			self.bpmShow.setText('')
			if audioFile == '' and performance == None:
				self.setPlayable(False)

	def importMidi(self):
		global performanceFile

		if performance != None:
			qm = QMessageBox()
			resp = qm.question(self,'', "OK to overwrite existing performance information? ", qm.Yes | qm.No )
			if resp == qm.Yes:
				pass
			else:
				return
		(performanceFile, filter) = QFileDialog.getOpenFileName(self,'Open Midi File',setup['lastmidisource'],"Midi files (*.mid *.MID)")
		if performanceFile != '':
			setup['lastmidisource'] = os.path.dirname(performanceFile)
			checkSetupChange('lastmidisource',setup['lastmidisource'])
			self.setMidi(performanceFile, True)
			self.setClean(False)

	def playslot(self):
		# this pushes out the events in the performance in (roughly) the right timing
		# and maintains the soundBoard with all currently playing notes

		mess = self.p.playNext(self.lastMess)
		if str(mess) != "None":
			self.lastMess = mess
			# convert from a float number of seconds to and integer number of milliseconds
			if not self.stopFlag:
				ms = int(mess.time * 1000)
				QTimer.singleShot(ms,self.playslot)
		elif self.stopFlag:
			return

	def cameraSlot(self):
		# the camera takes snaps of the soundboard and renders them
		global theatre

		if self.stopFlag:
			return
		self.c.exposure()
		theatre.show()
		theatre.repaint()

		QTimer.singleShot(self.gateTimerPeriod,self.cameraSlot)

	def startPerfTimer(self):
		# flush out any midi events that may have come in while we were dealing with the event
		for msg in self.inport.iter_pending():
				pass
		self.livePerfTimer.start(30)


	def tickDelta(self):
		global performance
		global tickDuration
		global totalTicks
		global lastMsgTime

		oldEventTime = self.lastEventTime
		self.lastEventTime = time.time()
		lastMsgTime = self.lastEventTime
		deltaTicks = int((time.time() - oldEventTime ) * 1000000/ tickDuration )
		totalTicks += deltaTicks
		return deltaTicks

	def checkPerfSlot(self):
		global board
		global listenChannel

		self.livePerfTimer.stop()

		if self.stopFlag:
			return
		msg = self.inport.poll()
		# because of some bug, mido's msg object doesn't support direct comparison with
		# None, even though poll() is documented as either returning a message or a None
		# so stringify it:
		while str(msg) != "None":
			if msg.type == "sysex":
				msg = self.inport.poll()
				continue
			msg.channel = listenChannel # most likely it's coming in on chan 0
			#print(msg)
			if msg.type == 'note_on':
				board.noteOn(msg)
			elif msg.type == "note_off":
				board.noteOff(msg)
			if True:
				msg.time = self.tickDelta()
				#print("putting out event with fixed-up time",end=" ")
				#print(str(msg))
				self.track.append(msg)
				self.lastEventTime = time.time()
			msg = self.inport.poll()
		self.startPerfTimer()

	def setInport(self):
		global inPortName

		if inPortName != None:
			self.inport = mido.open_input(inPortName)
			if not self.setupTime:
				checkSetupChange('preferredmidiinput',inPortName)
		else:
			if not self.setupTime:
				checkSetupChange('preferredmidiinput',"<none>")

	# this is the routine that kicks off all the facets of 'playing'. I launches the reference audio track
	# it starts the midi/performance play to soundboard, it starts the performance listener, sending
	# output to soundboard, and it starts the camera that renders the soundboard and displays to screen.
	def play(self):
		global CVMap
		global theatre
		global board
		global fRate
		global performance
		global perfPlayable
		global lastMsgTime

		lastMsgTime = None
		self.stopFlag = False
		# this shouldn't happen, but:
		if performance == None and audioFile == '':
			err("Nothing to play")
			return

		if listenChannel != None:
			if inPortName != None:
				self.setInport()
				self.livePerfTimer = QTimer()
				self.livePerfTimer.timeout.connect(self.checkPerfSlot)
				self.performanceStartTime = time.time()
				self.track = MidiTrack()
				self.track.name = "forChan"+str(listenChannel)
				performance.tracks.append(self.track)
				self.lastPerfMess = Message('program_change', channel = listenChannel, program=12, time=0)
				mixerLag = 0.16
				self.firstEventTime = self.performanceStartTime + mixerLag
				self.lastEventTime = self.firstEventTime
				totalTicks = 0
				self.startPerfTimer()

		if performance != None:

			if len(CVMap)==0:
				err("No voices assigned to layers. Can't render performance info")
				self.setPerfPlayable(False)
			else:
				self.checkPerfPlayable(False)
			if perfPlayable:
				self.lastMess = None
				# create camera
				board = soundBoard('realtime')
				self.gateTimerPeriod = int(1000 / fRate)

				self.c = camera(None,theatre)
				#start the camera
				self.cameraSlot()

				self.p = player(performance,self)
				# start the midi player
				self.playslot()
		else:
			self.setPerfPlayable(False)

		if not perfPlayable:
			warn("Audio only, no voiced performance info")

		if audioFile != '':
			#self.st.play()
			mixer.music.play()
			#playsound.playsound(audioFile)
			self.btnStop.setEnabled(True)

	def channelMap(self):
		global CVMap

		cvm = CVMapEdit(self)
		cvm.changedProj.connect(self.sd)
		cvm.exec_()
		self.edComboInit() # new voices may have been added
		# if an existing populated track has been assigned a voice, this will now be
		# generatable
		if len(chanPixmaps) == 0:
			mess("that'll be the problem")
			quit()
		#mess("checking playable ")
		self.checkPerfPlayable(False)
		#mess("perfPlayable: "+ str(perfPlayable))
		if mode == 'export':
			for i in range(0,16):
				if not chanPixmaps[i][1]:
					if CVMap[i][1] != None and CVMap[i][1] != "<none>":
						self.setCanGenVid(True)


	def edComboInit(self):
		self.edCombo.clear()
		self.edCombo.addItem("<Select Voice To Edit>")
		i = self.edCombo.findText("<Select Voice To Edit>")
		self.edCombo.setCurrentIndex(i)
		for v in voices:
			self.edCombo.addItem(v.vdata['name'])

	def inPortInit(self):
		global inPortName

		self.inPortCombo.clear()
		self.inPortCombo.addItem("<none>")
		alreadySeen = []
		for p in mido.get_input_names():
			if not p in alreadySeen:
				alreadySeen.append(p)
				if inPortName == None:
					inPortName = p
				self.inPortCombo.addItem(p)
		idx = self.inPortCombo.findText(inPortName)
		if idx == -1:
			idx = self.inPortCombo.findText(p)
			if idx == -1:
				idx = self.inPortCombo.findText("<none>")
				inPortName = None
			else:
				inPortName = p
		self.inPortCombo.setCurrentIndex(idx)
		self.setInport()

	def newVoice(self):
		v = voice()
		v.edit()
		if not v.isClean:
			#mess('voice seems to be dirty')
			voices.append(v)
			self.edComboInit()
			self.setGotVoices(True)
			self.setClean(False)
		#else:
		#	mess('voice seems to be clean')

	def startImg(self):
		global emptyImg
		global iimf
		global theatre

		emptyPath = amenicDir+"/Empty.png"
		if iimf == 'q':
			emptyImg = QPixmap(emptyPath).scaled(tWidth,tHeight,2,1)
			theatre.setPixmap(emptyImg)
		else:
			# print ("loading emptyImg")
			emptyImg = cv2.resize(cv2.imread(emptyPath,cv2.IMREAD_COLOR),(tWidth,tHeight))
			ei = QPixmap(emptyPath).scaled(tWidth,tHeight,2,1)
			theatre.setPixmap(ei)
			#theatre.setPixmap(convertCvImage2QtImage(emtyImg))
		# I have a suspicion that these two lines are the only ones that actually do anything
		theatre.setLayers([])
		theatre.show()

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
		# don't think I'm getting a lot of benefit from the buddying
		# but look at https://doc.qt.io/archives/qt-4.8/designer-buddy-mode.html and
		# https://doc.qt.io/qtcreator/creator-keyboard-shortcuts.html
		timeLineGeometry()

		for row in range(0,16):
			CVMap.append([ row, None])

		self.newPAct = QAction(QIcon(),'New Project',self)
		self.newPAct.setShortcut('Ctrl+N')
		self.newPAct.setStatusTip("New Project")
		self.newPAct.triggered.connect(self.newProj)

		openPAct = QAction(QIcon(),'Open Project',self)
		openPAct.setShortcut('Ctrl+O')
		openPAct.setStatusTip('Open Project')
		openPAct.triggered.connect(self.openProj)

		self.savePAct = QAction(QIcon(), 'Save Project', self)
		self.savePAct.setShortcut('Ctrl+S')
		self.savePAct.setStatusTip('Save Project')
		self.savePAct.triggered.connect(self.saveProj)

		self.savePAsAct = QAction(QIcon(), 'Save Project As', self)
		self.savePAsAct.setStatusTip('Save Project As')
		self.savePAsAct.triggered.connect(self.sPAs)

		self.expVAct = QAction(QIcon(), 'Export Voice', self)
		self.expVAct.setShortcut('Ctrl+E')
		self.expVAct.setStatusTip('Export Voice')
		self.expVAct.triggered.connect(self.exportVoice)

		self.impVAct = QAction(QIcon(), 'Import Voice', self)
		self.impVAct.setShortcut('Ctrl+I')
		self.impVAct.setStatusTip('Import Voice')
		self.impVAct.triggered.connect(self.importVoice)

		self.impMAct = QAction(QIcon(), 'Import Midi', self)
		self.impMAct.setShortcut('Ctrl+M')
		self.impMAct.setStatusTip('Import Midi')
		self.impMAct.triggered.connect(self.importMidi)

		impAAct = QAction(QIcon(), 'Import Audio', self)
		impAAct.setShortcut('Ctrl+A')
		impAAct.setStatusTip('Import Audio')
		impAAct.triggered.connect(self.importAudio)

		self.expVidAct = QAction(QIcon(),'Generate MP4',self)
		self.expVidAct.setStatusTip('Export project video to MP4 file')
		self.expVidAct.triggered.connect(self.genVid)

		self.checkPortsAct = QAction(QIcon(),'Check Devices')
		self.checkPortsAct.setStatusTip('Check for new midi input devices')
		self.checkPortsAct.triggered.connect(self.inPortInit)

		menubar = self.menuBar()
		fileMenu = menubar.addMenu('&File')
		fileMenu.addAction(self.newPAct)
		fileMenu.addAction(openPAct)
		fileMenu.addAction(self.savePAct)
		fileMenu.addAction(self.savePAsAct)
		fileMenu.addAction(self.expVAct)
		fileMenu.addAction(self.impVAct)
		fileMenu.addAction(self.impMAct)
		fileMenu.addAction(impAAct)
		fileMenu.addAction(self.expVidAct)
		midiMenu = menubar.addMenu('Midi')
		midiMenu.addAction(self.checkPortsAct)

		self.cMapBtn = QPushButton("Layers")
		self.cMapBtn.clicked.connect(self.channelMap)
		self.cMapBtn.setEnabled(False)

		self.nVoiceBtn = QPushButton("New Voice")
		self.nVoiceBtn.clicked.connect(self.newVoice)
		self.nVoiceBtn.setEnabled(False)

		edLabel = QLabel('Edit Voice',self)
		self.edCombo = QComboBox(self)
		self.edComboInit()
		self.edCombo.currentIndexChanged.connect(self.edSelChg)

		self.edCombo.setEnabled(False)

		self.inPortCombo = QComboBox(self)
		self.inPortInit()
		# don't want to trigger inPortChg at setup time, so use activated
		# which happens on user action only
		#self.inPortCombo.currentIndexChanged.connect(self.inPortChg)
		self.inPortCombo.activated.connect(self.inPortChg)

		self.dirtyCheck = QCheckBox()
		self.dirtyCheck.setTristate(False)
		self.dirtyCheck.setChecked(False)
		self.dirtyCheck.setEnabled(False)

		ssLabel = QLabel('Sound Source',self)
		self.ssFileShow= QLineEdit(self)
		self.ssFileShow.readOnly = True
		adLabel = QLabel('Audio Duration seconds')
		self.adShow = QLineEdit(self)
		self.adShow.setMaximumWidth(80)
		self.adShow.readOnly = True
		difLabel = QLabel(' Frames ')
		self.difShow = QLineEdit(self)
		self.difShow.setMaximumWidth(80)
		self.difShow.readOnly = True

		mpLabel = QLabel('Performance File',self)
		self.mpFileShow= QLineEdit(self)
		self.mpFileShow.readOnly = True
		bpmLabel = QLabel("BPM")
		self.bpmShow = QLineEdit(self)
		self.bpmShow.readOnly = True
		self.recLED = QLabel()
		redLEDOff = QPixmap(amenicDir+"/led-off-th.png").scaled(20,20,2,1)
		redLEDOn  = QPixmap(amenicDir+"/red-ledon-th.png").scaled(20,20,2,1)
		self.recLED.setPixmap(redLEDOff)

		theatre = theatreLabel(self)
		theatre.setMaximumHeight(tHeight)

		cleanPixmap = QPixmap(amenicDir+"/clean.png")
		blackPath = amenicDir + "/black.png"
		blackImgQ = QPixmap(blackPath)
		blackImg = cv2.resize(cv2.imread(blackPath,cv2.IMREAD_COLOR),(tWidth,tHeight))
		self.startImg()

		self.btnPlay = QPushButton('&Play')
		self.btnPlay.clicked.connect(self.play)
		self.btnPlay.setEnabled(False)

		self.btnStop = QPushButton('&Stop')
		self.btnStop.clicked.connect(self.transportStop)
		self.btnStop.setEnabled(False)

		vbox1 = QVBoxLayout()
		hbox1 = QHBoxLayout()
		hbox1.addWidget(self.cMapBtn)

		hbox1.addWidget(self.nVoiceBtn)

		hbox1.addWidget(edLabel)
		hbox1.addWidget(self.edCombo)
		hbox1.addWidget(self.inPortCombo)
		hbox1.addWidget(self.dirtyCheck)

		vbox1.addLayout(hbox1)

		hbox2 = QHBoxLayout()
		hbox2.addWidget(ssLabel)
		hbox2.addWidget(self.ssFileShow)
		hbox2.addWidget(adLabel)
		hbox2.addWidget(self.adShow)
		hbox2.addWidget(difLabel)
		hbox2.addWidget(self.difShow)

		vbox1.addLayout(hbox2)

		hbox25 = QHBoxLayout()
		hbox25.addWidget(mpLabel)
		hbox25.addWidget(self.mpFileShow)
		hbox25.addWidget(bpmLabel)
		hbox25.addWidget(self.bpmShow)
		hbox25.addWidget(self.recLED)

		vbox1.addLayout(hbox25)
		vbox1.addWidget(theatre)

		hbox3 = QHBoxLayout()
		hbox3.addWidget(self.btnPlay)
		hbox3.addWidget(self.btnStop)

		vbox1.addLayout(hbox3)

		container = QWidget()
		container.setLayout(vbox1)

		# Set the central widget of the Window.
		self.setCentralWidget(container)
		self.setGotAudio(False)

		self.emptyProj() # same code as used by newProj

	def edSelChg(self,i):
		if self.edCombo.currentText() != "<Select Voice To Edit>":
			# mess("edit "+self.edCombo.currentText())
			edv = getVoiceByName(self.edCombo.currentText())
			if edv == None:
				if not self.loading:
					pass
					# don't see what's wrong with this. It just means cancelled out
					#mess("Panic, no stored voice with name"+self.edCombo.currentText())
			else:
				edv.edit()
				if not edv.isClean:
					self.sd()
				vn = edv.vdata["name"]
				if vn == "Untitled" or vn == '' or vn == None:
					# mess("looks like you cancelled out")
					#repair the voice object name
					edv.vdata["name"] = self.edCombo.currentText()
				else:
					pass
					# mess("edited "+edv.vdata["name"])
		i = self.edCombo.findText("<Select Voice To Edit>")
		self.edCombo.setCurrentIndex(i)

	def inPortChg(self,i):
		global inPortName

		if self.inPortCombo.currentText() == "none":
			self.inPortName = None
		else:
			inPortName = self.inPortCombo.currentText()
		self.setInport()

	def createNewVoice(self):
		# in the voice table create a new voice and return its index.
		# need to be vigilant about confusing the index of voices with
		# the index of the combobox
		self.activeV=voice()
		self.activeV.edit()
		vn = self.activeV.vdata["name"]
		if vn != "Untitled" and vn != '' and vn != None:
			voices.append(self.activeV)
			self.setGotVoices(True)
			self.setClean(False)
			return vn
		else:
			return None

	def transportStop(self):
		global performance
		global tickDuration
		global totalTicks
		global lastMsgTime

		#logit(3,"in transportStop")
		self.stopFlag = True # stops midi listener and camera
		if perfPlayable:
			self.p.stop() # stops midfile player
			if listenChannel != None:
				if lastMsgTime == None:
					print('No midi data recorded')
				else:
					print("according to tickCount, last midi message was at "+str(totalTicks * tickDuration / 1000000 ))
					print("according to rtc, it was at "+str(lastMsgTime-self.firstEventTime))

		mixer.stop()
		mixer.quit() # just stop doesn't work. quit leaves it in an unplayable state so:
		mixer.init()
		mixer.music.load(audioFile)
		self.btnStop.setEnabled(False)


		if listenChannel != None:
			print("putting out final event with raw time",end=" ")
			# this value is typically a note_off or a note_on V=0
			print(str(self.lastPerfMess))
			self.track.append(self.lastPerfMess)
			performance.save(amenicDir + "/secmid.apf")
			#logit(3,"calling makeChannelTimelines")
			makeChannelTimelines(performance)
			if mode == "export":
				self.setCanGenVid(True)

		self.startImg()

if __name__ == '__main__':
	loadSetup()
	app = QApplication(sys.argv)
	main = AmenicMain()
	main.show()
	sys.exit(app.exec_())
