import jsonpickle # pip install jsonpickle
import json
from decimal import *
from functools import partial
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPixmap, QPalette, QIcon, QColor, QStandardItemModel, QStandardItem
import sys
import vlc

voices = []
presTable = []
tWidth = 960
tHeight = 540
fRate = 24

# I mean yes, I could define a voicelist class, and then instantiate one instance of it and
# have it contain the list of voices and give it access methods. But really how would that help?

def getVoiceByName(vName):
	mess(" there are "+str(len(voices))+" voices stored")
	for v in voices:
		if v.vdata["name"] == vName:
			return v
	return None

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
			"defImg": None,
			"restImg": None,
			"imgTable": [ ],
			"name": 'Untitled'
		}

	def edit(self):
		ve = vEditD(self)
		ve.exec_()
		rval = ve.getVal()
		# the brevity of this next line is the entire point of using the vdata dict
		# to carry the data in voice:
		self.vdata = rval.vdata.copy()
		return

class vEditD(QDialog):
	def __init__(self, v:voice):
		super().__init__()
		self.setModal(True)
		self.initUI(v)

	def getImg(self,idx):
		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open file', '~/Documents',"Image files (*.png, *.jpg)")
		self.model._data[idx][3] = fname

	def getDefImg(self,idx):
		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open Default Image', '~/Documents',"Image files (*.png, *.jpg)")
		self.diEdit.setText(fname)

	def getRestImg(self,idx):
		( fname, filter)  = QFileDialog.getOpenFileName(self, 'Open Rest Image', '~/Documents',"Image files (*.png, *.jpg)")
		self.restEdit.setText(fname)

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

		# set up widgets
		self.nameLabel = QLabel('Name')
		self.nameEdit = QLineEdit(self)
		self.nameEdit.setText(v.vdata["name"])
		self.nameEdit.textChanged.connect(self.maybeActiveSave)

		self.diLabel = QLabel("Default Image")
		self.diEdit = QLineEdit(self)
		self.diEdit.setText(v.vdata.get("defImg"))
		self.diEdit.setToolTip("Image shown when any key pressed unless overridded in note map table")
		self.diLookup = QPushButton('>')
		self.diLookup.clicked.connect(self.getDefImg)

		self.restLabel = QLabel("Rest Image")
		self.restEdit = QLineEdit(self)
		self.restEdit.setText(v.vdata["restImg"])
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
		self.btnSave.setEnabled(False)

		# Layout
		vbox = QVBoxLayout()
		hbox1=QHBoxLayout()
		hbox1.addWidget(self.nameLabel)
		hbox1.addWidget(self.nameEdit)
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

	def cancelOut(self):
		self.saveV = voice()
		self.reject()
		return None

	def saveOut(self,v:voice):
		self.saveV = voice()
		self.saveV.vdata["name"] = self.nameEdit.text()
		self.saveV.vdata["defImg"] = self.diEdit.text()
		self.saveV.vdata["restImg"] = self.restEdit.text()
		# self.saveV.imgTable -- what exactly?
		mess("model data size  "+str(len(self.model._data)))
		for idx in range(0, len(self.model._data)):
			if self.model._data[idx][3] != None and self.model._data[idx][3] != '':
				mess("found "+ self.model._data[idx][3]+" in note map")
				self.saveV.vdata["imgTable"].append([ self.model._data[idx][0], self.model._data[idx][3]])
		self.accept()

	def getVal(self):
		return self.saveV
		#mess("I think I'm done here")

	def maybeActiveSave(self):
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

	def initUI(self):
		self.setWindowTitle('Amenic')
		self.resize(1020,600)
		# don't think I'm getting a lot of benefit from the buddying
		# but look at https://doc.qt.io/archives/qt-4.8/designer-buddy-mode.html and
		# https://doc.qt.io/qtcreator/creator-keyboard-shortcuts.html

		dvLabel = QLabel('&Default Voice',self)
		self.dvCombo = QComboBox(self)
		self.dvCombo.addItem("<none>")
		self.dvCombo.addItem("+Add New")
		for v in voices:
			self.dvCombo.addItem(v.name)
		self.dvCombo.currentIndexChanged.connect(self.dvSelChg)

		dvLabel.setBuddy(self.dvCombo)

		droneLabel = QLabel('&Drone Voice',self)
		self.droneCombo = QComboBox(self)
		self.droneCombo.addItem("<none>")
		self.droneCombo.addItem("+Add New")
		for v in voices:
			self.dvCombo.addItem(v.name)
		self.droneCombo.currentIndexChanged.connect(self.drSelChg)

		droneLabel.setBuddy(self.droneCombo)

		edLabel = QLabel('&Edit Voice',self)
		self.edCombo = QComboBox(self)
		self.edCombo.addItem("<Select Voice To Edit>")
		for v in voices:
			self.edCombo.addItem(v.name)
		self.edCombo.currentIndexChanged.connect(self.edSelChg)

		ssLabel = QLabel('&Sound Source',self)
		self.ssFileShow= QLineEdit(self)
		self.ssFileShow.readOnly = True
		ssButton = QPushButton('>')
		ssButton.clicked.connect(self.getSound)
		ssLabel.setBuddy(ssButton)

		theatre = QLabel(self)
		theatre.setPixmap(QPixmap("/Users/johnhollingum/Documents/AMENIC/Empty.png").scaled(tWidth,tHeight,2,1))

		self.btnPlay = QPushButton('&Play')
		self.btnPlay.clicked.connect(self.playsound)
		self.btnPlay.setEnabled(False)

		self.btnStop = QPushButton('&Stop')
		self.btnStop.clicked.connect(self.stopsound)
		self.btnStop.setEnabled(False)

		vbox1 = QVBoxLayout()
		hbox1 = QHBoxLayout()
		hbox1.addWidget(dvLabel)
		hbox1.addWidget(self.dvCombo)

		hbox1.addWidget(droneLabel)
		hbox1.addWidget(self.droneCombo)

		hbox1.addWidget(edLabel)
		hbox1.addWidget(self.edCombo)

		vbox1.addLayout(hbox1)

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

	def dvSelChg(self,i):
		# this routine responds to an event that it, itself raises
		if self.dvCombo.currentText() == "+Add New":
			self.playerVn = self.createNewVoice()
			if self.playerVn == None :
				i = self.dvCombo.findText("<none>")
				self.dvCombo.setCurrentIndex(i)
			else:
				self.droneCombo.addItem(self.playerVn)
				self.dvCombo.addItem(self.playerVn)
				self.edCombo.addItem(self.playerVn)
				i = self.dvCombo.findText(self.playerVn)
				self.dvCombo.setCurrentIndex(i)
			return
		elif self.dvCombo.currentText() != "<none>":
			mess("use "+self.dvCombo.currentText())
		else:
			self.playerVn = None

	def drSelChg(self,i):
		if self.droneCombo.currentText() == "+Add New":
			self.droneVn = self.createNewVoice()
			if self.droneVn == None :
				i = self.droneCombo.findText("<none>")
				self.droneCombo.setCurrentIndex(i)
			else:
				self.droneCombo.addItem(self.droneVn)
				self.dvCombo.addItem(self.droneVn)
				self.edCombo.addItem(self.playerVn)
				i = self.droneCombo.findText(self.droneVn)
				self.droneCombo.setCurrentIndex(i)
				# find droneV from droneVn

	def edSelChg(self,i):
		if self.edCombo.currentText() != "<Select Voice To Edit>":
			mess("edit "+self.edCombo.currentText())
			edv = getVoiceByName(self.edCombo.currentText())
			if edv == None:
				mess("Panic, no stored voice with name '%s'",self.edCombo.currentText())
			else:
				edv.edit()
				mess("edited "+edv.vdata["name"])
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
