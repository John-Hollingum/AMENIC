import mido


inport=mido.open_input('Steinberg UR22mkII  Port1')
for msg in inport:
    if msg.type == 'note_on':
        if msg.note == 67:
            break
        print(msg)
    elif msg.type == 'note_off':
        print(msg)
    else:
        print(msg)



        
        
