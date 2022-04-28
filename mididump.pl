use MIDI::Tweaks;
# Read midi data.

$midfile = shift;
chomp($midfile);
print "'$midfile'\n";
my $op = new MIDI::Tweaks::Opus ({ from_file => $midfile, require_sanity=> 1 });

$op->dump();
