import PIL

from PIL import Image

f = r'/Users/johnhollingum/Documents/Turnips/luttrell_empty_table.jpg'
bg = Image.open(f)
f=r'/Users/johnhollingum/Documents/Turnips/Horn_section.png'
fg=Image.open(f)
bg.paste(fg,(0,0),fg)

bg.show()
