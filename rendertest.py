import jsonpickle # pip install jsonpickle
import json
import time
import mido
import random
from decimal import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPixmap, QPainter, QPalette, QIcon, QColor, QStandardItemModel, QStandardItem
import sys

tWidth = 960
tHeight = 540
voices = []
orchPath = "./"
orchName = "Untitled"
oExtn = 'orc'

def mess(mymess):
	msg = QMessageBox()
	msg.setIcon(QMessageBox.Information)
	msg.setText(mymess)
	msg.setStandardButtons(QMessageBox.Ok)
	retval = msg.exec_()

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


class theatreLabel(QLabel):
	def __init__(self, parent):
		super().__init__(parent=parent)
		self.setStyleSheet('QFrame {background-color:grey;}')
		self.resize(tWidth, tHeight)
		self.layers =[]

	def setLayers(self,l):
		self.layers = l

	def paintEvent(self, e):
		global emptyImg

		qp = QPainter(self)
		baseImg = emptyImg.copy(QRect())
		#baseImg = QPixmap("/Users/johnhollingum/Documents/Turnips/luttrell imp.jpeg")
		qp.drawPixmap(0,0,baseImg)
		print(str(len(self.layers)))
		for img in self.layers:
			if img != None:
				print("[PaintEvent] using ok image")
				#qp.drawPixmap(QRect(),img)
				qp.drawPixmap(0,0,img)
			else:
				print("[PaintEvent] trying to use null image")

class RenderTest(QMainWindow):
	def __init__(self):
		super().__init__()
		icon = QIcon()
		self.initUI()

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

		self.citimer.start(5000)


	def imgchg(self):
		#qpm = QPixmap("/Users/johnhollingum/Documents/Turnips/rapperc.png").scaled(tWidth,tHeight,2,1)
		qpm1 = QPixmap("/Users/johnhollingum/Documents/Turnips/rapperc.png")
		#qpm = QPixmap("/Users/johnhollingum/Documents/Turnips/Print2.jpeg")
		rnd = random.randrange(0,3)
		#mess(str(rnd))
		qpm = voices[0].vdata["imgTable"][rnd][2]
		self.theatre.setLayers([qpm,qpm1])
		self.theatre.show()
		self.theatre.repaint()


	def initUI(self):
		global tWidth
		global tHeight
		global emptyImg

		self.setWindowTitle('render test')
		self.resize(1020,600)

		openOAct = QAction(QIcon(), 'Open Orchestra', self)
		openOAct.setShortcut('Ctrl+O')
		openOAct.setStatusTip('Open Orchestra')
		openOAct.triggered.connect(self.openOrch)

		menubar = self.menuBar()
		fileMenu = menubar.addMenu('&File')
		fileMenu.addAction(openOAct)

		self.citimer = QTimer()
		self.citimer.timeout.connect(self.imgchg)


		le = QLineEdit(self)

		chgbtn = QPushButton("Change Image")
		chgbtn.clicked.connect(self.imgchg)

		#qbtn = QPushButton("quit")
		#qbtn.clicked.connect(quit())

		emptyImg = QPixmap("/Users/johnhollingum/Documents/AMENIC/Empty.png").scaled(tWidth,tHeight,2,1)
		self.theatre = theatreLabel(self)
		self.theatre.setPixmap(emptyImg)

		vbox1 = QVBoxLayout()

		vbox1.addWidget(le)
		vbox1.addWidget(chgbtn)
		#vbox1.addWidget(qbtn)
		vbox1.addWidget(self.theatre)

		container = QWidget()
		container.setLayout(vbox1)

		# Set the central widget of the Window.
		self.setCentralWidget(container)


if __name__ == '__main__':
	app = QApplication(sys.argv)
	main = RenderTest()
	main.show()
	sys.exit(app.exec_())
