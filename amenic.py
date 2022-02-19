import jsonpickle # pip install jsonpickle
import json
import time
import mido
from mido import MidiFile
from decimal import *
from functools import partial
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPixmap, QPainter, QPalette, QIcon, QColor, QStandardItemModel, QStandardItem
import sys
import vlc

orchPath = "./"
orchName = "Untitled"
oExtn = 'orc'
vExtn = 'vcf'
voices = []
presTable = []
CVMap = []
tWidth = 960
tHeight = 540
#fRate = 24
fRate = 5
ecount=0
emptyImg = None
board = None


# I mean yes, I could define a voicelist class, and then instantiate one instance of it and
# have it contain the list of voices and give it access methods. But really how would that help?

def getVoiceByName(vName):
	# mess(" there are "+str(len(voices))+" voices stored")
	for v in voices:
		if v.vdata["name"] == vName:
			return v
	return None

class theatreLabel(QLabel):
	def __init__(self, parent):
		super().__init__(parent=parent)
		self.setStyleSheet('QFrame {background-color:grey;}')
		self.resize(tWidth, tHeight)
		self.layers =[]

	def setLayers(self,l):
		self.layers = l

	def paintEvent(self, e):
		qp = QPainter(self)
		baseImg = emptyImg.copy(QRect())
		qp.drawPixmap(0,0,baseImg)

		for img in self.layers:
			if img != None:
				#print("[PaintEvent] using ok image")
				#qp.drawPixmap(QRect(),img)
				qp.drawPixmap(0,0,img)
			else:
				pass # this just means there's no rest image
				#print("[PaintEvent] trying to use null image")

class soundBoard():
	def __init__(self):
		self.board = dict()
		self.evLockQueue = []
		self.locked = False

	def addNoteOn(self,msg):
		t = time.ctime()
		if msg.channel not in self.board.keys():
			self.board[msg.channel] = {}
		#print("[Board] chan "+str(msg.channel)+" note "+str(msg.note)+ " time " + str(t) + " velocity "+ str(msg.velocity))
		#print("chan "+str(msg.channel)+" note "+str(msg.note)+ " time " + str(msg.time) + " velocity "+ str(msg.velocity)+chr(7))
		if msg.velocity ==0: # It's effectively an old skule note off
			self.board[msg.channel].pop(msg.note)
		else:  # it's a genuine note on
			self.board[msg.channel][msg.note] = [ t,msg.velocity]
		#print("[board chan 0 contents] "+str(self.board[msg.channel]))

	def addNoteOff(self,msg):
		#print("[AddNoteOff] removing board["+str(msg.channel)+"]["+str(msg.note)+"]")
		self.board[msg.channel].pop(msg.note)


	def noteOn(self,msg):
		if self.locked:
			self.evLockQueue.append(msg)
		else:
			self.addNoteOn(msg)

	def noteOff(self,msg):
		if self.locked:
			self.evLockQueue.append(msg)
		else:
			self.addNoteOff(msg)

	def stopAll(self):
		self.board = []

	def lockBoard(self):
		self.locked = True

	def unLockBoard(self):

		while len(self.evLockQueue) >0:
			msg = self.evLockQueue.pop(0)
			if msg.type == 'note_on':
				self.addNoteOn(msg)
			else:
				self.addNoteOff(msg)


	def currentNotes(self):
		if not self.locked:
			err("Call to currentNotes without board locked")
			quit()
		return self.board.copy()


class player():
	def __init__(self,file):
		self.myF = file
		self.stopIt = False
		self.pauseIt = False
		self.msgList = []
		for m in MidiFile(self.myF):
			self.msgList.append(m)

	def playNext(self,sendNow):
		global board
		self.stopIt = False
		if str(sendNow) != "None":
			# print("[player] "+str(sendNow))
			if sendNow.type == 'note_on':
				# print("[PlayNext a] sending note_on "+str(sendNow.note))
				board.noteOn(sendNow)
			elif sendNow.type == 'note_off':
				# print("[PlayNext a] sending note_off "+str(sendNow.note))
				board.noteOff(sendNow)

		if len(self.msgList) > 0:
			msg = self.msgList.pop(0)
			while msg.time == 0:
				if msg.type == 'note_on':
					board.noteOn(msg)
				elif msg.type == 'note_off':
					board.noteOff(msg)
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


class camera():

	def __init__(self, t):
		self.cmode = 'rehearsal'
		self.myTheatre = t
		self.cacheShow =''

	def render(self,ch,nv):
		global CVMap

		print("[Render]",end = " " )
		if len(nv) == 0:
			print("rest", end = " ")

		for n in nv.keys():
			t = nv[n][0]
			v = nv[n][1]
			# so we have channel in ch, note in n and velocity in v
			# and start time in t.
			# for now, we're going to assume the channel is 0 and
			# it will be mapped to the default voice. And we don't
			# care about velocity or time for now.
			# the only thing we need to do is to select the right
			# image for the note.
			ch = 0 # just in case it isn't
			voice = CVMap[ch]
			#print("note "+str(n), end = "|")

			image = None
			defI = None
			useI = None
			for i in voice.vdata["imgTable"]:
				if i[0] == n:
					#print("specific note map "+i[1])
					image = i[2]
				if i[0] == -1:
					defIFName = i[1]
					defI = i[2]
			if image == None:
				if defI != None:
					print("default note map"+defIFName)
					useI = defI
			else:
				useI = image
			if useI == None:
				err("useI was None. note was "+str(n))
				quit()
			return useI
		#print(" ")

	def merge(self,l):
		# bang the list of qpixmaps in l into one merged image
		self.myTheatre.setLayers(l)
		self.myTheatre.show()

	def exposure(self):
		global board
		global ecount
		# construct image from myBoard, then, depending on mode, show in myTheatre or
		# ?and? write to film.
		board.lockBoard()
		snap = board.currentNotes()
		board.unLockBoard()
		layers = []
		ecount += 1
		#print("E "+str(ecount))
		for ch in snap.keys():
			layers.append(self.render(ch,snap[ch]))
		self.merge(layers)


	def rollEm(self,mode):
		print("roll!")
		self.cmode = mode

	def cut(self):
		self.gate.stop()
		# maybe, if in film mode, ask if you want it stored
		# but we're not worrying about film mode just now anyway


class cvmModel(QAbstractTableModel):
	header_labels = ['Chan No.', 'Voice' ]

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

class voice():

	def __init__(self):
		self.vdata = {
			"imgTable": [ ],
			"name": 'Untitled'
		}

	def edit(self):
		ve = vEditD(self)
		ve.exec_()
		return

class CVMapEdit(QDialog):
	def __init__(self):
		super().__init__()
		self.setModal(True)
		self.initUI()

	def comboAdd(self,idx):
		selVoiceCombo = QComboBox()
		selVoiceCombo.clear()
		selVoiceCombo.addItem("<none>")
		selVoiceCombo.addItem("+Add New")
		# mess("in vcomboinit, attempting to load from voices which has "+str(len(voices))+" items")
		vc =0
		for v in voices:
			vc += 1
			selVoiceCombo.addItem(v.vdata["name"])
		if CVMap[idx][1] != None:
			i = selVoiceCombo.findText(CVMap[idx][1])
		else:
			i = selVoiceCombo.findText("<none>")
		selVoiceCombo.setCurrentIndex(i)
		self.cvm.setIndexWidget(self.model.index(idx, 1), selVoiceCombo)


	def initUI(self):
		self.setWindowTitle('Edit Channel/Voice mapping')
		self.resize(300,600)
		self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.Tool)

		self.cvm = QTableView()
		CVPresTable = []

		for row in range(0,16):
			CVPresTable.append([ row, None])
		self.model = cvmModel(CVPresTable)

		self.cvm.setModel(self.model)

		for idx in range(0, 16):
			self.comboAdd(idx)

		self.cvm.verticalHeader().hide()

		self.cvm.setColumnWidth(0,55)
		self.cvm.setColumnWidth(1,180)

		self.btnCancel = QPushButton('Cancel')
		self.btnCancel.clicked.connect(self.cancelOut)

		self.btnSave = QPushButton('Save')
		self.btnSave.clicked.connect(self.saveOut)

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
		global VCMap
		VCMap=[]
		for idx in range(0, 16):
			VCMap.append([idx,self.model._data[idx][1] ] )
		self.accept()
# !!! todo, the channel map isn't actually updating at save time

class vEditD(QDialog):
	def __init__(self, v:voice):
		super().__init__()
		self.setModal(True)
		self.initUI(v)
		# a reference to the passed-in voice. We need this so we can write to it
		# at save time and totally ignore it at cancel time
		self.myv = v

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
		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open file', '~/Documents',"Image files (*.png *.jpg *.jpeg)")
		self.model._data[idx][3] = fname
		self.resumeTimer()

	def getDefImg(self,idx):
		self.midiTimer.stop()
		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open Default Image', '~/Documents',"Image files (*.png *.jpg *.jpeg)")
		self.diEdit.setText(fname)
		self.resumeTimer()

	def imgt(self,v,n):
		# imgTable rows have 0= note 1 = filename 2= cached image
		for it in v.vdata["imgTable"]:
			if it[0] == n:
				return it[1]

	def getRestImg(self,idx):
		self.midiTimer.stop()
		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open Rest Image', '~/Documents',"Image files (*.png *.jpg *.jpeg)")
		self.restEdit.setText(fname)
		self.resumeTimer()

	def noteRowAdd(self,idx):
		# This only adds the button to a pre-existing row created by
		# the SetModel call. It doesn't actually add a row
		btnGetImg = QPushButton("Select image")
		btnGetImg.clicked.connect(partial(self.getImg, idx))
		self.noteMap.setIndexWidget(self.model.index(idx, 2), btnGetImg)

	def initUI(self, v:voice):
		self.setWindowTitle('Edit Voice')
		self.resize(800,600)
		self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.Tool)
		if v.vdata["name"] == "Untitled":
			self.nameAcquired = False
			self.new = True
		else:
			self.nameAcquired = True
			self.new = False

		self.inport = mido.open_input('Steinberg UR22mkII  Port1')
		self.midiTimer = QTimer(self)
		self.midiTimer.timeout.connect(self.checkMidi)
		self.midiTimer.start(50)

		# set up widgets
		self.nameLabel = QLabel('Name')
		self.nameEdit = QLineEdit(self)
		if not self.new:
			self.nameEdit.setEnabled(False)
			self.btnCname = QPushButton("Change")
			self.btnCname.clicked.connect(self.chName)

		self.nameEdit.setText(v.vdata["name"])
		self.nameEdit.textChanged.connect(self.maybeActiveSave)

		self.diLabel = QLabel("Default Image")
		self.diEdit = QLineEdit(self)
		self.diEdit.setText(self.imgt(v,-1))
		self.diEdit.setToolTip("Image shown when any key pressed unless overridded in note map table")
		self.diLookup = QPushButton('>')
		self.diLookup.clicked.connect(self.getDefImg)

		self.restLabel = QLabel("Rest Image")
		self.restEdit = QLineEdit(self)
		self.restEdit.setText(self.imgt(v,-2))
		self.restEdit.setToolTip("Image, in monophonic mode shown when no note playing")
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
				mess("loading into note map "+v.vdata["imgTable"][iti][1])
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

		self.btnCancel = QPushButton('Cancel')
		self.btnCancel.clicked.connect(self.cancelOut)

		self.btnSave = QPushButton('Save')
		self.btnSave.clicked.connect(self.saveOut)
		self.btnSave.setEnabled(self.nameAcquired)

		# Layout
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
		self.setLayout(vbox)

	def chName(self):
		mess("Here we offer to change the name of the voice")

	def cancelOut(self):
		self.midiTimer.stop()
		self.reject()
		return None

	def saveOut(self):
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
			self.model._data.append([-1,None,None,self.diEdit.text()])
		elif defImgIdx != None:
			self.model._data[defImgIdx] = [-1,None,None,self.diEdit.text()]

		if restImgIdx == None and self.restEdit.text() != None and self.restEdit.text() != '':
			# create new entry in imgTable for rest image
			self.model._data.append([-2,None,None,self.restEdit.text()])
		elif restImgIdx != None:
			self.model._data[restImgIdx] = [-2,None,None,self.restEdit.text()]

		self.myv.vdata["imgTable"] = []
		for idx in range(0, len(self.model._data)):
			if self.model._data[idx][3] != None and self.model._data[idx][3] != '':
				# mess("found "+ self.model._data[idx][3]+" in note map")

				image = QPixmap(self.model._data[idx][3])
				# put cached image into table
				self.myv.vdata["imgTable"].append([ self.model._data[idx][0], self.model._data[idx][3],image])
		self.accept()

	def maybeActiveSave(self):
		# two things wrong here.
		# 1 any dirtying action when the name isn't 'Untitled' should make save active
		# 2 Any change of the name should call into question whether this is a name change or
		#   a 'save as'
		# so the whole form would be numb until there was a valid name
		#    Once a valid name is acquired, the form should be active and the name numb
		#    when the name is numb, (and nothing is dirty?) there is an option to save a copy
		#    with a diifferent name or to rename the voice
		s = self.nameEdit.text
		if s != "Untitled" and s != "" and s != None :
			self.btnSave.setEnabled(True)
		else:
			self.btnSave.setEnabled(False)

#class AmenicMain(QDialog) :
class AmenicMain(QMainWindow):
	def __init__(self):
		super().__init__()
		icon = QIcon()
		icon.addPixmap(QPixmap("AmenicIcon.png"), QIcon.Selected, QIcon.On)
		self.setWindowIcon(icon)
		self.initUI()
		self.vtable = []
		self.loading = False
		self.lastMess = None

	def openOrch(self):
		# mess("Here we'd open an orchestra file")
		self.loading = True
		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open Orchestra File', orchPath,"Orchestra files (*.orc)")
		# mess("then load json from "+fname)
		fh = open(fname,'r')
		loadData = fh.read()
		fh.close()
		orch = json.loads(loadData)
		voices.clear() # DON'T do voices = [] as that declares a local voices!

		for vname in orch:
			v = voice()
			v.vdata = orch[vname].copy()
			# cache the images in the imgTable
			for nm in v.vdata["imgTable"]:
				image = QPixmap(nm[1])
				nm.append(image) # nm is a ref not a copy right?
			voices.append(v)

		self.vComboInit(self.droneCombo)
		self.edComboInit()
		self.loading = False

	def saveOrch(self):
		orch = dict()
		for v in voices:
			vname = v.vdata["name"]
			orch[vname] = v.vdata
			for nm in orch[vname]["imgTable"]:
				# strip the cached image file
				del nm[2]
		saveData = json.dumps(orch)
		n = orchPath + orchName + "."+oExtn
		( sFileName, filter ) = QFileDialog.getSaveFileName(self,"Save Orchestra File",n,"Orchestra (*.orc)")
		#mess("now save it as "+ sFileName)
		# need to check for collisions, but for now just overwrite
		fh = open(sFileName,"w")
		fh.write(saveData)
		fh.close()

	def exportVoice(self):
		mess("Here we'd export a single voice to a voice file")

	def importVoice(self):
		mess("Here we'd import a single voice from a voice file into the current orchestra")

	def vComboInit(self,combo):
		combo.clear()
		combo.addItem("<none>")
		combo.addItem("+Add New")
		# mess("in vcomboinit, attempting to load from voices which has "+str(len(voices))+" items")
		vc =0
		for v in voices:
			vc += 1
			# mess(v.vdata["name"])
			combo.addItem(v.vdata["name"])
		# mess("inserted "+str(vc)+" items")

	def playslot(self):
		nextMess = self.p.playNext(self.lastMess)
		if str(nextMess) != "None":
			self.lastMess = nextMess
			# convert from a float number of seconds to and integer number of milliseconds
			ms = int(nextMess.time * 1000)
			QTimer.singleShot(ms,self.playslot)

	def cameraSlot(self):
		global theatre
		self.c.exposure()
		theatre.show()
		theatre.repaint()

		QTimer.singleShot(self.gateTimerPeriod,self.cameraSlot)

	def test(self):
		global CVMap
		global theatre
		global board
		global fRate
		CVMap= [ getVoiceByName("Oink") ]

		# create camera
		board = soundBoard()
		self.gateTimerPeriod = int(1000 / fRate)

		self.c = camera(theatre)
		self.cameraSlot()

		# create player
		#self.p = player('/users/johnhollingum/Documents/sounds/Raw_midi/BIT.MID',board)
		self.p = player('/users/johnhollingum/Documents/AMENIC/test.mid')
		# start the camera
		# c.rollEm('rehearse')
		self.playslot()


	def channelMap(self):
		cvm = CVMapEdit()
		cvm.exec_()


	def edComboInit(self):
		self.edCombo.clear()
		self.edCombo.addItem("<Select Voice To Edit>")
		i = self.edCombo.findText("<Select Voice To Edit>")
		self.edCombo.setCurrentIndex(i)
		for v in voices:
			self.edCombo.addItem(v.vdata["name"])


	def initUI(self):
		global emptyImg
		global theatre

		self.setWindowTitle('Amenic')
		self.resize(1020,600)
		# don't think I'm getting a lot of benefit from the buddying
		# but look at https://doc.qt.io/archives/qt-4.8/designer-buddy-mode.html and
		# https://doc.qt.io/qtcreator/creator-keyboard-shortcuts.html

		for row in range(0,16):
			CVMap.append([ row, None])

		openOAct = QAction(QIcon(), 'Open Orchestra', self)
		openOAct.setShortcut('Ctrl+O')
		openOAct.setStatusTip('Open Orchestra')
		openOAct.triggered.connect(self.openOrch)

		saveOAct = QAction(QIcon(), 'Save Orchestra', self)
		saveOAct.setShortcut('Ctrl+S')
		saveOAct.setStatusTip('Save Orchestra')
		saveOAct.triggered.connect(self.saveOrch)

		expVAct = QAction(QIcon(), 'Export Voice', self)
		expVAct.setShortcut('Ctrl+E')
		expVAct.setStatusTip('Export Voice')
		expVAct.triggered.connect(self.exportVoice)

		impVAct = QAction(QIcon(), 'Import Voice', self)
		impVAct.setShortcut('Ctrl+I')
		impVAct.setStatusTip('Import Voice')
		impVAct.triggered.connect(self.importVoice)

		menubar = self.menuBar()
		fileMenu = menubar.addMenu('&File')
		fileMenu.addAction(openOAct)
		fileMenu.addAction(saveOAct)
		fileMenu.addAction(expVAct)
		fileMenu.addAction(impVAct)

		self.cMapBtn = QPushButton("Channel Map")
		self.cMapBtn.clicked.connect(self.channelMap)

		droneLabel = QLabel('&Drone Voice',self)
		self.droneCombo = QComboBox(self)
		self.vComboInit(self.droneCombo)
		self.droneCombo.currentIndexChanged.connect(self.drSelChg)

		droneLabel.setBuddy(self.droneCombo)

		edLabel = QLabel('&Edit Voice',self)
		self.edCombo = QComboBox(self)
		self.edComboInit()
		self.edCombo.currentIndexChanged.connect(self.edSelChg)

		self.testButton = QPushButton('Test')
		self.testButton.clicked.connect(self.test)

		ssLabel = QLabel('&Sound Source',self)
		self.ssFileShow= QLineEdit(self)
		self.ssFileShow.readOnly = True
		ssButton = QPushButton('>')
		ssButton.clicked.connect(self.getSound)
		ssLabel.setBuddy(ssButton)

		emptyImg = QPixmap("/Users/johnhollingum/Documents/AMENIC/Empty.png").scaled(tWidth,tHeight,2,1)
		theatre = theatreLabel(self)
		theatre.setPixmap(emptyImg)

		self.btnPlay = QPushButton('&Play')
		self.btnPlay.clicked.connect(self.playsound)
		self.btnPlay.setEnabled(False)

		self.btnStop = QPushButton('&Stop')
		self.btnStop.clicked.connect(self.stopsound)
		self.btnStop.setEnabled(False)

		vbox1 = QVBoxLayout()
		hbox1 = QHBoxLayout()
		hbox1.addWidget(self.cMapBtn)

		hbox1.addWidget(droneLabel)
		hbox1.addWidget(self.droneCombo)

		hbox1.addWidget(edLabel)
		hbox1.addWidget(self.edCombo)

		vbox1.addLayout(hbox1)

		vbox1.addWidget(self.testButton)

		hbox2 = QHBoxLayout()
		hbox2.addWidget(ssLabel)
		hbox2.addWidget(self.ssFileShow)
		hbox2.addWidget(ssButton)

		vbox1.addLayout(hbox2)
		vbox1.addWidget(theatre)

		hbox3 = QHBoxLayout()
		hbox3.addWidget(self.btnPlay)
		hbox3.addWidget(self.btnStop)

		vbox1.addLayout(hbox3)

		container = QWidget()
		container.setLayout(vbox1)

		# Set the central widget of the Window.
		self.setCentralWidget(container)

	#def dvSelChg(self,i):
	#	# this routine responds to an event that it, itself raises
	#	if self.dvCombo.currentText() == "+Add New":
	#		self.playerVn = self.createNewVoice()
	#		if self.playerVn == None :
	#			i = self.dvCombo.findText("<none>")
	#			self.dvCombo.setCurrentIndex(i)
	#		else:
	#			self.droneCombo.addItem(self.playerVn)
	#			self.dvCombo.addItem(self.playerVn)
	#			self.edCombo.addItem(self.playerVn)
	#			i = self.dvCombo.findText(self.playerVn)
	#			self.dvCombo.setCurrentIndex(i)
	#		return
	#	elif self.dvCombo.currentText() != "<none>":
	#		pass
	#		# mess("use "+self.dvCombo.currentText())
	#	else:
	#		self.playerVn = None

	def drSelChg(self,i):
		if self.droneCombo.currentText() == "+Add New":
			self.droneVn = self.createNewVoice()
			if self.droneVn == None :
				i = self.droneCombo.findText("<none>")
				self.droneCombo.setCurrentIndex(i)
			else:
				self.droneCombo.addItem(self.droneVn)
				#self.dvCombo.addItem(self.droneVn)
				self.edCombo.addItem(self.playerVn)
				i = self.droneCombo.findText(self.droneVn)
				self.droneCombo.setCurrentIndex(i)
				# find droneV from droneVn

	def edSelChg(self,i):
		if self.edCombo.currentText() != "<Select Voice To Edit>":
			# mess("edit "+self.edCombo.currentText())
			edv = getVoiceByName(self.edCombo.currentText())
			if edv == None:
				if not self.loading:
					mess("Panic, no stored voice with name"+self.edCombo.currentText())
			else:
				edv.edit()
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

	def createNewVoice(self):
		# in the voice table create a new voice and return its index.
		# need to be vigilant about confusing the index of voices with
		# the index of the combobox
		self.activeV=voice()
		self.activeV.edit()
		vn = self.activeV.vdata["name"]
		if vn != "Untitled" and vn != '' and vn != None:
			voices.append(self.activeV)
			return vn
		else:
			return None

	def getSound(self):
		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open file', '~/Documents',"Sound files (*.mp3)")
		self.ssFileShow.setText(fname)
		self.st = vlc.MediaPlayer("File://"+fname)
		self.btnPlay.setEnabled(True)

	def playsound(self):
		self.st.play()
		self.btnStop.setEnabled(True)

	def stopsound(self):
		self.st.stop()
		self.btnStop.setEnabled(False)

def to_name(nn):
	nnt = [ "C  ","C#","D  ","D#","E  ","F  ","F#","G  ","G#","A  ", "A#","B  "]
	on = int(nn / 12) -1 # opinion seems to differ about whether it's necessary to subtract 1
	nis = nn % 12
	nname = nnt[nis]
	return nname + " " + str(on)

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

if __name__ == '__main__':
	app = QApplication(sys.argv)
	main = AmenicMain()
	main.show()
	sys.exit(app.exec_())
