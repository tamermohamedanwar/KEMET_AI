#!/data/data/com.termux/files/usr/bin/bash
cd ~/products/Kemet_AI
export PIPER_VOICE_PATH=$PWD/.kemet_runtime/piper/voices
piper -m ar_JO-kareem-medium -i ops/commercial_video/commercial_v2/voice_script_ar_v2.txt -f ops/commercial_video/commercial_v2/voice_ar_v2.raw
ffmpeg -y -f f32le -ar 22050 -ac 1 -i ops/commercial_video/commercial_v2/voice_ar_v2.raw -ar 48000 -ac 2 -c:a pcm_s16le ops/commercial_video/commercial_v2/voice_ar_v2.wav >/dev/null 2>&1
ffmpeg -y -i ops/commercial_video/commercial_v2/voice_ar_v2.wav -af 'highpass=f=80,lowpass=f=11000,acompressor=threshold=-18dB:ratio=2.5:attack=8:release=80,loudnorm=I=-16:TP=-1.5:LRA=7' -ar 48000 -ac 2 -c:a pcm_s16le ops/commercial_video/commercial_v2/voice_ar_v2_master.wav >/dev/null 2>&1
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 ops/commercial_video/commercial_v2/voice_ar_v2_master.wav
