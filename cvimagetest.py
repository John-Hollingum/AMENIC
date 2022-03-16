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

def mess(mymess):
	msg = QMessageBox()
	msg.setIcon(QMessageBox.Information)
	msg.setText(mymess)
	msg.setStandardButtons(QMessageBox.Ok)
	retval = msg.exec_()

# Convert an opencv image to QPixmap
def convertCvImage2QtImage(cv_img):
	rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
	PIL_image = Image.fromarray(rgb_image).convert('RGB')
	return QPixmap.fromImage(ImageQt(PIL_image))

def convertQt2Cv(qt_img):
	pass
	# onv = qt_img.convertToFormat(QImage::Format_ARGB32);
	# and then some magic.
	# in C++ it apparently goes like this:
	#QImage conv = image.convertToFormat(QImage::Format_ARGB32);
	#cv::Mat view(conv.height(),conv.width(),CV_8UC4,(void *)conv.constBits(),conv.bytesPerLine());
	#view.copyTo(out);

def showsize(s,i):
	print("image "+s,end=' ')
	print(i.shape)

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

	# will the overlay go beyond the bounds of the background?
	if x + w > background_width:
		w = background_width - x
		overlay = overlay[:, :w]

	if y + h > background_height:
		h = background_height - y
		overlay = overlay[:h]

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
	overlay_image = overlay[..., :3] # yeah, right, must figure what this means some day
	mask = overlay[..., 3:] / 255.0

	# my added debug
	print('background ')
	print(background.shape)
	print('mask ')
	print(mask.shape)
	print('overlay_image')
	print(overlay_image.shape)
	# ends

	background[y:y+h, x:x+w] = (1.0 - mask) * background[y:y+h, x:x+w] + mask * overlay_image

	return background

def overlaySzOpAt(background,overlay,xsize,ysize,opacity,xpos,ypos):
	print("xsize"+str(xsize)+" ysize "+str(ysize)+" opacity "+str(opacity)+" xpos "+str(xpos)+ " ypos "+str(ypos))
	if ysize == -1: # retain AR
		ar =  overlay.shape[0] / overlay.shape[1]
		ysize = int(xsize * ar)

	opacity = opacity / 100

	if opacity == 1:
		bg = background
	else:
		bg = background.copy()

	if xsize != 0: # use scaled size
		print("scaled")
		comb1 = overlay_transparent(bg,cv2.resize(overlay,(xsize,ysize)),xpos,ypos)
	else: # use native size
		print("native size")
		comb1 = overlay_transparent(bg,overlay,xpos,ypos)

	if opacity < 1:
		alpha =opacity
		beta = 1 - opacity
		combined = cv2.addWeighted(background,alpha,comb1,beta,0.0)
	else:
		combined = comb1
	return combined

class demoMain(QMainWindow):
	def __init__(self):
		super().__init__()
		self.initUI()

	def initUI(self):
		#self.img = cv2.imread("/Users/johnhollingum/Documents/crotal/adv1.jpg")
		self.img = cv2.imread("/Users/johnhollingum/Documents/crotal/adv1.jpg", cv2.IMREAD_UNCHANGED)
		showsize('1',self.img)
		#self.img2 = cv2.imread("/Users/johnhollingum/Documents/Turnips/Horn_section.png", cv2.IMREAD_UNCHANGED)
		self.img2 = cv2.imread("/Users/johnhollingum/Documents/Turnips/Horn_section.png", cv2.IMREAD_UNCHANGED)
		showsize('2',self.img2)
		if False:
			self.img3 = self.img2[0:self.img.shape[0],0:self.img.shape[1]]
			showsize('2',self.img3)
			print(str(type(self.img)))
		self.i = QLabel()
		self.setCentralWidget(self.i)

	def fade(self):
		combine1 = overlay_transparent(self.img.copy(),self.img2,0,0)
		for a in range( 0, 10):
			alpha = a/10
			beta = 1 - alpha
			combined = cv2.addWeighted(self.img, alpha, combine1, beta, 0.0)
			qti = convertCvImage2QtImage(combined)
			self.i.setPixmap(qti)
			QGuiApplication.processEvents()
			time.sleep(0.2)

		for a in range(0,10):
			xpos = int(self.img.shape[1] * a /10)
			combined = overlay_transparent(self.img.copy(),self.img2,xpos,0)
			qti = convertCvImage2QtImage(combined)
			self.i.setPixmap(qti)
			QGuiApplication.processEvents()
			time.sleep(0.2)

		for a in range(1,10):
			xsize = int(self.img2.shape[1] * a /10)
			ysize = int(self.img2.shape[0] * a /10)
			combined = overlay_transparent(self.img.copy(),cv2.resize(self.img2,(xsize,ysize)),0,0)
			qti = convertCvImage2QtImage(combined)
			self.i.setPixmap(qti)
			QGuiApplication.processEvents()
			time.sleep(0.2)

		# display at 50,100 at a size of x= 200, y= matching AR, opacity = 70%
		xpos = 50
		ypos = 100
		xsize = 200
		ar =  self.img2.shape[0] / self.img2.shape[1]
		ysize = int(xsize * ar)
		opacity = 0.7

		if False:
			comb1 = overlay_transparent(self.img.copy(),cv2.resize(self.img2,(xsize,ysize)),xpos,ypos)
			if opacity < 1:
				alpha =opacity
				beta = 1 - opacity
				combined = cv2.addWeighted(self.img,alpha,comb1,beta,0.0)
			else:
				combined = comb1
		else:
			combined = overlaySzOpAt(self.img,self.img2,xsize,ysize,70,xpos,ypos)
		qti = convertCvImage2QtImage(combined)
		self.i.setPixmap(qti)
		QGuiApplication.processEvents()
		mess("try with jpeg now")

		# now let's try the same with a jpeg rather than png overlay
		jpOver = cv2.imread("/Users/johnhollingum/Documents/AMENIC/JPEG_Horn_section_blast.jpg", cv2.IMREAD_UNCHANGED)
		combined = overlaySzOpAt(self.img,jpOver,xsize,ysize,100,xpos,ypos)
		qti = convertCvImage2QtImage(combined)
		self.i.setPixmap(qti)
		QGuiApplication.processEvents()

	def roundTrip(self):
		matImg = convertQt2Cv(self.img)
		img2 = convertCvImage2QtImage(matImg)
		self.i.setPixmap(img2)

if __name__ == '__main__':
	app = QApplication(sys.argv)
	main = demoMain()
	main.show()
	main.fade()
	sys.exit(app.exec_())
