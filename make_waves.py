# waveform.py
import os, subprocess

def waveform(in_file, out_file):
	command = 'ffmpeg \
		-hide_banner -loglevel panic \
		-i "{in_file}" \
		-filter_complex \
			"[0:a]aformat=channel_layouts=mono, \
			compand=gain=5, \
			showwavespic=s=600x120:colors=#9cf42f[fg]; \
			color=s=600x120:color=#44582c, \
			drawgrid=width=iw/10:height=ih/5:color=#9cf42f@0.1[bg]; \
			[bg][fg]overlay=format=rgb, \
			drawbox=x=(iw-w)/2:y=(ih-h)/2:w=iw:h=1:color=#9cf42f" \
		-vframes 1 \
		-y "{out_file}"'.format(
			in_file = in_file,
			out_file = out_file
		)

	p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	out, err = p.communicate()

	return out

if __name__ == '__main__':
	basepath = './media'
	for xtype in ['audios', 'videos']:
		filedir = '{}/{}'.format(basepath, xtype)
		waveformdir = '{}/waveforms/{}'.format(basepath, xtype)
		files = [f for f in os.listdir(filedir) if not f.startswith('.')]

		# make sure waveforms/{xtype} dir exists
		if not os.path.exists(waveformdir):
			os.makedirs(waveformdir)

		curr = 0
		for file in files:
			filename, file_extension = os.path.splitext(file)
			in_file = '{}/{}'.format(filedir, file)
			out_file = '{}/{}.jpg'.format(waveformdir, filename)
			waveform(in_file, out_file)
			curr += 1
			progress = '{:.2f}'.format((curr / len(files)) * 100)
			print('{} progress {}%'.format(xtype, progress), end='\r')
		print('')
	print('\nall done!')
