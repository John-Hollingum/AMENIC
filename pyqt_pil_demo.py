import sys
from PyQt5.QtWidgets import QVBoxLayout,QMainWindow,QApplication,QLabel,QWidget
from PyQt5.QtGui import QPixmap, QPalette
from PyQt5.QtCore import Qt

class QLabelDemo(QWidget) :
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        label3 = QLabel(self)


        label3.setAlignment(Qt.AlignCenter)
        label3.setToolTip('Hint')
        label3.setPixmap(QPixmap("/Users/johnhollingum/Documents/Turnips/luttrell_empty_table.jpg").scaled(960,540,2,1))


        vbox = QVBoxLayout()

        vbox.addWidget(label3)

 
        self.setLayout(vbox)
        self.setWindowTitle('QLabel Example')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = QLabelDemo()
    main.show()
    sys.exit(app.exec_())
