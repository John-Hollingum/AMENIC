import mido
import time

inport=mido.open_input('Steinberg UR22mkII  Port1')

x = "fred"
if x != None:
  print("fine")
else:
  print("frankly surprising")

while True:
    m= inport.poll()
    if str(m) != "None":
        print(str(m))
    time.sleep(1)
