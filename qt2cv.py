import io
from PIL.ImageQt import ImageQt
from PIL import Image
from PySide2.QtGui import QPixmap
import cv2
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPixmap, QPainter, QPalette, QIcon, QColor, QStandardItemModel, QStandardItem, QGuiApplication
import sys
import numpy as np
import time

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

class demoMain(QMainWindow):
	def __init__(self):
		super().__init__()
		self.initUI()

	def initUI(self):
		qpi = QPixmap("/Users/johnhollingum/Documents/Turnips/Horn_section.png")
		if True:
			open_cv_image = qt2cv(qpi)
		else:
			img = qpi.toImage()
			buffer = QBuffer()
			buffer.open(QBuffer.ReadWrite)
			img.save(buffer, "PNG")
			pil_image = Image.open(io.BytesIO(buffer.data()))
			open_cv_image = np.array(pil_image)
			# Convert RGB to BGR
			open_cv_image = open_cv_image[:, :, ::-1].copy()
		print(open_cv_image.shape)

if __name__ == '__main__':
	app = QApplication(sys.argv)
	main = demoMain()
	main.show()

	sys.exit(app.exec_())
