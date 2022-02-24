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
projPath = "./"
projName = "Untitled"
pExtn = 'apr'
voices = []
presTable = []
CVMap = []
tWidth = 960
tHeight = 540
#fRate = 24
fRate = 12
ecount=0
emptyImg = None
board = None
midiFile = None
audioFile = None
listenChannel = None
maxRange = 511
rangeFrom7bit = int((maxRange +1) / 128)
PTList = [ "fixed", "nflat", "vflat","sweep", "fade", "fall", "wobble"]

def getVoiceByName(vName):
	# mess(" there are "+str(len(voices))+" voices stored")
	# print("in getvoicebyname, seeking "+vName)
	for v in voices:
		if v.vdata['name'] == vName:
			return v
	return None

class ipath():
	def __init__(self,forUse,min,max,pt,ts,fv):
		self.data = {
			"ptype": None,
			"timestep": None,
			"fixedval": None,
			'usedfor': forUse,
			'lower': min,
			'upper': max
		}
		if not pt in PTList:
			error("ipath supplied with bad ptype "+pt)
			quit()
		if ts == None:
			error("ipath not given valid timestep")
			quit()
		if pt == "fixed" and fv == None:
			error("ipath. must supply a fixedval for ptype fixed")
		self.data["ptype"] = pt
		self.data["timestep"] = ts
		self.data["fixedval"] = fv

	def getVal(self,onTime,note,velocity):
		global maxRange
		global rangeFrom7bit

		if pType == "fixed":
			return self.data["fixedval"]

		if pType == "nflat":
			return int(note * rangeFrom7bit)

		if pType == "vflat":
			return int(velocity * rangeFrom7bit )

		e = time.ctime() - onTime
		nTimeSteps = e / timeStep
		# depending on the duration of note and the timeStep value, it may
		# go beyond maxRange before the note off
		if pType == "sweep":
			x = int(nTimeSteps) # can't really see a fudge factor is needed here. It's just a question of adjusting timeStep
			return x

		# like sweep, but initial value comes from velocity and falls
		if pType == "fade":
			return velocity * rangeFrom7bit - int(nTimeSteps)

		# like fade, but based on note rather than velocity
		if pType == "fall":
			return note * rangeFrom7bit - int(nTimeSteps)

		if pType == "wobble":
			a = (nTimeSteps * 0.1) % math.pi
			return int((sin(a) + 1) * velocity)


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
				if img == None:
					print("Image is none")
				else:
					# we need layer to contain values for position, scale and
					# opacity. That'll do for starters
					qp.drawPixmap(0,0,img)
			else:
				pass # this just means there's no rest image
				#print("[PaintEvent] trying to use null image")

class soundBoard():
	# registers all currently-playing notes whether from midi file or
	# live performance
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
	#pushes midi events out from a file onto the soundboard
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
		self.imgCache = dict()

	def imgFor(self,ch,n):
		if len(self.imgCache) == 0:

			for cv in CVMap:
				if cv[1] != "<none>": # if the mapping isn't blank
					mapIndex =15 - cv[0] # because it's backwards
					vname = cv[1]
					voice = getVoiceByName(vname)
					if voice == None:
						mess("lookup for voice '"+vname+"' produced no result")
						quit()
					self.imgCache[mapIndex] = dict()
					for i in voice.vdata["imgTable"]:
						print("mi = "+str(mapIndex)+" note = "+ str(i[0]))
						self.imgCache[mapIndex][i[0]]= i[2] # cache[ch][note]= image

		image = None
		#print(self.imgCache.keys())
		if n in self.imgCache[ch]: # if there's a direct map use it (Includes Rest)
			image = self.imgCache[ch][n]
		elif n > -1: # it's not a rest and there's no direct map
			if -1 in self.imgCache[ch]: # if the default exists
				image = self.imgCache[ch][-1]

		return image

	def render(self,ch,nv):
		global CVMap
		global emptyImg

		if len(nv) == 0:
			#print("rest", end = " ")
			img = self.imgFor(ch,-2)

		for n in nv.keys():
			t = nv[n][0]
			v = nv[n][1]
			# so we have channel in ch, note in n and velocity in v
			# and start time in t.
			img = self.imgFor(ch,n)
			if img == None:
				img = emptyImg
		return img

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
	header_labels = ['Layer', 'Voice', "Listen" ]

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
			"name": 'Untitled',
			"xpos": None ,
			"ypos": None,
			"xscale": None,
			"yscale": None,
			"opacity": None
		}
		self.vdata["xpos"] = ipath("xpos",0,tWidth,"fixed",0,0)
		self.vdata["ypos"] = ipath("ypos",0,tHeight,"fixed",0,0)
		self.vdata["xscale"] = ipath("yscale",-10,+10,"fixed",0,0)
		self.vdata["yscale"] = ipath("xscale",-10,+10,"fixed",0,0)
		self.vdata["opacity"] = ipath("opacity",0,100,"fixed",0,0)

	def edit(self):
		ve = vEditD(self)
		ve.exec_()
		return

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
		self.myPath.data['timestep'] = 0
		self.myPath.data['fixedval'] = 0
		self.myPath.data['ptype'] = self.currentText()
		pe = pathEdit(self.myPath)
		pe.exec_()

class PEButton(QPushButton):
	def __init__(self,path):
		super().__init__()
		self.setText("Edit")
		self.clicked.connect(self.eptype)

		self.myPath = path

	def eptype(self,idx):
		pe = pathEdit(self.myPath)
		pe.exec_()

class vSlide(QSlider):
	def __init__(self,min,max,linkedLabel,current,parent):
		super().__init__(Qt.Horizontal,parent)
		self.setMinimum(min)
		self.setMaximum(max)
		self.setValue(current)
		self.setGeometry(30, 40, 200, 30)
		self.myLinkedLabel = linkedLabel
		self.valueChanged[int].connect(self.updLabel)

	def updLabel(self):
		self.myLinkedLabel.setText(str(self.value()))

	def getVal(self):
		return self.value()


class pathEdit(QDialog):
	def __init__(self,path):
		super().__init__()
		self.setModal(True)
		self.myPath = path
		self.initUI()

	def saveOut(self):
		if self.timeBased:
			self.timeStep = self.timeSlide.getVal()
			self.myPath.data['timestep'] = self.timeStep
		else:
			self.myPath.data['timestep'] = 0

		self.fixedVal = self.fixSlide.getVal()
		self.myPath.data['fixedval'] = self.fixedVal
		self.accept()

	def cancelOut(self):
		self.reject()

	def syncToX(self,idx):
		global xScalePath

		mess("by some miracle we sync these values to the X values")
		self.myPath.data = xScalePath.data.copy()
		self.myPath.data['usedfor'] = 'yscale'
		self.accept()

	def initUI(self):
		self.setWindowTitle('Edit Attribute Path')
		self.resize(350,200)
		self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.Tool)

		# how we caption these and whether we show them at all will depend on ptype
		forUse = self.myPath.data['usedfor']

		pType = self.myPath.data['ptype']
		self.forLabel = QLabel("Parameters for "+forUse+" Path Type "+pType)

		self.timeBased = pType in [ "sweep", "fade", "fall", "wobble"]
		if self.timeBased:
			self.tLabel = QLabel("Time Period")
			self.timeVLabel = QLabel()
			self.timeStep = self.myPath.data["timestep"]
			self.timeVLabel.setText(str(self.timeStep))
			self.timeSlide = vSlide(0,100,self.timeVLabel,self.timeStep,self)

		if forUse == "yscale":
			self.syncXbtn = QPushButton("Sync to Xscale")
			self.syncXbtn.clicked.connect(self.syncToX)

		self.fixedVal = self.myPath.data["fixedval"]
		self.fixLabel = QLabel("Fixed Param")
		self.fixVLabel = QLabel()
		self.fixVLabel.setText(str(self.fixedVal))
		self.fixSlide = vSlide(self.myPath.data['lower'],self.myPath.data['upper'],self.fixVLabel,self.fixedVal,self)

		self.btnSave = QPushButton()
		self.btnSave.setText("Save")
		self.btnSave.clicked.connect(self.saveOut)

		self.btnCancel = QPushButton()
		self.btnCancel.setText("Cancel")
		self.btnCancel.clicked.connect(self.cancelOut)

		vbox = QVBoxLayout()

		vbox.addWidget(self.forLabel)

		if forUse == "yscale":
			vbox.addWidget(self.syncXbtn)

		if self.timeBased:
			thbox = QHBoxLayout()
			thbox.addWidget(self.tLabel)
			thbox.addWidget(self.timeSlide)
			thbox.addWidget(self.timeVLabel)
			vbox.addLayout(thbox)

		phbox = QHBoxLayout()
		phbox.addWidget(self.fixLabel)
		phbox.addWidget(self.fixSlide)
		phbox.addWidget(self.fixVLabel)
		vbox.addLayout(phbox)

		bhbox = QHBoxLayout()
		bhbox.addWidget(self.btnCancel)
		bhbox.addWidget(self.btnSave)

		vbox.addLayout(bhbox)

		self.setLayout(vbox)

class CVMapEdit(QDialog):
	def __init__(self):
		super().__init__()
		self.setModal(True)
		self.initUI()
		self.newCVMap = []

	def checkNew(self,idx):
		global voices
		global CVMap

		w = self.cvm.indexWidget(self.model.index(idx,1))
		if w.currentText() == "+Add New":
			v = voice()
			v.edit()
			if v != None:
				if v.vdata["name"] == "Untitled":
					v= None
			if v != None:
				voices.append(v)
				w.addItem(v.vdata["name"]) # no doubt causes a kinda recursive call here
				i = w.findText(v.vdata["name"])
				w.setCurrentIndex(i)

			else:
				i = w.findText("<none>")
				w.setCurrentIndex(i)

	def toggleChecked(self,idx):
		global listenChannel

		w = self.cvm.indexWidget(self.model.index(idx, 2))
		if w.checkState():
			#mess("state changed, now checked")

			# ensure it has a mapping
			cbw = self.cvm.indexWidget(self.model.index(idx,1))
			vname = cbw.currentText()
			if vname == "<none>":
				#mess("Can't listen on channel with no voice assigned")
				w.setChecked(False)
			else:
				# ensure no others are checked
				#mess("Unchecking all others")
				for i in range(0,15):
					if i != idx:
						w = self.cvm.indexWidget(self.model.index(i, 2))
						w.setChecked(False)
					else:
						listenChannel = self.model._data[i][0]
		else:
			#mess("state changed, now unchecked")
			listenChannel = None

	def comboAdd(self,idx):
		selVoiceCombo = QComboBox()
		selVoiceCombo.clear()
		selVoiceCombo.addItem("<none>")
		selVoiceCombo.addItem("+Add New")
		vc =0
		for v in voices:
			vc += 1
			selVoiceCombo.addItem(v.vdata["name"])
		if CVMap[idx][1] != None:
			i = selVoiceCombo.findText(CVMap[idx][1])
		else:
			i = selVoiceCombo.findText("<none>")
		selVoiceCombo.setCurrentIndex(i)
		selVoiceCombo.currentTextChanged.connect(partial(self.checkNew,idx))
		self.cvm.setIndexWidget(self.model.index(idx, 1), selVoiceCombo)

		listening = QCheckBox()
		listening.setTristate(False)
		listening.setChecked(False)
		self.cvm.setIndexWidget(self.model.index(idx,2),listening)
		listening.stateChanged.connect(partial(self.toggleChecked,idx))

	def initUI(self):
		self.setWindowTitle('Edit Channel/Voice mapping')
		self.resize(350,600)
		self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.Tool)

		self.cvm = QTableView()
		CVPresTable = []

		for row in range(15,-1,-1):
			CVPresTable.append([ row, None, ""])
		self.model = cvmModel(CVPresTable)

		self.cvm.setModel(self.model)

		for idx in range(0, 16):
			self.comboAdd(idx)

		self.cvm.verticalHeader().hide()

		self.cvm.setColumnWidth(0,55)
		self.cvm.setColumnWidth(1,180)
		self.cvm.setColumnWidth(2,50)

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
		global CVMap
		CVMap.clear()
		for idx in range(0, 16):
			w = self.cvm.indexWidget(self.model.index(idx, 1))
			CVMap.append([idx,w.currentText() ] )
		self.accept()

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
		global xScalePath

		self.setWindowTitle('Edit Voice')
		self.resize(800,600)
		self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.Tool)

		xScalePath = v.vdata['xscale']

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

		self.btnCancel = QPushButton('Cancel')
		self.btnCancel.clicked.connect(self.cancelOut)

		self.btnSave = QPushButton('Save')
		self.btnSave.clicked.connect(self.saveOut)
		self.btnSave.setEnabled(self.nameAcquired)

		self.xpP = v.vdata["xpos"]
		self.xposLabel = QLabel("xpos")
		self.xpPCombo = PCombo(self.xpP)
		self.xpE = PEButton(self.xpP)

		self.ypP = v.vdata["ypos"]
		self.yposLabel = QLabel("ypos")
		self.ypPCombo = PCombo(self.ypP)
		self.ypE = PEButton(self.ypP)

		self.xsP = v.vdata["xscale"]
		self.xscaleLabel = QLabel("xscale")
		self.xsPCombo = PCombo(self.xsP)
		self.xsE = PEButton(self.xsP)

		self.ysP = v.vdata["yscale"]
		self.yscaleLabel = QLabel("yscale")
		self.ysPCombo = PCombo(self.ysP)
		self.ysE = PEButton(self.ysP)

		self.opP = v.vdata["opacity"]
		self.opacityLabel = QLabel("opacity")
		self.opPCombo = PCombo(self.opP)
		self.opE =PEButton(self.opP)

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

		hboxXScale = QHBoxLayout()
		hboxXScale.addWidget(self.xscaleLabel)
		hboxXScale.addWidget(self.xsPCombo)
		hboxXScale.addWidget(self.xsE)
		vbox2.addLayout(hboxXScale)

		hboxYScale = QHBoxLayout()
		hboxYScale.addWidget(self.yscaleLabel)
		hboxYScale.addWidget(self.ysPCombo)
		hboxYScale.addWidget(self.ysE)
		vbox2.addLayout(hboxYScale)

		hboxOpacity = QHBoxLayout()
		hboxOpacity.addWidget(self.opacityLabel)
		hboxOpacity.addWidget(self.opPCombo)
		hboxOpacity.addWidget(self.opE)
		vbox2.addLayout(hboxOpacity)

		hboxouter.addLayout(vbox)
		hboxouter.addLayout(vbox2)

		self.setLayout(hboxouter)

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

	def addPath(self,forUse,min,max,pathAttr):
		p = ipath(forUse,min,max,pathAttr['ptype'],pathAttr['timestep'],pathAttr['fixedval'])
		return p

	def openProj(self):
		global audioFile
		global midiFile

		self.loading = True
		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open Project File', projPath,"Amenic Project files (*.apr)")
		fh = open(fname,'r')
		loadData = fh.read()
		fh.close()
		proj = json.loads(loadData)
		voices.clear() # DON'T do voices = [] as that declares a local voices!
		CVMap.clear()

		for vname in proj["voices"]:
			# print("Loading voice "+vname)
			v = voice()
			v.vdata['name'] = vname
			v.vdata['imgTable'] = proj["voices"][vname]['imgTable']
			# cache the images in the imgTable
			for nm in v.vdata["imgTable"]:
				image = QPixmap(nm[1])
				nm.append(image) # nm is a ref not a copy right?
			voices.append(v)
			v.vdata['xpos'] = self.addPath("xpos",0,tWidth,proj['voices'][vname]['xpos'])
			v.vdata['ypos'] = self.addPath("ypos",0,tHeight,proj['voices'][vname]['ypos'])
			v.vdata['xscale'] = self.addPath("xscale",-10,10,proj['voices'][vname]['xscale'])
			v.vdata['yscale'] = self.addPath("yscale",-10,10,proj['voices'][vname]['yscale'])
			v.vdata['opacity'] = self.addPath("opacity",0,100,proj['voices'][vname]['opacity'])

		for map in proj["cvmap"]:
			CVMap.append(map)

		midiFile = proj["midifile"]
		self.setMidi()

		audioFile = proj["audiofile"]
		self.setAudio()

		self.edComboInit()
		self.loading = False

	def saveProj(self):
		proj = dict()
		proj["voices"]= dict()
		for v in voices:
			vname = v.vdata["name"]
			proj['voices'][vname]= dict()
			proj["voices"][vname]['imgTable'] = v.vdata['imgTable']
			for nm in proj["voices"][vname]["imgTable"]:
				# strip the cached image file
				del nm[2]
			proj['voices'][vname]['xpos'] = v.vdata['xpos'].data
			proj['voices'][vname]['ypos'] = v.vdata['ypos'].data
			proj['voices'][vname]['xscale'] = v.vdata['xscale'].data
			proj['voices'][vname]['yscale'] = v.vdata['yscale'].data
			proj['voices'][vname]['opacity'] = v.vdata['opacity'].data

		proj["cvmap"] = []
		for map in CVMap:
			proj["cvmap"].append(map)

		proj["midifile"] = midiFile
		proj["audiofile"] = audioFile


		saveData = json.dumps(proj)
		n = projPath + projName + "."+pExtn
		( sFileName, filter ) = QFileDialog.getSaveFileName(self,"Save Project File",n,"Amenic Project (*.apr)")
		fh = open(sFileName,"w")
		fh.write(saveData)
		fh.close()

	def exportVoice(self):
		mess("Here we'd export a single voice to a voice file")

	def importVoice(self):
		mess("Here we'd import a single voice from a voice file into the current project")

	def setAudio(self):
		global audioFile

		if audioFile != None:
			self.ssFileShow.setText(audioFile)
			self.btnPlay.setEnabled(True)
			# may as well initialise the audio player here
			self.st = vlc.MediaPlayer("File://"+audioFile)
		elif midiFile == None:
				self.btnPlay.setEnabled(False)

	def importAudio(self):
		global audioFile

		( audioFile, filter)  = QFileDialog.getOpenFileName(self, 'Open file', '~/Documents',"Sound files (*.mp3)")
		self.setAudio()

	def setMidi(self):
		global midiFile
		if midiFile != None :
			self.btnPlay.setEnabled(True)
			self.mpFileShow.setText(midiFile)
		elif audioFile == None:
			self.btnPlay.setEnabled(False)

	def importMidi(self):
		global midiFile
		(midiFile, filter) = QFileDialog.getOpenFileName(self,'Open Performance File','./',"Midi files (*.mid *.MID)")
		self.setMidi()

	def playslot(self):
		# this pushes out the events in the midiFile in (roughly) the right timing
		# and maintains the soundBoard with all currently playing notes
		nextMess = self.p.playNext(self.lastMess)
		if str(nextMess) != "None":
			self.lastMess = nextMess
			# convert from a float number of seconds to and integer number of milliseconds
			ms = int(nextMess.time * 1000)
			QTimer.singleShot(ms,self.playslot)

	def cameraSlot(self):
		# the camera takes snaps of the soundboard and renders them
		global theatre
		self.c.exposure()
		theatre.show()
		theatre.repaint()

		QTimer.singleShot(self.gateTimerPeriod,self.cameraSlot)

	def startPerfTimer(self):
		# flush out any midi events that may have come in while we were dealing with the event
		for msg in self.inport.iter_pending():
				pass
		self.livePerfTimer.start(30)

	def checkPerfSlot(self):
		global board
		global listenChannel

		self.livePerfTimer.stop()
		msg = self.inport.poll()
		# because of some bug, mido's msg object doesn't support direct comparison with
		# None, even though poll() is documented as either returning a message or a None
		# so stringify it:
		while str(msg) != "None":
			msg.channel = listenChannel # most likely it's coming in on chan 0
			if msg.type == 'note_on':
				board.noteOn(msg)
			elif msg.type == "note_off":
				board.noteOff(msg)
			msg = self.inport.poll()
		self.startPerfTimer()

	def play(self):
		global CVMap
		global theatre
		global board
		global fRate
		global midiFile

		# this shouldn't happen, but:
		if midiFile == None and audioFile == None:
			err("Nothing to play")
			return

		if listenChannel != None:
			self.inport = mido.open_input('Steinberg UR22mkII  Port1')
			self.livePerfTimer = QTimer()
			self.livePerfTimer.timeout.connect(self.checkPerfSlot)
			self.startPerfTimer()

		# I'm rather suspecting that st player will be blocking. We'll see
		if audioFile != None:
			self.st.play()
			self.btnStop.setEnabled(True)


		if midiFile != None:

			if len(CVMap)==0:
				err("No voices assigned to layers. Can't render performance info")
				return

			# create camera
			board = soundBoard()
			self.gateTimerPeriod = int(1000 / fRate)

			self.c = camera(theatre)
			#start the camera
			self.cameraSlot()

			self.p = player(midiFile)
			# start the midi player
			self.playslot()
		else:
			msgBox("Audio only, no performance info")

	def channelMap(self):
		cvm = CVMapEdit()
		cvm.exec_()
		self.edComboInit() # new voices may have been added

	def edComboInit(self):
		self.edCombo.clear()
		self.edCombo.addItem("<Select Voice To Edit>")
		i = self.edCombo.findText("<Select Voice To Edit>")
		self.edCombo.setCurrentIndex(i)
		for v in voices:
			self.edCombo.addItem(v.vdata['name'])

	def newVoice(self):
		v = voice()
		v.edit()
		if v != None:
			voices.append(v)
			self.edComboInit()

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

		openPAct = QAction(QIcon(),'Open Project',self)
		openPAct.setShortcut('Ctrl+O')
		openPAct.setStatusTip('Open Project')
		openPAct.triggered.connect(self.openProj)

		savePAct = QAction(QIcon(), 'Save Project', self)
		savePAct.setShortcut('Ctrl+S')
		savePAct.setStatusTip('Save Project')
		savePAct.triggered.connect(self.saveProj)

		expVAct = QAction(QIcon(), 'Export Voice', self)
		expVAct.setShortcut('Ctrl+E')
		expVAct.setStatusTip('Export Voice')
		expVAct.triggered.connect(self.exportVoice)

		impVAct = QAction(QIcon(), 'Import Voice', self)
		impVAct.setShortcut('Ctrl+I')
		impVAct.setStatusTip('Import Voice')
		impVAct.triggered.connect(self.importVoice)

		impMAct = QAction(QIcon(), 'Import Midi', self)
		impMAct.setShortcut('Ctrl+M')
		impMAct.setStatusTip('Import Midi')
		impMAct.triggered.connect(self.importMidi)

		impAAct = QAction(QIcon(), 'Import Audio', self)
		impAAct.setShortcut('Ctrl+A')
		impAAct.setStatusTip('Import Audio')
		impAAct.triggered.connect(self.importAudio)

		menubar = self.menuBar()
		fileMenu = menubar.addMenu('&File')
		fileMenu.addAction(openPAct)
		fileMenu.addAction(savePAct)
		fileMenu.addAction(expVAct)
		fileMenu.addAction(impVAct)
		fileMenu.addAction(impMAct)
		fileMenu.addAction(impAAct)

		self.cMapBtn = QPushButton("Layers")
		self.cMapBtn.clicked.connect(self.channelMap)

		self.nVoiceBtn = QPushButton("New Voice")
		self.nVoiceBtn.clicked.connect(self.newVoice)

		edLabel = QLabel('&Edit Voice',self)
		self.edCombo = QComboBox(self)
		self.edComboInit()
		self.edCombo.currentIndexChanged.connect(self.edSelChg)

		ssLabel = QLabel('Sound Source',self)
		self.ssFileShow= QLineEdit(self)
		self.ssFileShow.readOnly = True

		mpLabel = QLabel('Performance File',self)
		self.mpFileShow= QLineEdit(self)
		self.mpFileShow.readOnly = True

		emptyImg = QPixmap("/Users/johnhollingum/Documents/AMENIC/Empty.png").scaled(tWidth,tHeight,2,1)
		theatre = theatreLabel(self)
		theatre.setPixmap(emptyImg)

		self.btnPlay = QPushButton('&Play')
		self.btnPlay.clicked.connect(self.play)
		self.btnPlay.setEnabled(False)

		self.btnStop = QPushButton('&Stop')
		self.btnStop.clicked.connect(self.stopsound)
		self.btnStop.setEnabled(False)

		vbox1 = QVBoxLayout()
		hbox1 = QHBoxLayout()
		hbox1.addWidget(self.cMapBtn)

		hbox1.addWidget(self.nVoiceBtn)

		hbox1.addWidget(edLabel)
		hbox1.addWidget(self.edCombo)

		vbox1.addLayout(hbox1)

		hbox2 = QHBoxLayout()
		hbox2.addWidget(ssLabel)
		hbox2.addWidget(self.ssFileShow)

		vbox1.addLayout(hbox2)

		hbox25 = QHBoxLayout()
		hbox25.addWidget(mpLabel)
		hbox25.addWidget(self.mpFileShow)

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
