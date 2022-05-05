# rallax creates variable tempo track from taps
import time
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from decimal import *
from functools import partial
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPixmap, QPainter, QPen, QPalette, QIcon, QColor, QStandardItemModel, QStandardItem, QGuiApplication
import sys
from pygame import mixer
import os, subprocess
import shutil
from mutagen.mp3 import MP3
import re

mainWindowX = 800
mainWindowY = 200
audioFile = None
inPortName = None
# load audio
# record tempo track against audio playback
# test by playing back with generated metronome using tempo track
# save tempo track

def mess(mymess):
	msg = QMessageBox()
	msg.setIcon(QMessageBox.Information)
	msg.setText(mymess)
	msg.setStandardButtons(QMessageBox.Ok)
	retval = msg.exec_()

class RallaxMain(QMainWindow):
	def __init__(self):
		super().__init__()
		self.initUI()

	def genMidi(self):
		# use taps list to generate a tempo track and a tick track
		tpb = 120
		self.mfile = MidiFile(ticks_per_beat = tpb)
		# need to stuff in a tempo Message
		# make a pure tempo track. This is fairly normally the first track in a type 1 midi file
		tt = MidiTrack()
		tt.name = 'Tempo Track'
		self.mfile.tracks.append(tt)
		t1 = MidiTrack()
		t1.name = 'Metronome'
		self.mfile.tracks.append(t1)
		lastBeatTime = 0
		tempoEventAt = 0
		noteOnEventAt = tpb
		for tap in self.taps:
			# ok, get your head into reverse. Every tap is one beat after the last or the start
			# you need to adjust the tempo so that a click placed at beat beatNumber will be at the right time
			sinceLast = tap - lastBeatTime
			lastBeatTime = tap
			print("sincelast = "+str(sinceLast))
			#hamo
			# tempo is microseconds per quarter note. We are treating each tap as a quarter note, so the
			# time in set tempo will be sinceLast * 1000000
			msg = MetaMessage('set_tempo', tempo = int(sinceLast * 1000000), time = tempoEventAt )
			tt.append(msg)
			tempoEventAt = int(tpb / 2)  # half a beat after the note off
			# no click on first beat, only where the taps 'heard'
			msg = Message('note_on',note=55,velocity=80, time = noteOnEventAt )
			t1.append(msg)
			msg = Message('note_off',note=55,time = int(tpb / 2))
			t1.append(msg)
			noteOnEventAt = int(tpb / 2)
			tempoEventAt = tpb

		self.saveTTAct.setEnabled(True)


	def transportStop(self):
		global audioFile

		self.midiTimer.stop()
		mixer.stop()
		mixer.quit() # just stop doesn't work. quit leaves it in an unplayable state so:
		mixer.init()
		mixer.music.load(audioFile)
		self.btnStop.setEnabled(False)
		self.genMidi()
		self.playBackBtn.setEnabled(True)

	def playBack(self):
		pass

	def setRecordable(self,recordable):
		self.recordBtn.setEnabled(recordable)

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
				# ignore note-on zeros
				if msg.velocity != 0:
					e = time.time() - self.start
					self.taps.append(e)
		self.resumeTimer()

	def setInport(self):
		global inPortName

		if inPortName == None:
			self.inport = None
		else:
			self.inport = mido.open_input(inPortName)
			print("done mido.open_input on "+str(inPortName))

	def inPortChg(self,i):
		global inPortName

		if self.inPortCombo.currentText() == "none":
			self.inPortName = None
		else:
			inPortName = self.inPortCombo.currentText()
		self.setInport()

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

	def importAudio(self):
		global audioFile

		( audioFile, filter)  = QFileDialog.getOpenFileName(self, 'Open file', "./","Sound files (*.mp3)")
		if audioFile != '':
			self.setAudio()

	def setAudio(self):
		global audioFile
		global audioDuration

		if audioFile != '':
			self.audioPath = audioFile
			self.audioPath = re.sub('\.[^\.]*$','',self.audioPath)
			self.ssFileShow.setText(audioFile)
			self.setRecordable(True)
			# may as well initialise the audio player here
			audio = MP3(audioFile)
			audioDuration = audio.info.length
			self.adShow.setText(f'{audioDuration:.2f}')
			mixer.init()
			mixer.music.load(audioFile)
		else:
			self.setRecordable(False)

	def record(self):
		mixer.music.play()
		self.start = time.time()
		self.taps= []
		self.btnStop.setEnabled(True)
		self.midiTimer = QTimer(self)
		self.midiTimer.timeout.connect(self.checkMidi)
		self.midiTimer.start(50)

	def saveTT(self):
		# Later we'll remove the click track
		n = self.audioPath + ".mid"
		( mfname, filter ) = QFileDialog.getSaveFileName(self,"Save midi tempo file",n,"MIDI files (*.mid)")
		if mfname == '':
			return
		self.mfile.save(mfname)

	def initUI(self):
		self.setWindowTitle('Rallax')
		self.resize(mainWindowX,mainWindowY)

		self.saveTTAct = QAction(QIcon(), 'Save Tempo Track', self)
		self.saveTTAct.setShortcut('Ctrl+S')
		self.saveTTAct.setStatusTip('Save Tempo Track')
		self.saveTTAct.triggered.connect(self.saveTT)
		self.saveTTAct.setEnabled(False)

		impAAct = QAction(QIcon(), 'Import Audio', self)
		impAAct.setShortcut('Ctrl+A')
		impAAct.setStatusTip('Import Audio')
		impAAct.triggered.connect(self.importAudio)

		menubar = self.menuBar()
		fileMenu = menubar.addMenu('&File')

		fileMenu.addAction(self.saveTTAct)
		fileMenu.addAction(impAAct)

		self.inPortCombo = QComboBox()
		self.inPortInit()
		self.inPortCombo.activated.connect(self.inPortChg)

		ssLabel = QLabel('Sound Source',self)
		self.ssFileShow= QLineEdit(self)
		self.ssFileShow.readOnly = True
		adLabel = QLabel('Audio Duration seconds')
		self.adShow = QLineEdit(self)
		self.adShow.setMaximumWidth(80)
		self.adShow.readOnly = True

		self.recordBtn = QPushButton("record")
		self.recordBtn.clicked.connect(self.record)
		self.recordBtn.setEnabled(False)

		self.playBackBtn = QPushButton('Playback/test')
		self.playBackBtn.clicked.connect(self.playBack)
		self.playBackBtn.setEnabled(False)

		self.btnStop = QPushButton('&Stop')
		self.btnStop.clicked.connect(self.transportStop)
		self.btnStop.setEnabled(False)

		vbox1 = QVBoxLayout()

		hbox2 = QHBoxLayout()
		hbox2.addWidget(ssLabel)
		hbox2.addWidget(self.ssFileShow)
		hbox2.addWidget(adLabel)
		hbox2.addWidget(self.adShow)

		hbox25 = QHBoxLayout()
		hbox25.addWidget(self.inPortCombo)

		hbox3 = QHBoxLayout()
		hbox3.addWidget(self.recordBtn)
		hbox3.addWidget(self.btnStop)

		vbox1.addLayout(hbox2)
		vbox1.addLayout(hbox25)
		vbox1.addLayout(hbox3)

		container = QWidget()
		container.setLayout(vbox1)

		# Set the central widget of the Window.
		self.setCentralWidget(container)

if __name__ == '__main__':

	app = QApplication(sys.argv)
	main = RallaxMain()
	main.show()
	sys.exit(app.exec_())
