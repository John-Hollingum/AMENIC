from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import sys

class AmenicMain(QMainWindow):
	def __init__(self):
		super().__init__()
		self.initUI()


	def initUI(self):

		self.setWindowTitle('Amenic')

		self.resize(900,500)

		ssLabel = QLabel('Sound Source',self)
		self.ssFileShow= QLineEdit(self)

		hbox2 = QHBoxLayout()
		hbox2.addWidget(ssLabel)
		hbox2.addWidget(self.ssFileShow)

		container = QWidget()

		container.setLayout(hbox2)

		self.setCentralWidget(container)


if __name__ == '__main__':
	app = QApplication(sys.argv)
	main = AmenicMain()
	main.show()
	sys.exit(app.exec_())
