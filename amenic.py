from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPixmap, QPalette
import sys

class QAmenicMain(QDialog) :
	def __init__(self):
		super().__init__()
		self.initUI()

	def initUI(self):
		self.setWindowTitle('Amenic')
		self.resize(1020,600)

		dvLabel = QLabel('&Default Voice',self)
		dvCombo = QComboBox(self)
		dvCombo.addItem("+Add New")
		dvLabel.setBuddy(dvCombo)

		droneLabel = QLabel('&Drone Voiice',self)
		droneCombo = QComboBox(self)
		droneCombo.addItem("+Add New")
		droneCombo.addItem("<none>")
		droneLabel.setBuddy(droneCombo)

		ssLabel = QLabel('&Sound Source',self)
		ssLineEdit = QTextEdit(self)
		ssLabel.setBuddy(ssLineEdit)
        
		theatre = QLabel(self)
		theatre.setPixmap(QPixmap("/Users/johnhollingum/Documents/Turnips/luttrell_empty_table.jpg").scaled(960,540,2,1))      
        
		btnPlay = QPushButton('&Play')
		btnStop = QPushButton('&Stop')

		mainLayout = QGridLayout(self)
		mainLayout.addWidget(dvLabel,0,0)
		mainLayout.addWidget(dvCombo,0,1,1,2)

		mainLayout.addWidget(droneLabel,1,0)
		mainLayout.addWidget(droneCombo,1,1,1,2)

		mainLayout.addWidget(ssLabel,2,0)
		mainLayout.addWidget(ssLineEdit,2,1)

		mainLayout.addWidget(theatre,3,1)
        
		mainLayout.addWidget(btnPlay,4,0)
		mainLayout.addWidget(btnStop,4,1)

if __name__ == '__main__':
	app = QApplication(sys.argv)
	main = QAmenicMain()
	main.show()
	sys.exit(app.exec_())
