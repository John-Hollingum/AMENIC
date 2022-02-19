import random
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPixmap, QPainter, QPalette, QIcon, QColor, QStandardItemModel, QStandardItem
import sys

# regularly recurring qtimers seem to work fine. When using successive starts of Qtimers set to variable times, it all goes screwy when
# you re-start the timer in the slot routine that services the timeout. You end up with the number of concurrent timers doubling each time
# As below, if you use static singleShot timers, this problem disappears

class TTMain(QMainWindow):
	def __init__(self):
		super().__init__()
		self.t1 = QTimer()
		self.t2 = QTimer()
		self.initUI()

	def t1slot(self):
		rndDel = random.randrange(1,5)
		rndms = rndDel * 1000
		print("in t1slot, coming back in "+str(rndDel)+ "s")
		QTimer.singleShot(rndms,self.t1slot)

	def t2slot(self):
		print("  In t2slot, coming back in 6s")

		QTimer.singleShot(6000,self.t2slot)

	def initUI(self):
		self.t1slot()
		self.t2slot()


if __name__ == '__main__':
	app = QApplication(sys.argv)
	main = TTMain()
	main.show()
	sys.exit(app.exec_())
